"""Usage events — first-party billing/consumption meter.

One row per metered quantity (tokens, AI actions, pages, documents). Raw events
are the audit trail for the pricing meters in docs/PRICING_AND_PACKAGING.md;
dashboards should aggregate over them (rollups can come later). Written only by
app.services.usage_metering — never insert directly from product code.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import UUIDMixin


class UsageMetric:
    """Metric names (plain strings, not a PG enum, so new meters need no migration)."""

    TOKENS_PROMPT = "tokens_prompt"
    TOKENS_COMPLETION = "tokens_completion"
    TOKENS_EMBEDDING = "tokens_embedding"
    AI_ACTIONS = "ai_actions"  # one per LLM call — the Managed-AI overage unit
    PAGES_PROCESSED = "pages_processed"
    DOCUMENTS_INGESTED = "documents_ingested"


class UsageEvent(Base, UUIDMixin):
    __tablename__ = "usage_events"
    __table_args__ = (
        Index("ix_usage_events_tenant_occurred", "tenant_id", "occurred_at"),
    )

    # Nullable: calls made without tenant context (super admin, platform jobs)
    # still get metered, attributed to the platform itself.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    metric: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # LLM model that produced the tokens — needed to price Managed-AI usage.
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Loose reference to the triggering object (e.g. "contract", <contract id>).
    # Not a FK: usage must survive deletion of the referenced object.
    ref_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
