"""Pydantic schemas for Service Portfolio endpoints."""

from datetime import datetime
from uuid import UUID
from typing import Optional, List

from pydantic import BaseModel, Field

from app.models.service_portfolio import ServiceType, ServiceStatus


# ===== Base Schemas =====

class ServicePortfolioBase(BaseModel):
    """Base service portfolio schema."""
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    service_type: ServiceType = ServiceType.OTHER
    status: ServiceStatus = ServiceStatus.ACTIVE


# ===== Request Schemas =====

class ServicePortfolioCreate(ServicePortfolioBase):
    """Schema for creating a service portfolio entry."""
    organization_id: UUID


class ServicePortfolioUpdate(BaseModel):
    """Schema for updating a service portfolio entry."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    service_type: Optional[ServiceType] = None
    status: Optional[ServiceStatus] = None
    organization_id: Optional[UUID] = None


class RelationshipServiceCreate(BaseModel):
    """Schema for linking a service to a relationship."""
    relationship_id: UUID
    scope: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: bool = True


# ===== Response Schemas =====

class ServicePortfolioResponse(ServicePortfolioBase):
    """Schema for service portfolio response."""
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ServicePortfolioListResponse(BaseModel):
    """Schema for paginated service portfolio list."""
    items: List[ServicePortfolioResponse]
    total: int
    page: int
    page_size: int
    pages: int


class RelationshipServiceResponse(BaseModel):
    """Schema for relationship service link response."""
    id: UUID
    relationship_id: UUID
    service_portfolio_id: UUID
    scope: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ServicePortfolioSummary(BaseModel):
    """Minimal service portfolio info for embedding in other responses."""
    id: UUID
    name: str
    code: str
    service_type: ServiceType
    status: ServiceStatus

    class Config:
        from_attributes = True
