"""Pydantic schemas for Organization Officer endpoints."""

from datetime import datetime
from uuid import UUID
from typing import Optional, List

from pydantic import BaseModel, Field, EmailStr

from app.models.organization_officer import GovernanceRole, OfficerSide


# ===== Request Schemas =====

class OfficerCreate(BaseModel):
    """Schema for creating an organization officer."""
    name: str = Field(..., min_length=1, max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    department: Optional[str] = Field(None, max_length=100)
    governance_role: Optional[GovernanceRole] = None
    side: Optional[OfficerSide] = None
    is_primary: bool = False
    notes: Optional[str] = None


class OfficerUpdate(BaseModel):
    """Schema for updating an organization officer."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    department: Optional[str] = Field(None, max_length=100)
    governance_role: Optional[GovernanceRole] = None
    side: Optional[OfficerSide] = None
    is_primary: Optional[bool] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


# ===== Response Schemas =====

class OfficerResponse(BaseModel):
    """Schema for organization officer response."""
    id: UUID
    organization_id: UUID
    name: str
    title: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    governance_role: Optional[GovernanceRole] = None
    side: Optional[OfficerSide] = None
    is_primary: bool
    is_active: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OfficerListResponse(BaseModel):
    """Schema for paginated officer list."""
    items: List[OfficerResponse]
    total: int
