import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import AuditLog, Document, DocumentSigner, Signature, SignatureRecord, User
from app.schemas import (
    AuditLogOut,
    DocumentDetailOut,
    DocumentSignerOut,
    DocumentSummaryOut,
    EmbeddedPdfSignatureOut,
    InviteSignersRequest,
    RevokeRequest,
    SignatureRecordOut,
    SignDocumentRequest,
)
from app.security import (
    compute_sha256,
    generate_secure_token,
    get_client_ip,
    get_current_user,
    get_user_agent,
    limiter,
    require_csrf_and_user,
    validate_pdf_upload,
)
from app.services.email import get_email_provider
from app.services.pdf_signer import (
    get_pdf_info,
    inspect_embedded_signatures,
    sign_pdf_incremental,
)
from app.services.storage import get_storage

router = APIRouter(prefix="/documents", tags=["Documents"])
settings = get_settings()


def _user_can_access_doc(doc: Document, user: User) -> bool:
    if doc.owner_id == user.id:
        return True
    email_norm = user.email.lower()
    return any(
        s.user_id == user.id or s.email.lower() == email_norm
        for s in doc.signers
    )


def _evaluate_signing_eligibility(
    doc: Document, user: User
) -> Tuple[bool, Optional[str], Optional[DocumentSigner]]:
    """
    Menentukan apakah `user` boleh menandatangani dokumen saat ini.
    Mendukung:
    1. Self-sign oleh pemilik dokumen (dokumen baru atau dokumen sudah bertanda tangan).
    2. Multi-signer berurutan (berdasarkan `order_no`).
    3. Pemilik menandatangani ulang dokumen atau menambah tanda tangan selama belum revoked.
    """
    if doc.status == "revoked":
        return False, "Dokumen ini sudah dicabut (revoked) dan tidak dapat ditandatangani.", None

    email_norm = user.email.lower()
    pending_signers = sorted(
        [s for s in doc.signers if s.status == "pending"],
        key=lambda s: s.order_no,
    )

    if pending_signers:
        # Cek apakah user termasuk dalam daftar penanda tangan pending
        matching_pending = [
            s for s in pending_signers if s.user_id == user.id or s.email.lower() == email_norm
        ]
        if matching_pending:
            my_slot = matching_pending[0]
            min_pending_order = pending_signers[0].order_no
            if my_slot.order_no > min_pending_order:
                return (
                    False,
                    f"Belum giliran Anda. Menunggu penanda tangan urutan ke-{min_pending_order} selesai terlebih dahulu.",
                    my_slot,
                )
            return True, None, my_slot

        # Jika user adalah pemilik tetapi sudah mengundang pihak lain yang sedang menunggu giliran
        if doc.owner_id == user.id:
            return (
                False,
                f"Dokumen sedang menunggu penanda tangan undangan (urutan ke-{pending_signers[0].order_no}: {pending_signers[0].email}).",
                None,
            )
        return False, "Anda sudah menyelesaikan giliran tanda tangan pada dokumen ini.", None

    # Tidak ada penanda tangan undangan yang pending: pemilik boleh self-sign atau counter-sign dokumennya sendiri
    if doc.owner_id == user.id:
        return True, None, None

    return False, "Anda sudah menyelesaikan tanda tangan pada dokumen ini.", None


def _build_document_detail(doc: Document, user: User, pdf_bytes: Optional[bytes] = None) -> DocumentDetailOut:
    can_sign, reason, _ = _evaluate_signing_eligibility(doc, user)
    base_url = settings.PUBLIC_BASE_URL.rstrip("/")

    embedded_out: List[EmbeddedPdfSignatureOut] = []
    if pdf_bytes is not None:
        for info in inspect_embedded_signatures(pdf_bytes):
            embedded_out.append(
                EmbeddedPdfSignatureOut(
                    field_name=info.field_name,
                    signer_cn=info.signer_cn,
                    signing_time=info.signing_time,
                    intact=info.intact,
                    valid=info.valid,
                    summary=info.summary,
                )
            )

    signers_out = [
        DocumentSignerOut(
            id=s.id,
            email=s.email,
            signer_name=s.signer_name,
            order_no=s.order_no,
            status=s.status,
            signed_at=s.signed_at,
            invite_link=(
                f"{base_url}/invite/{s.invite_token}"
                if (doc.owner_id == user.id and s.status == "pending")
                else None
            ),
        )
        for s in doc.signers
    ]

    records_out = [
        SignatureRecordOut(
            id=r.id,
            field_name=r.field_name,
            token=r.token,
            verify_url=f"{base_url}/verify/{r.token}",
            page=r.page,
            all_pages=r.all_pages,
            x=r.x,
            y=r.y,
            width=r.width,
            height=r.height,
            signer_name=r.signer_name,
            signer_title=r.signer_title,
            doc_hash_after=r.doc_hash_after,
            signed_at=r.signed_at,
            revoked_at=r.revoked_at,
        )
        for r in doc.signature_records
    ]

    logs_out = [AuditLogOut.model_validate(l) for l in doc.audit_logs]

    return DocumentDetailOut(
        id=doc.id,
        owner_id=doc.owner_id,
        title=doc.title,
        original_filename=doc.original_filename,
        status=doc.status,
        current_hash=doc.current_hash,
        page_count=doc.page_count,
        signature_count=len(doc.signature_records),
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        is_owner=(doc.owner_id == user.id),
        can_sign_now=can_sign,
        cannot_sign_reason=reason,
        signers=signers_out,
        signature_records=records_out,
        embedded_signatures=embedded_out,
        audit_logs=logs_out,
    )


@router.post("", response_model=DocumentDetailOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    user: User = Depends(require_csrf_and_user),
    db: Session = Depends(get_db),
):
    pdf_bytes = await file.read()
    safe_filename = validate_pdf_upload(pdf_bytes, file.filename or "dokumen.pdf", file.content_type)

    try:
        page_count, _ = get_pdf_info(pdf_bytes)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Dokumen PDF rusak atau tidak dapat dibaca: {exc}")

    doc_id = str(uuid.uuid4())
    doc_hash = compute_sha256(pdf_bytes)
    storage = get_storage()
    orig_key = f"documents/{doc_id}/rev_0_original.pdf"
    storage.save_bytes(orig_key, pdf_bytes, content_type="application/pdf")

    doc_title = (title or safe_filename.rsplit(".", 1)[0]).strip()[:255] or "Dokumen Tanpa Judul"
    doc = Document(
        id=doc_id,
        owner_id=user.id,
        title=doc_title,
        original_filename=safe_filename,
        original_path=orig_key,
        current_path=orig_key,
        status="draft",
        current_hash=doc_hash,
        page_count=page_count,
    )
    db.add(doc)
    db.add(
        AuditLog(
            document_id=doc_id,
            user_id=user.id,
            action="DOCUMENT_UPLOADED",
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
            doc_hash=doc_hash,
            details=f"Unggah PDF '{safe_filename}' ({len(pdf_bytes)} bytes, {page_count} halaman)",
        )
    )
    db.commit()
    db.refresh(doc)

    return _build_document_detail(doc, user, pdf_bytes=pdf_bytes)


@router.get("", response_model=List[DocumentSummaryOut])
def list_documents(
    status_filter: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    email_norm = user.email.lower()
    invited_doc_ids = (
        db.query(DocumentSigner.document_id)
        .filter(or_(DocumentSigner.user_id == user.id, DocumentSigner.email == email_norm))
        .subquery()
    )

    q = db.query(Document).filter(
        or_(Document.owner_id == user.id, Document.id.in_(invited_doc_ids))
    )
    if status_filter and status_filter in ("draft", "pending", "completed", "revoked"):
        q = q.filter(Document.status == status_filter)

    docs = q.order_by(Document.updated_at.desc()).all()
    return [
        DocumentSummaryOut(
            id=d.id,
            owner_id=d.owner_id,
            title=d.title,
            original_filename=d.original_filename,
            status=d.status,
            current_hash=d.current_hash,
            page_count=d.page_count,
            signature_count=len(d.signature_records),
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in docs
    ]


@router.get("/invite/{invite_token}")
def resolve_invite(
    invite_token: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    signer = db.query(DocumentSigner).filter(DocumentSigner.invite_token == invite_token).first()
    if not signer:
        raise HTTPException(status_code=404, detail="Tautan undangan tidak valid atau kedaluwarsa.")

    if signer.email.lower() != user.email.lower():
        raise HTTPException(
            status_code=403,
            detail=f"Undangan ini ditujukan untuk {signer.email}. Silakan masuk menggunakan email tersebut.",
        )

    if signer.user_id is None:
        signer.user_id = user.id
        db.commit()

    return {
        "document_id": signer.document_id,
        "order_no": signer.order_no,
        "status": signer.status,
        "message": "Undangan diterima.",
    }


@router.get("/{document_id}", response_model=DocumentDetailOut)
def get_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc or not _user_can_access_doc(doc, user):
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan.")

    pdf_bytes = get_storage().read_bytes(doc.current_path)
    return _build_document_detail(doc, user, pdf_bytes=pdf_bytes)


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc or not _user_can_access_doc(doc, user):
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan.")

    pdf_bytes = get_storage().read_bytes(doc.current_path)
    suffix = "_signed" if doc.signature_records else ""
    base = doc.original_filename.rsplit(".", 1)[0]
    download_name = f"{base}{suffix}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{download_name}"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/{document_id}/invite", response_model=DocumentDetailOut)
def invite_signers(
    document_id: str,
    request: Request,
    payload: InviteSignersRequest,
    user: User = Depends(require_csrf_and_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc or doc.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan atau bukan milik Anda.")
    if doc.status == "revoked":
        raise HTTPException(status_code=400, detail="Dokumen yang sudah dicabut tidak dapat menerima undangan baru.")

    email_provider = get_email_provider()
    base_url = settings.PUBLIC_BASE_URL.rstrip("/")

    existing_max_order = max([s.order_no for s in doc.signers], default=0)
    added_emails: List[str] = []

    for item in sorted(payload.signers, key=lambda x: x.order_no):
        email_norm = item.email.strip().lower()
        existing_user = db.query(User).filter(User.email == email_norm).first()

        # Pastikan order_no tidak bentrok dengan penanda tangan lama yang sama persis
        order_no = item.order_no
        if any(s.email.lower() == email_norm and s.order_no == order_no for s in doc.signers):
            order_no = existing_max_order + 1
            existing_max_order = order_no

        inv_token = generate_secure_token(24)
        ds = DocumentSigner(
            document_id=doc.id,
            user_id=existing_user.id if existing_user else None,
            email=email_norm,
            signer_name=(item.name or (existing_user.name if existing_user else None)),
            order_no=order_no,
            status="pending",
            invite_token=inv_token,
        )
        db.add(ds)
        added_emails.append(f"{email_norm} (#{order_no})")

        invite_link = f"{base_url}/invite/{inv_token}"
        email_provider.send_email(
            to_email=email_norm,
            subject=f"[{settings.APP_NAME}] Undangan Tanda Tangan Dokumen: {doc.title}",
            body_text=(
                f"Halo {item.name or email_norm},\n\n"
                f"{user.name} mengundang Anda untuk menandatangani dokumen '{doc.title}' "
                f"(urutan ke-{order_no}).\n\n"
                f"Buka tautan berikut untuk menandatangani:\n"
                f"{invite_link}\n"
            ),
        )

    doc.status = "pending"
    db.add(
        AuditLog(
            document_id=doc.id,
            user_id=user.id,
            action="SIGNERS_INVITED",
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
            doc_hash=doc.current_hash,
            details="Mengundang penanda tangan: " + ", ".join(added_emails),
        )
    )
    db.commit()
    db.refresh(doc)

    pdf_bytes = get_storage().read_bytes(doc.current_path)
    return _build_document_detail(doc, user, pdf_bytes=pdf_bytes)


@router.post("/{document_id}/sign", response_model=DocumentDetailOut)
@limiter.limit(settings.RATE_LIMIT_SIGN)
def sign_document(
    document_id: str,
    request: Request,
    payload: SignDocumentRequest,
    user: User = Depends(require_csrf_and_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc or not _user_can_access_doc(doc, user):
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan.")

    can_sign, reason, active_signer_slot = _evaluate_signing_eligibility(doc, user)
    if not can_sign:
        raise HTTPException(status_code=403, detail=reason or "Tidak diizinkan menandatangani saat ini.")

    sig = (
        db.query(Signature)
        .filter(Signature.id == payload.signature_id, Signature.user_id == user.id)
        .first()
    )
    if not sig:
        raise HTTPException(status_code=404, detail="Tanda tangan tidak ditemukan di profil Anda.")

    storage = get_storage()
    current_pdf_bytes = storage.read_bytes(doc.current_path)
    sig_png_bytes = storage.read_bytes(sig.image_path)

    # Token verifikasi publik acak >= 192 bit (bukan ID berurutan)
    verify_token = generate_secure_token(24)
    verify_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/verify/{verify_token}"
    signer_name = (payload.signer_display_name or user.name).strip()

    try:
        sign_result = sign_pdf_incremental(
            pdf_bytes=current_pdf_bytes,
            signature_png_bytes=sig_png_bytes,
            verify_url=verify_url,
            signer_name=signer_name,
            page=payload.page,
            x=payload.x,
            y=payload.y,
            w=payload.w,
            h=payload.h,
            signer_title=payload.signer_title,
            all_pages=payload.all_pages,
            transparent_background=payload.transparent_background,
            show_qr=payload.show_qr,
            show_labels=payload.show_labels,
            show_name=payload.show_name,
            show_date=payload.show_date,
            show_border=payload.show_border,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Gagal menandatangani PDF: {exc}")

    new_hash = compute_sha256(sign_result.signed_pdf_bytes)
    rev_num = len(doc.signature_records) + 1
    new_path = f"documents/{doc.id}/rev_{rev_num}_{sign_result.field_name}.pdf"
    storage.save_bytes(new_path, sign_result.signed_pdf_bytes, content_type="application/pdf")

    record = SignatureRecord(
        document_id=doc.id,
        signer_id=user.id,
        field_name=sign_result.field_name,
        token=verify_token,
        page=payload.page,
        all_pages=payload.all_pages,
        x=payload.x,
        y=payload.y,
        width=payload.w,
        height=payload.h,
        signer_name=signer_name,
        signer_title=payload.signer_title.strip() if payload.signer_title else None,
        doc_hash_after=new_hash,
        signed_at=sign_result.signed_at,
    )
    db.add(record)

    if active_signer_slot is not None:
        active_signer_slot.user_id = user.id
        active_signer_slot.signer_name = signer_name
        active_signer_slot.status = "signed"
        active_signer_slot.signed_at = sign_result.signed_at

    doc.current_path = new_path
    doc.current_hash = new_hash
    doc.updated_at = datetime.now(timezone.utc)

    # Tentukan status dokumen terbaru
    remaining_pending = [
        s for s in doc.signers
        if s.status == "pending" and (active_signer_slot is None or s.id != active_signer_slot.id)
    ]
    doc.status = "pending" if remaining_pending else "completed"

    db.add(
        AuditLog(
            document_id=doc.id,
            user_id=user.id,
            action="DOCUMENT_SIGNED",
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
            doc_hash=new_hash,
            details=(
                f"Ditandatangani oleh {signer_name} pada field {sign_result.field_name} "
                f"(halaman {payload.page}, all_pages={payload.all_pages})"
            ),
        )
    )
    db.commit()
    db.refresh(doc)

    return _build_document_detail(doc, user, pdf_bytes=sign_result.signed_pdf_bytes)


@router.post("/{document_id}/revoke", response_model=DocumentDetailOut)
def revoke_document(
    document_id: str,
    request: Request,
    payload: RevokeRequest = RevokeRequest(),
    user: User = Depends(require_csrf_and_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc or doc.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan atau hanya pemilik yang dapat mencabut.")

    if doc.status == "revoked":
        raise HTTPException(status_code=400, detail="Dokumen sudah dicabut sebelumnya.")

    now = datetime.now(timezone.utc)
    for rec in doc.signature_records:
        if rec.revoked_at is None:
            rec.revoked_at = now
    for signer in doc.signers:
        if signer.status == "pending":
            signer.status = "revoked"

    doc.status = "revoked"
    doc.updated_at = now

    db.add(
        AuditLog(
            document_id=doc.id,
            user_id=user.id,
            action="DOCUMENT_REVOKED",
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
            doc_hash=doc.current_hash,
            details=payload.reason or "Tanda tangan dicabut oleh pemilik dokumen",
        )
    )
    db.commit()
    db.refresh(doc)

    pdf_bytes = get_storage().read_bytes(doc.current_path)
    return _build_document_detail(doc, user, pdf_bytes=pdf_bytes)
