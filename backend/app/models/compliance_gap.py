"""Compliance Gap model.

Tracks missing or incomplete compliance requirements for contracts.
Gaps are created when a contract is analyzed and found to be missing
required compliance documents.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin
from app.models.industry import (
    ComplianceDocumentType,
    ComplianceGapSeverity,
    ComplianceGapStatus,
)

if TYPE_CHECKING:
    from app.models.compliance_rule import IndustryComplianceRule
    from app.models.contract import Contract
    from app.models.user import User


class ComplianceGap(Base, UUIDMixin, TimestampMixin):
    """Missing or incomplete compliance requirement.

    Each gap represents a specific compliance document that is required
    but not yet linked to a contract. Gaps can be resolved by linking
    an appropriate document or by waiving the requirement.
    """

    __tablename__ = "compliance_gaps"

    # Related contract
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contract: Mapped["Contract"] = relationship(
        "Contract",
        foreign_keys=[contract_id],
        back_populates="compliance_gaps",
    )

    # Rule that created this gap (optional - may be manually created)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("industry_compliance_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    rule: Mapped[Optional["IndustryComplianceRule"]] = relationship(
        "IndustryComplianceRule",
        back_populates="gaps",
    )

    # Gap details
    missing_document_type: Mapped[ComplianceDocumentType] = mapped_column(
        Enum(
            ComplianceDocumentType,
            name='compliancedocumenttype',
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )
    gap_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Human-readable description of the compliance gap",
    )
    regulatory_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Reference to regulation requiring this document",
    )

    # Severity and status
    severity: Mapped[ComplianceGapSeverity] = mapped_column(
        Enum(
            ComplianceGapSeverity,
            name='compliancegapseverity',
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ComplianceGapSeverity.MEDIUM,
        index=True,
    )
    status: Mapped[ComplianceGapStatus] = mapped_column(
        Enum(
            ComplianceGapStatus,
            name='compliancegapstatus',
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ComplianceGapStatus.OPEN,
        index=True,
    )

    # Resolution tracking
    resolution_due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Document that resolves this gap (linked contract)
    linked_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contracts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    linked_document: Mapped[Optional["Contract"]] = relationship(
        "Contract",
        foreign_keys=[linked_document_id],
    )

    # Detection metadata
    detection_confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        doc="Confidence score from AI detection (0.0-1.0)",
    )
    detection_reasoning: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Explanation of why this gap was detected",
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    # Waiver information (if status = WAIVED)
    waiver_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    waiver_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    waiver_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_compliance_gaps_contract_status", "contract_id", "status"),
        Index("ix_compliance_gaps_severity_status", "severity", "status"),
        Index("ix_compliance_gaps_due_date", "resolution_due_date", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<ComplianceGap {self.missing_document_type.value} "
            f"[{self.severity.value}] - {self.status.value}>"
        )

    @property
    def is_open(self) -> bool:
        """Check if this gap is still open and needs attention."""
        return self.status in [
            ComplianceGapStatus.OPEN,
            ComplianceGapStatus.IN_PROGRESS,
            ComplianceGapStatus.PENDING_REVIEW,
        ]

    @property
    def is_overdue(self) -> bool:
        """Check if this gap is past its resolution due date."""
        if self.resolution_due_date is None:
            return False
        return self.is_open and date.today() > self.resolution_due_date

    @property
    def days_until_due(self) -> int | None:
        """Number of days until resolution is due."""
        if self.resolution_due_date is None:
            return None
        return (self.resolution_due_date - date.today()).days
