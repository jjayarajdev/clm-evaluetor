import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class AuditAction(str, enum.Enum):
    """Types of auditable actions."""

    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"

    # User management
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"

    # Contract operations
    CONTRACT_UPLOAD = "contract_upload"
    CONTRACT_PROCESS = "contract_process"
    CONTRACT_VIEW = "contract_view"
    CONTRACT_UPDATE = "contract_update"
    CONTRACT_DELETE = "contract_delete"
    CONTRACT_DOWNLOAD = "contract_download"

    # AI/Query operations
    QUERY_EXECUTE = "query_execute"
    AGENT_INVOKE = "agent_invoke"

    # Admin operations
    SETTINGS_UPDATE = "settings_update"


class AuditLog(Base, UUIDMixin, TimestampMixin):
    """Audit log model for tracking user actions."""

    __tablename__ = "audit_logs"

    # User who performed the action
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user: Mapped["User | None"] = relationship(
        "User",
        back_populates="audit_logs",
    )

    # Action details
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name='auditaction', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )

    # Resource affected
    resource_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Additional details as JSON
    details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Request metadata
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_audit_logs_user_action", "user_id", "action"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action.value} by user {self.user_id}>"
