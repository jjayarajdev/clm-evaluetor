"""Pydantic schemas for Business Unit endpoints."""

from datetime import datetime
from uuid import UUID
from typing import Optional, List

from pydantic import BaseModel, Field


# ===== Base Schemas =====

class BusinessUnitBase(BaseModel):
    """Base business unit schema."""
    name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None


# ===== Request Schemas =====

class BusinessUnitCreate(BusinessUnitBase):
    """Schema for creating a business unit."""
    parent_id: Optional[UUID] = None
    head_user_id: Optional[UUID] = None


class BusinessUnitUpdate(BaseModel):
    """Schema for updating a business unit."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
    head_user_id: Optional[UUID] = None
    is_active: Optional[bool] = None


# ===== Response Schemas =====

class BusinessUnitSummary(BaseModel):
    """Minimal business unit info for embedding in other responses."""
    id: UUID
    name: str
    code: str
    is_active: bool

    class Config:
        from_attributes = True


class BusinessUnitResponse(BusinessUnitBase):
    """Schema for business unit response."""
    id: UUID
    tenant_id: UUID
    parent_id: Optional[UUID] = None
    head_user_id: Optional[UUID] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BusinessUnitWithHierarchy(BusinessUnitResponse):
    """Business unit with parent and children info."""
    parent: Optional[BusinessUnitSummary] = None
    children: List[BusinessUnitSummary] = []
    full_path: str

    class Config:
        from_attributes = True


class BusinessUnitListResponse(BaseModel):
    """Schema for paginated business unit list."""
    items: List[BusinessUnitResponse]
    total: int
    page: int
    page_size: int
    pages: int


class BusinessUnitTree(BaseModel):
    """Business unit with nested children for tree view."""
    id: UUID
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool
    head_user_id: Optional[UUID] = None
    children: List["BusinessUnitTree"] = []

    class Config:
        from_attributes = True


# Allow forward reference for recursive type
BusinessUnitTree.model_rebuild()
