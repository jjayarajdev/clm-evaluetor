"""Actionable notifications feed for the header bell.

Distinct from routers/notifications.py (which is an admin-only delivery log of
sent emails/webhooks). This surfaces real, time-relevant items for ANY signed-in
user — obligations overdue or due soon, contracts expiring or recently expired,
and active SLA alerts — scoped to their tenant. Read-only and computed on the
fly (no stored per-user feed), so the bell reflects reality: quiet when there is
nothing to act on.
"""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, CurrentTenantId
from app.core.tenant import apply_bu_filter
from app.database import get_db
from app.models.contract import Contract
from app.models.obligation import Obligation, ObligationStatus
from app.models.sla_alert import SLAAlert, AlertPriority, AlertStatus

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])

_SEV_RANK = {"high": 0, "medium": 1, "low": 2}


def _trunc(text: str | None, n: int = 90) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


@router.get("/feed")
async def get_notification_feed(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(25, ge=1, le=100),
) -> dict:
    """Current actionable notifications for the caller's tenant.

    ``{"count": <total>, "items": [{id, type, severity, label, title, subtitle,
    contract_id, link, date}]}``. ``count`` is the true total; ``items`` is capped.
    """
    today = date.today()
    due_soon = today + timedelta(days=30)
    expiring_horizon = today + timedelta(days=90)
    recently_expired = today - timedelta(days=30)

    # Respect business-unit scoping: a BU-restricted user must only be notified
    # about their own BU's contracts. All three feeds join/select Contract, so
    # we filter on Contract.business_unit_id (admins/unassigned users see all).
    bu_id = current_user.business_unit_id if current_user else None
    role = current_user.role.value if current_user and current_user.role else None

    def _bu(query):
        return apply_bu_filter(query, bu_id, role, model=Contract)

    items: list[dict] = []

    # 1) Obligations overdue or due within 30 days, still open
    oq = (
        select(Obligation, Contract)
        .join(Contract, Obligation.contract_id == Contract.id)
        .where(
            Obligation.deadline.isnot(None),
            # Bound the overdue window to the last year — obligations overdue by
            # years are stale artifacts, not actionable notifications.
            Obligation.deadline >= today - timedelta(days=365),
            Obligation.deadline <= due_soon,
            Obligation.status.in_([ObligationStatus.PENDING, ObligationStatus.IN_PROGRESS]),
        )
    )
    if tenant_id is not None:
        oq = oq.where(Contract.tenant_id == tenant_id)
    oq = _bu(oq).order_by(Obligation.deadline.asc()).limit(200)
    for obl, con in (await db.execute(oq)).all():
        overdue = obl.deadline < today
        items.append({
            "id": f"obl:{obl.id}",
            "type": "obligation",
            "severity": "high" if overdue else "medium",
            "label": "overdue" if overdue else "due_soon",  # i18n key; frontend translates
            "title": _trunc(obl.description) or "Obligation",
            "subtitle": con.counterparty or con.filename or "",
            "contract_id": str(obl.contract_id),
            "link": f"/contracts/{obl.contract_id}",
            "date": obl.deadline.isoformat(),
        })

    # 2) Contracts expiring within 90 days or expired in the last 30
    cq = select(Contract).where(
        Contract.expiration_date.isnot(None),
        Contract.expiration_date >= recently_expired,
        Contract.expiration_date <= expiring_horizon,
    )
    if tenant_id is not None:
        cq = cq.where(Contract.tenant_id == tenant_id)
    cq = _bu(cq).order_by(Contract.expiration_date.asc()).limit(200)
    for con in (await db.execute(cq)).scalars().all():
        expired = con.expiration_date < today
        urgent = expired or con.expiration_date <= today + timedelta(days=30)
        items.append({
            "id": f"con:{con.id}",
            "type": "renewal",
            "severity": "high" if urgent else "medium",
            "label": "expired" if expired else "renewal_due",  # i18n key
            "title": con.filename or "Contract",  # label badge conveys expired/expiring
            "subtitle": con.counterparty or "",
            "contract_id": str(con.id),
            "link": f"/contracts/{con.id}",
            "date": con.expiration_date.isoformat(),
        })

    # 3) Active SLA alerts (none today, but wired for when they exist)
    aq = (
        select(SLAAlert, Contract)
        .join(Contract, SLAAlert.contract_id == Contract.id)
        .where(
            SLAAlert.status.in_([
                AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED, AlertStatus.ESCALATED,
            ])
        )
    )
    if tenant_id is not None:
        aq = aq.where(Contract.tenant_id == tenant_id)
    aq = _bu(aq).order_by(SLAAlert.detected_at.desc()).limit(100)
    for al, con in (await db.execute(aq)).all():
        high = al.priority in (AlertPriority.CRITICAL, AlertPriority.HIGH)
        items.append({
            "id": f"sla:{al.id}",
            "type": "sla",
            "severity": "high" if high else "medium",
            "label": "sla",  # i18n key
            "title": _trunc(al.title) or "SLA alert",
            "subtitle": con.counterparty or con.filename or "",
            "contract_id": str(al.contract_id),
            "link": f"/contracts/{al.contract_id}",
            "date": al.detected_at.date().isoformat() if al.detected_at else today.isoformat(),
        })

    # High severity first, then most overdue / soonest date
    items.sort(key=lambda i: (_SEV_RANK.get(i["severity"], 3), i["date"]))

    return {"count": len(items), "items": items[:limit]}
