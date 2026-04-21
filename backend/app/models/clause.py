import enum
import uuid

from sqlalchemy import Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin
from app.models.contract import RiskLevel


class ClauseType(str, enum.Enum):
    """Supported clause types for extraction."""

    # Legal/Risk clauses
    INDEMNIFICATION = "indemnification"
    LIMITATION_OF_LIABILITY = "limitation_of_liability"
    TERMINATION = "termination"
    CONFIDENTIALITY = "confidentiality"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    PAYMENT_TERMS = "payment_terms"
    WARRANTY = "warranty"
    FORCE_MAJEURE = "force_majeure"
    NON_COMPETE = "non_compete"
    NON_SOLICITATION = "non_solicitation"
    DATA_PROTECTION = "data_protection"
    DISPUTE_RESOLUTION = "dispute_resolution"
    ASSIGNMENT = "assignment"
    NOTICE = "notice"
    GOVERNING_LAW = "governing_law"
    SLA = "sla"
    AUTO_RENEWAL = "auto_renewal"

    # Structural clauses (for different dashboards)
    PREAMBLE = "preamble"  # Header, parties, effective date
    DEFINITIONS = "definitions"  # Defined terms
    SERVICE_ORDER = "service_order"  # Scope, fees, deliverables
    PROCEDURAL = "procedural"  # Process steps, SLAs, workflows
    EXHIBIT = "exhibit"  # Schedules, attachments, price tables

    # IT Service/Outsourcing contract clauses
    SERVICE_DESCRIPTION = "service_description"  # What services are provided
    SERVICE_LEVEL = "service_level"  # Performance metrics and targets
    DELIVERABLE = "deliverable"  # What must be delivered, milestones
    GOVERNANCE = "governance"  # Management, oversight, reporting structure
    TRANSITION = "transition"  # Exit planning, knowledge transfer
    CHANGE_MANAGEMENT = "change_management"  # How changes are handled
    SUPPORT = "support"  # Helpdesk, escalation, incident management
    SECURITY = "security"  # Security requirements and controls
    PERSONNEL = "personnel"  # Staffing, roles, responsibilities
    PRICING = "pricing"  # Cost structure, fees, rate cards
    RISK_MITIGATION = "risk_mitigation"  # Risk management provisions
    SCOPE = "scope"  # Scope of work, inclusions/exclusions
    ACCEPTANCE = "acceptance"  # Acceptance criteria and testing

    OTHER = "other"


class Clause(Base, UUIDMixin, TimestampMixin):
    """Clause model representing an extracted clause from a contract."""

    __tablename__ = "clauses"

    # Relationship to contract
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contract: Mapped["Contract"] = relationship(
        "Contract",
        back_populates="clauses",
    )

    # Clause classification
    clause_type: Mapped[ClauseType] = mapped_column(
        Enum(ClauseType, name='clausetype', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )

    # Clause content
    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Location in document
    section_number: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    char_start: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    char_end: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Pre-computed highlight coordinates from PyMuPDF (PDF points, 72 DPI)
    # Format: [{"page": 3, "x0": 72.0, "y0": 120.5, "x1": 540.0, "y1": 135.2}, ...]
    highlight_rects: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )

    # Risk assessment
    risk_level: Mapped[RiskLevel | None] = mapped_column(
        Enum(RiskLevel, name='risklevel', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
        index=True,
    )
    risk_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # AI confidence
    confidence_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # Extracted values (for specific clause types)
    extracted_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Tenant-defined custom fields
    custom_fields: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default='{}',
    )

    # Relationship to obligations
    obligations: Mapped[list["Obligation"]] = relationship(
        "Obligation",
        back_populates="clause",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_clauses_contract_type", "contract_id", "clause_type"),
        Index("ix_clauses_risk", "risk_level", "confidence_score"),
    )

    def __repr__(self) -> str:
        return f"<Clause {self.clause_type.value} (contract: {self.contract_id})>"
