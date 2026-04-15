"""Models for extraction quality golden set and verification."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, Float, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class VerificationStatus(str, enum.Enum):
    """Status of an extraction verification."""
    PENDING = "pending"
    CORRECT = "correct"
    INCORRECT = "incorrect"
    PARTIAL = "partial"


class GoldenSetContract(Base, UUIDMixin, TimestampMixin):
    """Tracks which contracts are in a golden set for extraction quality.

    Global entries (tenant_id=NULL) are managed by super admin and benefit all tenants.
    Tenant-specific entries (tenant_id set) are managed by that tenant's admin.
    """

    __tablename__ = "golden_set_contracts"

    # Nullable tenant_id: NULL = global/platform, set = tenant-specific
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=True,
        index=True,
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
    )
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_baseline: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        doc="True for system-provided baseline contracts"
    )
    is_global: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        doc="True for platform-wide golden set entries (managed by super admin)"
    )

    # Aggregate quality scores (computed after verification)
    metadata_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    clause_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    obligation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    sla_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    contract = relationship("Contract", lazy="selectin")
    verifications = relationship(
        "ExtractionVerification",
        back_populates="golden_set_contract",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_golden_set_tenant_contract", "tenant_id", "contract_id", unique=True),
    )


class ExtractionVerification(Base, UUIDMixin, TimestampMixin):
    """Verification of a single extracted item (clause, obligation, SLA, or metadata field)."""

    __tablename__ = "extraction_verifications"

    golden_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("golden_set_contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        doc="Type: metadata_field, clause, obligation, sla"
    )
    entity_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        doc="ID of the clause/obligation/SLA, or field name for metadata"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=VerificationStatus.PENDING.value,
    )
    corrected_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Relationships
    golden_set_contract = relationship("GoldenSetContract", back_populates="verifications")

    __table_args__ = (
        Index("ix_verification_entity", "golden_set_id", "entity_type", "entity_id", unique=True),
    )
