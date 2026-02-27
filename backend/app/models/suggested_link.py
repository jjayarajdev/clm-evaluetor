"""Suggested contract links model - AI-detected relationship suggestions."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, String, Text, Float, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin, TenantMixin
from app.models.contract_link import LinkType

if TYPE_CHECKING:
    from app.models.contract import Contract
    from app.models.user import User


class SuggestionStatus(str, enum.Enum):
    """Status of a suggested contract link."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class SuggestedContractLink(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """AI-detected suggestions for contract relationships.

    When contracts are uploaded and processed, the system automatically
    detects potential relationships (MSA→SOW, Contract→Amendment, etc.)
    and stores them here for user review and approval.
    """

    __tablename__ = "suggested_contract_links"

    # Source contract (newly uploaded)
    source_contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Target contract (suggested parent/related)
    target_contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Suggested relationship details
    # Using String(50) to match migration, but still typed as LinkType for validation
    suggested_link_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="related",
    )

    # Direction of the suggested relationship
    # "source_is_child" = source is child of target (e.g., SOW under MSA)
    # "source_is_parent" = source is parent of target (e.g., MSA with existing SOWs)
    suggested_direction: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="source_is_child",
    )

    # Confidence score (0.0 to 1.0)
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    # AI-generated explanation of why this link was suggested
    reasoning: Mapped[str | None] = mapped_column(Text)

    # Detailed matching signals (JSON)
    # e.g., {"counterparty_match": 0.30, "type_hierarchy": 0.25, ...}
    matching_signals: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Review status
    # Using the PostgreSQL enum created in migration
    from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
    status: Mapped[str] = mapped_column(
        PG_ENUM('pending', 'approved', 'rejected', 'expired', name='suggestionstatus', create_type=False),
        nullable=False,
        default='pending',
        index=True,
    )

    # Review details
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # If approved, the created ContractLink ID
    created_link_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contract_links.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Batch ID for grouping suggestions from same upload batch
    batch_id: Mapped[str | None] = mapped_column(String(100), index=True)

    # Relationships
    source_contract: Mapped["Contract"] = relationship(
        foreign_keys=[source_contract_id],
    )
    target_contract: Mapped["Contract"] = relationship(
        foreign_keys=[target_contract_id],
    )
    reviewer: Mapped["User | None"] = relationship(
        foreign_keys=[reviewed_by],
    )

    def __repr__(self) -> str:
        return (
            f"<SuggestedContractLink {self.suggested_link_type.value}: "
            f"{self.source_contract_id} → {self.target_contract_id} "
            f"({self.confidence_score:.0%} confidence, {self.status.value})>"
        )

    @property
    def is_high_confidence(self) -> bool:
        """Check if suggestion has high confidence (>80%)."""
        return self.confidence_score >= 0.8

    @property
    def is_pending(self) -> bool:
        """Check if suggestion is still pending review."""
        return self.status == SuggestionStatus.PENDING
