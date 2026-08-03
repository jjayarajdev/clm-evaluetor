"""DB-backed RBAC: role definitions and their permission grants.

Written only by the super-admin editor (routers/role_permissions.py) and the
one-time startup seed (core/permissions.py). Consumed by the cached matrix in
core/permissions.py — never query these tables directly from endpoints.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RoleDef(Base):
    """One of the six platform roles (metadata; the assignable set is still
    bounded by the users.role PG enum — adding a role needs an enum migration)."""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class RolePermission(Base):
    """A single permission grant for a role (platform-wide)."""

    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_name", "permission", name="uq_role_permission"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    role_name: Mapped[str] = mapped_column(
        ForeignKey("roles.name", ondelete="CASCADE"), nullable=False, index=True
    )
    permission: Mapped[str] = mapped_column(String(100), nullable=False)
