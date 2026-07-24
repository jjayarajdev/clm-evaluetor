"""Pydantic schemas for contract group endpoints."""

from datetime import datetime
from typing import Any, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

GroupType = Literal["manual", "upload_batch", "auto_family"]
FindingStatus = Literal["open", "resolved", "dismissed"]


# ===== Request Schemas =====

class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    parent_group_id: Optional[UUID] = None
    owner_user_id: Optional[UUID] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    parent_group_id: Optional[UUID] = None
    owner_user_id: Optional[UUID] = None


class GroupMemberAdd(BaseModel):
    contract_ids: List[UUID] = Field(..., min_length=1)


class FindingStatusUpdate(BaseModel):
    status: Literal["open", "dismissed"]


# ===== Response Schemas =====

class GroupSummary(BaseModel):
    id: UUID
    name: str
    group_type: GroupType
    parent_group_id: Optional[UUID] = None
    owner_user_id: Optional[UUID] = None
    member_count: int = 0

    class Config:
        from_attributes = True


class GroupMemberContract(BaseModel):
    """Contract summary embedded in group detail."""
    contract_id: UUID
    filename: str
    contract_type: Optional[str] = None
    counterparty: Optional[str] = None
    status: Optional[str] = None
    risk_level: Optional[str] = None
    expiration_date: Optional[str] = None
    source: str
    member_id: UUID


class GroupFindingResponse(BaseModel):
    id: UUID
    group_id: Optional[UUID] = None
    contract_id: UUID
    contract_filename: Optional[str] = None
    finding_type: str
    reference_label: str
    reference_type: Optional[str] = None
    details: dict[str, Any] = {}
    status: FindingStatus
    created_at: datetime

    class Config:
        from_attributes = True


class GroupResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: Optional[str] = None
    group_type: GroupType
    parent_group_id: Optional[UUID] = None
    owner_user_id: Optional[UUID] = None
    owner_name: Optional[str] = None
    root_contract_id: Optional[UUID] = None
    upload_batch_id: Optional[str] = None
    member_count: int = 0
    open_finding_count: int = 0
    child_groups: List[GroupSummary] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GroupDetailResponse(GroupResponse):
    members: List[GroupMemberContract] = []
    findings: List[GroupFindingResponse] = []


class GroupListResponse(BaseModel):
    items: List[GroupResponse]
    total: int
    page: int
    page_size: int
    pages: int
