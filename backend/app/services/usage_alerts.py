"""Usage threshold alerts (metering phase 3).

Compares each tenant's current-month metered usage against the soft limits
stored in tenant.config_overrides["usage_limits"]:

    {"monthly_pages": 5000, "monthly_ai_actions": 20000, "monthly_cost_usd": 300}

Tenants without limits are skipped (entitlement enforcement is phase 4 —
these alerts warn, they never block). Crossing 80% or 100% of any limit
notifies the tenant's admins through the notification service; a
(tenant, metric, threshold, month) tuple is alerted at most once, deduped
against the notification log.

Runs from the scheduler job `usage_threshold_check`.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import NotificationLog
from app.models.tenant import Tenant
from app.models.usage_event import UsageMetric
from app.models.user import Role, User
from app.routers.usage import _aggregate, _bucketize, _month_start

logger = logging.getLogger(__name__)

THRESHOLDS = (100, 80)  # checked high→low; only the highest crossed one alerts

# limit key in usage_limits -> (display name, extractor from bucketized usage)
_LIMIT_METRICS = {
    "monthly_pages": ("pages processed", lambda u: u.get(UsageMetric.PAGES_PROCESSED, 0)),
    "monthly_ai_actions": ("AI actions", lambda u: u.get(UsageMetric.AI_ACTIONS, 0)),
    "monthly_cost_usd": ("estimated AI cost (USD)", lambda u: u.get("estimated_cost_usd", 0.0)),
}

_ALERT_KIND = "usage_threshold"


def get_usage_limits(tenant: Tenant) -> dict:
    limits = (tenant.config_overrides or {}).get("usage_limits") or {}
    return {k: v for k, v in limits.items() if k in _LIMIT_METRICS and v}


async def _already_alerted(
    db: AsyncSession, tenant_id: str, metric: str, threshold: int, month: str
) -> bool:
    """Dedup against the notification log (python-side filter on the JSON
    context — dialect-portable and the candidate set is tiny)."""
    rows = (
        (await db.execute(
            select(NotificationLog.variables_used).where(
                NotificationLog.variables_used.isnot(None)
            )
        )).scalars().all()
    )
    for ctx in rows:
        if (
            isinstance(ctx, dict)
            and ctx.get("kind") == _ALERT_KIND
            and ctx.get("tenant_id") == tenant_id
            and ctx.get("metric") == metric
            and ctx.get("month") == month
            and int(ctx.get("threshold", 0)) >= threshold
        ):
            return True
    return False


async def _tenant_admin_recipients(db: AsyncSession, tenant_id) -> list[User]:
    result = await db.execute(
        select(User).where(
            User.tenant_id == tenant_id,
            User.role == Role.ADMIN,
            User.is_active == True,  # noqa: E712
        )
    )
    return list(result.scalars().all())


async def check_usage_thresholds(db: AsyncSession) -> dict:
    """Check every tenant with limits; send due alerts. Returns a summary."""
    from app.services.notification_service import NotificationService

    month_start = _month_start(datetime.now(timezone.utc))
    month = month_start.strftime("%Y-%m")
    notifier = NotificationService(db)

    tenants = (await db.execute(select(Tenant).where(Tenant.is_active == True))).scalars().all()  # noqa: E712
    checked = alerts_sent = 0

    for tenant in tenants:
        limits = get_usage_limits(tenant)
        if not limits:
            continue
        checked += 1
        usage = _bucketize(await _aggregate(db, tenant.id, month_start, None), full=True)

        for limit_key, limit_value in limits.items():
            display, extract = _LIMIT_METRICS[limit_key]
            current = extract(usage)
            pct = current / limit_value * 100 if limit_value else 0
            crossed = next((t for t in THRESHOLDS if pct >= t), None)
            if crossed is None:
                continue
            if await _already_alerted(db, str(tenant.id), limit_key, crossed, month):
                continue

            recipients = await _tenant_admin_recipients(db, tenant.id)
            subject = (
                f"[Evaluetor] {tenant.name}: {display} at {pct:.0f}% "
                f"of the monthly limit"
            )
            body = (
                f"Tenant '{tenant.name}' has used {current:,.0f} of the "
                f"{limit_value:,.0f} {display} configured for {month} "
                f"({pct:.0f}%).\n\n"
                + (
                    "The limit is exceeded. Usage is not blocked, but this "
                    "month is over the configured allowance."
                    if crossed >= 100
                    else "This is an early warning at the 80% threshold."
                )
            )
            context = {
                "kind": _ALERT_KIND,
                "tenant_id": str(tenant.id),
                "tenant_name": tenant.name,
                "metric": limit_key,
                "threshold": crossed,
                "month": month,
                "current": current,
                "limit": limit_value,
                "subject": subject,
                "body": body,
            }
            for user in recipients:
                await notifier.send_notification(
                    template_name="usage_threshold",
                    recipient_email=user.email,
                    recipient_name=user.full_name or user.username,
                    context=context,
                )
            if recipients:
                alerts_sent += 1
                logger.info(
                    "usage alert: %s %s at %d%% (%s admins notified)",
                    tenant.name, limit_key, crossed, len(recipients),
                )

    return {"tenants_with_limits": checked, "alerts_sent": alerts_sent, "month": month}
