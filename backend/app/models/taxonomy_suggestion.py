"""Taxonomy Suggestion model for AI-discovered taxonomy items.

When the AI processes a contract, it may discover clause types, risk categories,
contract types, or SLA metrics that aren't in the tenant's current industry profile.
These are stored as suggestions for the admin to approve, modify, or reject.

Approved items are automatically added to the config_overrides JSONB at the
appropriate level (BU if the contract belongs to a BU with its own profile,
otherwise tenant).
"""

import enum
import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class SuggestionStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    MODIFIED = "modified"  # approved with changes
    REJECTED = "rejected"


class TaxonomySuggestion(Base, UUIDMixin, TimestampMixin):
    """AI-discovered taxonomy item pending admin review.

    After contract processing, the system compares extracted items
    against the effective config (BU or tenant). New items become suggestions.
    """

    __tablename__ = "taxonomy_suggestions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Optional BU association — if set, approval writes to BU config_overrides
    business_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("business_units.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # What kind of taxonomy item: contract_types, clause_types, risk_categories, sla_metrics
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # The suggested code and label
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)

    # Additional details (severity, weight, description, unit, etc.)
    details: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    # Where this came from
    source_agent: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Admin review status
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SuggestionStatus.PENDING.value,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<TaxonomySuggestion {self.category}/{self.code} ({self.status})>"
