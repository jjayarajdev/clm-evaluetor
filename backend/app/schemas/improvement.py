"""Pydantic schemas for Improvement Point endpoints."""

from datetime import datetime, date
from uuid import UUID
from typing import Optional, List

from pydantic import BaseModel, Field

from app.models.improvement import (
    ImprovementPriority,
    ImprovementStatus,
    ImprovementSource,
    ActionStatus,
)


# ===== Action Schemas =====

class ActionBase(BaseModel):
    """Base action schema."""
    description: str = Field(..., min_length=1)
    sequence: Optional[int] = None
    owner_id: Optional[UUID] = None
    due_date: Optional[date] = None


class ActionCreate(ActionBase):
    """Schema for creating an action."""
    pass


class ActionUpdate(BaseModel):
    """Schema for updating an action."""
    description: Optional[str] = Field(None, min_length=1)
    status: Optional[ActionStatus] = None
    sequence: Optional[int] = None
    owner_id: Optional[UUID] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None
    blocker_reason: Optional[str] = None


class ActionResponse(ActionBase):
    """Schema for action response."""
    id: UUID
    improvement_id: UUID
    status: ActionStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    blocker_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Populated from join
    owner_name: Optional[str] = None

    class Config:
        from_attributes = True


# ===== Improvement Point Schemas =====

class ImprovementBase(BaseModel):
    """Base improvement schema."""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    source: ImprovementSource = ImprovementSource.MANUAL
    priority: ImprovementPriority = ImprovementPriority.MEDIUM
    owner_id: Optional[UUID] = None
    assigned_org_id: Optional[UUID] = None
    due_date: Optional[date] = None
    target_outcome: Optional[str] = None


class ImprovementCreate(ImprovementBase):
    """Schema for creating an improvement point."""
    relationship_id: UUID
    kpi_id: Optional[UUID] = None
    gap_id: Optional[UUID] = None


class ImprovementUpdate(BaseModel):
    """Schema for updating an improvement point."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    priority: Optional[ImprovementPriority] = None
    status: Optional[ImprovementStatus] = None
    owner_id: Optional[UUID] = None
    assigned_org_id: Optional[UUID] = None
    due_date: Optional[date] = None
    target_outcome: Optional[str] = None
    actual_outcome: Optional[str] = None
    impact_score: Optional[int] = Field(None, ge=1, le=10)


class ImprovementResponse(ImprovementBase):
    """Schema for improvement point response."""
    id: UUID
    relationship_id: UUID
    kpi_id: Optional[UUID] = None
    gap_id: Optional[UUID] = None
    status: ImprovementStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    actual_outcome: Optional[str] = None
    impact_score: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    # Computed
    progress_percentage: Optional[int] = None
    action_count: Optional[int] = None
    completed_action_count: Optional[int] = None

    # Populated from joins
    owner_name: Optional[str] = None
    assigned_org_name: Optional[str] = None
    kpi_name: Optional[str] = None
    relationship_name: Optional[str] = None

    # Nested
    actions: Optional[List[ActionResponse]] = None

    class Config:
        from_attributes = True


class ImprovementListResponse(BaseModel):
    """Schema for improvement list."""
    items: List[ImprovementResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ImprovementSummary(BaseModel):
    """Summary of improvements for a relationship."""
    relationship_id: UUID
    total: int
    open: int
    in_progress: int
    blocked: int
    completed: int
    cancelled: int
    overdue: int
    critical_priority: int
    high_priority: int


# ===== Improvement Filters =====

class ImprovementFilters(BaseModel):
    """Filters for improvement list."""
    status: Optional[List[ImprovementStatus]] = None
    priority: Optional[List[ImprovementPriority]] = None
    owner_id: Optional[UUID] = None
    kpi_id: Optional[UUID] = None
    source: Optional[ImprovementSource] = None
    overdue_only: Optional[bool] = None
