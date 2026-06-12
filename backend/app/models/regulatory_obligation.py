"""Regulatory Obligation model.

Tracks industry-specific regulatory obligations extracted from contracts.
These are distinct from general contract obligations and focus specifically
on regulatory compliance requirements (FDA, HIPAA, GMP, etc.).
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin
from app.models.industry import Industry
from app.models.obligation import RAGStatus

if TYPE_CHECKING:
    from app.models.contract import Contract


class RegulationType(str, __import__("enum").Enum):
    """Types of regulatory frameworks."""

    # US Regulations
    FDA = "fda"  # Food and Drug Administration
    HIPAA = "hipaa"  # Health Insurance Portability and Accountability Act
    EPA = "epa"  # Environmental Protection Agency
    OSHA = "osha"  # Occupational Safety and Health
    SOX = "sox"  # Sarbanes-Oxley
    FINRA = "finra"  # Financial Industry Regulatory Authority
    SEC = "sec"  # Securities and Exchange Commission
    FTC = "ftc"  # Federal Trade Commission

    # EU Regulations
    GDPR = "gdpr"  # General Data Protection Regulation
    MDR = "mdr"  # Medical Device Regulation
    IVDR = "ivdr"  # In Vitro Diagnostic Regulation
    REACH = "reach"  # Registration, Evaluation, Authorization, Chemicals

    # Industry Standards (often regulatory-equivalent)
    GMP = "gmp"  # Good Manufacturing Practice
    GCP = "gcp"  # Good Clinical Practice
    GLP = "glp"  # Good Laboratory Practice
    ISO_9001 = "iso_9001"
    ISO_13485 = "iso_13485"
    ISO_27001 = "iso_27001"
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"

    # International
    ICH = "ich"  # International Council for Harmonisation
    WHO = "who"  # World Health Organization

    OTHER = "other"


class ObligationCategory(str, __import__("enum").Enum):
    """Categories of regulatory obligations."""

    # Quality and Compliance
    AUDIT_RIGHTS = "audit_rights"
    CHANGE_CONTROL = "change_control"
    DEVIATION_REPORTING = "deviation_reporting"
    CORRECTIVE_ACTION = "corrective_action"
    QUALITY_REVIEW = "quality_review"

    # Safety and Risk
    RECALL_RESPONSE = "recall_response"
    ADVERSE_EVENT_REPORTING = "adverse_event_reporting"
    SAFETY_MONITORING = "safety_monitoring"
    RISK_ASSESSMENT = "risk_assessment"

    # Documentation
    RECORD_RETENTION = "record_retention"
    DOCUMENTATION_CONTROL = "documentation_control"
    BATCH_RECORDS = "batch_records"
    VALIDATION_RECORDS = "validation_records"

    # Training and Personnel
    TRAINING_REQUIREMENTS = "training_requirements"
    QUALIFICATION_REQUIREMENTS = "qualification_requirements"

    # Reporting
    REGULATORY_REPORTING = "regulatory_reporting"
    PERIODIC_REPORTING = "periodic_reporting"
    NOTIFICATION_REQUIREMENTS = "notification_requirements"

    # Data and Privacy
    DATA_PROTECTION = "data_protection"
    BREACH_NOTIFICATION = "breach_notification"
    DATA_RETENTION = "data_retention"

    # Environmental
    ENVIRONMENTAL_COMPLIANCE = "environmental_compliance"
    WASTE_MANAGEMENT = "waste_management"

    OTHER = "other"


class RegulatoryObligation(Base, UUIDMixin, TimestampMixin):
    """Industry-specific regulatory obligation extracted from a contract.

    These obligations are extracted from contracts in regulated industries
    and track specific regulatory requirements that must be complied with.
    """

    __tablename__ = "regulatory_obligations"

    # Related contract
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contract: Mapped["Contract"] = relationship(
        "Contract",
        back_populates="regulatory_obligations",
    )

    # Industry and regulation
    industry: Mapped[Industry] = mapped_column(
        Enum(
            Industry,
            name='industry',
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    regulation_type: Mapped[RegulationType] = mapped_column(
        Enum(
            RegulationType,
            name='regulationtype',
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    regulation_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        doc="Specific reference, e.g., '21 CFR 211.68'",
    )

    # Obligation details
    obligation_category: Mapped[ObligationCategory] = mapped_column(
        Enum(
            ObligationCategory,
            name='regulatoryobligationcategory',
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    source_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Original text from the contract",
    )
    source_section: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Section reference in the contract",
    )

    # Responsible party
    responsible_party: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Frequency and timing
    frequency: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Frequency: 'annual', 'quarterly', 'ongoing', etc.",
    )
    next_due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )
    last_completed_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    # Compliance tracking
    compliance_status: Mapped[RAGStatus] = mapped_column(
        Enum(
            RAGStatus,
            name='ragstatus',
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=RAGStatus.NOT_ASSESSED,
        index=True,
    )
    last_compliance_check: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    compliance_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    compliance_evidence: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="File paths or descriptions of evidence",
    )

    # Extraction metadata
    extraction_confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )
    extraction_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        doc="Additional extraction details from AI",
    )

    # Indexes for common queries
    __table_args__ = (
        Index(
            "ix_regulatory_obligations_contract_status",
            "contract_id",
            "compliance_status",
        ),
        Index(
            "ix_regulatory_obligations_regulation",
            "regulation_type",
            "obligation_category",
        ),
        Index(
            "ix_regulatory_obligations_due_date",
            "next_due_date",
            "compliance_status",
        ),
        Index(
            "ix_regulatory_obligations_industry",
            "industry",
            "regulation_type",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<RegulatoryObligation {self.regulation_type.value}/"
            f"{self.obligation_category.value} - {self.compliance_status.value}>"
        )

    @property
    def is_compliant(self) -> bool:
        """Check if this obligation is currently compliant."""
        return self.compliance_status == RAGStatus.GREEN

    @property
    def needs_attention(self) -> bool:
        """Check if this obligation needs attention."""
        return self.compliance_status in [RAGStatus.AMBER, RAGStatus.RED]

    @property
    def is_overdue(self) -> bool:
        """Check if this obligation is past its due date."""
        if self.next_due_date is None:
            return False
        return date.today() > self.next_due_date
