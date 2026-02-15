"""Pydantic schemas for Business Relationship endpoints."""

from datetime import datetime, date
from uuid import UUID
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field

from app.models.relationship import RelationshipType, RelationshipStatus, GovernanceTier, TeamRole
from app.schemas.organization import OrganizationSummary


# ===== Team Member Schemas =====

class TeamMemberBase(BaseModel):
    """Base team member schema."""
    user_id: UUID
    role: TeamRole = TeamRole.MEMBER
    responsibilities: Optional[List[str]] = None
    is_primary: bool = False


class TeamMemberCreate(TeamMemberBase):
    """Schema for adding a team member."""
    pass


class TeamMemberUpdate(BaseModel):
    """Schema for updating a team member."""
    role: Optional[TeamRole] = None
    responsibilities: Optional[List[str]] = None
    is_primary: Optional[bool] = None
    is_active: Optional[bool] = None


class TeamMemberResponse(TeamMemberBase):
    """Schema for team member response."""
    id: UUID
    relationship_id: UUID
    is_active: bool
    joined_at: datetime
    left_at: Optional[datetime] = None
    user_name: Optional[str] = None  # Populated from join

    class Config:
        from_attributes = True


# ===== Relationship Schemas =====

class RelationshipBase(BaseModel):
    """Base relationship schema."""
    org_a_id: UUID
    org_b_id: UUID
    relationship_type: RelationshipType
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    governance_tier: Optional[GovernanceTier] = GovernanceTier.OPERATIONAL
    governance_config: Optional[Dict[str, Any]] = None
    start_date: Optional[datetime] = None
    review_frequency_days: Optional[int] = 30


class RelationshipCreate(RelationshipBase):
    """Schema for creating a relationship."""
    pass


class RelationshipUpdate(BaseModel):
    """Schema for updating a relationship."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    status: Optional[RelationshipStatus] = None
    governance_tier: Optional[GovernanceTier] = None
    governance_config: Optional[Dict[str, Any]] = None
    review_frequency_days: Optional[int] = None
    next_review_date: Optional[datetime] = None


class RelationshipResponse(BaseModel):
    """Schema for relationship response."""
    id: UUID
    org_a_id: UUID
    org_b_id: UUID
    relationship_type: RelationshipType
    status: RelationshipStatus
    name: Optional[str] = None
    description: Optional[str] = None
    health_score: Optional[int] = None
    last_health_calculation: Optional[datetime] = None
    governance_tier: Optional[GovernanceTier] = None
    governance_config: Optional[Dict[str, Any]] = None
    start_date: Optional[datetime] = None
    review_frequency_days: Optional[int] = None
    next_review_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Nested data
    org_a: Optional[OrganizationSummary] = None
    org_b: Optional[OrganizationSummary] = None
    team_members: Optional[List[TeamMemberResponse]] = None

    class Config:
        from_attributes = True


class RelationshipListResponse(BaseModel):
    """Schema for paginated relationship list."""
    items: List[RelationshipResponse]
    total: int
    page: int
    page_size: int
    pages: int


class RelationshipSummary(BaseModel):
    """Minimal relationship info for embedding in other responses."""
    id: UUID
    name: Optional[str] = None
    relationship_type: RelationshipType
    status: RelationshipStatus
    health_score: Optional[int] = None

    class Config:
        from_attributes = True


# ===== Health Score Schemas =====

class HealthScoreBreakdown(BaseModel):
    """Breakdown of health score factors."""
    compliance_score: Optional[float] = None
    sla_score: Optional[float] = None
    perception_score: Optional[float] = None
    improvement_score: Optional[float] = None
    overall_score: int
    calculated_at: datetime


class HealthScoreResponse(BaseModel):
    """Response for health score calculation."""
    relationship_id: UUID
    health_score: int
    breakdown: HealthScoreBreakdown
    trend: Optional[str] = None  # "improving", "stable", "declining"
    factors: Optional[Dict[str, Any]] = None
