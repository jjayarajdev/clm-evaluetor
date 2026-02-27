"""Audit log router."""

import math
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import AdminUser, CurrentTenantId
from app.database import get_db
from app.models.audit import AuditAction
from app.schemas.audit import AuditLogFilter, AuditLogListResponse, AuditLogResponse
from app.services.audit import AuditService

router = APIRouter(prefix="/api/audit", tags=["Audit"])


def log_to_response(log) -> AuditLogResponse:
    """Convert AuditLog model to AuditLogResponse schema."""
    return AuditLogResponse(
        id=str(log.id),
        user_id=str(log.user_id) if log.user_id else None,
        username=log.user.username if log.user else None,
        action=log.action.value,
        resource_type=log.resource_type,
        resource_id=log.resource_id,
        details=log.details,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        created_at=log.created_at,
    )


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    admin: AdminUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str | None = None,
    action: AuditAction | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> AuditLogListResponse:
    """List audit logs with optional filters (admin only).

    Args:
        admin: Authenticated admin user.
        tenant_id: Current tenant ID for isolation.
        db: Database session.
        user_id: Filter by user ID.
        action: Filter by action type.
        resource_type: Filter by resource type.
        resource_id: Filter by resource ID.
        start_date: Filter by start date.
        end_date: Filter by end date.
        page: Page number.
        page_size: Results per page.

    Returns:
        Paginated list of audit logs.
    """
    service = AuditService(db, tenant_id=tenant_id)
    filters = AuditLogFilter(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        start_date=start_date,
        end_date=end_date,
    )

    logs, total = await service.list_logs(filters, page, page_size)

    return AuditLogListResponse(
        logs=[log_to_response(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/stats")
async def get_audit_stats(
    admin: AdminUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(7, ge=1, le=90),
) -> dict:
    """Get audit action statistics (admin only).

    Args:
        admin: Authenticated admin user.
        tenant_id: Current tenant ID for isolation.
        db: Database session.
        days: Number of days to look back.

    Returns:
        Dictionary with action counts.
    """
    service = AuditService(db, tenant_id=tenant_id)
    stats = await service.get_action_stats(days)

    return {
        "period_days": days,
        "actions": stats,
        "total": sum(stats.values()),
    }


@router.get("/resource/{resource_type}/{resource_id}")
async def get_resource_audit_history(
    resource_type: str,
    resource_id: str,
    admin: AdminUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AuditLogResponse]:
    """Get audit history for a specific resource (admin only).

    Args:
        resource_type: Type of resource (e.g., "contract", "user").
        resource_id: ID of the resource.
        admin: Authenticated admin user.
        tenant_id: Current tenant ID for isolation.
        db: Database session.

    Returns:
        List of audit logs for the resource.
    """
    service = AuditService(db, tenant_id=tenant_id)
    logs = await service.get_resource_history(resource_type, resource_id)

    return [log_to_response(log) for log in logs]
