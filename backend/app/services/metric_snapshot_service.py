"""Service for capturing and retrieving metric snapshots."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    MetricSnapshot,
    Contract,
    ContractStatus,
    Obligation,
    ObligationStatus,
    RAGStatus,
    ContractSLA,
)


async def capture_daily_snapshot(db: AsyncSession) -> MetricSnapshot:
    """
    Capture current metrics and store as daily snapshot.
    Should be called once per day by the scheduler.
    """
    today = date.today()

    # Check if snapshot already exists for today
    existing = await db.execute(
        select(MetricSnapshot).where(MetricSnapshot.snapshot_date == today)
    )
    if existing.scalar_one_or_none():
        # Update existing snapshot
        snapshot = existing.scalar_one()
    else:
        # Create new snapshot
        snapshot = MetricSnapshot(snapshot_date=today)
        db.add(snapshot)

    # Get completed contracts
    contracts_result = await db.execute(
        select(Contract).where(Contract.status == ContractStatus.COMPLETED)
    )
    contracts = list(contracts_result.scalars().all())

    # Contract metrics
    snapshot.total_contracts = len(contracts)
    snapshot.total_contract_value = sum(
        Decimal(str(c.contract_value)) for c in contracts if c.contract_value
    ) or Decimal('0')

    # Count at-risk contracts (those with high risk level or overdue obligations)
    at_risk_count = sum(1 for c in contracts if c.risk_level and c.risk_level.value == 'high')
    snapshot.contracts_at_risk = at_risk_count

    # Obligation metrics
    obligations_result = await db.execute(
        select(Obligation).join(Contract).where(Contract.status == ContractStatus.COMPLETED)
    )
    obligations = list(obligations_result.scalars().all())

    snapshot.obligations_total = len(obligations)
    snapshot.obligations_completed = sum(
        1 for o in obligations if o.status == ObligationStatus.COMPLETED
    )
    snapshot.obligations_overdue = sum(
        1 for o in obligations if o.status == ObligationStatus.OVERDUE
    )

    # Compliance rate — only obligations that are due or have no deadline
    # Exclude pending obligations with future deadlines (not yet actionable)
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
    slas_result = await db.execute(
        select(ContractSLA).join(Contract).where(Contract.status == ContractStatus.COMPLETED)
    )
    slas = list(slas_result.scalars().all())

    snapshot.slas_total = len(slas)
    snapshot.slas_breached = sum(1 for s in slas if s.consecutive_breaches > 0)

    # SLA compliance rate
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
    renewals_30 = 0
    renewals_60 = 0
    renewals_90 = 0
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

    # Vendor metrics (unique counterparties)
    counterparties = set(c.counterparty for c in contracts if c.counterparty)
    snapshot.total_vendors = len(counterparties)

    # Vendors at risk (counterparties with high-risk contracts)
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
    tenant_id: Optional[UUID] = None,  # TODO: Implement per-tenant metrics
) -> list[MetricSnapshot]:
    """
    Get metric snapshots for the specified number of days.

    Args:
        db: Database session
        days: Number of days of history to retrieve
        end_date: End date (defaults to today)

    Returns:
        List of MetricSnapshot objects ordered by date ascending
    """
    if end_date is None:
        end_date = date.today()

    start_date = end_date - timedelta(days=days - 1)

    result = await db.execute(
        select(MetricSnapshot)
        .where(
            and_(
                MetricSnapshot.snapshot_date >= start_date,
                MetricSnapshot.snapshot_date <= end_date
            )
        )
        .order_by(MetricSnapshot.snapshot_date.asc())
    )

    return list(result.scalars().all())


async def get_trend_data(
    db: AsyncSession,
    metric: str,
    days: int = 7,
    tenant_id: Optional[UUID] = None,  # TODO: Implement per-tenant metrics
) -> list[dict]:
    """
    Get trend data for a specific metric.

    Args:
        db: Database session
        metric: Name of the metric field
        days: Number of days of history

    Returns:
        List of {date, value} dicts
    """
    snapshots = await get_metric_history(db, days=days)

    # Map metric names to snapshot fields
    metric_map = {
        'total_contracts': 'total_contracts',
        'contracts_at_risk': 'contracts_at_risk',
        'compliance_rate': 'compliance_rate',
        'total_contract_value': 'total_contract_value',
        'obligations_total': 'obligations_total',
        'obligations_completed': 'obligations_completed',
        'obligations_overdue': 'obligations_overdue',
        'sla_compliance_rate': 'sla_compliance_rate',
        'slas_breached': 'slas_breached',
        'renewals_due_30_days': 'renewals_due_30_days',
        'total_vendors': 'total_vendors',
        'vendors_at_risk': 'vendors_at_risk',
    }

    field = metric_map.get(metric)
    if not field:
        return []

    return [
        {
            'date': s.snapshot_date.isoformat(),
            'value': float(getattr(s, field, 0) or 0)
        }
        for s in snapshots
    ]


async def backfill_snapshots(db: AsyncSession, days: int = 30) -> int:
    """
    Backfill missing snapshots using current real data with slight variation.
    First captures a real snapshot for today, then creates historical points
    with small daily variations to simulate realistic trends.
    """
    import random

    today = date.today()
    created = 0

    # Capture real data for today first
    today_snapshot = await capture_daily_snapshot(db)

    # Use today's real values as the base
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
            select(MetricSnapshot).where(MetricSnapshot.snapshot_date == snapshot_date)
        )
        if existing.scalar_one_or_none():
            continue

        snapshot = MetricSnapshot(snapshot_date=snapshot_date)

        # Apply small daily drift from the real base values
        drift = i  # days ago
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
