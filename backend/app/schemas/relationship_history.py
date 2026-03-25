"""Pydantic schemas for Relationship Performance Status History endpoints."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import Optional, List

from pydantic import BaseModel, Field

from app.models.relationship_history import PerformanceStatus


class RelationshipHistoryCreate(BaseModel):
    """Schema for manually recording a relationship status history entry."""
    status: PerformanceStatus
    previous_status: Optional[PerformanceStatus] = None
    overall_score: Optional[Decimal] = Field(None, ge=0, le=100)
    period: str = Field(..., min_length=4, max_length=20)
    notes: Optional[str] = None
    trigger: Optional[str] = Field(None, max_length=100)


class RelationshipHistoryResponse(BaseModel):
    """Schema for relationship status history response."""
    id: UUID
    tenant_id: UUID
    relationship_id: UUID
    status: PerformanceStatus
    previous_status: Optional[PerformanceStatus] = None
    overall_score: Optional[Decimal] = None
    period: str
    recorded_date: datetime
    recorded_by: Optional[UUID] = None
    notes: Optional[str] = None
    trigger: Optional[str] = None
    created_at: datetime

    # Populated from joins
    recorded_by_name: Optional[str] = None

    class Config:
        from_attributes = True


class RelationshipHistoryListResponse(BaseModel):
    """Schema for paginated relationship status history list."""
    items: List[RelationshipHistoryResponse]
    total: int
    page: int
    page_size: int
    pages: int


class PerformanceTrendPoint(BaseModel):
    """A single point in a performance trend chart."""
    period: str
    score: Optional[Decimal] = None
    status: PerformanceStatus


class PerformanceTrendResponse(BaseModel):
    """Performance trend data for charting."""
    relationship_id: UUID
    trend: List[PerformanceTrendPoint]
    total_entries: int
