"""Tenant model for multi-tenancy support."""
import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class TenantPlan(str, enum.Enum):
    """Subscription plan tiers."""

    STARTER = "starter"  # Up to 100 contracts
    PROFESSIONAL = "professional"  # Up to 500 contracts
    ENTERPRISE = "enterprise"  # Up to 2000 contracts
    STRATEGIC = "strategic"  # Unlimited


# Plan limits
PLAN_CONTRACT_LIMITS = {
    TenantPlan.STARTER: 100,
    TenantPlan.PROFESSIONAL: 500,
    TenantPlan.ENTERPRISE: 2000,
    TenantPlan.STRATEGIC: None,  # Unlimited
}


class Tenant(Base, UUIDMixin, TimestampMixin):
    """
    Tenant model representing a customer organization.

    All data in the system belongs to a tenant, enabling complete
    data isolation between customers.
    """

    __tablename__ = "tenants"

    # Basic info
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

    # Contact info
    contact_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    contact_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Subscription
    plan: Mapped[TenantPlan] = mapped_column(
        Enum(TenantPlan, name='tenantplan', create_type=False,
             values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TenantPlan.STARTER,
    )
    contract_limit: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Settings
    settings: Mapped[str | None] = mapped_column(
        Text,  # JSON string for tenant-specific settings
        nullable=True,
    )

    # Industry profile — defines contract types, risk categories, UI config, etc.
    industry_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("industry_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Tenant-specific overrides to the industry profile
    # Same top-level keys as IndustryProfile JSONB columns; merged at runtime
    config_overrides: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default='{}',
    )

    # Custom field definitions for dynamic fields
    # Schema: {entity_type: [{name, label, field_type, required, options, extraction_hints, ...}]}
    custom_field_definitions: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default='{}',
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Relationships
    industry_profile: Mapped["IndustryProfile | None"] = relationship(
        "IndustryProfile",
        back_populates="tenants",
        lazy="selectin",
    )
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="tenant",
        lazy="selectin",
    )
    business_units: Mapped[list["BusinessUnit"]] = relationship(
        "BusinessUnit",
        back_populates="tenant",
        lazy="selectin",
    )
    notification_rules: Mapped[list["NotificationRule"]] = relationship(
        "NotificationRule",
        back_populates="tenant",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Tenant {self.name} ({self.slug})>"

    def get_industry_config(self) -> dict:
        """Get merged industry config (profile defaults + tenant overrides).

        Returns the IT Services default config if no profile is assigned.
        """
        if self.industry_profile:
            return self.industry_profile.get_merged_config(self.config_overrides or None)
        # No profile assigned — return empty config (frontend will use its defaults)
        return {"industry": None, "industry_name": None}

    def get_contract_limit(self) -> int | None:
        """Get the contract limit for this tenant based on plan or override."""
        if self.contract_limit is not None:
            return self.contract_limit
        return PLAN_CONTRACT_LIMITS.get(self.plan)
