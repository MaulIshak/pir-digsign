from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AuditLog, Document, SignatureRecord
from app.schemas import EmbeddedPdfSignatureOut, PublicVerifyResponse, VerifyUploadResponse
from app.security import compute_sha256, get_client_ip, get_user_agent, limiter, validate_pdf_upload
from app.services.pdf_signer import async_inspect_embedded_signatures

router = APIRouter(prefix="/verify", tags=["Public Verification"])
settings = get_settings()


def _record_to_public_response(rec: SignatureRecord, doc: Document) -> PublicVerifyResponse:
    is_revoked = rec.revoked_at is not None or doc.status == "revoked"
    status_str = "DICABUT" if is_revoked else "VALID"
    message = (
        "Tanda tangan pada dokumen ini telah DICABUT oleh pemilik dokumen."
        if is_revoked
        else "Tanda tangan terdaftar dan VALID pada sistem."
    )
    return PublicVerifyResponse(
        status=status_str,
        message=message,
        token=rec.token,
        document_title=doc.title,
        signer_name=rec.signer_name,
        signer_title=rec.signer_title,
        signed_at=rec.signed_at,
        revoked_at=rec.revoked_at,
        doc_hash_sha256=rec.doc_hash_after,
        field_name=rec.field_name,
        page=rec.page,
        total_signatures_on_doc=len(doc.signature_records),
    )


@router.get("/{token}", response_model=PublicVerifyResponse)
@limiter.limit(settings.RATE_LIMIT_VERIFY)
def verify_by_token(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Halaman/API verifikasi publik via QR code.
    Tidak membocorkan data sensitif (email, IP, path storage, user_id).
    """
    rec = db.query(SignatureRecord).filter(SignatureRecord.token == token).first()
    if not rec:
        raise HTTPException(
            status_code=404,
            detail="Token verifikasi tidak ditemukan (TIDAK VALID).",
        )

    doc = db.query(Document).filter(Document.id == rec.document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Dokumen terkait tidak ditemukan.")

    db.add(
        AuditLog(
            document_id=doc.id,
            user_id=None,
            action="PUBLIC_VERIFY_VIEW",
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
            doc_hash=rec.doc_hash_after,
            details=f"Verifikasi QR untuk field {rec.field_name}",
        )
    )
    db.commit()

    return _record_to_public_response(rec, doc)


@router.post("/upload", response_model=VerifyUploadResponse)
@limiter.limit(settings.RATE_LIMIT_VERIFY)
async def verify_uploaded_pdf(
    request: Request,
    file: UploadFile = File(...),
    token: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    """
    Mencocokkan hash SHA-256 PDF yang diunggah pengguna terhadap catatan tanda tangan
    serta memverifikasi integritas tanda tangan kriptografis PAdES di dalam PDF.
    Perubahan 1 byte saja pada PDF akan menghasilkan status TIDAK VALID.
    """
    pdf_bytes = await file.read()
    validate_pdf_upload(pdf_bytes, file.filename or "dokumen.pdf", file.content_type)

    uploaded_sha256 = compute_sha256(pdf_bytes)
    embedded_raw = await async_inspect_embedded_signatures(pdf_bytes)
    embedded_out: List[EmbeddedPdfSignatureOut] = [
        EmbeddedPdfSignatureOut(
            field_name=e.field_name,
            signer_cn=e.signer_cn,
            signing_time=e.signing_time,
            intact=e.intact,
            valid=e.valid,
            summary=e.summary,
        )
        for e in embedded_raw
    ]

    if token and token.strip():
        rec = db.query(SignatureRecord).filter(SignatureRecord.token == token.strip()).first()
        if not rec:
            return VerifyUploadResponse(
                status="TIDAK VALID",
                message="Token verifikasi tidak dikenal.",
                uploaded_sha256=uploaded_sha256,
                expected_sha256=None,
                matched_record=None,
                embedded_signatures=embedded_out,
            )

        doc = db.query(Document).filter(Document.id == rec.document_id).first()
        if not doc:
            return VerifyUploadResponse(
                status="TIDAK VALID",
                message="Dokumen terkait token tidak ditemukan.",
                uploaded_sha256=uploaded_sha256,
                expected_sha256=rec.doc_hash_after,
                matched_record=None,
                embedded_signatures=embedded_out,
            )

        if rec.revoked_at is not None or doc.status == "revoked":
            return VerifyUploadResponse(
                status="DICABUT",
                message="Tanda tangan pada dokumen ini telah DICABUT.",
                uploaded_sha256=uploaded_sha256,
                expected_sha256=rec.doc_hash_after,
                matched_record=_record_to_public_response(rec, doc),
                embedded_signatures=embedded_out,
            )

        # Cocokkan terhadap hash revisi token ini ATAU revisi lanjutan multi-signer dari dokumen yang sama
        valid_doc_hashes = {r.doc_hash_after for r in doc.signature_records if r.revoked_at is None}
        hash_matches = uploaded_sha256 in valid_doc_hashes

        # Cek integritas kriptografis tanda tangan field terkait di dalam PDF
        matching_embedded = [e for e in embedded_raw if e.field_name == rec.field_name]
        crypto_intact = bool(matching_embedded and matching_embedded[0].intact)

        if hash_matches and crypto_intact:
            msg = (
                "Hash SHA-256 cocok persis dan integritas kriptografis PAdES UTUH (VALID)."
                if uploaded_sha256 == rec.doc_hash_after
                else "Dokumen cocok dengan revisi multi-penanda tangan yang sah dan tanda tangan ini tetap UTUH (VALID)."
            )
            return VerifyUploadResponse(
                status="VALID",
                message=msg,
                uploaded_sha256=uploaded_sha256,
                expected_sha256=rec.doc_hash_after,
                matched_record=_record_to_public_response(rec, doc),
                embedded_signatures=embedded_out,
            )

        return VerifyUploadResponse(
            status="TIDAK VALID",
            message=(
                "TIDAK VALID! Hash SHA-256 PDF yang diunggah tidak cocok dengan dokumen asli "
                "atau dokumen telah dimodifikasi setelah ditandatangani."
            ),
            uploaded_sha256=uploaded_sha256,
            expected_sha256=rec.doc_hash_after,
            matched_record=_record_to_public_response(rec, doc),
            embedded_signatures=embedded_out,
        )

    # Verifikasi tanpa token: cari langsung berdasarkan hash SHA-256
    rec = (
        db.query(SignatureRecord)
        .filter(SignatureRecord.doc_hash_after == uploaded_sha256)
        .first()
    )
    if not rec:
        return VerifyUploadResponse(
            status="TIDAK VALID",
            message="TIDAK VALID! Hash SHA-256 PDF tidak ditemukan di sistem atau dokumen telah diubah.",
            uploaded_sha256=uploaded_sha256,
            expected_sha256=None,
            matched_record=None,
            embedded_signatures=embedded_out,
        )

    doc = db.query(Document).filter(Document.id == rec.document_id).first()
    if not doc:
        return VerifyUploadResponse(
            status="TIDAK VALID",
            message="Dokumen terkait tidak ditemukan.",
            uploaded_sha256=uploaded_sha256,
            expected_sha256=rec.doc_hash_after,
            matched_record=None,
            embedded_signatures=embedded_out,
        )

    if rec.revoked_at is not None or doc.status == "revoked":
        return VerifyUploadResponse(
            status="DICABUT",
            message="Dokumen cocok, tetapi tanda tangannya telah DICABUT.",
            uploaded_sha256=uploaded_sha256,
            expected_sha256=rec.doc_hash_after,
            matched_record=_record_to_public_response(rec, doc),
            embedded_signatures=embedded_out,
        )

    all_intact = bool(embedded_raw) and all(e.intact for e in embedded_raw)
    if not all_intact:
        return VerifyUploadResponse(
            status="TIDAK VALID",
            message="Integritas kriptografis tanda tangan di dalam PDF tidak utuh.",
            uploaded_sha256=uploaded_sha256,
            expected_sha256=rec.doc_hash_after,
            matched_record=_record_to_public_response(rec, doc),
            embedded_signatures=embedded_out,
        )

    return VerifyUploadResponse(
        status="VALID",
        message="Dokumen asli dan seluruh tanda tangan kriptografis VALID.",
        uploaded_sha256=uploaded_sha256,
        expected_sha256=rec.doc_hash_after,
        matched_record=_record_to_public_response(rec, doc),
        embedded_signatures=embedded_out,
    )
