"""Notification models for email templates and logs."""

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin
from app.models.event import EventType


class NotificationChannel(str, enum.Enum):
    """Channels for sending notifications."""

    email = "email"
    slack = "slack"
    teams = "teams"
    webhook = "webhook"


class NotificationStatus(str, enum.Enum):
    """Status of a sent notification."""

    pending = "pending"
    sent = "sent"
    delivered = "delivered"
    failed = "failed"
    bounced = "bounced"


class RecipientType(str, enum.Enum):
    """Types of recipients for notifications."""

    contract_owner = "contract_owner"
    vendor_contact = "vendor_contact"
    approver = "approver"
    escalation_contact = "escalation_contact"
    external_user = "external_user"
    custom = "custom"


class NotificationTemplate(Base, TimestampMixin):
    """Email/notification templates.

    Templates use Jinja2 syntax for variable substitution.
    Variables available depend on the event type.
    """

    __tablename__ = "notification_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Template identification
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    event_type: Mapped[Optional[EventType]] = mapped_column(Enum(EventType))
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel), default=NotificationChannel.email
    )

    # Template content
    subject_template: Mapped[str] = mapped_column(String(500), nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    # Example subject: "SLA Breach Alert: {{ contract_name }}"
    # Example body: "Dear {{ recipient_name }},\n\n{{ sla_name }} has breached..."

    # HTML support (for email)
    is_html: Mapped[bool] = mapped_column(Boolean, default=True)
    html_template: Mapped[Optional[str]] = mapped_column(Text)

    # Default recipients
    default_recipient_type: Mapped[Optional[RecipientType]] = mapped_column(
        Enum(RecipientType)
    )

    # Template status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Available variables documentation
    available_variables: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Example: {"contract_name": "string", "sla_value": "number", ...}

    def __repr__(self) -> str:
        return f"<NotificationTemplate {self.name}>"


class NotificationLog(Base, TimestampMixin):
    """Log of sent notifications.

    Every notification sent is logged for tracking and debugging.
    """

    __tablename__ = "notification_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Related entities
    template_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("notification_templates.id", ondelete="SET NULL"), nullable=True
    )
    event_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), nullable=True
    )
    action_execution_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("action_executions.id", ondelete="SET NULL"), nullable=True
    )

    # Notification details
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel), nullable=False
    )
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_name: Mapped[Optional[str]] = mapped_column(String(255))
    recipient_type: Mapped[Optional[RecipientType]] = mapped_column(
        Enum(RecipientType)
    )

    # Content (as sent)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    variables_used: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Status tracking
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus), default=NotificationStatus.pending
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Error tracking
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # External tracking
    external_id: Mapped[Optional[str]] = mapped_column(String(200))
    # Example: SendGrid message ID

    # Relationships
    template: Mapped[Optional["NotificationTemplate"]] = relationship(
        "NotificationTemplate"
    )
    event: Mapped[Optional["Event"]] = relationship("Event")

    def __repr__(self) -> str:
        return f"<NotificationLog {self.recipient_email} [{self.status.value}]>"

    @property
    def is_successful(self) -> bool:
        """Check if notification was successfully sent."""
        return self.status in [NotificationStatus.sent, NotificationStatus.delivered]
