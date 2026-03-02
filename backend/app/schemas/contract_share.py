"""Pydantic schemas for Contract Share endpoints."""

from datetime import datetime
from uuid import UUID
from typing import Optional, List

from pydantic import BaseModel, Field

from app.schemas.external_user import ExternalUserSummary


# ===== Request Schemas =====

class ContractShareCreate(BaseModel):
    """Schema for sharing a contract with an external user."""
    external_user_id: UUID
    can_download: bool = False
    can_comment: bool = True
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)
    message: Optional[str] = None


class ContractShareBulkCreate(BaseModel):
    """Schema for sharing a contract with multiple external users."""
    external_user_ids: List[UUID] = Field(..., min_length=1)
    can_download: bool = False
    can_comment: bool = True
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)
    message: Optional[str] = None


class ContractShareUpdate(BaseModel):
    """Schema for updating a contract share."""
    can_download: Optional[bool] = None
    can_comment: Optional[bool] = None
    expires_at: Optional[datetime] = None


# ===== Response Schemas =====

class ContractShareSummary(BaseModel):
    """Minimal contract share info."""
    id: UUID
    external_user_id: UUID
    can_download: bool
    can_comment: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ContractShareResponse(BaseModel):
    """Schema for contract share response."""
    id: UUID
    contract_id: UUID
    external_user_id: UUID
    shared_by_id: UUID
    can_download: bool
    can_comment: bool
    expires_at: Optional[datetime] = None
    message: Optional[str] = None
    access_count: int
    last_access_at: Optional[datetime] = None
    is_revoked: bool
    revoked_at: Optional[datetime] = None
    revoked_by_id: Optional[UUID] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContractShareWithUser(ContractShareResponse):
    """Contract share with external user details."""
    external_user: ExternalUserSummary

    class Config:
        from_attributes = True


class ContractShareListResponse(BaseModel):
    """Schema for list of contract shares."""
    items: List[ContractShareWithUser]
    total: int


class ShareInviteResponse(BaseModel):
    """Response for share invitation with access link."""
    share: ContractShareResponse
    access_url: str
    token: str
