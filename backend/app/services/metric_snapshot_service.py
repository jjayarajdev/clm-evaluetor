"""Service for capturing metric snapshots and managing dashboard cache."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    MetricSnapshot,
    DashboardCache,
    Contract,
    ContractStatus,
    Obligation,
    ObligationStatus,
    RAGStatus,
    ContractSLA,
)
from app.core.tenant import apply_tenant_filter


# ============== Metric Snapshots ==============


async def capture_daily_snapshot(
    db: AsyncSession, tenant_id: Optional[UUID] = None,
) -> MetricSnapshot:
    """Capture current metrics as daily snapshot for a specific tenant.

    If tenant_id is None, captures global (cross-tenant) metrics.
    """
    today = date.today()

    # Check if snapshot already exists for this tenant+date
    existing_result = await db.execute(
        select(MetricSnapshot).where(
            MetricSnapshot.snapshot_date == today,
            MetricSnapshot.tenant_id == tenant_id,
        )
    )
    snapshot = existing_result.scalar_one_or_none()

    if not snapshot:
        snapshot = MetricSnapshot(snapshot_date=today, tenant_id=tenant_id)
        db.add(snapshot)

    # Get completed contracts (tenant-filtered)
    contracts_query = select(Contract).where(Contract.status == ContractStatus.COMPLETED)
    contracts_query = apply_tenant_filter(contracts_query, tenant_id, Contract)
    contracts_result = await db.execute(contracts_query)
    contracts = list(contracts_result.scalars().all())

    # Contract metrics
    snapshot.total_contracts = len(contracts)
    snapshot.total_contract_value = sum(
        Decimal(str(c.contract_value)) for c in contracts if c.contract_value
    ) or Decimal('0')

    at_risk_count = sum(1 for c in contracts if c.risk_level and c.risk_level.value == 'high')
    snapshot.contracts_at_risk = at_risk_count

    # Obligation metrics
    obligations_query = (
        select(Obligation).join(Contract)
        .where(Contract.status == ContractStatus.COMPLETED)
    )
    obligations_query = apply_tenant_filter(obligations_query, tenant_id, Contract)
    obligations_result = await db.execute(obligations_query)
    obligations = list(obligations_result.scalars().all())

    snapshot.obligations_total = len(obligations)
    snapshot.obligations_completed = sum(
        1 for o in obligations if o.status == ObligationStatus.COMPLETED
    )
    snapshot.obligations_overdue = sum(
        1 for o in obligations if o.status == ObligationStatus.OVERDUE
    )

    # Compliance rate
    waived = sum(1 for o in obligations if o.status == ObligationStatus.WAIVED)
    in_progress = sum(1 for o in obligations if o.status == ObligationStatus.IN_PROGRESS)
    pending_future = sum(1 for o in obligations
                         if o.status == ObligationStatus.PENDING
                         and o.deadline and o.deadline > today)
    assessable = len(obligations) - waived - pending_future
    if assessable > 0:
        snapshot.compliance_rate = Decimal(str(
            round((snapshot.obligations_completed + in_progress) / assessable * 100, 2)
        ))
    else:
        snapshot.compliance_rate = Decimal('100.00')

    # SLA metrics
    slas_query = (
        select(ContractSLA).join(Contract)
        .where(Contract.status == ContractStatus.COMPLETED)
    )
    slas_query = apply_tenant_filter(slas_query, tenant_id, Contract)
    slas_result = await db.execute(slas_query)
    slas = list(slas_result.scalars().all())

    snapshot.slas_total = len(slas)
    snapshot.slas_breached = sum(1 for s in slas if s.consecutive_breaches > 0)

    compliance_rates = [
        float(s.current_compliance_rate)
        for s in slas
        if s.current_compliance_rate is not None
    ]
    if compliance_rates:
        snapshot.sla_compliance_rate = Decimal(str(
            round(sum(compliance_rates) / len(compliance_rates), 2)
        ))
    else:
        snapshot.sla_compliance_rate = Decimal('100.00')

    # Renewal metrics
    renewals_30 = renewals_60 = renewals_90 = 0
    for c in contracts:
        if c.expiration_date:
            days_until = (c.expiration_date - today).days
            if 0 <= days_until <= 30:
                renewals_30 += 1
            if 0 <= days_until <= 60:
                renewals_60 += 1
            if 0 <= days_until <= 90:
                renewals_90 += 1

    snapshot.renewals_due_30_days = renewals_30
    snapshot.renewals_due_60_days = renewals_60
    snapshot.renewals_due_90_days = renewals_90

    # Vendor metrics
    counterparties = set(c.counterparty for c in contracts if c.counterparty)
    snapshot.total_vendors = len(counterparties)

    at_risk_vendors = set(
        c.counterparty for c in contracts
        if c.counterparty and c.risk_level and c.risk_level.value == 'high'
    )
    snapshot.vendors_at_risk = len(at_risk_vendors)

    await db.commit()
    await db.refresh(snapshot)
    return snapshot


async def get_metric_history(
    db: AsyncSession,
    days: int = 30,
    end_date: Optional[date] = None,
    tenant_id: Optional[UUID] = None,
) -> list[MetricSnapshot]:
    """Get metric snapshots for a tenant over the specified period."""
    if end_date is None:
        end_date = date.today()

    start_date = end_date - timedelta(days=days - 1)

    query = (
        select(MetricSnapshot)
        .where(
            MetricSnapshot.snapshot_date >= start_date,
            MetricSnapshot.snapshot_date <= end_date,
            MetricSnapshot.tenant_id == tenant_id,
        )
        .order_by(MetricSnapshot.snapshot_date.asc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_trend_data(
    db: AsyncSession,
    metric: str,
    days: int = 7,
    tenant_id: Optional[UUID] = None,
) -> list[dict]:
    """Get trend data for a specific metric."""
    snapshots = await get_metric_history(db, days=days, tenant_id=tenant_id)

    metric_fields = {
        'total_contracts', 'contracts_at_risk', 'compliance_rate',
        'total_contract_value', 'obligations_total', 'obligations_completed',
        'obligations_overdue', 'sla_compliance_rate', 'slas_breached',
        'renewals_due_30_days', 'total_vendors', 'vendors_at_risk',
    }

    if metric not in metric_fields:
        return []

    return [
        {
            'date': s.snapshot_date.isoformat(),
            'value': float(getattr(s, metric, 0) or 0)
        }
        for s in snapshots
    ]


# ============== Dashboard Cache ==============

# Default TTL: 5 minutes for dashboards
DASHBOARD_CACHE_TTL = timedelta(minutes=5)


async def get_cached_dashboard(
    db: AsyncSession,
    tenant_id: Optional[UUID],
    dashboard_type: str,
    cache_key: str = "",
) -> Optional[dict]:
    """Get cached dashboard response if still valid."""
    now = datetime.utcnow()

    result = await db.execute(
        select(DashboardCache).where(
            DashboardCache.tenant_id == tenant_id,
            DashboardCache.dashboard_type == dashboard_type,
            DashboardCache.cache_key == (cache_key or ""),
            DashboardCache.expires_at > now,
        )
    )
    cache_entry = result.scalar_one_or_none()

    if cache_entry:
        return cache_entry.data
    return None


async def set_cached_dashboard(
    db: AsyncSession,
    tenant_id: Optional[UUID],
    dashboard_type: str,
    data: dict,
    cache_key: str = "",
    ttl: Optional[timedelta] = None,
) -> None:
    """Store computed dashboard response in cache."""
    now = datetime.utcnow()
    expires = now + (ttl or DASHBOARD_CACHE_TTL)

    # Upsert: find existing or create
    result = await db.execute(
        select(DashboardCache).where(
            DashboardCache.tenant_id == tenant_id,
            DashboardCache.dashboard_type == dashboard_type,
            DashboardCache.cache_key == (cache_key or ""),
        )
    )
    cache_entry = result.scalar_one_or_none()

    if cache_entry:
        cache_entry.data = data
        cache_entry.computed_at = now
        cache_entry.expires_at = expires
    else:
        cache_entry = DashboardCache(
            tenant_id=tenant_id,
            dashboard_type=dashboard_type,
            cache_key=cache_key or "",
            data=data,
            computed_at=now,
            expires_at=expires,
        )
        db.add(cache_entry)

    await db.commit()


async def invalidate_dashboard_cache(
    db: AsyncSession,
    tenant_id: Optional[UUID],
    dashboard_types: Optional[list[str]] = None,
) -> int:
    """Invalidate cached dashboards for a tenant.

    Args:
        tenant_id: Tenant whose caches to invalidate. None = global.
        dashboard_types: Specific types to invalidate. None = all.

    Returns:
        Number of cache entries deleted.
    """
    query = delete(DashboardCache).where(DashboardCache.tenant_id == tenant_id)

    if dashboard_types:
        query = query.where(DashboardCache.dashboard_type.in_(dashboard_types))

    result = await db.execute(query)
    await db.commit()
    return result.rowcount


async def cleanup_expired_cache(db: AsyncSession) -> int:
    """Remove all expired cache entries."""
    result = await db.execute(
        delete(DashboardCache).where(DashboardCache.expires_at <= datetime.utcnow())
    )
    await db.commit()
    return result.rowcount


# ============== Demo / Backfill ==============


async def backfill_snapshots(db: AsyncSession, days: int = 30) -> int:
    """Backfill missing snapshots with simulated data based on today's real values.

    Demo/testing only — in production use real historical data.
    """
    import random

    today = date.today()
    created = 0

    today_snapshot = await capture_daily_snapshot(db)

    base = {
        'total_contracts': today_snapshot.total_contracts,
        'contracts_at_risk': today_snapshot.contracts_at_risk,
        'total_contract_value': float(today_snapshot.total_contract_value),
        'compliance_rate': float(today_snapshot.compliance_rate),
        'obligations_total': today_snapshot.obligations_total,
        'obligations_completed': today_snapshot.obligations_completed,
        'obligations_overdue': today_snapshot.obligations_overdue,
        'sla_compliance_rate': float(today_snapshot.sla_compliance_rate),
        'slas_total': today_snapshot.slas_total,
        'slas_breached': today_snapshot.slas_breached,
        'renewals_due_30_days': today_snapshot.renewals_due_30_days,
        'renewals_due_60_days': today_snapshot.renewals_due_60_days,
        'renewals_due_90_days': today_snapshot.renewals_due_90_days,
        'total_vendors': today_snapshot.total_vendors,
        'vendors_at_risk': today_snapshot.vendors_at_risk,
    }

    for i in range(1, days):
        snapshot_date = today - timedelta(days=i)

        existing = await db.execute(
            select(MetricSnapshot).where(
                MetricSnapshot.snapshot_date == snapshot_date,
                MetricSnapshot.tenant_id == today_snapshot.tenant_id,
            )
        )
        if existing.scalar_one_or_none():
            continue

        snapshot = MetricSnapshot(
            snapshot_date=snapshot_date,
            tenant_id=today_snapshot.tenant_id,
        )

        drift = i
        snapshot.total_contracts = max(1, base['total_contracts'] - drift // 7)
        snapshot.contracts_at_risk = max(0, base['contracts_at_risk'] + random.randint(-1, 1))
        snapshot.total_contract_value = Decimal(str(max(0, base['total_contract_value'] * (1 - drift * 0.005 + random.uniform(-0.01, 0.01)))))
        snapshot.compliance_rate = Decimal(str(min(100, max(0, base['compliance_rate'] + random.uniform(-3, 3)))))
        snapshot.obligations_total = base['obligations_total']
        snapshot.obligations_completed = max(0, base['obligations_completed'] - random.randint(0, drift // 5))
        snapshot.obligations_overdue = max(0, base['obligations_overdue'] + random.randint(-1, 1))
        snapshot.sla_compliance_rate = Decimal(str(min(100, max(0, base['sla_compliance_rate'] + random.uniform(-3, 3)))))
        snapshot.slas_total = base['slas_total']
        snapshot.slas_breached = max(0, base['slas_breached'] + random.randint(-2, 2))
        snapshot.renewals_due_30_days = max(0, base['renewals_due_30_days'] + random.randint(-1, 1))
        snapshot.renewals_due_60_days = max(0, base['renewals_due_60_days'] + random.randint(-1, 1))
        snapshot.renewals_due_90_days = max(0, base['renewals_due_90_days'] + random.randint(-1, 2))
        snapshot.total_vendors = base['total_vendors']
        snapshot.vendors_at_risk = max(0, base['vendors_at_risk'] + random.randint(-1, 1))

        db.add(snapshot)
        created += 1

    await db.commit()
    return created
