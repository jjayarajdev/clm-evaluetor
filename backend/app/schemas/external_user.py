"""Pydantic schemas for External User endpoints."""

from datetime import datetime
from uuid import UUID
from typing import Optional, List

from pydantic import BaseModel, Field, EmailStr


# ===== Base Schemas =====

class ExternalUserBase(BaseModel):
    """Base external user schema."""
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=255)
    company_name: Optional[str] = Field(None, max_length=255)
    title: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)


# ===== Request Schemas =====

class ExternalUserCreate(ExternalUserBase):
    """Schema for creating (inviting) an external user."""
    organization_id: Optional[UUID] = None
    notes: Optional[str] = None


class ExternalUserUpdate(BaseModel):
    """Schema for updating an external user."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    company_name: Optional[str] = Field(None, max_length=255)
    title: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    organization_id: Optional[UUID] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class ExternalUserInvite(BaseModel):
    """Schema for inviting an external user with contract share."""
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=255)
    company_name: Optional[str] = Field(None, max_length=255)
    organization_id: Optional[UUID] = None
    contract_ids: List[UUID] = Field(default_factory=list)
    can_download: bool = False
    can_comment: bool = True
    message: Optional[str] = None
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


# ===== Response Schemas =====

class ExternalUserSummary(BaseModel):
    """Minimal external user info for embedding in other responses."""
    id: UUID
    email: str
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class ExternalUserResponse(ExternalUserBase):
    """Schema for external user response."""
    id: UUID
    tenant_id: UUID
    organization_id: Optional[UUID] = None
    is_active: bool
    invited_by_id: Optional[UUID] = None
    invited_at: Optional[datetime] = None
    last_access_at: Optional[datetime] = None
    access_count: int
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExternalUserWithShares(ExternalUserResponse):
    """External user with their contract shares."""
    shared_contracts_count: int = 0

    class Config:
        from_attributes = True


class ExternalUserListResponse(BaseModel):
    """Schema for paginated external user list."""
    items: List[ExternalUserResponse]
    total: int
    page: int
    page_size: int
    pages: int
