"""Knowledge graph models for contract entity extraction.

This module defines the SQLAlchemy models for storing extracted entities
and their relationships from contracts. The knowledge graph enables:
- Better entity resolution ("The Provider" -> actual company name)
- Cross-reference understanding (Section references resolved)
- Obligation tracking (party -> obligation -> limits chain)
- Risk pattern detection (unlimited liabilities, etc.)
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class KGEntityType(str, enum.Enum):
    """Types of entities in the knowledge graph."""

    PARTY = "party"  # Company, person (includes role: provider, client, vendor)
    CLAUSE = "clause"  # Contract section reference
    OBLIGATION = "obligation"  # What must be done (payment, delivery, reporting)
    TERM = "term"  # Defined term ("Provider" means..., "Effective Date" means...)
    DATE = "date"  # Key date (effective, expiration, deadlines)
    AMOUNT = "amount"  # Money value with context
    JURISDICTION = "jurisdiction"  # Governing law
    SLA_METRIC = "sla_metric"  # Service level metric and target


class KGRelationshipType(str, enum.Enum):
    """Types of relationships between entities in the knowledge graph."""

    HAS_PARTY = "has_party"  # Contract has party
    HAS_OBLIGATION = "has_obligation"  # Party has obligation
    BENEFITS_FROM = "benefits_from"  # Party benefits from obligation
    REFERENCES = "references"  # Clause references another clause
    LIMITED_BY = "limited_by"  # Obligation has limit (amount, clause)
    DEFINED_AS = "defined_as"  # Term definition
    TRIGGERED_BY = "triggered_by"  # Condition triggers obligation
    GOVERNED_BY = "governed_by"  # Contract governed by jurisdiction
    AMENDS = "amends"  # Amendment modifies original
    EXPIRES_ON = "expires_on"  # Contract/obligation expires on date
    SAME_AS = "same_as"  # Cross-contract entity identity


class KGMasterEntity(Base, UUIDMixin, TimestampMixin):
    """Canonical representation of an entity at the tenant level.

    Aggregates multiple KGEntity instances from different contracts
    into a single business entity (e.g., "Acme Corp" across 50 contracts).
    """

    __tablename__ = "kg_master_entities"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[KGEntityType] = mapped_column(
        Enum(
            KGEntityType,
            values_callable=lambda x: [e.value for e in x],
            native_enum=True,
            name='kgentitytype',
            create_type=False,
        ),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str] = mapped_column(
        String(500), nullable=False, index=True
    )

    # Consolidated properties from all linked entities
    properties: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    # Metadata
    entity_count: Mapped[int] = mapped_column(Integer, server_default="0")
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    # Relationships
    entities: Mapped[list["KGEntity"]] = relationship(
        "KGEntity",
        back_populates="master_entity",
    )

    def __repr__(self) -> str:
        return f"<KGMasterEntity {self.entity_type.value}: {self.name}>"


class KGEntity(Base, UUIDMixin, TimestampMixin):
    """Entity (node) in the contract knowledge graph.

    Represents extracted entities from contracts such as parties, clauses,
    obligations, terms, dates, amounts, jurisdictions, and SLA metrics.
    """

    __tablename__ = "kg_entities"

    # Foreign keys
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    master_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("kg_master_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Entity identification
    # Use native_enum=False to avoid SQLAlchemy enum name/value confusion
    # PostgreSQL enum was created with lowercase values
    entity_type: Mapped[KGEntityType] = mapped_column(
        Enum(
            KGEntityType,
            values_callable=lambda x: [e.value for e in x],
            native_enum=True,
            name='kgentitytype',
            create_type=False,  # Don't try to create, it already exists
        ),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(
        String(500), nullable=True, index=True
    )

    # Flexible attributes stored as JSON
    properties: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    # Source tracking
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_section: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Extraction confidence (0.0 to 1.0)
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0"
    )

    # Relationships
    master_entity: Mapped[KGMasterEntity | None] = relationship(
        "KGMasterEntity",
        back_populates="entities",
    )
    outgoing_relationships: Mapped[list["KGRelationship"]] = relationship(
        "KGRelationship",
        foreign_keys="KGRelationship.source_entity_id",
        back_populates="source_entity",
        cascade="all, delete-orphan",
    )
    incoming_relationships: Mapped[list["KGRelationship"]] = relationship(
        "KGRelationship",
        foreign_keys="KGRelationship.target_entity_id",
        back_populates="target_entity",
        cascade="all, delete-orphan",
    )

    # Composite indexes for common queries
    __table_args__ = (
        Index("ix_kg_entities_contract_type", "contract_id", "entity_type"),
    )

    def __repr__(self) -> str:
        return f"<KGEntity {self.entity_type.value}: {self.name[:50]}>"


class KGRelationship(Base, UUIDMixin):
    """Relationship (edge) in the contract knowledge graph.

    Represents connections between entities such as "Party HAS_OBLIGATION Obligation"
    or "Obligation LIMITED_BY Amount".
    """

    __tablename__ = "kg_relationships"

    # Foreign keys
    contract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )

    # Relationship endpoints
    source_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kg_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kg_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationship type
    # Use values_callable to ensure enum values (lowercase) are used
    relationship_type: Mapped[KGRelationshipType] = mapped_column(
        Enum(
            KGRelationshipType,
            values_callable=lambda x: [e.value for e in x],
            native_enum=True,
            name='kgrelationshiptype',
            create_type=False,  # Already exists in DB
        ),
        nullable=False,
        index=True,
    )

    # Flexible attributes
    properties: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    # Source text where relationship was identified
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Extraction confidence (0.0 to 1.0)
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0"
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    # Navigation relationships
    source_entity: Mapped["KGEntity"] = relationship(
        "KGEntity",
        foreign_keys=[source_entity_id],
        back_populates="outgoing_relationships",
    )
    target_entity: Mapped["KGEntity"] = relationship(
        "KGEntity",
        foreign_keys=[target_entity_id],
        back_populates="incoming_relationships",
    )

    # Composite index for common traversal pattern
    __table_args__ = (
        Index("ix_kg_relationships_source_type", "source_entity_id", "relationship_type"),
    )

    def __repr__(self) -> str:
        return f"<KGRelationship {self.source_entity_id} -{self.relationship_type.value}-> {self.target_entity_id}>"
