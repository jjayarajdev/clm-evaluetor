"""Contract Comment model for internal and external user comments."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ContractComment(Base):
    """Contract Comment model for discussions on contracts.

    Supports both internal users (User) and external users (ExternalUser).
    Comments can be threaded (parent/child), linked to specific clauses,
    and marked as internal-only (not visible to external users).
    """

    __tablename__ = "contract_comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Contract link
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Author - exactly one of these must be set
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    external_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("external_users.id"),
        nullable=True,
        index=True,
    )

    # Threading - parent comment for replies
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contract_comments.id"),
        nullable=True,
        index=True,
    )

    # Content
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Location reference (optional)
    clause_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clauses.id"),
        nullable=True,
        index=True,
    )
    section_reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Visibility - internal comments are only visible to internal users
    is_internal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Resolution tracking
    is_resolved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime,
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
        back_populates="comments",
        lazy="selectin",
    )
    user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[user_id],
        lazy="selectin",
    )
    external_user: Mapped["ExternalUser | None"] = relationship(
        "ExternalUser",
        back_populates="comments",
        lazy="selectin",
    )
    parent: Mapped["ContractComment | None"] = relationship(
        "ContractComment",
        remote_side="ContractComment.id",
        back_populates="replies",
        lazy="selectin",
    )
    replies: Mapped[list["ContractComment"]] = relationship(
        "ContractComment",
        back_populates="parent",
        lazy="selectin",
    )
    clause: Mapped["Clause | None"] = relationship(
        "Clause",
        lazy="selectin",
    )
    resolved_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[resolved_by_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        author = f"user={self.user_id}" if self.user_id else f"external={self.external_user_id}"
        return f"<ContractComment {author} contract={self.contract_id}>"

    @property
    def author_name(self) -> str:
        """Get the display name of the comment author."""
        if self.user:
            return self.user.full_name or self.user.username
        if self.external_user:
            return self.external_user.display_name
        return "Unknown"

    @property
    def author_email(self) -> str | None:
        """Get the email of the comment author."""
        if self.user:
            return self.user.email
        if self.external_user:
            return self.external_user.email
        return None

    @property
    def is_internal_author(self) -> bool:
        """Check if the author is an internal user."""
        return self.user_id is not None

    def resolve(self, resolved_by_id: uuid.UUID) -> None:
        """Mark this comment as resolved."""
        self.is_resolved = True
        self.resolved_by_id = resolved_by_id
        self.resolved_at = datetime.utcnow()

    def soft_delete(self) -> None:
        """Soft delete this comment."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
