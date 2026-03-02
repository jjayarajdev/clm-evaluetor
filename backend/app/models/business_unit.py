"""Business Unit model for organizational hierarchy within tenants."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BusinessUnit(Base):
    """Business Unit model representing departments/divisions within a tenant.

    Supports hierarchical structure with parent-child relationships.
    Users and contracts can be assigned to business units for access control.
    """

    __tablename__ = "business_units"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Tenant association
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )

    # Basic info
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Hierarchy - parent BU for nested structure
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("business_units.id"),
        nullable=True,
        index=True,
    )

    # BU Head - user who manages this BU
    head_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="business_units",
        lazy="selectin",
    )
    parent: Mapped["BusinessUnit | None"] = relationship(
        "BusinessUnit",
        remote_side="BusinessUnit.id",
        back_populates="children",
        lazy="selectin",
    )
    children: Mapped[list["BusinessUnit"]] = relationship(
        "BusinessUnit",
        back_populates="parent",
        lazy="selectin",
    )
    head_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[head_user_id],
        lazy="selectin",
    )
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="business_unit",
        foreign_keys="User.business_unit_id",
        lazy="selectin",
    )
    contracts: Mapped[list["Contract"]] = relationship(
        "Contract",
        back_populates="business_unit",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<BusinessUnit {self.code}: {self.name}>"

    @property
    def full_path(self) -> str:
        """Get the full hierarchical path of this BU."""
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name

    def get_all_child_ids(self) -> set[uuid.UUID]:
        """Recursively get all child BU IDs."""
        child_ids = set()
        for child in self.children:
            child_ids.add(child.id)
            child_ids.update(child.get_all_child_ids())
        return child_ids
