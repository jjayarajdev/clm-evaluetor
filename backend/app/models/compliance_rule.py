"""Industry Compliance Rule model.

Defines rules for required compliance documents per industry and contract type.
These rules are used by the compliance gap detector to identify missing documents.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDMixin
from app.models.industry import (
    ComplianceDocumentType,
    ComplianceGapSeverity,
    Industry,
)

if TYPE_CHECKING:
    from app.models.compliance_gap import ComplianceGap


class IndustryComplianceRule(Base, UUIDMixin, TimestampMixin, TenantMixin):
    """Rules defining required compliance documents per industry.

    Each rule specifies:
    - Which industry the rule applies to
    - The primary contract type that triggers the requirement
    - What compliance document is required
    - Whether it's mandatory or recommended
    - The severity if the document is missing
    - Regulatory reference (e.g., "21 CFR Part 211")
    """

    __tablename__ = "industry_compliance_rules"

    # Industry and contract type this rule applies to
    industry: Mapped[Industry] = mapped_column(
        Enum(
            Industry,
            name='industry',
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )
    primary_contract_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    # Required document type
    required_document_type: Mapped[ComplianceDocumentType] = mapped_column(
        Enum(
            ComplianceDocumentType,
            name='compliancedocumenttype',
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )

    # Requirement details
    is_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="True = mandatory, False = recommended",
    )
    condition_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Condition when this rule applies, e.g., 'if PHI involved'",
    )

    # Severity and regulatory info
    severity_if_missing: Mapped[ComplianceGapSeverity] = mapped_column(
        Enum(
            ComplianceGapSeverity,
            name='compliancegapseverity',
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ComplianceGapSeverity.MEDIUM,
    )
    regulatory_reference: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        doc="Reference to regulation, e.g., '21 CFR Part 211'",
    )

    # Rule metadata
    rule_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Human-readable name for the rule",
    )
    rule_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Detailed description of why this rule exists",
    )

    # Active flag for soft-disable
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Relationship to gaps created from this rule
    gaps: Mapped[list["ComplianceGap"]] = relationship(
        "ComplianceGap",
        back_populates="rule",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Indexes for common queries
    __table_args__ = (
        Index(
            "ix_compliance_rules_industry_contract",
            "industry",
            "primary_contract_type",
        ),
        Index(
            "ix_compliance_rules_active_industry",
            "is_active",
            "industry",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<IndustryComplianceRule {self.industry.value}/"
            f"{self.primary_contract_type} -> "
            f"{self.required_document_type.value}>"
        )
