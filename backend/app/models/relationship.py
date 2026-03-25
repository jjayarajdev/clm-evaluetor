"""Business Relationship models for relationship governance (Evaluetor features)."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text, Boolean, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM
from sqlalchemy.orm import relationship as sa_relationship

from app.database import Base


class RelationshipType(str, enum.Enum):
    """Type of business relationship."""
    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    PARTNER = "partner"
    JOINT_VENTURE = "joint_venture"
    RESELLER = "reseller"
    DISTRIBUTOR = "distributor"


class RelationshipStatus(str, enum.Enum):
    """Status of a business relationship."""
    PROSPECTING = "prospecting"
    ACTIVE = "active"
    AT_RISK = "at_risk"
    ON_HOLD = "on_hold"
    TERMINATED = "terminated"


class GovernanceTier(str, enum.Enum):
    """Governance tier level."""
    OPERATIONAL = "operational"  # Weekly reviews
    TACTICAL = "tactical"  # Monthly reviews
    STRATEGIC = "strategic"  # Quarterly reviews
    EXECUTIVE = "executive"  # Annual reviews


class BusinessRelationship(Base):
    """Business relationship between two organizations.

    Supports governance structures, KPI tracking, and perception scoring
    for Evaluetor-style relationship management.
    """

    __tablename__ = "business_relationships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Tenant (multi-tenancy)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)

    # The two parties in the relationship
    org_a_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    org_b_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)

    # Relationship metadata
    relationship_type = Column(
        PG_ENUM('customer', 'supplier', 'partner', 'joint_venture', 'reseller', 'distributor', name='relationshiptype', create_type=False),
        nullable=False
    )
    status = Column(
        PG_ENUM('prospecting', 'active', 'at_risk', 'on_hold', 'terminated', name='relationshipstatus', create_type=False),
        nullable=False,
        default='active'
    )
    name = Column(String(255), nullable=True)  # Optional friendly name
    description = Column(Text, nullable=True)

    # Health metrics (0-100 composite score)
    health_score = Column(Integer, nullable=True, default=None)
    last_health_calculation = Column(DateTime, nullable=True)

    # Governance
    governance_tier = Column(
        PG_ENUM('operational', 'tactical', 'strategic', 'executive', name='governancetier', create_type=False),
        nullable=True,
        default='operational'
    )
    governance_config = Column(JSON, nullable=True)  # Custom governance rules

    # Key dates
    start_date = Column(DateTime, nullable=True)
    review_frequency_days = Column(Integer, nullable=True, default=30)
    next_review_date = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    org_a = sa_relationship("Organization", foreign_keys=[org_a_id], back_populates="relationships_as_a")
    org_b = sa_relationship("Organization", foreign_keys=[org_b_id], back_populates="relationships_as_b")
    team_members = sa_relationship("RelationshipTeam", back_populates="business_relationship", lazy="dynamic")
    kpis = sa_relationship("KPI", back_populates="relationship", lazy="dynamic")
    improvement_points = sa_relationship("ImprovementPoint", back_populates="relationship", lazy="dynamic")
    contracts = sa_relationship("Contract", back_populates="business_relationship", lazy="dynamic")
    survey_instances = sa_relationship("SurveyInstance", back_populates="relationship", lazy="dynamic")
    status_history = sa_relationship("RelationshipStatusHistory", back_populates="relationship", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<BusinessRelationship {self.id}: {self.relationship_type.value}>"


class TeamRole(str, enum.Enum):
    """Role within a relationship team."""
    RELATIONSHIP_MANAGER = "relationship_manager"
    ACCOUNT_MANAGER = "account_manager"
    EXECUTIVE_SPONSOR = "executive_sponsor"
    TECHNICAL_LEAD = "technical_lead"
    OPERATIONS_LEAD = "operations_lead"
    FINANCE_LEAD = "finance_lead"
    MEMBER = "member"


class RelationshipTeam(Base):
    """Team member assignment to a business relationship."""

    __tablename__ = "relationship_teams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    relationship_id = Column(UUID(as_uuid=True), ForeignKey("business_relationships.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Role and responsibilities
    role = Column(
        PG_ENUM('relationship_manager', 'account_manager', 'executive_sponsor', 'technical_lead', 'operations_lead', 'finance_lead', 'member', name='teamrole', create_type=False),
        nullable=False,
        default='member'
    )
    responsibilities = Column(JSON, nullable=True)  # List of responsibility strings
    is_primary = Column(Boolean, default=False, nullable=False)  # Primary contact for this role

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    left_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    business_relationship = sa_relationship("BusinessRelationship", back_populates="team_members")
    user = sa_relationship("User")

    def __repr__(self) -> str:
        return f"<RelationshipTeam {self.user_id} -> {self.relationship_id} ({self.role.value})>"
