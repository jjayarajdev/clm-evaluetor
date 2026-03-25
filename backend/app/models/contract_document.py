"""Contract Document models for managing document packages within contracts.

Supports multiple document types (amendments, addenda, SOWs, etc.) per contract,
with signature tracking and hierarchical section outlines.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUIDMixin


# ===== Enum Definitions =====

class DocumentType(str, enum.Enum):
    """Type of document within a contract package."""
    MAIN_AGREEMENT = "main_agreement"
    AMENDMENT = "amendment"
    ADDENDUM = "addendum"
    SCHEDULE = "schedule"
    EXHIBIT = "exhibit"
    STATEMENT_OF_WORK = "statement_of_work"
    SIDE_LETTER = "side_letter"
    APPENDIX = "appendix"
    CERTIFICATE = "certificate"
    OTHER = "other"


class SignatureType(str, enum.Enum):
    """Method of signing."""
    WET_INK = "wet_ink"
    DIGITAL = "digital"
    ELECTRONIC = "electronic"
    STAMP = "stamp"


class SignatureStatus(str, enum.Enum):
    """Current state of a signature."""
    PENDING = "pending"
    SIGNED = "signed"
    DECLINED = "declined"
    EXPIRED = "expired"


# ===== Models =====

class ContractDocument(Base, UUIDMixin):
    """A document within a contract package.

    Each contract can have multiple documents: a main agreement plus
    amendments, addenda, schedules, exhibits, SOWs, side letters, etc.
    """

    __tablename__ = "contract_documents"

    # Tenant isolation
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )

    # Parent contract
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Document classification
    document_type: Mapped[str] = mapped_column(
        PG_ENUM(
            *[e.value for e in DocumentType],
            name="documenttype",
            create_type=False,
        ),
        nullable=False,
        default=DocumentType.OTHER.value,
        index=True,
    )

    # Document metadata
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    language: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="en",
    )
    version: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # File information
    file_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    file_size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Dates
    upload_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    contract: Mapped["Contract"] = relationship(
        "Contract",
        back_populates="documents",
    )
    signatures: Mapped[list["DocumentSignature"]] = relationship(
        "DocumentSignature",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    sections: Mapped[list["DocumentSection"]] = relationship(
        "DocumentSection",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ContractDocument {self.title} ({self.document_type})>"


class DocumentSignature(Base, UUIDMixin):
    """A signature record on a contract document.

    Tracks who signed, when, and with what method.
    """

    __tablename__ = "document_signatures"

    # Parent document
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contract_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Signer information
    signer_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    signer_title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    signer_organization: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    signer_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Signature dates
    signed_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Signature classification
    signature_type: Mapped[str] = mapped_column(
        PG_ENUM(
            *[e.value for e in SignatureType],
            name="signaturetype",
            create_type=False,
        ),
        nullable=False,
        default=SignatureType.ELECTRONIC.value,
    )
    signature_status: Mapped[str] = mapped_column(
        PG_ENUM(
            *[e.value for e in SignatureStatus],
            name="signaturestatus",
            create_type=False,
        ),
        nullable=False,
        default=SignatureStatus.PENDING.value,
    )

    # Additional info
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    document: Mapped["ContractDocument"] = relationship(
        "ContractDocument",
        back_populates="signatures",
    )

    def __repr__(self) -> str:
        return f"<DocumentSignature {self.signer_name} ({self.signature_status})>"


class DocumentSection(Base, UUIDMixin):
    """A section or sub-section within a contract document.

    Supports hierarchical structure via parent_section_id for
    nested section outlines (e.g., 1 > 1.1 > 1.1.1).
    """

    __tablename__ = "document_sections"

    # Parent document
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contract_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Hierarchy - self-referencing FK for sub-sections
    parent_section_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_sections.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Section identification
    section_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    content_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Page references
    page_start: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    page_end: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Ordering
    order_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    document: Mapped["ContractDocument"] = relationship(
        "ContractDocument",
        back_populates="sections",
    )
    parent_section: Mapped["DocumentSection | None"] = relationship(
        "DocumentSection",
        remote_side="DocumentSection.id",
        back_populates="sub_sections",
    )
    sub_sections: Mapped[list["DocumentSection"]] = relationship(
        "DocumentSection",
        back_populates="parent_section",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<DocumentSection {self.section_number}: {self.title}>"
