import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class AlertType(str, enum.Enum):
    """Types of alerts that can be configured."""

    CONTRACT_EXPIRATION = "contract_expiration"
    RENEWAL_NOTICE = "renewal_notice"
    OBLIGATION_DUE = "obligation_due"
    HIGH_RISK_DETECTED = "high_risk_detected"
    PROCESSING_COMPLETE = "processing_complete"
    PROCESSING_FAILED = "processing_failed"


class AlertConfig(Base, UUIDMixin, TimestampMixin):
    """Alert configuration model for user notification preferences."""

    __tablename__ = "alert_configs"

    # User who owns this config
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="alert_configs",
    )

    # Alert type
    alert_type: Mapped[AlertType] = mapped_column(
        Enum(AlertType, name='alerttype', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )

    # Configuration
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    threshold_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Notification channel (for future use)
    notification_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    def __repr__(self) -> str:
        status = "enabled" if self.is_enabled else "disabled"
        return f"<AlertConfig {self.alert_type.value} ({status})>"
