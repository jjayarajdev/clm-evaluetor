"""Pydantic schemas for Organization endpoints."""

from datetime import datetime
from uuid import UUID
from typing import Optional, List

from pydantic import BaseModel, Field, EmailStr

from app.models.organization import OrganizationType, OrganizationSize


# ===== Base Schemas =====

class OrganizationBase(BaseModel):
    """Base organization schema."""
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    org_type: OrganizationType = OrganizationType.CUSTOMER
    industry: Optional[str] = Field(None, max_length=100)
    size: Optional[OrganizationSize] = None
    region: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None
    primary_contact_name: Optional[str] = Field(None, max_length=255)
    primary_contact_email: Optional[EmailStr] = None
    primary_contact_phone: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


# ===== Request Schemas =====

class OrganizationCreate(OrganizationBase):
    """Schema for creating an organization."""
    relationship_owner_id: Optional[UUID] = None


class OrganizationUpdate(BaseModel):
    """Schema for updating an organization."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    org_type: Optional[OrganizationType] = None
    industry: Optional[str] = Field(None, max_length=100)
    size: Optional[OrganizationSize] = None
    region: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None
    primary_contact_name: Optional[str] = Field(None, max_length=255)
    primary_contact_email: Optional[EmailStr] = None
    primary_contact_phone: Optional[str] = Field(None, max_length=50)
    relationship_owner_id: Optional[UUID] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


# ===== Response Schemas =====

class OrganizationResponse(OrganizationBase):
    """Schema for organization response."""
    id: UUID
    relationship_owner_id: Optional[UUID] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrganizationListResponse(BaseModel):
    """Schema for paginated organization list."""
    items: List[OrganizationResponse]
    total: int
    page: int
    page_size: int
    pages: int


class OrganizationSummary(BaseModel):
    """Minimal organization info for embedding in other responses."""
    id: UUID
    name: str
    code: str
    org_type: OrganizationType

    class Config:
        from_attributes = True
