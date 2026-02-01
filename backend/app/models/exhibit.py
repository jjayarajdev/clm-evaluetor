"""Contract exhibit/schedule model for attachments and fee tables."""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class ExhibitType(str, enum.Enum):
    """Type of exhibit/schedule."""

    SCHEDULE = "schedule"
    EXHIBIT = "exhibit"
    APPENDIX = "appendix"
    ANNEXURE = "annexure"
    ATTACHMENT = "attachment"
    PRICING = "pricing"
    SOW = "sow"  # Statement of Work
    OTHER = "other"


class ContractExhibit(Base, UUIDMixin, TimestampMixin):
    """
    Exhibit or schedule attached to a contract.

    Contains:
    - Exhibit identifier (A, B, 1, 2, etc.)
    - Title and description
    - Fee table entries if applicable
    """

    __tablename__ = "contract_exhibits"

    # Relationship to contract
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contract: Mapped["Contract"] = relationship(
        "Contract",
        back_populates="exhibits",
    )

    # Optional link to source clause
    source_clause_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clauses.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Exhibit identification
    exhibit_identifier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # e.g., "A", "B", "1", "Schedule 1"

    exhibit_type: Mapped[ExhibitType] = mapped_column(
        Enum(ExhibitType, name='exhibittype', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ExhibitType.EXHIBIT,
    )

    title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Page reference
    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Source text
    source_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    __table_args__ = (
        Index("ix_exhibits_contract", "contract_id"),
        Index("ix_exhibits_type", "exhibit_type"),
    )

    def __repr__(self) -> str:
        return f"<ContractExhibit {self.exhibit_identifier}: {self.title or 'Untitled'}>"


class ExhibitFeeItem(Base, UUIDMixin, TimestampMixin):
    """
    Fee item extracted from an exhibit/schedule pricing table.
    """

    __tablename__ = "exhibit_fee_items"

    # Relationship to exhibit
    exhibit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contract_exhibits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exhibit: Mapped["ContractExhibit"] = relationship(
        "ContractExhibit",
        backref="fee_items",
    )

    # Fee item details
    item_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    item_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    quantity: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    unit_price: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    total_price: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )

    currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
        default="USD",
    )

    # Item ordering
    item_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    __table_args__ = (
        Index("ix_fee_items_exhibit", "exhibit_id"),
    )

    def __repr__(self) -> str:
        return f"<ExhibitFeeItem {self.item_name}: {self.total_price}>"
