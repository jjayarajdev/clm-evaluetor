"""Audit logging utilities and helpers."""

from typing import Any

from fastapi import BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditAction
from app.services.audit import AuditService


def get_client_ip(request: Request) -> str | None:
    """Extract client IP from request.

    Args:
        request: FastAPI request object.

    Returns:
        Client IP address or None.
    """
    # Check for forwarded IP (behind proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # Check for real IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client
    if request.client:
        return request.client.host

    return None


def get_user_agent(request: Request) -> str | None:
    """Extract user agent from request.

    Args:
        request: FastAPI request object.

    Returns:
        User agent string or None.
    """
    return request.headers.get("User-Agent")


async def log_audit(
    db: AsyncSession,
    action: AuditAction,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    """Log an audit action.

    Args:
        db: Database session.
        action: The action being performed.
        user_id: ID of the user performing the action.
        resource_type: Type of resource affected.
        resource_id: ID of the resource affected.
        details: Additional details.
        request: Optional FastAPI request for IP/user agent.
    """
    service = AuditService(db)

    ip_address = get_client_ip(request) if request else None
    user_agent = get_user_agent(request) if request else None

    await service.log_action(
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
    )


def log_audit_background(
    background_tasks: BackgroundTasks,
    db: AsyncSession,
    action: AuditAction,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Schedule audit logging as a background task.

    Note: This is non-blocking but requires the db session to remain valid.
    For truly async audit logging, consider using a message queue.

    Args:
        background_tasks: FastAPI background tasks.
        db: Database session.
        action: The action being performed.
        user_id: ID of the user performing the action.
        resource_type: Type of resource affected.
        resource_id: ID of the resource affected.
        details: Additional details.
        ip_address: Client IP address.
        user_agent: Client user agent.
    """

    async def _log():
        service = AuditService(db)
        await service.log_action(
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    background_tasks.add_task(_log)
