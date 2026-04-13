"""Pydantic schemas for KPI and Perception endpoints."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator

from app.models.kpi import KPIMeasurementType, KPICategory, GapSeverity, ScoreApprovalStatus


# ===== KPI Schemas =====

class KPIBase(BaseModel):
    """Base KPI schema."""
    name: str = Field(..., min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    category: KPICategory = KPICategory.OTHER
    measurement_type: KPIMeasurementType = KPIMeasurementType.RATING
    target_value: Optional[Decimal] = None
    minimum_value: Optional[Decimal] = None
    threshold_amber: Optional[Decimal] = None
    threshold_red: Optional[Decimal] = None
    weight: Optional[Decimal] = Field(default=Decimal("1.0"))
    is_perception_based: bool = True


class KPICreate(KPIBase):
    """Schema for creating a KPI."""
    relationship_id: UUID


class KPIUpdate(BaseModel):
    """Schema for updating a KPI."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    category: Optional[KPICategory] = None
    measurement_type: Optional[KPIMeasurementType] = None
    target_value: Optional[Decimal] = None
    minimum_value: Optional[Decimal] = None
    threshold_amber: Optional[Decimal] = None
    threshold_red: Optional[Decimal] = None
    weight: Optional[Decimal] = None
    is_perception_based: Optional[bool] = None
    is_active: Optional[bool] = None


class KPIResponse(KPIBase):
    """Schema for KPI response."""
    id: UUID
    relationship_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Latest perception data (populated by service)
    latest_internal_score: Optional[Decimal] = None
    latest_external_score: Optional[Decimal] = None
    latest_gap: Optional[Decimal] = None
    latest_gap_severity: Optional[GapSeverity] = None

    class Config:
        from_attributes = True


class KPIListResponse(BaseModel):
    """Schema for KPI list."""
    items: List[KPIResponse]
    total: int


# ===== Perception Score Schemas =====

class PerceptionScoreCreate(BaseModel):
    """Schema for submitting a perception score."""
    score: Decimal = Field(..., ge=1, le=10)
    period: str = Field(..., min_length=1, max_length=20)  # e.g., "2024-Q1"
    comments: Optional[str] = None
    is_internal: bool = True

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        # Simple validation - could be enhanced
        if not v or len(v) < 4:
            raise ValueError("Period must be at least 4 characters (e.g., '2024-Q1')")
        return v


class PerceptionScoreResponse(BaseModel):
    """Schema for perception score response."""
    id: UUID
    kpi_id: UUID
    scorer_org_id: UUID
    scored_by_user_id: Optional[UUID] = None
    score: Decimal
    period: str
    comments: Optional[str] = None
    is_internal: bool
    scored_at: datetime

    # Approval workflow fields
    approval_status: Optional[ScoreApprovalStatus] = None
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    approval_comments: Optional[str] = None

    # Populated from joins
    scorer_org_name: Optional[str] = None
    scored_by_name: Optional[str] = None
    approver_name: Optional[str] = None

    class Config:
        from_attributes = True


class PerceptionScoreListResponse(BaseModel):
    """Schema for perception score list."""
    items: List[PerceptionScoreResponse]
    total: int


# ===== Perception Gap Schemas =====

class PerceptionGapResponse(BaseModel):
    """Schema for perception gap response."""
    id: UUID
    kpi_id: UUID
    period: str
    internal_score: Optional[Decimal] = None
    external_score: Optional[Decimal] = None
    gap: Optional[Decimal] = None
    gap_severity: Optional[GapSeverity] = None
    requires_action: bool
    notes: Optional[str] = None
    calculated_at: datetime

    # KPI info (populated from join)
    kpi_name: Optional[str] = None
    kpi_category: Optional[KPICategory] = None

    class Config:
        from_attributes = True


class PerceptionGapListResponse(BaseModel):
    """Schema for perception gap list."""
    items: List[PerceptionGapResponse]
    total: int
    periods: List[str]  # Available periods


class GapSummary(BaseModel):
    """Summary of gaps for a relationship."""
    relationship_id: UUID
    period: str
    total_kpis: int
    scored_kpis: int
    critical_gaps: int
    significant_gaps: int
    moderate_gaps: int
    minor_gaps: int
    average_gap: Optional[Decimal] = None
    worst_gap_kpi_name: Optional[str] = None
    worst_gap_value: Optional[Decimal] = None


# ===== External Scoring Schemas =====

class ExternalScoringContext(BaseModel):
    """Context for external perception scoring."""
    relationship_id: UUID
    relationship_name: Optional[str] = None
    organization_name: str
    period: str
    kpis: List[KPIResponse]
    introduction_text: Optional[str] = None


class ExternalScoreSubmission(BaseModel):
    """Batch submission of external scores."""
    scores: List[PerceptionScoreCreate]
    respondent_name: Optional[str] = None
    respondent_email: Optional[str] = None


# ===== Approval Workflow Schemas =====

class PerceptionScoreUpdate(BaseModel):
    """Schema for updating a perception score."""
    score: Optional[Decimal] = Field(None, ge=1, le=10)
    comments: Optional[str] = None


class ScoreApprovalAction(BaseModel):
    """Schema for approving or rejecting a perception score."""
    comments: Optional[str] = None


class PendingApprovalResponse(BaseModel):
    """Schema for a pending approval item with enriched context."""
    id: UUID
    kpi_id: UUID
    kpi_name: Optional[str] = None
    kpi_category: Optional[KPICategory] = None
    relationship_id: Optional[UUID] = None
    relationship_name: Optional[str] = None
    scorer_org_id: UUID
    scored_by_user_id: Optional[UUID] = None
    score: Decimal
    period: str
    comments: Optional[str] = None
    is_internal: bool
    scored_at: datetime
    approval_status: ScoreApprovalStatus

    # Populated from joins
    scorer_org_name: Optional[str] = None
    scored_by_name: Optional[str] = None

    class Config:
        from_attributes = True
