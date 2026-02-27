"""Metrics API endpoints for historical trend data."""

from datetime import date
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, CurrentTenantId
from app.database import get_db
from app.services.metric_snapshot_service import (
    capture_daily_snapshot,
    get_metric_history,
    get_trend_data,
    backfill_snapshots,
)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


class TrendPoint(BaseModel):
    """Single point in a trend line."""
    date: str
    value: float


class TrendResponse(BaseModel):
    """Response with trend data for sparklines."""
    metric: str
    days: int
    data: list[TrendPoint]


class DashboardTrends(BaseModel):
    """All trends needed for the dashboard."""
    total_contracts: list[float]
    contracts_at_risk: list[float]
    compliance_rate: list[float]
    total_contract_value: list[float]
    sla_compliance_rate: list[float]
    obligations_overdue: list[float]


class SnapshotResponse(BaseModel):
    """Full snapshot data."""
    snapshot_date: str
    total_contracts: int
    contracts_at_risk: int
    total_contract_value: float
    compliance_rate: float
    obligations_total: int
    obligations_completed: int
    obligations_overdue: int
    sla_compliance_rate: float
    slas_total: int
    slas_breached: int
    renewals_due_30_days: int
    renewals_due_60_days: int
    renewals_due_90_days: int
    total_vendors: int
    vendors_at_risk: int


@router.get("/trends/{metric}", response_model=TrendResponse)
async def get_metric_trend(
    metric: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    days: int = Query(default=7, ge=1, le=90),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """
    Get trend data for a specific metric.

    Supported metrics:
    - total_contracts
    - contracts_at_risk
    - compliance_rate
    - total_contract_value
    - obligations_overdue
    - sla_compliance_rate
    - slas_breached
    """
    # TODO: Pass tenant_id to get_trend_data for tenant-scoped metrics
    data = await get_trend_data(db, metric, days, tenant_id=tenant_id)
    return TrendResponse(
        metric=metric,
        days=days,
        data=[TrendPoint(**d) for d in data]
    )


@router.get("/dashboard-trends", response_model=DashboardTrends)
async def get_dashboard_trends(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    days: int = Query(default=7, ge=1, le=30),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    """
    Get all trend data needed for the dashboard sparklines.
    Returns arrays of values (most recent last) for each metric.
    """
    # TODO: Pass tenant_id to get_metric_history for tenant-scoped metrics
    snapshots = await get_metric_history(db, days=days, tenant_id=tenant_id)

    # If no snapshots, return empty arrays
    if not snapshots:
        return DashboardTrends(
            total_contracts=[],
            contracts_at_risk=[],
            compliance_rate=[],
            total_contract_value=[],
            sla_compliance_rate=[],
            obligations_overdue=[],
        )

    return DashboardTrends(
        total_contracts=[s.total_contracts for s in snapshots],
        contracts_at_risk=[s.contracts_at_risk for s in snapshots],
        compliance_rate=[float(s.compliance_rate) for s in snapshots],
        total_contract_value=[float(s.total_contract_value) for s in snapshots],
        sla_compliance_rate=[float(s.sla_compliance_rate) for s in snapshots],
        obligations_overdue=[s.obligations_overdue for s in snapshots],
    )


@router.get("/history", response_model=list[SnapshotResponse])
async def get_history(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get full metric history for the specified number of days."""
    snapshots = await get_metric_history(db, days=days)

    return [
        SnapshotResponse(
            snapshot_date=s.snapshot_date.isoformat(),
            total_contracts=s.total_contracts,
            contracts_at_risk=s.contracts_at_risk,
            total_contract_value=float(s.total_contract_value),
            compliance_rate=float(s.compliance_rate),
            obligations_total=s.obligations_total,
            obligations_completed=s.obligations_completed,
            obligations_overdue=s.obligations_overdue,
            sla_compliance_rate=float(s.sla_compliance_rate),
            slas_total=s.slas_total,
            slas_breached=s.slas_breached,
            renewals_due_30_days=s.renewals_due_30_days,
            renewals_due_60_days=s.renewals_due_60_days,
            renewals_due_90_days=s.renewals_due_90_days,
            total_vendors=s.total_vendors,
            vendors_at_risk=s.vendors_at_risk,
        )
        for s in snapshots
    ]


@router.post("/capture")
async def capture_snapshot(db: AsyncSession = Depends(get_db)):
    """
    Manually capture a snapshot for today.
    Usually called by the scheduler, but can be triggered manually.
    """
    snapshot = await capture_daily_snapshot(db)
    return {
        "status": "success",
        "date": snapshot.snapshot_date.isoformat(),
        "message": f"Snapshot captured for {snapshot.snapshot_date}"
    }


@router.post("/backfill")
async def backfill(
    days: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """
    Backfill missing snapshots with simulated data.
    Only for demo/testing - in production use real historical data.
    """
    created = await backfill_snapshots(db, days=days)
    return {
        "status": "success",
        "created": created,
        "message": f"Created {created} backfill snapshots"
    }
