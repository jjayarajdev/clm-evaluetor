"""External User model for counterparty portal access."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ExternalUser(Base):
    """External User model representing counterparty contacts.

    External users can be invited to view specific contracts they are
    party to, and can add comments. They don't have full user accounts
    but use token-based authentication.
    """

    __tablename__ = "external_users"

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

    # Organization association (optional - link to existing org)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )

    # Contact info
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    company_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    title: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Invitation tracking
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    invited_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Access tracking
    last_access_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    access_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Notes
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
        lazy="selectin",
    )
    organization: Mapped["Organization | None"] = relationship(
        "Organization",
        back_populates="external_users",
        lazy="selectin",
    )
    invited_by: Mapped["User | None"] = relationship(
        "User",
        lazy="selectin",
    )
    contract_shares: Mapped[list["ContractShare"]] = relationship(
        "ContractShare",
        back_populates="external_user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    comments: Mapped[list["ContractComment"]] = relationship(
        "ContractComment",
        back_populates="external_user",
        lazy="selectin",
    )
    access_tokens: Mapped[list["ExternalAccessToken"]] = relationship(
        "ExternalAccessToken",
        back_populates="external_user",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ExternalUser {self.email}>"

    def record_access(self) -> None:
        """Record an access to update tracking fields."""
        self.last_access_at = datetime.utcnow()
        self.access_count += 1

    @property
    def display_name(self) -> str:
        """Get the display name for this external user."""
        if self.full_name:
            return self.full_name
        return self.email.split("@")[0]
