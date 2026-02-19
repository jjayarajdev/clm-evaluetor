import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class ObligationType(str, enum.Enum):
    """Types of contractual obligations."""

    PAYMENT = "payment"
    DELIVERY = "delivery"
    REPORTING = "reporting"
    COMPLIANCE = "compliance"
    NOTIFICATION = "notification"
    PERFORMANCE = "performance"
    OTHER = "other"


class ObligationOwner(str, enum.Enum):
    """Who is responsible for the obligation."""

    PROVIDER = "provider"
    CLIENT = "client"
    MUTUAL = "mutual"
    THIRD_PARTY = "third_party"
    UNSPECIFIED = "unspecified"


class ObligationCategory(str, enum.Enum):
    """Detailed categories of obligations."""

    # Service Related
    SERVICE_PROVISION = "service_provision"
    SERVICE_LEVELS = "service_levels"
    DELIVERY = "delivery"
    PERFORMANCE = "performance"

    # Financial
    PAYMENT = "payment"
    INVOICING = "invoicing"
    PRICING = "pricing"

    # Data & Information
    DATA_PROTECTION = "data_protection"
    DATA_HANDLING = "data_handling"
    REPORTING = "reporting"
    INFORMATION_PROVISION = "information_provision"
    RECORD_KEEPING = "record_keeping"

    # Compliance & Legal
    REGULATORY_COMPLIANCE = "regulatory_compliance"
    AUDIT = "audit"
    CERTIFICATION = "certification"
    INSURANCE = "insurance"

    # Confidentiality & IP
    CONFIDENTIALITY = "confidentiality"
    IP_PROTECTION = "ip_protection"

    # Communication
    NOTIFICATION = "notification"
    APPROVAL = "approval"
    COOPERATION = "cooperation"

    # Operational
    STAFFING = "staffing"
    TRAINING = "training"
    DOCUMENTATION = "documentation"
    MAINTENANCE = "maintenance"
    SUPPORT = "support"
    TESTING = "testing"
    QUALITY_ASSURANCE = "quality_assurance"

    # Termination & Transition
    TRANSITION = "transition"
    EXIT_MANAGEMENT = "exit_management"
    RETURN_OF_MATERIALS = "return_of_materials"

    # Other
    BRANDING = "branding"
    MARKETING = "marketing"
    COLLABORATION = "collaboration"
    OTHER = "other"


class ObligationFrequency(str, enum.Enum):
    """How often the obligation recurs."""

    ONE_TIME = "one_time"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    ONGOING = "ongoing"
    TRIGGERED = "triggered"  # Occurs when a condition is met
    AS_NEEDED = "as_needed"
    CUSTOM = "custom"


class RAGStatus(str, enum.Enum):
    """Red/Amber/Green status for compliance tracking."""

    GREEN = "green"  # On track, no issues
    AMBER = "amber"  # At risk, attention needed
    RED = "red"  # Overdue or breached
    NOT_ASSESSED = "not_assessed"


class DeadlineType(str, enum.Enum):
    """Types of obligation deadlines."""

    FIXED_DATE = "fixed_date"
    RECURRING = "recurring"
    RELATIVE = "relative"
    ONGOING = "ongoing"


class ObligationStatus(str, enum.Enum):
    """Status of an obligation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    WAIVED = "waived"


class Obligation(Base, UUIDMixin, TimestampMixin):
    """Obligation model representing a contractual obligation."""

    __tablename__ = "obligations"

    # Relationship to contract
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contract: Mapped["Contract"] = relationship(
        "Contract",
        back_populates="obligations",
    )

    # Relationship to clause (optional - obligation may not be from a specific clause)
    clause_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clauses.id", ondelete="SET NULL"),
        nullable=True,
    )
    clause: Mapped["Clause | None"] = relationship(
        "Clause",
        back_populates="obligations",
    )

    # Obligation details
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    obligation_type: Mapped[ObligationType] = mapped_column(
        Enum(ObligationType, name='obligationtype', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ObligationType.OTHER,
        index=True,
    )

    # Parties
    obligated_party: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    beneficiary_party: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Deadline information
    deadline_type: Mapped[DeadlineType | None] = mapped_column(
        Enum(DeadlineType, name='deadlinetype', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    deadline: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )
    recurrence_pattern: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    relative_deadline_text: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Status tracking
    status: Mapped[ObligationStatus] = mapped_column(
        Enum(ObligationStatus, name='obligationstatus', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ObligationStatus.PENDING,
        index=True,
    )

    # ===== NEW CANONICAL FIELDS =====

    # Owner - who is responsible
    owner_type: Mapped[ObligationOwner | None] = mapped_column(
        Enum(ObligationOwner, name='obligationowner', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
        default=ObligationOwner.UNSPECIFIED,
        index=True,
    )

    # Detailed category
    category: Mapped[ObligationCategory | None] = mapped_column(
        Enum(ObligationCategory, name='obligationcategory', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
        index=True,
    )

    # Frequency
    frequency: Mapped[ObligationFrequency | None] = mapped_column(
        Enum(ObligationFrequency, name='obligationfrequency', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )
    frequency_custom: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # RAG Status for compliance tracking
    rag_status: Mapped[RAGStatus | None] = mapped_column(
        Enum(RAGStatus, name='ragstatus', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
        default=RAGStatus.NOT_ASSESSED,
        index=True,
    )

    # Compliance tracking
    last_compliance_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_compliance_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_compliance_due: Mapped[date | None] = mapped_column(Date, nullable=True)
    compliance_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    compliance_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)  # File paths or descriptions

    # Priority and criticality
    is_critical: Mapped[bool | None] = mapped_column(Boolean, default=False)
    priority: Mapped[int | None] = mapped_column()  # 1=highest, 5=lowest

    # Section reference from contract
    section_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ===== END NEW FIELDS =====

    # Consequences
    consequence_of_breach: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Triggering conditions
    trigger_condition: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Source text from contract
    source_text: Mapped[str | None] = mapped_column(
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

    # Indexes for common queries
    __table_args__ = (
        Index("ix_obligations_contract_status", "contract_id", "status"),
        Index("ix_obligations_deadline_status", "deadline", "status"),
        Index("ix_obligations_owner_category", "owner_type", "category"),
        Index("ix_obligations_rag_status", "rag_status"),
        Index("ix_obligations_next_compliance", "next_compliance_due"),
    )

    def __repr__(self) -> str:
        return f"<Obligation {self.obligation_type.value} ({self.status.value})>"
