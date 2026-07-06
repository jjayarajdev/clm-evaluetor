"""API endpoints for notification history and management.

Provides:
- Notification log viewing
- Retry failed notifications
- Notification statistics
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db, require_admin_if_enterprise
from app.models.notification import (
    NotificationChannel,
    NotificationLog,
    NotificationStatus,
    NotificationTemplate,
)
from app.services.notification_service import NotificationService

router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    dependencies=[Depends(require_admin_if_enterprise)],
)


class NotificationSummary(BaseModel):
    """Summary of a notification."""
    id: str
    channel: str
    recipient_email: str
    subject: str
    status: str
    sent_at: Optional[datetime]
    created_at: datetime


class NotificationDetail(BaseModel):
    """Detailed notification information."""
    id: str
    template_name: Optional[str]
    event_id: Optional[str]
    channel: str
    recipient_email: str
    recipient_name: Optional[str]
    recipient_type: Optional[str]
    subject: str
    body: str
    status: str
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    attempts: int
    error_message: Optional[str]
    created_at: datetime


class NotificationStats(BaseModel):
    """Notification statistics."""
    total_sent: int
    total_pending: int
    total_failed: int
    total_delivered: int
    sent_last_24h: int
    failed_last_24h: int
    by_channel: dict
    by_status: dict


@router.get("/", response_model=list[NotificationSummary])
async def list_notifications(
    status: Optional[NotificationStatus] = None,
    channel: Optional[NotificationChannel] = None,
    event_id: Optional[UUID] = None,
    recipient: Optional[str] = None,
    days: int = Query(default=7, le=90),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List notifications with filters."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    query = select(NotificationLog).where(NotificationLog.created_at >= cutoff)

    if status:
        query = query.where(NotificationLog.status == status)
    if channel:
        query = query.where(NotificationLog.channel == channel)
    if event_id:
        query = query.where(NotificationLog.event_id == event_id)
    if recipient:
        query = query.where(NotificationLog.recipient_email.ilike(f"%{recipient}%"))

    query = query.order_by(NotificationLog.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    notifications = result.scalars().all()

    return [
        NotificationSummary(
            id=str(n.id),
            channel=n.channel.value if n.channel else "unknown",
            recipient_email=n.recipient_email,
            subject=n.subject,
            status=n.status.value,
            sent_at=n.sent_at,
            created_at=n.created_at,
        )
        for n in notifications
    ]


@router.get("/stats", response_model=NotificationStats)
async def get_notification_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get notification statistics."""
    # Status counts
    status_counts = {}
    for status in NotificationStatus:
        result = await db.execute(
            select(func.count(NotificationLog.id)).where(
                NotificationLog.status == status
            )
        )
        status_counts[status.value] = result.scalar() or 0

    # Channel counts
    channel_counts = {}
    for channel in NotificationChannel:
        result = await db.execute(
            select(func.count(NotificationLog.id)).where(
                NotificationLog.channel == channel
            )
        )
        channel_counts[channel.value] = result.scalar() or 0

    # Last 24 hours
    cutoff_24h = datetime.utcnow() - timedelta(hours=24)

    sent_24h = await db.execute(
        select(func.count(NotificationLog.id)).where(
            and_(
                NotificationLog.status == NotificationStatus.sent,
                NotificationLog.sent_at >= cutoff_24h,
            )
        )
    )
    failed_24h = await db.execute(
        select(func.count(NotificationLog.id)).where(
            and_(
                NotificationLog.status == NotificationStatus.failed,
                NotificationLog.created_at >= cutoff_24h,
            )
        )
    )

    return NotificationStats(
        total_sent=status_counts.get("sent", 0),
        total_pending=status_counts.get("pending", 0),
        total_failed=status_counts.get("failed", 0),
        total_delivered=status_counts.get("delivered", 0),
        sent_last_24h=sent_24h.scalar() or 0,
        failed_last_24h=failed_24h.scalar() or 0,
        by_channel=channel_counts,
        by_status=status_counts,
    )


@router.get("/{notification_id}", response_model=NotificationDetail)
async def get_notification(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get notification details."""
    result = await db.execute(
        select(NotificationLog)
        .where(NotificationLog.id == notification_id)
        .options(selectinload(NotificationLog.template))
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    return NotificationDetail(
        id=str(notification.id),
        template_name=notification.template.name if notification.template else None,
        event_id=str(notification.event_id) if notification.event_id else None,
        channel=notification.channel.value if notification.channel else "unknown",
        recipient_email=notification.recipient_email,
        recipient_name=notification.recipient_name,
        recipient_type=notification.recipient_type.value if notification.recipient_type else None,
        subject=notification.subject,
        body=notification.body,
        status=notification.status.value,
        sent_at=notification.sent_at,
        delivered_at=notification.delivered_at,
        attempts=notification.attempts,
        error_message=notification.error_message,
        created_at=notification.created_at,
    )


@router.post("/{notification_id}/retry")
async def retry_notification(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed notification."""
    result = await db.execute(
        select(NotificationLog).where(NotificationLog.id == notification_id)
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if notification.status != NotificationStatus.failed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry notification in '{notification.status.value}' status"
        )

    # Retry the notification
    notification_service = NotificationService(db)

    try:
        await notification_service._send(notification)
        notification.status = NotificationStatus.sent
        notification.sent_at = datetime.utcnow()
        notification.error_message = None
        await db.commit()

        return {"success": True, "message": "Notification resent"}
    except Exception as e:
        notification.attempts += 1
        notification.last_attempt_at = datetime.utcnow()
        notification.error_message = str(e)[:500]
        await db.commit()

        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retry-failed")
async def retry_all_failed(
    max_retries: int = Query(default=3, le=5),
    db: AsyncSession = Depends(get_db),
):
    """Retry all failed notifications."""
    notification_service = NotificationService(db)
    retried = await notification_service.retry_failed_notifications(max_retries=max_retries)

    return {
        "success": True,
        "retried_count": retried,
        "message": f"Retried {retried} failed notifications",
    }


@router.get("/by-event/{event_id}", response_model=list[NotificationSummary])
async def get_notifications_by_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get all notifications for an event."""
    result = await db.execute(
        select(NotificationLog)
        .where(NotificationLog.event_id == event_id)
        .order_by(NotificationLog.created_at.desc())
    )
    notifications = result.scalars().all()

    return [
        NotificationSummary(
            id=str(n.id),
            channel=n.channel.value if n.channel else "unknown",
            recipient_email=n.recipient_email,
            subject=n.subject,
            status=n.status.value,
            sent_at=n.sent_at,
            created_at=n.created_at,
        )
        for n in notifications
    ]


@router.post("/test")
async def send_test_notification(
    recipient_email: str,
    template_name: str = "sla_breach_vendor",
    db: AsyncSession = Depends(get_db),
):
    """Send a test notification."""
    notification_service = NotificationService(db)

    # Sample context for testing
    test_context = {
        "vendor_name": "Test Vendor",
        "contract_name": "Test Contract",
        "sla_name": "System Uptime",
        "target_value": 99.9,
        "actual_value": 98.5,
        "unit": "%",
        "period_start": "2024-01-01",
        "period_end": "2024-01-31",
        "deviation_percent": 1.4,
        "credit_amount": 5000,
        "sla_section": "5.2",
        "remedy_description": "Service credit to be applied to next invoice.",
        "sender_name": "Contract Management System",
    }

    notification = await notification_service.send_notification(
        template_name=template_name,
        recipient_email=recipient_email,
        context=test_context,
        recipient_name="Test Recipient",
    )

    return {
        "success": notification.status == NotificationStatus.sent,
        "notification_id": str(notification.id),
        "status": notification.status.value,
        "message": notification.error_message if notification.error_message else "Sent successfully",
    }
