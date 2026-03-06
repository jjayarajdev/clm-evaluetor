"""Notification Rule model for configurable alert settings."""

import enum
import uuid
from datetime import datetime, time
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class RuleEventType(str, enum.Enum):
    """Types of events that can trigger notifications."""

    CONTRACT_EXPIRATION = "contract_expiration"
    NOTICE_DEADLINE = "notice_deadline"
    OBLIGATION_DUE = "obligation_due"
    SLA_BREACH = "sla_breach"
    SLA_WARNING = "sla_warning"
    RENEWAL_REMINDER = "renewal_reminder"
    KEY_DATE = "key_date"
    COMPLIANCE_OVERDUE = "compliance_overdue"


class NotificationChannel(str, enum.Enum):
    """Channels for sending notifications."""

    EMAIL = "email"
    IN_APP = "in_app"
    SLACK = "slack"
    WEBHOOK = "webhook"


class NotificationRule(Base, UUIDMixin, TimestampMixin):
    """Configurable notification rule."""

    __tablename__ = "notification_rules"

    # Tenant scoping
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Rule metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Event trigger
    event_type: Mapped[RuleEventType] = mapped_column(
        Enum(RuleEventType, name='ruleeventtype', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )

    # Timing configuration
    days_before: Mapped[int] = mapped_column(
        Integer,
        default=7,
        nullable=False,
        doc="Days before event to send notification"
    )
    repeat_interval_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="Days between repeat notifications (null = no repeat)"
    )
    max_repeats: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
        doc="Maximum number of repeat notifications"
    )

    # Delivery settings
    channels: Mapped[list] = mapped_column(
        JSON,
        default=["email"],
        nullable=False,
        doc="List of notification channels"
    )

    # Recipients
    notify_contract_owner: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notify_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    additional_recipients: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="List of additional email addresses"
    )

    # Filters
    contract_types: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="Filter by contract types (null = all)"
    )
    min_contract_value: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        doc="Minimum contract value to trigger"
    )
    risk_levels: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        doc="Filter by risk levels (null = all)"
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        default="normal",
        nullable=False,
        doc="Notification priority: low, normal, high, critical"
    )

    # Business hours restriction
    respect_business_hours: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    business_hours_start: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    business_hours_end: Mapped[Optional[time]] = mapped_column(Time, nullable=True)

    # Template override
    email_template: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Tracking
    last_triggered: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    trigger_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationship to tenant
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="notification_rules")

    def __repr__(self) -> str:
        return f"<NotificationRule {self.name}: {self.event_type.value}>"

    @property
    def channels_list(self) -> list[str]:
        """Get channels as typed list."""
        return self.channels if isinstance(self.channels, list) else ["email"]

    @property
    def recipients_list(self) -> list[str]:
        """Get additional recipients as typed list."""
        return self.additional_recipients if isinstance(self.additional_recipients, list) else []
