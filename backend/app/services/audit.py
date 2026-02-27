"""Audit logging service."""

import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.audit import AuditAction, AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogFilter


class AuditService:
    """Service for audit logging operations."""

    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID | None = None) -> None:
        """Initialize with database session and optional tenant filter."""
        self.db = db
        self.tenant_id = tenant_id

    async def log_action(
        self,
        action: AuditAction,
        user_id: str | uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Log an audit action.

        Args:
            action: The action being performed.
            user_id: ID of the user performing the action.
            resource_type: Type of resource affected (e.g., "contract", "user").
            resource_id: ID of the resource affected.
            details: Additional details as JSON.
            ip_address: Client IP address.
            user_agent: Client user agent string.

        Returns:
            Created AuditLog entry.
        """
        log = AuditLog(
            user_id=uuid.UUID(str(user_id)) if user_id else None,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db.add(log)
        await self.db.flush()

        return log

    async def list_logs(
        self,
        filters: AuditLogFilter | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[Sequence[AuditLog], int]:
        """List audit logs with optional filters and pagination.

        Args:
            filters: Optional filters.
            page: Page number (1-indexed).
            page_size: Number of results per page.

        Returns:
            Tuple of (logs list, total count).
        """
        query = select(AuditLog).options(joinedload(AuditLog.user))

        # Apply tenant filter via user
        if self.tenant_id is not None:
            query = query.join(User, AuditLog.user_id == User.id).where(
                User.tenant_id == self.tenant_id
            )

        # Apply filters
        if filters:
            if filters.user_id:
                query = query.where(AuditLog.user_id == filters.user_id)
            if filters.action:
                query = query.where(AuditLog.action == filters.action)
            if filters.resource_type:
                query = query.where(AuditLog.resource_type == filters.resource_type)
            if filters.resource_id:
                query = query.where(AuditLog.resource_id == filters.resource_id)
            if filters.start_date:
                query = query.where(AuditLog.created_at >= filters.start_date)
            if filters.end_date:
                query = query.where(AuditLog.created_at <= filters.end_date)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size).order_by(AuditLog.created_at.desc())

        # Execute query
        result = await self.db.execute(query)
        logs = result.scalars().unique().all()

        return logs, total

    async def get_user_activity(
        self,
        user_id: str | uuid.UUID,
        limit: int = 10,
    ) -> Sequence[AuditLog]:
        """Get recent activity for a specific user.

        Args:
            user_id: User's ID.
            limit: Maximum number of entries to return.

        Returns:
            List of recent audit logs for the user.
        """
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_resource_history(
        self,
        resource_type: str,
        resource_id: str,
    ) -> Sequence[AuditLog]:
        """Get audit history for a specific resource.

        Args:
            resource_type: Type of resource.
            resource_id: ID of the resource.

        Returns:
            List of audit logs for the resource.
        """
        query = (
            select(AuditLog)
            .options(joinedload(AuditLog.user))
            .where(
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id,
            )
        )

        # Apply tenant filter via user
        if self.tenant_id is not None:
            query = query.join(User, AuditLog.user_id == User.id).where(
                User.tenant_id == self.tenant_id
            )

        query = query.order_by(AuditLog.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().unique().all()

    async def count_actions_since(
        self,
        since: datetime,
        action: AuditAction | None = None,
    ) -> int:
        """Count actions since a given time.

        Args:
            since: Start datetime.
            action: Optional specific action to count.

        Returns:
            Count of actions.
        """
        query = select(func.count(AuditLog.id)).where(AuditLog.created_at >= since)

        if action:
            query = query.where(AuditLog.action == action)

        result = await self.db.execute(query)
        return result.scalar() or 0

    async def get_action_stats(
        self,
        days: int = 7,
    ) -> dict[str, int]:
        """Get action statistics for the last N days.

        Args:
            days: Number of days to look back.

        Returns:
            Dictionary with action counts.
        """
        since = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        query = (
            select(AuditLog.action, func.count(AuditLog.id))
            .where(AuditLog.created_at >= since)
        )

        # Apply tenant filter via user
        if self.tenant_id is not None:
            query = query.join(User, AuditLog.user_id == User.id).where(
                User.tenant_id == self.tenant_id
            )

        query = query.group_by(AuditLog.action)
        result = await self.db.execute(query)

        stats = {action.value: 0 for action in AuditAction}
        for action, count in result.all():
            stats[action.value] = count

        return stats
