import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDMixin
from app.models.industry import Industry


class ContractType(str, enum.Enum):
    """Legacy contract type enum — kept for backward compatibility.

    The database column is now VARCHAR(100), not a PostgreSQL enum.
    New contract types are defined in IndustryProfile.contract_types (JSONB).
    Use these constants for common comparisons but any string value is valid.
    """

    NDA = "nda"
    MSA = "msa"
    SOW = "sow"
    AMENDMENT = "amendment"
    VENDOR_AGREEMENT = "vendor_agreement"
    EMPLOYMENT_CONTRACT = "employment_contract"
    # Extended types (data-driven, no PG enum needed)
    LICENSE = "license"
    LEASE = "lease"


class ContractStatus(str, enum.Enum):
    """Contract processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(str, enum.Enum):
    """Contract risk level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Contract(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Contract model representing an uploaded contract document."""

    __tablename__ = "contracts"

    # File information
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    file_size: Mapped[int | None] = mapped_column(
        nullable=True,
    )
    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(64),  # SHA256 hex digest
        nullable=True,
        index=True,
    )

    # Extracted metadata — now VARCHAR, not PG enum; accepts any industry profile type
    contract_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    counterparty: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    effective_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    expiration_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )
    contract_value: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )
    currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
        default="USD",
    )
    jurisdiction: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Risk assessment
    risk_score: Mapped[int | None] = mapped_column(
        nullable=True,
    )
    risk_level: Mapped[RiskLevel | None] = mapped_column(
        Enum(RiskLevel, name='risklevel', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=True,
        index=True,
    )

    # Industry and compliance (Industry-Aware Compliance Module)
    detected_industry: Mapped[Industry | None] = mapped_column(
        Enum(
            Industry,
            name='industry',
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
        index=True,
    )
    industry_confidence: Mapped[float | None] = mapped_column(
        nullable=True,
        doc="Confidence score for industry detection (0.0-1.0)",
    )
    compliance_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Overall compliance score (0-100)",
    )
    last_compliance_check: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Renewal information
    auto_renewal: Mapped[bool | None] = mapped_column(
        nullable=True,
    )
    notice_period_days: Mapped[int | None] = mapped_column(
        nullable=True,
    )
    renewal_term_months: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    # Promoted fields from schema extraction (for efficient querying)
    governing_law: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    initial_term_months: Mapped[int | None] = mapped_column(
        nullable=True,
    )
    liability_cap_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    liability_cap_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )
    dispute_resolution_method: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    termination_for_convenience: Mapped[bool | None] = mapped_column(
        nullable=True,
    )
    confidentiality_term_years: Mapped[int | None] = mapped_column(
        nullable=True,
    )

    # Processing status
    status: Mapped[ContractStatus] = mapped_column(
        Enum(ContractStatus, name='contractstatus', create_type=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ContractStatus.PENDING,
        index=True,
    )
    processing_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Extracted content
    extracted_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Schema-extracted structured data (JSONB for flexible storage)
    schema_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    schema_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Tenant-defined custom fields (flexible metadata)
    custom_fields: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default='{}',
    )

    # Client association
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id"),
        nullable=True,
        index=True,
    )

    # Industry profile override (per-contract, overrides tenant/BU default)
    industry_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("industry_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Business Unit association
    business_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("business_units.id"),
        nullable=True,
        index=True,
    )

    # Business relationship association (Evaluetor feature)
    business_relationship_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("business_relationships.id"),
        nullable=True,
        index=True,
    )

    # Versioning
    version: Mapped[int] = mapped_column(
        nullable=False,
        default=1,
    )
    previous_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contracts.id"),
        nullable=True,
    )

    # Relationships
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    uploaded_by_user: Mapped["User"] = relationship(
        "User",
        back_populates="contracts",
    )
    client: Mapped["Client | None"] = relationship(
        "Client",
        back_populates="contracts",
    )
    business_unit: Mapped["BusinessUnit | None"] = relationship(
        "BusinessUnit",
        back_populates="contracts",
        lazy="noload",
    )
    industry_profile: Mapped["IndustryProfile | None"] = relationship(
        "IndustryProfile",
        lazy="noload",
    )
    business_relationship: Mapped["BusinessRelationship | None"] = relationship(
        "BusinessRelationship",
        back_populates="contracts",
    )
    previous_version: Mapped["Contract | None"] = relationship(
        "Contract",
        remote_side="Contract.id",
        foreign_keys="Contract.previous_version_id",
    )
    clauses: Mapped[list["Clause"]] = relationship(
        "Clause",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    obligations: Mapped[list["Obligation"]] = relationship(
        "Obligation",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    parties: Mapped[list["ContractParty"]] = relationship(
        "ContractParty",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    key_dates: Mapped[list["ContractKeyDate"]] = relationship(
        "ContractKeyDate",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # ===== NEW CANONICAL RELATIONSHIPS =====

    # Financial terms
    financials: Mapped[list["ContractFinancial"]] = relationship(
        "ContractFinancial",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # Liability terms
    liabilities: Mapped[list["ContractLiability"]] = relationship(
        "ContractLiability",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # Clause presence indicators (one-to-one)
    clause_indicators: Mapped["ContractClauseIndicator | None"] = relationship(
        "ContractClauseIndicator",
        back_populates="contract",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="noload",
    )

    # Contract links (parent-child relationships)
    # Links where this contract is the parent (e.g., MSA with SOWs)
    child_links: Mapped[list["ContractLink"]] = relationship(
        "ContractLink",
        foreign_keys="ContractLink.parent_contract_id",
        back_populates="parent_contract",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    # Links where this contract is the child (e.g., SOW under an MSA)
    parent_links: Mapped[list["ContractLink"]] = relationship(
        "ContractLink",
        foreign_keys="ContractLink.child_contract_id",
        back_populates="child_contract",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # Extracted definitions
    definitions: Mapped[list["ContractDefinition"]] = relationship(
        "ContractDefinition",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # Process steps from procedural clauses
    process_steps: Mapped[list["ContractProcessStep"]] = relationship(
        "ContractProcessStep",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # Preamble/Header data (one-to-one)
    preamble: Mapped["ContractPreamble | None"] = relationship(
        "ContractPreamble",
        back_populates="contract",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="noload",
    )

    # Exhibits/Schedules
    exhibits: Mapped[list["ContractExhibit"]] = relationship(
        "ContractExhibit",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # SLAs
    slas: Mapped[list["ContractSLA"]] = relationship(
        "ContractSLA",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # SLA Alerts
    sla_alerts: Mapped[list["SLAAlert"]] = relationship(
        "SLAAlert",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # Compliance Gaps (Industry-Aware Compliance Module)
    compliance_gaps: Mapped[list["ComplianceGap"]] = relationship(
        "ComplianceGap",
        back_populates="contract",
        foreign_keys="ComplianceGap.contract_id",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # Regulatory Obligations (Industry-Aware Compliance Module)
    regulatory_obligations: Mapped[list["RegulatoryObligation"]] = relationship(
        "RegulatoryObligation",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # Contract Documents (document package management)
    documents: Mapped[list["ContractDocument"]] = relationship(
        "ContractDocument",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # ===== END NEW RELATIONSHIPS =====

    # External sharing and comments
    shares: Mapped[list["ContractShare"]] = relationship(
        "ContractShare",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="noload",
    )
    comments: Mapped[list["ContractComment"]] = relationship(
        "ContractComment",
        back_populates="contract",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_contracts_expiration_risk", "expiration_date", "risk_level"),
        Index("ix_contracts_type_status", "contract_type", "status"),
        Index("ix_contracts_industry_compliance", "detected_industry", "compliance_score"),
    )

    def __repr__(self) -> str:
        return f"<Contract {self.filename} ({self.status.value})>"
