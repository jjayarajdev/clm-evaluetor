"""API endpoints for SLA alerts and dashboard notifications.

Provides:
- Alert listing and filtering
- Alert acknowledgement and resolution
- Alert escalation
- Dashboard summary
- Bulk alert operations
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.sla_alert import (
    SLAAlert,
    AlertCategory,
    AlertPriority,
    AlertStatus,
)
from app.models.sla import BreachSeverity
from app.services.sla_alert_service import SLAAlertService

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


# ===== Response Models =====

class AlertSummary(BaseModel):
    """Summary view of an alert."""

    id: str
    contract_id: str
    category: str
    priority: str
    status: str
    title: str
    sla_reference: Optional[str] = None
    sla_name: Optional[str] = None
    actual_value: Optional[float] = None
    target_value: Optional[float] = None
    deviation_percentage: Optional[float] = None
    breach_severity: Optional[str] = None
    has_financial_impact: bool = False
    estimated_credit: Optional[float] = None
    detected_at: datetime
    days_open: int = 0

    model_config = {"from_attributes": True}


class AlertDetail(BaseModel):
    """Detailed alert information."""

    id: str
    contract_id: str
    contract_name: Optional[str] = None
    sla_id: Optional[str] = None
    category: str
    priority: str
    status: str
    title: str
    description: str
    sla_reference: Optional[str] = None
    sla_name: Optional[str] = None
    target_value: Optional[float] = None
    minimum_value: Optional[float] = None
    actual_value: Optional[float] = None
    deviation_percentage: Optional[float] = None
    breach_severity: Optional[str] = None
    has_financial_impact: bool = False
    estimated_credit: Optional[float] = None
    at_risk_amount: Optional[float] = None
    measurement_start: Optional[datetime] = None
    measurement_end: Optional[datetime] = None
    source_system: Optional[str] = None
    detected_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None
    escalation_level: int = 0
    escalated_to: Optional[str] = None
    notification_sent: bool = False
    days_open: int = 0
    extra_data: Optional[dict] = None

    model_config = {"from_attributes": True}


class AlertDashboardSummary(BaseModel):
    """Dashboard summary of alerts."""

    active_count: int
    resolved_count: int
    critical_count: int
    high_count: int
    breaches_count: int
    warnings_count: int
    credits_due: float
    at_risk_total: float
    by_status: dict
    by_priority: dict
    by_category: dict


class AcknowledgeRequest(BaseModel):
    """Request to acknowledge an alert."""

    notes: Optional[str] = None


class ResolveRequest(BaseModel):
    """Request to resolve an alert."""

    resolution_notes: str = Field(..., min_length=1)


class EscalateRequest(BaseModel):
    """Request to escalate an alert."""

    escalate_to: str = Field(..., description="Email address to escalate to")
    notify: bool = True


class BulkActionRequest(BaseModel):
    """Request for bulk alert actions."""

    alert_ids: list[str]
    action: str = Field(..., pattern="^(acknowledge|resolve|dismiss)$")
    notes: Optional[str] = None


# ===== Endpoints =====

@router.get("/dashboard", response_model=AlertDashboardSummary)
async def get_alert_dashboard(
    contract_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get alert dashboard summary."""
    alert_service = SLAAlertService(db)
    summary = await alert_service.get_alert_summary(contract_id)

    return AlertDashboardSummary(
        active_count=summary["active_count"],
        resolved_count=summary["resolved_count"],
        critical_count=summary["critical_count"],
        high_count=summary["high_count"],
        breaches_count=summary["by_category"].get(AlertCategory.SLA_BREACH.value, 0),
        warnings_count=summary["by_category"].get(AlertCategory.SLA_WARNING.value, 0),
        credits_due=summary["financial_impact"]["credits_due"],
        at_risk_total=summary["financial_impact"]["at_risk"],
        by_status=summary["by_status"],
        by_priority=summary["by_priority"],
        by_category=summary["by_category"],
    )


@router.get("/", response_model=list[AlertSummary])
async def list_alerts(
    status: Optional[AlertStatus] = None,
    priority: Optional[AlertPriority] = None,
    category: Optional[AlertCategory] = None,
    contract_id: Optional[UUID] = None,
    active_only: bool = Query(default=True, description="Only show active alerts"),
    days: int = Query(default=30, le=365, description="Look back period in days"),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List alerts with filters."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    query = select(SLAAlert).where(SLAAlert.detected_at >= cutoff)

    if active_only:
        query = query.where(
            SLAAlert.status.in_([
                AlertStatus.ACTIVE,
                AlertStatus.ACKNOWLEDGED,
                AlertStatus.IN_PROGRESS,
                AlertStatus.ESCALATED,
            ])
        )
    elif status:
        query = query.where(SLAAlert.status == status)

    if priority:
        query = query.where(SLAAlert.priority == priority)
    if category:
        query = query.where(SLAAlert.category == category)
    if contract_id:
        query = query.where(SLAAlert.contract_id == contract_id)

    query = query.order_by(
        SLAAlert.priority.desc(),
        SLAAlert.detected_at.desc()
    ).offset(offset).limit(limit)

    result = await db.execute(query)
    alerts = result.scalars().all()

    return [
        AlertSummary(
            id=str(a.id),
            contract_id=str(a.contract_id),
            category=a.category.value,
            priority=a.priority.value,
            status=a.status.value,
            title=a.title,
            sla_reference=a.sla_reference,
            sla_name=a.sla_name,
            actual_value=float(a.actual_value) if a.actual_value else None,
            target_value=float(a.target_value) if a.target_value else None,
            deviation_percentage=float(a.deviation_percentage) if a.deviation_percentage else None,
            breach_severity=a.breach_severity.value if a.breach_severity else None,
            has_financial_impact=a.has_financial_impact,
            estimated_credit=float(a.estimated_credit) if a.estimated_credit else None,
            detected_at=a.detected_at,
            days_open=a.days_open,
        )
        for a in alerts
    ]


@router.get("/critical", response_model=list[AlertSummary])
async def list_critical_alerts(
    contract_id: Optional[UUID] = None,
    limit: int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get critical and high-priority active alerts for dashboard."""
    query = select(SLAAlert).where(
        SLAAlert.status.in_([
            AlertStatus.ACTIVE,
            AlertStatus.ACKNOWLEDGED,
            AlertStatus.ESCALATED,
        ]),
        SLAAlert.priority.in_([AlertPriority.CRITICAL, AlertPriority.HIGH])
    )

    if contract_id:
        query = query.where(SLAAlert.contract_id == contract_id)

    query = query.order_by(
        SLAAlert.priority.desc(),
        SLAAlert.detected_at.desc()
    ).limit(limit)

    result = await db.execute(query)
    alerts = result.scalars().all()

    return [
        AlertSummary(
            id=str(a.id),
            contract_id=str(a.contract_id),
            category=a.category.value,
            priority=a.priority.value,
            status=a.status.value,
            title=a.title,
            sla_reference=a.sla_reference,
            sla_name=a.sla_name,
            actual_value=float(a.actual_value) if a.actual_value else None,
            target_value=float(a.target_value) if a.target_value else None,
            deviation_percentage=float(a.deviation_percentage) if a.deviation_percentage else None,
            breach_severity=a.breach_severity.value if a.breach_severity else None,
            has_financial_impact=a.has_financial_impact,
            estimated_credit=float(a.estimated_credit) if a.estimated_credit else None,
            detected_at=a.detected_at,
            days_open=a.days_open,
        )
        for a in alerts
    ]


@router.get("/{alert_id}", response_model=AlertDetail)
async def get_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get alert details."""
    result = await db.execute(
        select(SLAAlert)
        .where(SLAAlert.id == alert_id)
        .options(selectinload(SLAAlert.contract))
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # Get acknowledger name if applicable
    acknowledged_by_name = None
    if alert.acknowledged_by:
        from app.models.user import User as UserModel
        user_result = await db.execute(
            select(UserModel).where(UserModel.id == alert.acknowledged_by)
        )
        user = user_result.scalar_one_or_none()
        if user:
            acknowledged_by_name = user.full_name or user.email

    # Get resolver name if applicable
    resolved_by_name = None
    if alert.resolved_by:
        from app.models.user import User as UserModel
        user_result = await db.execute(
            select(UserModel).where(UserModel.id == alert.resolved_by)
        )
        user = user_result.scalar_one_or_none()
        if user:
            resolved_by_name = user.full_name or user.email

    return AlertDetail(
        id=str(alert.id),
        contract_id=str(alert.contract_id),
        contract_name=alert.contract.filename if alert.contract else None,
        sla_id=str(alert.sla_id) if alert.sla_id else None,
        category=alert.category.value,
        priority=alert.priority.value,
        status=alert.status.value,
        title=alert.title,
        description=alert.description,
        sla_reference=alert.sla_reference,
        sla_name=alert.sla_name,
        target_value=float(alert.target_value) if alert.target_value else None,
        minimum_value=float(alert.minimum_value) if alert.minimum_value else None,
        actual_value=float(alert.actual_value) if alert.actual_value else None,
        deviation_percentage=float(alert.deviation_percentage) if alert.deviation_percentage else None,
        breach_severity=alert.breach_severity.value if alert.breach_severity else None,
        has_financial_impact=alert.has_financial_impact,
        estimated_credit=float(alert.estimated_credit) if alert.estimated_credit else None,
        at_risk_amount=float(alert.at_risk_amount) if alert.at_risk_amount else None,
        measurement_start=alert.measurement_start,
        measurement_end=alert.measurement_end,
        source_system=alert.source_system,
        detected_at=alert.detected_at,
        acknowledged_at=alert.acknowledged_at,
        acknowledged_by=acknowledged_by_name,
        resolved_at=alert.resolved_at,
        resolved_by=resolved_by_name,
        resolution_notes=alert.resolution_notes,
        escalation_level=alert.escalation_level,
        escalated_to=alert.escalated_to,
        notification_sent=alert.notification_sent,
        days_open=alert.days_open,
        extra_data=alert.extra_data,
    )


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: UUID,
    request: Optional[AcknowledgeRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Acknowledge an alert."""
    alert_service = SLAAlertService(db)

    try:
        alert = await alert_service.acknowledge_alert(alert_id, current_user.id)
        await db.commit()

        return {
            "success": True,
            "alert_id": str(alert.id),
            "status": alert.status.value,
            "acknowledged_at": alert.acknowledged_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: UUID,
    request: ResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resolve an alert."""
    alert_service = SLAAlertService(db)

    try:
        alert = await alert_service.resolve_alert(
            alert_id,
            current_user.id,
            request.resolution_notes
        )
        await db.commit()

        return {
            "success": True,
            "alert_id": str(alert.id),
            "status": alert.status.value,
            "resolved_at": alert.resolved_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{alert_id}/escalate")
async def escalate_alert(
    alert_id: UUID,
    request: EscalateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Escalate an alert."""
    alert_service = SLAAlertService(db)

    try:
        alert = await alert_service.escalate_alert(
            alert_id,
            request.escalate_to,
            request.notify
        )
        await db.commit()

        return {
            "success": True,
            "alert_id": str(alert.id),
            "status": alert.status.value,
            "escalation_level": alert.escalation_level,
            "escalated_to": alert.escalated_to,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{alert_id}/dismiss")
async def dismiss_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dismiss an alert (mark as not actionable)."""
    result = await db.execute(
        select(SLAAlert).where(SLAAlert.id == alert_id)
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = AlertStatus.DISMISSED
    alert.resolved_at = datetime.utcnow()
    alert.resolved_by = current_user.id
    alert.resolution_notes = "Dismissed by user"

    await db.commit()

    return {
        "success": True,
        "alert_id": str(alert.id),
        "status": alert.status.value,
    }


@router.post("/{alert_id}/notify")
async def send_alert_notification(
    alert_id: UUID,
    recipient_email: str,
    recipient_name: str = "",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send notification for an alert."""
    result = await db.execute(
        select(SLAAlert).where(SLAAlert.id == alert_id)
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert_service = SLAAlertService(db)
    success = await alert_service.send_alert_notification(
        alert,
        recipient_email,
        recipient_name
    )
    await db.commit()

    return {
        "success": success,
        "alert_id": str(alert.id),
        "notification_sent": alert.notification_sent,
        "sent_at": alert.notification_sent_at.isoformat() if alert.notification_sent_at else None,
    }


@router.post("/bulk-action")
async def bulk_alert_action(
    request: BulkActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Perform bulk action on multiple alerts."""
    alert_service = SLAAlertService(db)

    processed = []
    failed = []

    for alert_id_str in request.alert_ids:
        try:
            alert_id = UUID(alert_id_str)

            if request.action == "acknowledge":
                await alert_service.acknowledge_alert(alert_id, current_user.id)
            elif request.action == "resolve":
                await alert_service.resolve_alert(
                    alert_id,
                    current_user.id,
                    request.notes or "Bulk resolved"
                )
            elif request.action == "dismiss":
                result = await db.execute(
                    select(SLAAlert).where(SLAAlert.id == alert_id)
                )
                alert = result.scalar_one_or_none()
                if alert:
                    alert.status = AlertStatus.DISMISSED
                    alert.resolved_at = datetime.utcnow()
                    alert.resolved_by = current_user.id
                    alert.resolution_notes = request.notes or "Bulk dismissed"

            processed.append(alert_id_str)

        except Exception as e:
            failed.append({"id": alert_id_str, "error": str(e)})

    await db.commit()

    return {
        "success": len(failed) == 0,
        "processed_count": len(processed),
        "failed_count": len(failed),
        "processed": processed,
        "failed": failed,
    }


@router.get("/by-contract/{contract_id}", response_model=list[AlertSummary])
async def get_alerts_by_contract(
    contract_id: UUID,
    active_only: bool = True,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all alerts for a specific contract."""
    query = select(SLAAlert).where(SLAAlert.contract_id == contract_id)

    if active_only:
        query = query.where(
            SLAAlert.status.in_([
                AlertStatus.ACTIVE,
                AlertStatus.ACKNOWLEDGED,
                AlertStatus.IN_PROGRESS,
                AlertStatus.ESCALATED,
            ])
        )

    query = query.order_by(
        SLAAlert.priority.desc(),
        SLAAlert.detected_at.desc()
    ).limit(limit)

    result = await db.execute(query)
    alerts = result.scalars().all()

    return [
        AlertSummary(
            id=str(a.id),
            contract_id=str(a.contract_id),
            category=a.category.value,
            priority=a.priority.value,
            status=a.status.value,
            title=a.title,
            sla_reference=a.sla_reference,
            sla_name=a.sla_name,
            actual_value=float(a.actual_value) if a.actual_value else None,
            target_value=float(a.target_value) if a.target_value else None,
            deviation_percentage=float(a.deviation_percentage) if a.deviation_percentage else None,
            breach_severity=a.breach_severity.value if a.breach_severity else None,
            has_financial_impact=a.has_financial_impact,
            estimated_credit=float(a.estimated_credit) if a.estimated_credit else None,
            detected_at=a.detected_at,
            days_open=a.days_open,
        )
        for a in alerts
    ]


@router.get("/stats/trends")
async def get_alert_trends(
    contract_id: Optional[UUID] = None,
    days: int = Query(default=30, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get alert trends over time."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Alerts created per day
    from sqlalchemy import cast, Date

    query = (
        select(
            cast(SLAAlert.detected_at, Date).label("date"),
            func.count(SLAAlert.id).label("count"),
            SLAAlert.category,
        )
        .where(SLAAlert.detected_at >= cutoff)
        .group_by(cast(SLAAlert.detected_at, Date), SLAAlert.category)
        .order_by(cast(SLAAlert.detected_at, Date))
    )

    if contract_id:
        query = query.where(SLAAlert.contract_id == contract_id)

    result = await db.execute(query)
    rows = result.fetchall()

    # Build trend data
    daily_trends = {}
    for row in rows:
        date_str = row.date.isoformat() if row.date else "unknown"
        if date_str not in daily_trends:
            daily_trends[date_str] = {
                "total": 0,
                "by_category": {},
            }
        daily_trends[date_str]["total"] += row.count
        daily_trends[date_str]["by_category"][row.category.value] = row.count

    return {
        "period_days": days,
        "total_alerts": sum(t["total"] for t in daily_trends.values()),
        "daily_trends": [
            {"date": date, **data}
            for date, data in sorted(daily_trends.items())
        ],
    }
