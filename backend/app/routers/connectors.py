"""Connectors Router - API endpoints for external system data.

Provides access to SLA actuals, milestone status, FX rates, and other
external data needed for contract governance.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.servicenow_stub import get_servicenow_stub
from app.connectors.milestone_stub import get_milestone_stub
from app.connectors.fx_stub import get_fx_stub
from app.core.deps import CurrentUser
from app.database import get_db
from app.models.sla import ContractSLA
from app.services.sla_comparison import run_sla_comparison, ComplianceStatus

router = APIRouter(prefix="/api/connectors", tags=["Connectors"])


# Response models
class SLAActualResponse(BaseModel):
    """SLA actual value response."""

    sla_reference: str
    sla_name: str
    actual_value: float
    target_value: float | None
    measurement_period_start: date | None
    measurement_period_end: date | None
    is_compliant: bool | None
    deviation_percentage: float | None
    source_system: str
    notes: str | None


class MilestoneResponse(BaseModel):
    """Milestone status response."""

    milestone_id: str
    milestone_name: str
    planned_date: date
    actual_date: date | None
    status: str
    days_variance: int
    completion_percentage: int
    dependencies: list[str]
    notes: str | None


class FXRateResponse(BaseModel):
    """FX rate response."""

    base_currency: str
    target_currency: str
    rate: float
    rate_date: date
    source: str


class ConnectorStatusResponse(BaseModel):
    """Connector status response."""

    name: str
    type: str
    is_stub: bool
    is_connected: bool
    health: str


@router.get("/status")
async def get_connector_status(
    current_user: CurrentUser,
) -> list[ConnectorStatusResponse]:
    """Get status of all connectors.

    Returns:
        List of connector statuses.
    """
    connectors = [
        {
            "name": "ServiceNow (Stub)",
            "type": "ITSM",
            "is_stub": True,
            "is_connected": True,
            "health": "healthy",
        },
        {
            "name": "Project Management (Stub)",
            "type": "Project",
            "is_stub": True,
            "is_connected": True,
            "health": "healthy",
        },
        {
            "name": "FX Rates (Stub)",
            "type": "FX",
            "is_stub": True,
            "is_connected": True,
            "health": "healthy",
        },
    ]
    return [ConnectorStatusResponse(**c) for c in connectors]


@router.get("/sla-actuals/{contract_id}")
async def get_sla_actuals(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    start_date: date = Query(default=None, description="Start of measurement period"),
    end_date: date = Query(default=None, description="End of measurement period"),
) -> list[SLAActualResponse]:
    """Get actual SLA values from external system for a contract.

    Args:
        contract_id: Contract ID to get SLA actuals for.
        start_date: Start of measurement period (default: start of current month).
        end_date: End of measurement period (default: today).

    Returns:
        List of SLA actual values.
    """
    import uuid

    # Default to current month
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date.replace(day=1)

    # Get SLA references from database
    result = await db.execute(
        select(ContractSLA.section_reference, ContractSLA.sla_name, ContractSLA.target_value)
        .where(ContractSLA.contract_id == uuid.UUID(contract_id))
        .where(ContractSLA.section_reference.isnot(None))
    )
    slas = result.all()

    if not slas:
        return []

    # Get actuals from connector
    connector = get_servicenow_stub()
    await connector.connect()

    sla_refs = [s[0] for s in slas if s[0]]
    actuals_result = await connector.get_sla_actuals(sla_refs, start_date, end_date)

    if not actuals_result.success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to get SLA actuals: {actuals_result.error}",
        )

    return [
        SLAActualResponse(
            sla_reference=a.sla_reference,
            sla_name=a.sla_name,
            actual_value=float(a.actual_value),
            target_value=float(a.target_value) if a.target_value else None,
            measurement_period_start=a.measurement_period_start,
            measurement_period_end=a.measurement_period_end,
            is_compliant=a.is_compliant,
            deviation_percentage=float(a.deviation_percentage) if a.deviation_percentage else None,
            source_system=a.source_system,
            notes=a.notes,
        )
        for a in actuals_result.data
    ]


@router.get("/sla-history/{contract_id}")
async def get_sla_history(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    months: int = Query(default=12, ge=1, le=24, description="Months of history"),
) -> dict:
    """Get historical SLA performance for trend analysis.

    Args:
        contract_id: Contract ID.
        months: Number of months of history.

    Returns:
        Historical SLA data with trends.
    """
    import uuid

    # Get SLA references from database
    result = await db.execute(
        select(ContractSLA.section_reference)
        .where(ContractSLA.contract_id == uuid.UUID(contract_id))
        .where(ContractSLA.section_reference.isnot(None))
    )
    sla_refs = [r[0] for r in result.all() if r[0]]

    if not sla_refs:
        return {"history": {}, "summary": {}}

    # Get history from connector
    connector = get_servicenow_stub()
    await connector.connect()

    history_result = await connector.get_monthly_sla_history(sla_refs, months)

    if not history_result.success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to get SLA history: {history_result.error}",
        )

    return history_result.data


@router.get("/milestones")
async def get_milestones(
    current_user: CurrentUser,
    project_id: str = Query(default=None, description="Optional project ID"),
) -> list[MilestoneResponse]:
    """Get project milestone statuses.

    Args:
        project_id: Optional project ID filter.

    Returns:
        List of milestone statuses.
    """
    connector = get_milestone_stub()
    await connector.connect()

    result = await connector.get_milestone_status(project_id=project_id)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to get milestones: {result.error}",
        )

    return [
        MilestoneResponse(
            milestone_id=m.milestone_id,
            milestone_name=m.milestone_name,
            planned_date=m.planned_date,
            actual_date=m.actual_date,
            status=m.status,
            days_variance=m.days_variance,
            completion_percentage=m.completion_percentage,
            dependencies=m.dependencies,
            notes=m.notes,
        )
        for m in result.data
    ]


@router.get("/milestones/timeline")
async def get_milestone_timeline(
    current_user: CurrentUser,
) -> dict:
    """Get full milestone timeline with Gantt-style data.

    Returns:
        Timeline data for visualization.
    """
    connector = get_milestone_stub()
    await connector.connect()

    result = await connector.get_milestone_timeline()

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to get timeline: {result.error}",
        )

    return result.data


@router.get("/fx/rate")
async def get_fx_rate(
    current_user: CurrentUser,
    base: str = Query(..., description="Base currency code (e.g., EUR)"),
    target: str = Query(..., description="Target currency code (e.g., USD)"),
    rate_date: date = Query(default=None, description="Date for rate (default: today)"),
) -> FXRateResponse:
    """Get current exchange rate.

    Args:
        base: Base currency code.
        target: Target currency code.
        rate_date: Optional specific date.

    Returns:
        Exchange rate.
    """
    connector = get_fx_stub()
    await connector.connect()

    result = await connector.get_rate(base, target, rate_date)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    rate = result.data
    return FXRateResponse(
        base_currency=rate.base_currency,
        target_currency=rate.target_currency,
        rate=float(rate.rate),
        rate_date=rate.rate_date,
        source=rate.source,
    )


@router.get("/fx/history")
async def get_fx_history(
    current_user: CurrentUser,
    base: str = Query(..., description="Base currency code"),
    target: str = Query(..., description="Target currency code"),
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(default=None, description="End date (default: today)"),
) -> dict:
    """Get historical exchange rates.

    Args:
        base: Base currency code.
        target: Target currency code.
        start_date: Start date.
        end_date: End date.

    Returns:
        Historical rates with summary.
    """
    if end_date is None:
        end_date = date.today()

    connector = get_fx_stub()
    await connector.connect()

    result = await connector.get_rates_history(base, target, start_date, end_date)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    # Convert rates to serializable format
    data = result.data
    return {
        "rates": [
            {
                "date": r.rate_date.isoformat(),
                "rate": float(r.rate),
            }
            for r in data["rates"]
        ],
        "summary": data["summary"],
    }


@router.get("/fx/cola-adjustment")
async def get_cola_adjustment(
    current_user: CurrentUser,
    base: str = Query(..., description="Contract base currency"),
    target: str = Query(..., description="Payment currency"),
    contract_rate: float = Query(..., description="Exchange rate at contract signing"),
) -> dict:
    """Calculate COLA adjustment based on FX movement.

    Args:
        base: Contract base currency.
        target: Payment currency.
        contract_rate: Original contract exchange rate.

    Returns:
        COLA adjustment calculation.
    """
    connector = get_fx_stub()
    await connector.connect()

    result = await connector.get_cola_adjustment(
        base, target, Decimal(str(contract_rate))
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    return result.data


@router.get("/incident-metrics")
async def get_incident_metrics(
    current_user: CurrentUser,
    start_date: date = Query(default=None, description="Start date"),
    end_date: date = Query(default=None, description="End date"),
) -> dict:
    """Get incident management metrics.

    Args:
        start_date: Start date (default: 30 days ago).
        end_date: End date (default: today).

    Returns:
        Incident metrics summary.
    """
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    connector = get_servicenow_stub()
    await connector.connect()

    result = await connector.get_incident_metrics(start_date, end_date)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to get incident metrics: {result.error}",
        )

    return result.data


# Comparison response models
class SLAComparisonResponse(BaseModel):
    """Individual SLA comparison result."""

    sla_reference: str
    sla_name: str
    category: str | None
    target_value: float
    minimum_value: float | None
    actual_value: float | None
    status: str
    deviation_from_target: float | None
    breach_severity: str | None
    service_credit_applicable: bool
    service_credit_amount: float | None
    notes: str | None


class ComparisonSummaryResponse(BaseModel):
    """Contract comparison summary."""

    contract_id: str
    measurement_period_start: date
    measurement_period_end: date
    total_slas: int
    compliant_count: int
    warning_count: int
    breach_count: int
    no_data_count: int
    overall_compliance_rate: float
    overall_status: str
    total_at_risk: float
    total_credits_due: float
    comparisons: list[SLAComparisonResponse]


@router.post("/compare/{contract_id}")
async def run_contract_comparison(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    start_date: date = Query(default=None, description="Start of measurement period"),
    end_date: date = Query(default=None, description="End of measurement period"),
) -> ComparisonSummaryResponse:
    """Run SLA comparison for a contract.

    Compares contracted SLA targets against actual values from
    external systems (or stubs). Calculates breaches and service credits.

    Args:
        contract_id: Contract ID to compare.
        start_date: Start of measurement period (default: start of current month).
        end_date: End of measurement period (default: today).

    Returns:
        Comparison summary with all SLA results.
    """
    import uuid as uuid_mod

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date.replace(day=1)

    try:
        summary = await run_sla_comparison(
            db=db,
            contract_id=uuid_mod.UUID(contract_id),
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Comparison failed: {str(e)}",
        )

    await db.commit()

    return ComparisonSummaryResponse(
        contract_id=str(summary.contract_id),
        measurement_period_start=summary.measurement_period_start,
        measurement_period_end=summary.measurement_period_end,
        total_slas=summary.total_slas,
        compliant_count=summary.compliant_count,
        warning_count=summary.warning_count,
        breach_count=summary.breach_count,
        no_data_count=summary.no_data_count,
        overall_compliance_rate=float(summary.overall_compliance_rate),
        overall_status=summary.overall_status.value,
        total_at_risk=float(summary.total_at_risk),
        total_credits_due=float(summary.total_credits_due),
        comparisons=[
            SLAComparisonResponse(
                sla_reference=c.sla_reference,
                sla_name=c.sla_name,
                category=c.category,
                target_value=float(c.target_value),
                minimum_value=float(c.minimum_value) if c.minimum_value else None,
                actual_value=float(c.actual_value) if c.actual_value else None,
                status=c.status.value,
                deviation_from_target=float(c.deviation_from_target) if c.deviation_from_target else None,
                breach_severity=c.breach_severity.value if c.breach_severity else None,
                service_credit_applicable=c.service_credit_applicable,
                service_credit_amount=float(c.service_credit_amount) if c.service_credit_amount else None,
                notes=c.notes,
            )
            for c in summary.sla_comparisons
        ],
    )


@router.get("/compliance-dashboard/{contract_id}")
async def get_compliance_dashboard(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get compliance dashboard data for a contract.

    Provides summary metrics and recent comparison history.

    Args:
        contract_id: Contract ID.

    Returns:
        Dashboard data with compliance metrics.
    """
    import uuid as uuid_mod
    from datetime import datetime, timedelta

    contract_uuid = uuid_mod.UUID(contract_id)

    # Get SLA summary
    result = await db.execute(
        select(ContractSLA)
        .where(ContractSLA.contract_id == contract_uuid)
        .where(ContractSLA.is_active == True)
    )
    slas = result.scalars().all()

    if not slas:
        return {
            "contract_id": contract_id,
            "total_slas": 0,
            "categories": [],
            "compliance_summary": {},
            "at_risk_summary": {},
        }

    # Group by category
    categories = {}
    for sla in slas:
        cat = sla.category or "Other"
        if cat not in categories:
            categories[cat] = {
                "name": cat,
                "total": 0,
                "critical": 0,
                "with_penalty": 0,
                "at_risk_total": Decimal("0"),
            }
        categories[cat]["total"] += 1
        if sla.severity and sla.severity.value == "critical":
            categories[cat]["critical"] += 1
        if sla.has_penalty:
            categories[cat]["with_penalty"] += 1
        if sla.at_risk_percentage:
            categories[cat]["at_risk_total"] += sla.at_risk_percentage

    # Get recent performance data
    from app.models.sla import SLAPerformance

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    perf_result = await db.execute(
        select(SLAPerformance)
        .join(ContractSLA)
        .where(ContractSLA.contract_id == contract_uuid)
        .where(SLAPerformance.measured_at >= thirty_days_ago)
        .order_by(SLAPerformance.measured_at.desc())
        .limit(100)
    )
    performances = perf_result.scalars().all()

    compliant_count = sum(1 for p in performances if p.is_compliant)
    total_measured = len(performances)

    return {
        "contract_id": contract_id,
        "total_slas": len(slas),
        "categories": [
            {
                "name": k,
                "total": v["total"],
                "critical": v["critical"],
                "with_penalty": v["with_penalty"],
                "at_risk_total": float(v["at_risk_total"]),
            }
            for k, v in categories.items()
        ],
        "compliance_summary": {
            "last_30_days": {
                "measurements": total_measured,
                "compliant": compliant_count,
                "compliance_rate": round(compliant_count / total_measured * 100, 1) if total_measured > 0 else 0,
            },
        },
        "at_risk_summary": {
            "total_at_risk_percentage": float(sum(s.at_risk_percentage or 0 for s in slas)),
            "slas_with_penalty": sum(1 for s in slas if s.has_penalty),
            "earnback_eligible": sum(1 for s in slas if s.earnback_eligible),
        },
    }
