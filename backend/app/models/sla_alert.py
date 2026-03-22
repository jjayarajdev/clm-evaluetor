"""SLA Alert model for tracking breach notifications and compliance alerts.

Stores alerts triggered by the SLA comparison engine when breaches are detected.
Supports both in-app dashboard alerts and external notifications.
"""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin
from app.models.sla import BreachSeverity


class AlertPriority(str, enum.Enum):
    """Priority level for alerts."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, enum.Enum):
    """Status of an alert."""

    ACTIVE = "active"  # New, unacknowledged
    ACKNOWLEDGED = "acknowledged"  # Seen by user
    IN_PROGRESS = "in_progress"  # Being worked on
    RESOLVED = "resolved"  # Issue addressed
    DISMISSED = "dismissed"  # Marked as not actionable
    ESCALATED = "escalated"  # Sent to higher authority


class AlertCategory(str, enum.Enum):
    """Category of alert."""

    SLA_BREACH = "sla_breach"  # Performance below minimum
    SLA_WARNING = "sla_warning"  # Below target but above minimum
    SLA_IMPROVEMENT = "sla_improvement"  # Earnback opportunity
    MILESTONE_DELAYED = "milestone_delayed"  # Project milestone late
    MILESTONE_AT_RISK = "milestone_at_risk"  # Milestone may be late
    FX_THRESHOLD = "fx_threshold"  # COLA adjustment needed
    SERVICE_CREDIT = "service_credit"  # Credit due to customer
    CONTRACT_EXPIRY = "contract_expiry"  # Upcoming expiration
    OBLIGATION_DUE = "obligation_due"  # Obligation deadline


class SLAAlert(Base, TimestampMixin):
    """Alert instance triggered by monitoring systems.

    Each alert represents a specific issue that needs attention.
    Alerts can be acknowledged, escalated, or resolved.
    """

    __tablename__ = "sla_alerts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Related entities
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sla_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("contract_slas.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    performance_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("sla_performances.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Alert classification
    category: Mapped[AlertCategory] = mapped_column(
        Enum(AlertCategory, name='alertcategory', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    priority: Mapped[AlertPriority] = mapped_column(
        Enum(AlertPriority, name='alertpriority', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name='alertstatus', create_type=False, values_callable=lambda x: [e.value for e in x]),
        default=AlertStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    # Alert content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # SLA-specific data
    sla_reference: Mapped[Optional[str]] = mapped_column(String(50))
    sla_name: Mapped[Optional[str]] = mapped_column(String(200))
    target_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    minimum_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    actual_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    deviation_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    breach_severity: Mapped[Optional[BreachSeverity]] = mapped_column(
        Enum(BreachSeverity, name='breachseverity', create_type=False, values_callable=lambda x: [e.value for e in x])
    )

    # Financial impact
    has_financial_impact: Mapped[bool] = mapped_column(Boolean, default=False)
    estimated_credit: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    at_risk_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))

    # Measurement period
    measurement_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    measurement_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Status tracking
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Escalation
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    escalated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    escalated_to: Mapped[Optional[str]] = mapped_column(String(255))  # Email/name

    # Notification tracking
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    notification_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    notification_log_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("notification_logs.id", ondelete="SET NULL"),
    )

    # Source system info
    source_system: Mapped[Optional[str]] = mapped_column(String(100))

    # Additional data
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    contract: Mapped["Contract"] = relationship("Contract", back_populates="sla_alerts")
    sla: Mapped[Optional["ContractSLA"]] = relationship("ContractSLA")
    notification_log: Mapped[Optional["NotificationLog"]] = relationship("NotificationLog")

    def __repr__(self) -> str:
        return f"<SLAAlert {self.category.value} [{self.priority.value}] - {self.status.value}>"

    @property
    def is_actionable(self) -> bool:
        """Check if alert requires action."""
        return self.status in [AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED, AlertStatus.IN_PROGRESS]

    @property
    def days_open(self) -> int:
        """Number of days the alert has been open."""
        if self.resolved_at:
            return (self.resolved_at - self.detected_at).days
        return (datetime.now(timezone.utc) - self.detected_at).days


# Map breach severity to alert priority
BREACH_SEVERITY_TO_PRIORITY = {
    BreachSeverity.MINOR: AlertPriority.LOW,
    BreachSeverity.MODERATE: AlertPriority.MEDIUM,
    BreachSeverity.MAJOR: AlertPriority.HIGH,
    BreachSeverity.CRITICAL: AlertPriority.CRITICAL,
}
