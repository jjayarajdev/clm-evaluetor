"""Event model for detected contract events requiring action."""

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime, Enum, ForeignKey, Integer, String, Text, Boolean
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class EventType(str, enum.Enum):
    """Types of events that can trigger workflows."""

    sla_breach = "sla_breach"
    sla_warning = "sla_warning"
    milestone_approaching = "milestone_approaching"
    milestone_overdue = "milestone_overdue"
    renewal_approaching = "renewal_approaching"
    renewal_overdue = "renewal_overdue"
    obligation_due = "obligation_due"
    obligation_overdue = "obligation_overdue"
    contract_expiring = "contract_expiring"
    contract_expired = "contract_expired"
    benchmark_window = "benchmark_window"
    cola_adjustment = "cola_adjustment"
    custom = "custom"


class EventSeverity(str, enum.Enum):
    """Severity levels for events."""

    info = "info"
    warning = "warning"
    critical = "critical"


class EventStatus(str, enum.Enum):
    """Status of event processing."""

    pending = "pending"
    processing = "processing"
    awaiting_approval = "awaiting_approval"
    executing = "executing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class Event(Base, TimestampMixin):
    """A detected event that requires action.

    Events are created when the monitor service detects something
    actionable (SLA breach, upcoming deadline, etc.). Each event
    triggers a workflow that executes the appropriate actions.
    """

    __tablename__ = "events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Event identification
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)
    severity: Mapped[EventSeverity] = mapped_column(
        Enum(EventSeverity), default=EventSeverity.warning
    )

    # Related entities
    contract_id: Mapped[UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    obligation_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("obligations.id", ondelete="SET NULL"), nullable=True
    )
    sla_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("contract_slas.id", ondelete="SET NULL"), nullable=True
    )

    # Event details
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    details: Mapped[Optional[dict]] = mapped_column(JSONB)  # Additional context

    # Detection info
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    detected_by: Mapped[str] = mapped_column(
        String(100), default="monitor_service"
    )  # Which service detected it

    # Processing status
    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus), default=EventStatus.pending
    )
    workflow_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("workflow_definitions.id", ondelete="SET NULL"), nullable=True
    )

    # Completion tracking
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Prevent duplicate events
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    original_event_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    contract: Mapped["Contract"] = relationship("Contract", foreign_keys=[contract_id])
    action_executions: Mapped[list["ActionExecution"]] = relationship(
        "ActionExecution", back_populates="event", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Event {self.event_type.value}: {self.title[:50]}>"

    @property
    def is_actionable(self) -> bool:
        """Check if this event can still be acted upon."""
        return self.status in [EventStatus.pending, EventStatus.awaiting_approval]

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate how long the event took to process."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
