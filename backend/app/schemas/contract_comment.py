"""Pydantic schemas for Contract Comment endpoints."""

from datetime import datetime
from uuid import UUID
from typing import Optional, List

from pydantic import BaseModel, Field


# ===== Request Schemas =====

class ContractCommentCreate(BaseModel):
    """Schema for creating a comment on a contract."""
    content: str = Field(..., min_length=1, max_length=10000)
    parent_id: Optional[UUID] = None
    clause_id: Optional[UUID] = None
    section_reference: Optional[str] = Field(None, max_length=100)
    is_internal: bool = False


class ContractCommentUpdate(BaseModel):
    """Schema for updating a comment."""
    content: Optional[str] = Field(None, min_length=1, max_length=10000)


# ===== Response Schemas =====

class CommentAuthor(BaseModel):
    """Author information for a comment."""
    id: UUID
    name: str
    email: Optional[str] = None
    is_internal: bool

    class Config:
        from_attributes = True


class ContractCommentSummary(BaseModel):
    """Minimal comment info."""
    id: UUID
    content: str
    author_name: str
    is_internal_author: bool
    is_internal: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ContractCommentResponse(BaseModel):
    """Schema for contract comment response."""
    id: UUID
    contract_id: UUID
    user_id: Optional[UUID] = None
    external_user_id: Optional[UUID] = None
    parent_id: Optional[UUID] = None
    content: str
    clause_id: Optional[UUID] = None
    section_reference: Optional[str] = None
    is_internal: bool
    is_resolved: bool
    resolved_by_id: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    is_deleted: bool
    author_name: str
    author_email: Optional[str] = None
    is_internal_author: bool
    created_at: datetime
    updated_at: datetime
    reply_count: int = 0

    class Config:
        from_attributes = True


class ContractCommentWithReplies(ContractCommentResponse):
    """Comment with nested replies."""
    replies: List["ContractCommentResponse"] = []

    class Config:
        from_attributes = True


class ContractCommentListResponse(BaseModel):
    """Schema for list of contract comments."""
    items: List[ContractCommentResponse]
    total: int


class ContractCommentThreadResponse(BaseModel):
    """Schema for threaded comments on a contract."""
    items: List[ContractCommentWithReplies]
    total: int


# Allow forward reference for recursive type
ContractCommentWithReplies.model_rebuild()
