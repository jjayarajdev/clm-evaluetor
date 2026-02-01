"""Contract preamble model for header/background section data."""

import uuid

from sqlalchemy import ForeignKey, Index, String, Text, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class ContractPreamble(Base, UUIDMixin, TimestampMixin):
    """
    Preamble/Header data extracted from a contract.

    Contains:
    - Document title
    - Effective date (from header)
    - Parties with their roles
    - Recitals/Whereas clauses
    - Background summary
    """

    __tablename__ = "contract_preambles"

    # Relationship to contract (one-to-one)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    contract: Mapped["Contract"] = relationship(
        "Contract",
        back_populates="preamble",
    )

    # Document identification
    document_title: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Effective date from preamble
    effective_date_text: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    # Background/Recitals summary
    background_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Full recitals text
    recitals_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Source text (the actual preamble section)
    source_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<ContractPreamble {self.document_title or 'Untitled'} (contract: {self.contract_id})>"


class ContractPartyDetail(Base, UUIDMixin, TimestampMixin):
    """
    Detailed party information from preamble.

    More detailed than ContractParty - includes
    address, registration info from preamble.
    """

    __tablename__ = "contract_party_details"

    # Relationship to preamble
    preamble_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contract_preambles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    preamble: Mapped["ContractPreamble"] = relationship(
        "ContractPreamble",
        backref="party_details",
    )

    # Party identification
    party_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    party_role: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )  # e.g., "Provider", "Client", "Party A"

    party_short_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )  # e.g., "CLASP", "IA"

    # Legal details
    legal_form: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )  # e.g., "corporation", "LLC", "LLP"

    jurisdiction_of_incorporation: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Address
    address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Order in which party appears
    party_order: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )

    __table_args__ = (
        Index("ix_party_details_preamble", "preamble_id"),
        Index("ix_party_details_name", "party_name"),
    )

    def __repr__(self) -> str:
        return f"<ContractPartyDetail {self.party_name} ({self.party_role or 'unknown role'})>"
