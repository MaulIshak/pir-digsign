from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


# --- Auth ---
class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)
    totp_code: Optional[str] = Field(default=None, min_length=6, max_length=6)


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    is_verified: bool
    totp_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    user: UserOut
    csrf_token: str
    message: str = "OK"
    dev_verify_link: Optional[str] = None


class TotpSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    qr_data_url: str


class TotpCodeRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


# --- Signatures ---
class SignatureOut(BaseModel):
    id: str
    label: str
    type: str
    image_data_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SignatureCreateBase64(BaseModel):
    label: str = Field(default="Tanda Tangan Saya", min_length=1, max_length=120)
    type: str = Field(..., pattern="^(draw|upload|type)$")
    image_base64: str
    remove_background: bool = False


# --- Documents ---
class DocumentSignerOut(BaseModel):
    id: str
    email: str
    signer_name: Optional[str]
    order_no: int
    status: str
    signed_at: Optional[datetime]
    invite_link: Optional[str] = None

    model_config = {"from_attributes": True}


class SignatureRecordOut(BaseModel):
    id: str
    field_name: str
    token: str
    verify_url: str
    page: int
    all_pages: bool
    x: float
    y: float
    width: float
    height: float
    signer_name: str
    signer_title: Optional[str]
    doc_hash_after: str
    signed_at: datetime
    revoked_at: Optional[datetime]

    model_config = {"from_attributes": True}


class EmbeddedPdfSignatureOut(BaseModel):
    field_name: str
    signer_cn: Optional[str] = None
    signing_time: Optional[str] = None
    intact: bool
    valid: bool
    summary: str


class AuditLogOut(BaseModel):
    id: str
    user_id: Optional[str]
    action: str
    ip: Optional[str]
    user_agent: Optional[str]
    doc_hash: Optional[str]
    details: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentSummaryOut(BaseModel):
    id: str
    owner_id: str
    title: str
    original_filename: str
    status: str
    current_hash: str
    page_count: int
    signature_count: int = 0
    created_at: datetime
    updated_at: datetime


class DocumentDetailOut(DocumentSummaryOut):
    is_owner: bool
    can_sign_now: bool
    cannot_sign_reason: Optional[str] = None
    signers: List[DocumentSignerOut] = []
    signature_records: List[SignatureRecordOut] = []
    embedded_signatures: List[EmbeddedPdfSignatureOut] = []
    audit_logs: List[AuditLogOut] = []


class SignDocumentRequest(BaseModel):
    signature_id: str
    page: int = Field(..., ge=1)
    x: float = Field(..., ge=0)
    y: float = Field(..., ge=0)
    w: float = Field(..., gt=20)
    h: float = Field(..., gt=15)
    all_pages: bool = False
    signer_title: Optional[str] = Field(default=None, max_length=150)
    signer_display_name: Optional[str] = Field(default=None, max_length=150)
    # Opsi tampilan stempel visual
    show_qr: bool = True
    show_labels: bool = True
    show_name: bool = False
    show_date: bool = False
    show_border: bool = True
    transparent_background: bool = True


class InviteSignerItem(BaseModel):
    email: EmailStr
    name: Optional[str] = Field(default=None, max_length=150)
    order_no: int = Field(..., ge=1)


class InviteSignersRequest(BaseModel):
    signers: List[InviteSignerItem] = Field(..., min_length=1, max_length=20)


class RevokeRequest(BaseModel):
    reason: Optional[str] = Field(default="Dicabut oleh pemilik dokumen", max_length=300)


# --- Public Verification ---
class PublicVerifyResponse(BaseModel):
    status: str  # VALID | TIDAK VALID | DICABUT
    message: str
    token: str
    document_title: str
    signer_name: str
    signer_title: Optional[str] = None
    signed_at: datetime
    revoked_at: Optional[datetime] = None
    doc_hash_sha256: str
    field_name: str
    page: int
    total_signatures_on_doc: int


class VerifyUploadResponse(BaseModel):
    status: str  # VALID | TIDAK VALID | DICABUT
    message: str
    uploaded_sha256: str
    expected_sha256: Optional[str] = None
    matched_record: Optional[PublicVerifyResponse] = None
    embedded_signatures: List[EmbeddedPdfSignatureOut] = []
