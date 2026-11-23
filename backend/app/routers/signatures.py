import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Signature, User
from app.schemas import SignatureCreateBase64, SignatureOut
from app.security import get_current_user, require_csrf_and_user
from app.services.image_utils import (
    bytes_to_png_data_url,
    decode_data_url_or_base64,
    process_signature_image,
)
from app.services.storage import get_storage

router = APIRouter(prefix="/signatures", tags=["Signatures"])
settings = get_settings()


@router.get("", response_model=List[SignatureOut])
def list_signatures(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    storage = get_storage()
    sigs = (
        db.query(Signature)
        .filter(Signature.user_id == user.id)
        .order_by(Signature.created_at.desc())
        .all()
    )
    results: List[SignatureOut] = []
    for s in sigs:
        data_url: Optional[str] = None
        try:
            raw = storage.read_bytes(s.image_path)
            data_url = bytes_to_png_data_url(raw)
        except Exception:
            pass
        results.append(
            SignatureOut(
                id=s.id,
                label=s.label,
                type=s.type,
                image_data_url=data_url,
                created_at=s.created_at,
            )
        )
    return results


@router.post("", response_model=SignatureOut, status_code=status.HTTP_201_CREATED)
async def create_signature(
    request: Request,
    user: User = Depends(require_csrf_and_user),
    db: Session = Depends(get_db),
):
    """
    Menyimpan tanda tangan pengguna ke profil.
    Mendukung:
    - application/json (SignatureCreateBase64: draw / type / upload base64)
    - multipart/form-data (file PNG/JPG + label + type + remove_background)
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(status_code=400, detail="File gambar tanda tangan wajib diunggah.")
        raw_bytes = await upload.read()
        label = str(form.get("label") or "Tanda Tangan Upload").strip()[:120]
        sig_type = str(form.get("type") or "upload").strip()
        remove_bg = str(form.get("remove_background") or "true").lower() in ("true", "1", "yes")
    else:
        body = await request.json()
        payload = SignatureCreateBase64.model_validate(body)
        try:
            raw_bytes = decode_data_url_or_base64(payload.image_base64)
        except Exception:
            raise HTTPException(status_code=400, detail="Format gambar base64 tidak valid.")
        label = payload.label.strip()
        sig_type = payload.type
        remove_bg = payload.remove_background

    if sig_type not in ("draw", "upload", "type"):
        raise HTTPException(status_code=400, detail="Tipe tanda tangan harus draw, upload, atau type.")

    if not raw_bytes or len(raw_bytes) > settings.MAX_SIGNATURE_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Ukuran gambar tanda tangan tidak valid (maks 5 MB).")

    try:
        processed_png = process_signature_image(raw_bytes, remove_background=remove_bg)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Gagal memproses gambar tanda tangan (harus PNG/JPG): {exc}")

    storage = get_storage()
    sig_id = str(uuid.uuid4())
    storage_key = f"signatures/{user.id}/{sig_id}.png"
    storage.save_bytes(storage_key, processed_png, content_type="image/png")

    sig = Signature(
        id=sig_id,
        user_id=user.id,
        label=label or "Tanda Tangan Saya",
        image_path=storage_key,
        type=sig_type,
    )
    db.add(sig)
    db.commit()
    db.refresh(sig)

    return SignatureOut(
        id=sig.id,
        label=sig.label,
        type=sig.type,
        image_data_url=bytes_to_png_data_url(processed_png),
        created_at=sig.created_at,
    )


@router.delete("/{signature_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_signature(
    signature_id: str,
    user: User = Depends(require_csrf_and_user),
    db: Session = Depends(get_db),
):
    sig = (
        db.query(Signature)
        .filter(Signature.id == signature_id, Signature.user_id == user.id)
        .first()
    )
    if not sig:
        raise HTTPException(status_code=404, detail="Tanda tangan tidak ditemukan.")

    try:
        get_storage().delete(sig.image_path)
    except Exception:
        pass

    db.delete(sig)
    db.commit()
