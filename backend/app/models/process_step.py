"""Contract process step model for extracted procedural clauses."""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class StepType(str, enum.Enum):
    """Type of process step."""

    SUBMISSION = "submission"
    REVIEW = "review"
    TESTING = "testing"
    APPROVAL = "approval"
    DELIVERY = "delivery"
    CERTIFICATION = "certification"
    PAYMENT = "payment"
    REPORTING = "reporting"
    RENEWAL = "renewal"
    OTHER = "other"


class StepStatus(str, enum.Enum):
    """Status of a process step."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class ContractProcessStep(Base, UUIDMixin, TimestampMixin):
    """
    Process step extracted from a contract's procedural clauses.

    Examples:
    - Product sampling step
    - Testing phase
    - Certification approval
    - Renewal process
    """

    __tablename__ = "contract_process_steps"

    # Relationship to contract
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contract: Mapped["Contract"] = relationship(
        "Contract",
        back_populates="process_steps",
    )

    # Optional link to source clause
    source_clause_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clauses.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Step identification
    step_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    step_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    step_type: Mapped[StepType] = mapped_column(
        Enum(StepType, name='steptype', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=StepType.OTHER,
    )

    # Step details
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    responsible_party: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Timing
    duration_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    sla_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Dependencies (step names or IDs)
    dependencies: Mapped[str | None] = mapped_column(
        Text,  # Comma-separated list
        nullable=True,
    )

    # Deliverables
    deliverables: Mapped[str | None] = mapped_column(
        Text,  # Comma-separated list
        nullable=True,
    )

    # Status tracking
    status: Mapped[StepStatus] = mapped_column(
        Enum(StepStatus, name='stepstatus', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=StepStatus.PENDING,
    )

    # Source text
    source_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Section reference
    section_reference: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_process_steps_contract", "contract_id"),
        Index("ix_process_steps_type", "step_type"),
        Index("ix_process_steps_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<ProcessStep {self.step_number}: {self.step_name} (contract: {self.contract_id})>"
