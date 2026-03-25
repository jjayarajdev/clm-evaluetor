"""Organization Officer model for tracking key contacts and governance roles."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM
from sqlalchemy.orm import relationship as sa_relationship

from app.database import Base


class GovernanceRole(str, enum.Enum):
    """Governance role an officer fulfils within the relationship."""
    ACCOUNT_MANAGER = "account_manager"
    SERVICE_DELIVERY_MANAGER = "service_delivery_manager"
    RELATIONSHIP_OWNER = "relationship_owner"
    EXECUTIVE_SPONSOR = "executive_sponsor"
    COMMERCIAL_MANAGER = "commercial_manager"
    TECHNICAL_LEAD = "technical_lead"
    OPERATIONS_LEAD = "operations_lead"
    COMPLIANCE_OFFICER = "compliance_officer"
    OTHER = "other"


class OfficerSide(str, enum.Enum):
    """Which side of a business relationship an officer represents."""
    INTERNAL = "internal"
    EXTERNAL = "external"


class OrganizationOfficer(Base):
    """Key contact / officer associated with an organization.

    Tracks named individuals, their governance roles, and which side of the
    business relationship they represent (internal vs. external).
    """

    __tablename__ = "organization_officers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Tenant (multi-tenancy)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )

    # Parent organization
    organization_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    # Contact details
    name = Column(String(255), nullable=False)
    title = Column(String(255), nullable=True)  # job title
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    department = Column(String(100), nullable=True)

    # Governance classification
    governance_role = Column(
        PG_ENUM(
            *[e.value for e in GovernanceRole],
            name='governance_role_type',
            create_type=False,
        ),
        nullable=True,
    )
    side = Column(
        PG_ENUM(
            *[e.value for e in OfficerSide],
            name='officer_side',
            create_type=False,
        ),
        nullable=True,
    )

    # Flags
    is_primary = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Free-form notes
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # SA relationships
    organization = sa_relationship(
        "Organization",
        back_populates="officers",
    )

    def __repr__(self) -> str:
        return f"<OrganizationOfficer {self.name} ({self.governance_role}) @ {self.organization_id}>"
