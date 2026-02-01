import enum
import uuid

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Role(str, enum.Enum):
    """User roles for RBAC."""

    ADMIN = "admin"
    LEGAL = "legal"
    PROCUREMENT = "procurement"
    VIEWER = "viewer"


class User(Base, UUIDMixin, TimestampMixin):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[Role] = mapped_column(
        Enum(Role, name='role', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=Role.LEGAL,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Relationships
    contracts: Mapped[list["Contract"]] = relationship(
        "Contract",
        back_populates="uploaded_by_user",
        lazy="selectin",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        lazy="selectin",
    )
    alert_configs: Mapped[list["AlertConfig"]] = relationship(
        "AlertConfig",
        back_populates="user",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role.value})>"
