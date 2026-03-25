"""Organization model for relationship governance (Evaluetor features)."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM
from sqlalchemy.orm import relationship as sa_relationship

from app.database import Base


class OrganizationType(str, enum.Enum):
    """Type of organization."""
    CUSTOMER = "customer"
    VENDOR = "vendor"
    PARTNER = "partner"
    INTERNAL = "internal"


class OrganizationSize(str, enum.Enum):
    """Size classification of organization."""
    STARTUP = "startup"
    SMB = "smb"
    MID_MARKET = "mid_market"
    ENTERPRISE = "enterprise"
    GLOBAL = "global"


class OrganizationLevel(str, enum.Enum):
    """Level within a corporate hierarchy."""
    HOLDING = "holding"
    SUBSIDIARY = "subsidiary"
    DIVISION = "division"
    BRANCH = "branch"
    DEPARTMENT = "department"


class Organization(Base):
    """Organization entity for relationship governance.

    Extends beyond simple clients to support full relationship management
    with KPI tracking, perception scoring, and improvement points.
    Supports corporate hierarchy via parent_organization_id self-referential FK.
    """

    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Tenant (multi-tenancy)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)

    # Basic info
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=False, unique=True)  # Short identifier
    org_type = Column(
        PG_ENUM('customer', 'vendor', 'partner', 'internal', name='organizationtype', create_type=False),
        nullable=False,
        default='customer'
    )

    # Corporate hierarchy
    parent_organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )
    organization_level = Column(
        PG_ENUM(
            *[e.value for e in OrganizationLevel],
            name='organizationlevel',
            create_type=False,
        ),
        nullable=True,
    )

    # Classification
    industry = Column(String(100), nullable=True)
    size = Column(
        PG_ENUM('startup', 'smb', 'mid_market', 'enterprise', 'global', name='organizationsize', create_type=False),
        nullable=True
    )
    region = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)

    # Contact info
    website = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    primary_contact_name = Column(String(255), nullable=True)
    primary_contact_email = Column(String(255), nullable=True)
    primary_contact_phone = Column(String(50), nullable=True)

    # Relationship owner (internal user responsible for this organization)
    relationship_owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    relationship_owner = sa_relationship("User", foreign_keys=[relationship_owner_id])

    # Corporate hierarchy relationships
    parent_organization = sa_relationship(
        "Organization",
        remote_side="Organization.id",
        foreign_keys=[parent_organization_id],
        back_populates="subsidiaries",
    )
    subsidiaries = sa_relationship(
        "Organization",
        foreign_keys=[parent_organization_id],
        back_populates="parent_organization",
        lazy="selectin",
    )

    # Relationships where this org is party A
    relationships_as_a = sa_relationship(
        "BusinessRelationship",
        foreign_keys="BusinessRelationship.org_a_id",
        back_populates="org_a",
        lazy="dynamic"
    )

    # Relationships where this org is party B
    relationships_as_b = sa_relationship(
        "BusinessRelationship",
        foreign_keys="BusinessRelationship.org_b_id",
        back_populates="org_b",
        lazy="dynamic"
    )

    # External users associated with this organization
    external_users = sa_relationship(
        "ExternalUser",
        back_populates="organization",
        lazy="dynamic"
    )

    # Officers / contacts associated with this organization
    officers = sa_relationship(
        "OrganizationOfficer",
        back_populates="organization",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<Organization {self.code}: {self.name}>"

    @property
    def all_relationships(self):
        """Get all business relationships involving this organization."""
        from sqlalchemy import or_
        from app.models.relationship import BusinessRelationship
        return BusinessRelationship.query.filter(
            or_(
                BusinessRelationship.org_a_id == self.id,
                BusinessRelationship.org_b_id == self.id
            )
        )
