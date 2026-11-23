import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verify_token: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    totp_secret: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    signatures = relationship("Signature", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")


class Signature(Base):
    __tablename__ = "signatures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(120), default="Tanda Tangan Saya", nullable=False)
    image_path: Mapped[str] = mapped_column(String(512), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # draw | upload | type
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="signatures")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_path: Mapped[str] = mapped_column(String(512), nullable=False)
    current_path: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True, nullable=False)
    # draft | pending | completed | revoked
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    owner = relationship("User", back_populates="documents")
    signers = relationship(
        "DocumentSigner",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentSigner.order_no",
    )
    signature_records = relationship(
        "SignatureRecord",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="SignatureRecord.signed_at",
    )
    audit_logs = relationship(
        "AuditLog",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="AuditLog.created_at.desc()",
    )


class DocumentSigner(Base):
    __tablename__ = "document_signers"
    __table_args__ = (
        UniqueConstraint("document_id", "email", "order_no", name="uq_doc_signer_email_order"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    signer_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    order_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)  # pending | signed | revoked
    invite_token: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    document = relationship("Document", back_populates="signers")


class SignatureRecord(Base):
    __tablename__ = "signature_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    signer_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)  # Sig1, Sig2, ...
    token: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)  # >= 128-bit random token
    page: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-based page number
    all_pages: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    signer_name: Mapped[str] = mapped_column(String(150), nullable=False)
    signer_title: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    doc_hash_after: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    document = relationship("Document", back_populates="signature_records")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    document_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    doc_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    document = relationship("Document", back_populates="audit_logs")
