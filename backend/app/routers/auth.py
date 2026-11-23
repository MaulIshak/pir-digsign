import io

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AuditLog, DocumentSigner, User
from app.schemas import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    TotpCodeRequest,
    TotpSetupResponse,
    UserOut,
)
from app.security import (
    build_totp_uri,
    clear_auth_cookies,
    create_access_token,
    generate_secure_token,
    generate_totp_secret,
    get_client_ip,
    get_current_user,
    get_user_agent,
    hash_password,
    limiter,
    require_csrf_and_user,
    set_auth_cookies,
    verify_password,
    verify_totp_code,
)
from app.services.email import get_email_provider
from app.services.image_utils import bytes_to_png_data_url

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def register(
    request: Request,
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    email_norm = payload.email.strip().lower()
    existing = db.query(User).filter(User.email == email_norm).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email sudah terdaftar. Silakan masuk.",
        )

    verify_token = generate_secure_token(24)
    user = User(
        name=payload.name.strip(),
        email=email_norm,
        password_hash=hash_password(payload.password),
        is_verified=False,
        verify_token=verify_token,
    )
    db.add(user)
    db.flush()

    # Tautkan undangan dokumen yang sebelumnya dikirim ke email ini
    pending_invites = (
        db.query(DocumentSigner)
        .filter(DocumentSigner.email == email_norm, DocumentSigner.user_id.is_(None))
        .all()
    )
    for inv in pending_invites:
        inv.user_id = user.id

    db.add(
        AuditLog(
            document_id=None,
            user_id=user.id,
            action="USER_REGISTERED",
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
            details=f"Registrasi akun {email_norm}",
        )
    )
    db.commit()
    db.refresh(user)

    verify_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/verify-email?token={verify_token}"
    get_email_provider().send_email(
        to_email=user.email,
        subject=f"[{settings.APP_NAME}] Verifikasi Alamat Email Anda",
        body_text=(
            f"Halo {user.name},\n\n"
            f"Silakan verifikasi alamat email Anda dengan membuka tautan berikut:\n"
            f"{verify_url}\n\n"
            f"Abaikan email ini jika Anda tidak merasa mendaftar."
        ),
    )

    access_token = create_access_token(user.id)
    csrf_token = set_auth_cookies(response, access_token)

    return AuthResponse(
        user=UserOut.model_validate(user),
        csrf_token=csrf_token,
        message="Registrasi berhasil. Silakan verifikasi email Anda.",
        dev_verify_link=verify_url if settings.is_dev else None,
    )


@router.post("/login", response_model=AuthResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    email_norm = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email_norm).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau kata sandi salah.",
        )

    if user.totp_enabled:
        if not payload.totp_code:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="2FA_REQUIRED",
            )
        if not user.totp_secret or not verify_totp_code(user.totp_secret, payload.totp_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Kode 2FA (TOTP) tidak valid.",
            )

    # Tautkan undangan dokumen tertunda untuk email ini
    pending_invites = (
        db.query(DocumentSigner)
        .filter(DocumentSigner.email == email_norm, DocumentSigner.user_id.is_(None))
        .all()
    )
    for inv in pending_invites:
        inv.user_id = user.id

    db.add(
        AuditLog(
            document_id=None,
            user_id=user.id,
            action="USER_LOGIN",
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
            details="Login berhasil",
        )
    )
    db.commit()

    access_token = create_access_token(user.id)
    csrf_token = set_auth_cookies(response, access_token)

    return AuthResponse(
        user=UserOut.model_validate(user),
        csrf_token=csrf_token,
        message="Berhasil masuk.",
    )


@router.post("/logout")
def logout(response: Response):
    clear_auth_cookies(response)
    return {"message": "Berhasil keluar."}


@router.get("/me", response_model=AuthResponse)
def me(request: Request, user: User = Depends(get_current_user)):
    csrf_token = request.cookies.get("digsign_csrf_token", "")
    return AuthResponse(user=UserOut.model_validate(user), csrf_token=csrf_token)


@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.verify_token == token).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token verifikasi email tidak valid atau sudah digunakan.",
        )
    user.is_verified = True
    user.verify_token = None
    db.commit()
    return {"message": "Email berhasil diverifikasi.", "email": user.email}


@router.post("/2fa/setup", response_model=TotpSetupResponse)
def setup_2fa(
    user: User = Depends(require_csrf_and_user),
    db: Session = Depends(get_db),
):
    secret = generate_totp_secret()
    user.totp_secret = secret
    db.commit()

    uri = build_totp_uri(secret, user.email)
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=6, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    return TotpSetupResponse(
        secret=secret,
        otpauth_uri=uri,
        qr_data_url=bytes_to_png_data_url(buf.getvalue()),
    )


@router.post("/2fa/enable")
def enable_2fa(
    payload: TotpCodeRequest,
    user: User = Depends(require_csrf_and_user),
    db: Session = Depends(get_db),
):
    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="Jalankan setup 2FA terlebih dahulu.")
    if not verify_totp_code(user.totp_secret, payload.code):
        raise HTTPException(status_code=400, detail="Kode TOTP tidak cocok.")

    user.totp_enabled = True
    db.commit()
    return {"message": "2FA (TOTP) berhasil diaktifkan."}


@router.post("/2fa/disable")
def disable_2fa(
    payload: TotpCodeRequest,
    user: User = Depends(require_csrf_and_user),
    db: Session = Depends(get_db),
):
    if not user.totp_enabled or not user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA saat ini tidak aktif.")
    if not verify_totp_code(user.totp_secret, payload.code):
        raise HTTPException(status_code=400, detail="Kode TOTP tidak valid.")

    user.totp_enabled = False
    user.totp_secret = None
    db.commit()
    return {"message": "2FA berhasil dinonaktifkan."}
