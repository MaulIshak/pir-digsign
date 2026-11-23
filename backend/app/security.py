import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User

settings = get_settings()
ph = PasswordHasher()


def _rate_limit_key(request: Request) -> str:
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()[:64]
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)

ACCESS_COOKIE_NAME = "digsign_access_token"
CSRF_COOKIE_NAME = "digsign_csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def generate_secure_token(num_bytes: int = 24) -> str:
    """Menghasilkan token acak kriptografis (>= 192 bit untuk 24 byte)."""
    return secrets.token_urlsafe(num_bytes)


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": secrets.token_hex(12),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def set_auth_cookies(response: Response, access_token: str) -> str:
    csrf_token = generate_secure_token(24)
    max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=max_age,
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=max_age,
        path="/",
    )
    return csrf_token


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    if request.client:
        return request.client.host[:64]
    return "unknown"


def get_user_agent(request: Request) -> str:
    return (request.headers.get("user-agent") or "unknown")[:512]


def sanitize_filename(filename: str) -> str:
    """Membersihkan nama file dari path traversal dan karakter berbahaya."""
    name = filename.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._\-\s]", "_", name).strip()
    if not name:
        name = "dokumen.pdf"
    if len(name) > 200:
        base, _, ext = name.rpartition(".")
        name = f"{base[:180]}.{ext}" if ext else name[:200]
    return name


def validate_pdf_upload(data: bytes, filename: str, content_type: Optional[str]) -> str:
    if not data:
        raise HTTPException(status_code=400, detail="File kosong.")
    if len(data) > settings.MAX_PDF_SIZE_BYTES:
        max_mb = settings.MAX_PDF_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"Ukuran PDF melebihi batas maksimal {max_mb} MB.")

    safe_name = sanitize_filename(filename or "dokumen.pdf")
    if not safe_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Ekstensi file wajib .pdf.")

    if content_type and content_type not in (
        "application/pdf",
        "application/octet-stream",
        "application/x-pdf",
    ):
        raise HTTPException(status_code=400, detail="Tipe MIME file bukan PDF yang valid.")

    # Validasi magic bytes PDF (%PDF-) dalam 1024 byte pertama sesuai spesifikasi PDF
    if b"%PDF-" not in data[:1024]:
        raise HTTPException(status_code=400, detail="File bukan dokumen PDF valid (magic bytes %PDF- tidak ditemukan).")

    return safe_name


def verify_csrf(request: Request) -> None:
    """Memverifikasi double-submit CSRF token pada request mutasi terautentikasi."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    cookie_csrf = request.cookies.get(CSRF_COOKIE_NAME)
    header_csrf = request.headers.get(CSRF_HEADER_NAME)
    # Jika memakai Authorization Bearer header (misal API client/test), CSRF cookie tidak wajib
    if request.headers.get("authorization", "").lower().startswith("bearer "):
        return
    if not cookie_csrf or not header_csrf or not secrets.compare_digest(cookie_csrf, header_csrf):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token CSRF tidak valid atau tidak ditemukan.",
        )


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesi tidak ditemukan. Silakan masuk kembali.",
        )

    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak valid atau sudah kedaluwarsa.",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Pengguna tidak ditemukan.",
        )
    return user


def require_csrf_and_user(request: Request, user: User = Depends(get_current_user)) -> User:
    verify_csrf(request)
    return user


# --- TOTP (2FA) ---
def generate_totp_secret() -> str:
    return pyotp.random_base32()


def build_totp_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=settings.APP_NAME)


def verify_totp_code(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code.strip(), valid_window=1)
