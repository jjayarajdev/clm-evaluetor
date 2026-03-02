"""Contract Share model for external user access to contracts."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ContractShare(Base):
    """Contract Share model linking external users to specific contracts.

    Manages access permissions and tracks usage for shared contracts.
    """

    __tablename__ = "contract_shares"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Links
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("external_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Who shared it
    shared_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    # Permissions
    can_download: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    can_comment: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Expiration (optional)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Invitation message
    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Access tracking
    access_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_access_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Revocation
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    revoked_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
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
    contract: Mapped["Contract"] = relationship(
        "Contract",
        back_populates="shares",
        lazy="selectin",
    )
    external_user: Mapped["ExternalUser"] = relationship(
        "ExternalUser",
        back_populates="contract_shares",
        lazy="selectin",
    )
    shared_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[shared_by_id],
        lazy="selectin",
    )
    revoked_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[revoked_by_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ContractShare contract={self.contract_id} user={self.external_user_id}>"

    @property
    def is_active(self) -> bool:
        """Check if this share is currently active."""
        if self.is_revoked:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True

    def record_access(self) -> None:
        """Record an access to this share."""
        self.access_count += 1
        self.last_access_at = datetime.utcnow()

    def revoke(self, revoked_by_id: uuid.UUID) -> None:
        """Revoke this share."""
        self.is_revoked = True
        self.revoked_at = datetime.utcnow()
        self.revoked_by_id = revoked_by_id
