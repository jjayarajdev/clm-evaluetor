import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Role(str, enum.Enum):
    """User roles for RBAC."""

    SUPER_ADMIN = "super_admin"  # Can see all tenants
    ADMIN = "admin"  # Tenant admin
    BU_HEAD = "bu_head"  # Business Unit head - sees all contracts in their BU
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
    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
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

    # Tenant association (nullable for super_admin who can access all)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=True,
        index=True,
    )

    # Business Unit association (nullable for admins who can access all BUs)
    business_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("business_units.id"),
        nullable=True,
        index=True,
    )

    # Relationships
    tenant: Mapped["Tenant | None"] = relationship(
        "Tenant",
        back_populates="users",
        lazy="selectin",  # Eager load tenant with user
    )
    business_unit: Mapped["BusinessUnit | None"] = relationship(
        "BusinessUnit",
        back_populates="users",
        foreign_keys=[business_unit_id],
        lazy="selectin",
    )
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

    @property
    def is_super_admin(self) -> bool:
        """Check if user is a super admin."""
        return self.role == Role.SUPER_ADMIN

    @property
    def is_tenant_admin(self) -> bool:
        """Check if user is a tenant admin."""
        return self.role == Role.ADMIN

    @property
    def is_bu_head(self) -> bool:
        """Check if user is a business unit head."""
        return self.role == Role.BU_HEAD

    def __repr__(self) -> str:
        tenant_info = f" tenant={self.tenant_id}" if self.tenant_id else " (super)"
        return f"<User {self.username} ({self.role.value}){tenant_info}>"
