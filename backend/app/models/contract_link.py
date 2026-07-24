"""Contract links model - parent-child relationships between contracts."""

import enum
import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, Date, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.contract import Contract


class LinkType(str, enum.Enum):
    """Types of contract relationships."""

    # Hierarchical
    SOW = "sow"  # Statement of Work under MSA
    WORK_ORDER = "work_order"  # Work order under MSA/SOW
    SERVICE_ORDER = "service_order"  # Service order under MSA
    PURCHASE_ORDER = "purchase_order"  # PO under MSA

    # Amendments & Changes
    AMENDMENT = "amendment"  # Formal amendment
    ADDENDUM = "addendum"  # Additional terms
    CHANGE_ORDER = "change_order"  # Change to scope/terms
    MODIFICATION = "modification"  # General modification
    RENEWAL = "renewal"  # Renewal agreement

    # Attachments
    EXHIBIT = "exhibit"  # Attached exhibit
    SCHEDULE = "schedule"  # Attached schedule
    APPENDIX = "appendix"  # Attached appendix
    ATTACHMENT = "attachment"  # General attachment

    # Related
    SUPERSEDES = "supersedes"  # This contract replaces another
    REFERENCES = "references"  # References another contract
    RELATED = "related"  # Generally related


class ContractLink(Base, UUIDMixin, TimestampMixin):
    """Links between contracts (MSA→SOW, Contract→Amendment, etc.)."""

    __tablename__ = "contract_links"

    # The parent contract (e.g., MSA)
    parent_contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The child contract (e.g., SOW)
    child_contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Type of relationship
    # Use PostgreSQL ENUM directly to ensure lowercase values
    from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
    link_type: Mapped[str] = mapped_column(
        PG_ENUM(
            'sow', 'work_order', 'service_order', 'purchase_order',
            'amendment', 'addendum', 'change_order', 'modification',
            'renewal', 'exhibit', 'schedule', 'appendix', 'attachment',
            'supersedes', 'references', 'related',
            name='linktype', create_type=False
        ),
        nullable=False,
        default='related',
    )

    # Optional metadata
    link_description: Mapped[str | None] = mapped_column(String(500))
    effective_date: Mapped[date | None] = mapped_column(Date)
    reference_number: Mapped[str | None] = mapped_column(String(100))  # e.g., "Amendment #3"
    sequence_number: Mapped[int | None] = mapped_column()  # For ordering (1st SOW, 2nd SOW)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Which rule created this link (None = a human did). Used by the link
    # referee: higher-evidence rules may replace lower ones, never humans.
    created_by_rule: Mapped[str | None] = mapped_column(String(50))

    # Notes
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    parent_contract: Mapped["Contract"] = relationship(
        foreign_keys=[parent_contract_id],
        back_populates="child_links",
    )
    child_contract: Mapped["Contract"] = relationship(
        foreign_keys=[child_contract_id],
        back_populates="parent_links",
    )

    # Ensure no duplicate links
    __table_args__ = (
        UniqueConstraint(
            "parent_contract_id",
            "child_contract_id",
            "link_type",
            name="uq_contract_link",
        ),
    )

    def __repr__(self) -> str:
        return f"<ContractLink {self.link_type.value}: {self.parent_contract_id} → {self.child_contract_id}>"
