"""Contract Key Date model for tracking important dates and deadlines."""

import enum
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class DateEventType(str, enum.Enum):
    """Type of date event."""

    CONTRACT_START = "contract_start"
    CONTRACT_EXPIRATION = "contract_expiration"
    RENEWAL_NOTICE_DEADLINE = "renewal_notice_deadline"
    TERMINATION_NOTICE_DEADLINE = "termination_notice_deadline"
    PAYMENT_DUE = "payment_due"
    DELIVERY_DUE = "delivery_due"
    MILESTONE = "milestone"
    REVIEW_DATE = "review_date"
    RENEWAL_DATE = "renewal_date"
    OBLIGATION_DEADLINE = "obligation_deadline"
    CUSTOM = "custom"


class ContractKeyDate(Base, UUIDMixin, TimestampMixin):
    """Key date or deadline associated with a contract."""

    __tablename__ = "contract_key_dates"

    # Relationship to contract
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Event details
    event_type: Mapped[DateEventType] = mapped_column(
        Enum(DateEventType, name='dateeventtype', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    event_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # The key date
    event_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    # Notice/action deadline (if different from event_date)
    notice_required_by: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    # Action information
    action_required: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    responsible_party: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Recurrence
    is_recurring: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    recurrence_pattern: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Status tracking
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    completed_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    # Alert configuration
    alert_days_before: Mapped[int | None] = mapped_column(
        nullable=True,
        default=30,
    )
    alert_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Source reference
    section_reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Relationship back to contract
    contract: Mapped["Contract"] = relationship(
        "Contract",
        back_populates="key_dates",
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_key_dates_contract_event", "contract_id", "event_type"),
        Index("ix_key_dates_upcoming", "event_date", "is_completed"),
        Index("ix_key_dates_notice_deadline", "notice_required_by", "is_completed"),
    )

    def __repr__(self) -> str:
        return f"<ContractKeyDate {self.event_type.value}: {self.event_date}>"

    @property
    def days_until_event(self) -> int | None:
        """Calculate days until the event date."""
        if not self.event_date:
            return None
        from datetime import date as date_type
        return (self.event_date - date_type.today()).days

    @property
    def days_until_notice(self) -> int | None:
        """Calculate days until notice is required."""
        if not self.notice_required_by:
            return None
        from datetime import date as date_type
        return (self.notice_required_by - date_type.today()).days

    @property
    def is_overdue(self) -> bool:
        """Check if this date has passed without completion."""
        if self.is_completed:
            return False
        days = self.days_until_event
        return days is not None and days < 0
