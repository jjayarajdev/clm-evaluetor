"""Pydantic schemas for audit logging."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.audit import AuditAction


class AuditLogCreate(BaseModel):
    """Schema for creating an audit log entry."""

    action: AuditAction
    resource_type: str | None = None
    resource_id: str | None = None
    details: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None


class AuditLogResponse(BaseModel):
    """Schema for audit log response."""

    id: str
    user_id: str | None
    username: str | None  # Joined from user
    action: str
    resource_type: str | None
    resource_id: str | None
    details: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Schema for paginated audit log list."""

    logs: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class AuditLogFilter(BaseModel):
    """Schema for filtering audit logs."""

    user_id: str | None = None
    action: AuditAction | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
