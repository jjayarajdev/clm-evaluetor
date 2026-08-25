"""Usage meters API (pages, tokens, AI actions, estimated cost).

Visibility is enforced HERE, not in the UI:
  * every authenticated user      -> pages_processed + documents_ingested
  * tenant admin / super admin    -> also tokens, AI actions & estimated cost

Super admin (tenant_id=None) sees the platform-wide aggregate and may scope to
one tenant via ?tenant_id=, plus a per-tenant breakdown on /by-tenant.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentTenantId, CurrentUser, SuperAdminUser
from app.database import get_db
from app.models.tenant import Tenant
from app.models.usage_event import UsageEvent, UsageMetric
from app.models.user import Role

router = APIRouter(prefix="/api/usage", tags=["Usage"])


class UsageLimitsUpdate(BaseModel):
    """Monthly soft limits; null/0 clears a limit."""

    monthly_pages: int | None = Field(None, ge=0)
    monthly_ai_actions: int | None = Field(None, ge=0)
    monthly_cost_usd: float | None = Field(None, ge=0)

# USD per 1M tokens (input, output) — illustrative list prices for the cost
# ESTIMATE shown to tenant admins; not a billing rate card. Prefix-matched in
# order, so keep more specific prefixes (…-mini) before their base model.
MODEL_PRICES_PER_MTOK: list[tuple[str, float, float]] = [
    ("gpt-4o-mini", 0.15, 0.60),
    ("gpt-4o", 2.50, 10.00),
    ("gpt-4.1-mini", 0.40, 1.60),
    ("gpt-4.1", 2.00, 8.00),
    ("gpt-5-mini", 0.25, 2.00),
    ("gpt-5", 1.25, 10.00),
    ("text-embedding-3-large", 0.13, 0.0),
    ("text-embedding-3-small", 0.02, 0.0),
]

_INPUT_METRICS = (UsageMetric.TOKENS_PROMPT, UsageMetric.TOKENS_EMBEDDING)

PAGES_METRICS = (UsageMetric.PAGES_PROCESSED, UsageMetric.DOCUMENTS_INGESTED)
AI_METRICS = (
    UsageMetric.TOKENS_PROMPT,
    UsageMetric.TOKENS_COMPLETION,
    UsageMetric.TOKENS_EMBEDDING,
    UsageMetric.AI_ACTIONS,
)


def _prices_for(model: str | None) -> tuple[float, float]:
    if model:
        for prefix, inp, out in MODEL_PRICES_PER_MTOK:
            if model.startswith(prefix):
                return inp, out
    return 0.0, 0.0  # unknown model: tokens still reported, cost contribution 0


def _cost_usd(metric: str, model: str | None, quantity: int) -> float:
    inp, out = _prices_for(model)
    per_mtok = inp if metric in _INPUT_METRICS else out
    return quantity * per_mtok / 1_000_000


def _month_start(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _month_windows(months: int) -> list[tuple[datetime, datetime | None]]:
    """Last `months` [start, next_start) windows, oldest first.

    The current month is last with end=None (open-ended), so in-flight events
    with occurred_at slightly ahead of "now" still count.
    """
    result: list[tuple[datetime, datetime | None]] = []
    cursor = _month_start(datetime.now(timezone.utc))
    nxt: datetime | None = None
    for _ in range(months):
        result.append((cursor, nxt))
        nxt = cursor
        if cursor.month == 1:
            cursor = cursor.replace(year=cursor.year - 1, month=12)
        else:
            cursor = cursor.replace(month=cursor.month - 1)
    return list(reversed(result))


def _full_visibility(user) -> bool:
    # Token/cost visibility is the 'usage.viewCost' permission (super_admin
    # passes via the has_permission floor). Endpoints warm the matrix first.
    from app.core.permissions import has_permission

    return has_permission(user, "usage.viewCost")


async def _aggregate(
    db: AsyncSession,
    tenant_id: uuid.UUID | None,
    start: datetime,
    end: datetime | None,
) -> list[tuple[str, str | None, int]]:
    """Sum quantities grouped by (metric, model) for one tenant + window."""
    q = (
        select(UsageEvent.metric, UsageEvent.model, func.sum(UsageEvent.quantity))
        .where(UsageEvent.occurred_at >= start)
        .group_by(UsageEvent.metric, UsageEvent.model)
    )
    if end is not None:
        q = q.where(UsageEvent.occurred_at < end)
    if tenant_id is not None:
        q = q.where(UsageEvent.tenant_id == tenant_id)
    return [(m, model, int(total or 0)) for m, model, total in (await db.execute(q)).all()]


def _bucketize(rows: list[tuple[str, str | None, int]], full: bool) -> dict:
    out: dict = {m: 0 for m in PAGES_METRICS}
    if full:
        out.update({m: 0 for m in AI_METRICS})
        out["estimated_cost_usd"] = 0.0
    for metric, model, total in rows:
        if metric in PAGES_METRICS:
            out[metric] += total
        elif full and metric in AI_METRICS:
            out[metric] += total
            if metric != UsageMetric.AI_ACTIONS:
                out["estimated_cost_usd"] += _cost_usd(metric, model, total)
    if full:
        out["estimated_cost_usd"] = round(out["estimated_cost_usd"], 2)
    return out


@router.get("/summary")
async def usage_summary(
    current_user: CurrentUser,
    jwt_tenant_id: CurrentTenantId,
    months: int = Query(6, ge=1, le=24),
    tenant_id: uuid.UUID | None = Query(None, description="Super admin only: scope to one tenant"),
    db: AsyncSession = Depends(get_db),
):
    """Monthly usage for the caller's tenant (or platform-wide for super admin)."""
    from app.core.permissions import get_matrix

    await get_matrix(db)
    full = _full_visibility(current_user)
    # Non-super-admins are always scoped to their own tenant; the tenant_id
    # query param is honored only for super admin.
    scope = jwt_tenant_id if jwt_tenant_id is not None else tenant_id

    windows = _month_windows(months)
    month_rows = []
    for start, end in windows:
        rows = await _aggregate(db, scope, start, end)
        month_rows.append({"month": start.strftime("%Y-%m"), **_bucketize(rows, full)})

    totals = _bucketize(await _aggregate(db, scope, windows[0][0], None), full)
    return {
        "months": month_rows,
        "totals": totals,
        "can_view_ai_usage": full,
    }


@router.get("/by-tenant")
async def usage_by_tenant(
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Current-month usage + estimated cost per tenant (super admin fleet view).

    Lists EVERY active tenant (zero-usage tenants included) and, where
    monthly limits are configured, the utilization percentage per limit.
    """
    from app.services.usage_alerts import get_usage_limits, _LIMIT_METRICS

    start = _month_start(datetime.now(timezone.utc))
    q = (
        select(UsageEvent.tenant_id, UsageEvent.metric, UsageEvent.model, func.sum(UsageEvent.quantity))
        .where(UsageEvent.occurred_at >= start)
        .group_by(UsageEvent.tenant_id, UsageEvent.metric, UsageEvent.model)
    )
    by_tenant: dict = {}
    for tid, metric, model, total in (await db.execute(q)).all():
        by_tenant.setdefault(tid, []).append((metric, model, int(total or 0)))

    tenants = (await db.execute(select(Tenant))).scalars().all()
    for t in tenants:
        by_tenant.setdefault(t.id, [])
    tenant_by_id = {t.id: t for t in tenants}

    items = []
    for tid, rows in by_tenant.items():
        tenant = tenant_by_id.get(tid)
        usage = _bucketize(rows, full=True)
        limits = get_usage_limits(tenant) if tenant else {}
        utilization = {
            key: {
                "limit": limit,
                "current": _LIMIT_METRICS[key][1](usage),
                "pct": round(_LIMIT_METRICS[key][1](usage) / limit * 100, 1) if limit else 0,
            }
            for key, limit in limits.items()
        }
        items.append({
            "tenant_id": str(tid) if tid else None,
            "tenant_name": tenant.name if tenant else "Platform (no tenant)",
            **usage,
            "limits": utilization,
        })
    items.sort(key=lambda i: i.get("estimated_cost_usd", 0), reverse=True)
    return {"month": start.strftime("%Y-%m"), "items": items}


@router.get("/limits/{tenant_id}")
async def get_tenant_usage_limits(
    tenant_id: uuid.UUID,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Read a tenant's configured monthly usage limits (super admin)."""
    from app.services.usage_alerts import get_usage_limits

    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"tenant_id": str(tenant_id), "usage_limits": get_usage_limits(tenant)}


@router.put("/limits/{tenant_id}")
async def set_tenant_usage_limits(
    tenant_id: uuid.UUID,
    body: UsageLimitsUpdate,
    current_user: SuperAdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Set a tenant's monthly usage limits (super admin).

    Limits are soft: they drive the 80%/100% admin alerts, not enforcement
    (that's metering phase 4). Setting a value to null removes the limit.
    """
    from sqlalchemy.orm.attributes import flag_modified

    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    overrides = dict(tenant.config_overrides or {})
    limits = {
        k: v
        for k, v in body.model_dump().items()
        if v is not None and v > 0
    }
    if limits:
        overrides["usage_limits"] = limits
    else:
        overrides.pop("usage_limits", None)
    tenant.config_overrides = overrides
    flag_modified(tenant, "config_overrides")
    await db.commit()
    return {"tenant_id": str(tenant_id), "usage_limits": limits}
