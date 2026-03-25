"""Service Portfolio models for relationship governance (Evaluetor features)."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM
from sqlalchemy.orm import relationship as sa_relationship

from app.database import Base


class ServiceType(str, enum.Enum):
    """Type of service in the portfolio."""
    IT_SERVICES = "it_services"
    CONSULTING = "consulting"
    LEGAL = "legal"
    FINANCIAL = "financial"
    LOGISTICS = "logistics"
    MANUFACTURING = "manufacturing"
    MARKETING = "marketing"
    HR = "hr"
    PROCUREMENT = "procurement"
    OTHER = "other"


class ServiceStatus(str, enum.Enum):
    """Status of a service portfolio entry."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PLANNED = "planned"
    DEPRECATED = "deprecated"


class ServicePortfolio(Base):
    """Service portfolio entry for an organization.

    Tracks the services that an organization provides or receives,
    linking them to business relationships for scope and timeline tracking.
    """

    __tablename__ = "service_portfolios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Tenant (multi-tenancy)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)

    # Organization that provides/receives this service
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)

    # Service details
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=False)  # Unique within tenant
    description = Column(Text, nullable=True)

    service_type = Column(
        PG_ENUM(
            'it_services', 'consulting', 'legal', 'financial', 'logistics',
            'manufacturing', 'marketing', 'hr', 'procurement', 'other',
            name='servicetype', create_type=False
        ),
        nullable=False,
        default='other'
    )

    status = Column(
        PG_ENUM(
            'active', 'inactive', 'planned', 'deprecated',
            name='servicestatus', create_type=False
        ),
        nullable=False,
        default='active'
    )

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    organization = sa_relationship("Organization", foreign_keys=[organization_id])
    relationship_services = sa_relationship(
        "RelationshipService",
        back_populates="service_portfolio",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ServicePortfolio {self.code}: {self.name}>"


class RelationshipService(Base):
    """Links a service portfolio entry to a business relationship.

    Defines the scope, timeline, and active status of a service
    within a specific business relationship.
    """

    __tablename__ = "relationship_services"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Links
    relationship_id = Column(
        UUID(as_uuid=True), ForeignKey("business_relationships.id"), nullable=False, index=True
    )
    service_portfolio_id = Column(
        UUID(as_uuid=True), ForeignKey("service_portfolios.id"), nullable=False, index=True
    )

    # Scope and timeline
    scope = Column(Text, nullable=True)  # Description of service scope for this relationship
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    relationship = sa_relationship("BusinessRelationship", foreign_keys=[relationship_id])
    service_portfolio = sa_relationship("ServicePortfolio", back_populates="relationship_services")

    def __repr__(self) -> str:
        return f"<RelationshipService {self.service_portfolio_id} -> {self.relationship_id}>"
