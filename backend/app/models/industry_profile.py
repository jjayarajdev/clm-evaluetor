"""Industry Profile model for multi-domain CLM support.

An IndustryProfile defines the contract types, clause types, risk categories,
SLA metrics, field definitions, extraction hints, and UI configuration for
a specific industry vertical (IT Services, Manufacturing, Pharma, etc.).

Tenants link to a profile to get industry-appropriate defaults. They can
override specific values via the tenant's config_overrides JSONB column.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class IndustryProfile(Base, UUIDMixin, TimestampMixin):
    """
    Industry profile defining domain-specific configuration.

    Each profile encapsulates everything the platform needs to know about
    an industry vertical: what contract types exist, what clauses to look for,
    what risks matter, what SLA metrics are relevant, and how the UI should
    render.

    JSONB Column Schemas:
    ---------------------

    contract_types: list[dict]
        [{
            "code": "supply_agreement",
            "label": "Supply Agreement",
            "description": "Agreement for supply of goods/materials",
            "icon": "truck"  # optional, for UI rendering
        }]

    clause_types: list[dict]
        [{
            "code": "quality_specs",
            "label": "Quality Specifications",
            "category": "quality",  # grouping for UI
            "risk_weight": 8,  # 0-15, used in risk scoring
            "description": "Product quality requirements and standards"
        }]

    risk_categories: list[dict]
        [{
            "code": "supply_disruption",
            "label": "Supply Disruption",
            "severity": "high",
            "weight": 20,  # 0-30, scoring weight
            "description": "Risk of supply chain interruption"
        }]

    sla_metrics: list[dict]
        [{
            "code": "defect_ppm",
            "label": "Defect Rate (PPM)",
            "unit": "ppm",
            "direction": "lower_is_better",  # or "higher_is_better"
            "default_target": 50,
            "description": "Parts per million defective"
        }]

    field_definitions: dict[str, list[dict]]
        Keyed by contract_type code. Each entry defines the sections and
        fields to extract/display for that contract type.
        {
            "supply_agreement": [{
                "section": "Pricing",
                "fields": [
                    {"key": "unit_price", "label": "Unit Price", "type": "currency"},
                    {"key": "volume_tiers", "label": "Volume Tiers", "type": "table"},
                    {"key": "price_escalation", "label": "Price Escalation", "type": "percentage"}
                ]
            }]
        }

    extraction_hints: dict[str, str]
        Per-agent prompt fragments that guide extraction for this industry.
        {
            "metadata": "Look for Incoterms, payment terms, and volume commitments...",
            "clauses": "Pay special attention to quality specs, inspection rights...",
            "risks": "Evaluate supply chain risks, commodity price exposure...",
            "slas": "Extract delivery metrics (OTD%), quality metrics (PPM)...",
            "obligations": "Identify quality audit obligations, certification requirements..."
        }

    ui_config: dict
        Controls how the frontend renders for this industry.
        {
            "table_columns": [
                {"key": "counterparty", "label": "Supplier", "width": 200},
                {"key": "contract_value", "label": "Annual Spend", "format": "currency"},
                {"key": "risk_level", "label": "Risk"},
                {"key": "custom.defect_ppm", "label": "Defect PPM", "format": "number"}
            ],
            "dashboard_widgets": [
                {"key": "total_contracts", "label": "Total Contracts", "color": "primary"},
                {"key": "supply_risk", "label": "Supply Risk", "color": "danger"},
                {"key": "quality_score", "label": "Quality Score", "color": "success"}
            ],
            "detail_tabs": [
                {"id": "overview", "label": "Overview"},
                {"id": "review", "label": "Review"},
                {"id": "quality", "label": "Quality"},
                {"id": "supply_chain", "label": "Supply Chain"},
                {"id": "documents", "label": "Documents"},
                {"id": "sharing", "label": "Sharing"}
            ],
            "filters": ["contract_type", "risk_level", "business_unit", "supplier_tier"],
            "labels": {
                "counterparty": "Supplier",
                "contract_value": "Annual Spend",
                "portfolio": "Procurement Dashboard"
            }
        }
    """

    __tablename__ = "industry_profiles"

    # Identity
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Domain configuration (all JSONB)
    contract_types: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    clause_types: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    risk_categories: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    sla_metrics: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    field_definitions: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    extraction_hints: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    ui_config: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Ownership: NULL = global/system profile (visible to all tenants);
    # otherwise the tenant that created it — visible only to that tenant.
    owner_tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Relationships
    tenants: Mapped[list["Tenant"]] = relationship(
        "Tenant",
        back_populates="industry_profile",
        foreign_keys="Tenant.industry_profile_id",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"<IndustryProfile {self.name} ({self.slug})>"

    def get_contract_type_labels(self) -> dict[str, str]:
        """Return {code: label} mapping for contract types."""
        return {ct["code"]: ct["label"] for ct in self.contract_types}

    def get_risk_weights(self) -> dict[str, int]:
        """Return {code: weight} mapping for risk categories."""
        return {rc["code"]: rc.get("weight", 10) for rc in self.risk_categories}

    def get_merged_config(self, overrides: dict | None = None) -> dict:
        """Merge profile defaults with tenant-specific overrides.

        For list-type keys (contract_types, clause_types, risk_categories,
        sla_metrics), tenant additions are appended (deduplicated by code).
        For dict-type keys (extraction_hints, ui, field_definitions),
        values are shallow-merged.
        """
        config = {
            "industry": self.slug,
            "industry_name": self.name,
            "contract_types": list(self.contract_types),
            "clause_types": list(self.clause_types),
            "risk_categories": list(self.risk_categories),
            "sla_metrics": list(self.sla_metrics),
            "field_definitions": dict(self.field_definitions),
            "extraction_hints": dict(self.extraction_hints),
            "ui": dict(self.ui_config),
        }
        if not overrides:
            return config

        # List fields: append tenant additions (deduplicate by code)
        list_keys = ["contract_types", "clause_types", "risk_categories", "sla_metrics"]
        for key in list_keys:
            additions = overrides.get(key)
            if additions and isinstance(additions, list):
                existing_codes = {item.get("code") for item in config[key]}
                for item in additions:
                    if item.get("code") and item["code"] not in existing_codes:
                        config[key].append(item)
                        existing_codes.add(item["code"])

        # Dict fields: shallow merge
        dict_keys = ["extraction_hints", "ui", "field_definitions"]
        for key in dict_keys:
            additions = overrides.get(key)
            if additions and isinstance(additions, dict):
                config[key] = {**config[key], **additions}

        return config
