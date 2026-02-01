"""Contract definitions model for extracted defined terms."""

import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class ContractDefinition(Base, UUIDMixin, TimestampMixin):
    """
    Extracted definition from a contract's Definitions section.

    Examples:
    - "Agreement" means this Master Services Agreement...
    - "Certification Services" means the product certification...
    - "Sales Data" includes units sold, distributor contacts...
    """

    __tablename__ = "contract_definitions"

    # Relationship to contract
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contract: Mapped["Contract"] = relationship(
        "Contract",
        back_populates="definitions",
    )

    # Optional link to source clause
    source_clause_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clauses.id", ondelete="SET NULL"),
        nullable=True,
    )

    # The defined term (e.g., "Agreement", "Certification Services")
    term: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # Normalized term for matching (lowercase, no quotes)
    term_normalized: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # The full definition text
    definition_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Category of definition (helps with filtering)
    # e.g., "party", "service", "document", "term", "process", "data"
    category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    # Section/article reference (e.g., "1.1", "1.2")
    section_reference: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Page number where definition appears
    page_number: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    # Cross-references to other definitions (comma-separated terms)
    cross_references: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    __table_args__ = (
        Index("ix_definitions_contract_term", "contract_id", "term_normalized"),
        Index("ix_definitions_category", "category"),
    )

    def __repr__(self) -> str:
        return f"<ContractDefinition '{self.term}' (contract: {self.contract_id})>"
