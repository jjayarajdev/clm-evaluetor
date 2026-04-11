"""SLA router for tracking and breach detection."""

import uuid as uuid_mod
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, CurrentTenantId
from app.database import get_db
from app.models.sla import (
    ContractSLA,
    SLAPerformance,
    SLAMetricType,
    SLAUnit,
    SLASeverity,
    BreachSeverity,
)
from app.models.contract import Contract
from app.schemas.sla import (
    SLACreate,
    SLAUpdate,
    SLAResponse,
    SLAPerformanceCreate,
    SLAPerformanceResponse,
    SLAWithPerformance,
    SLAComplianceResponse,
    SLAComplianceByContract,
    SLABreachesResponse,
    SLABreachItem,
)

router = APIRouter(prefix="/api/sla", tags=["SLA Tracking"])


def sla_to_response(sla: ContractSLA) -> SLAResponse:
    """Convert ContractSLA model to response schema."""
    return SLAResponse(
        id=str(sla.id),
        contract_id=str(sla.contract_id),
        sla_name=sla.sla_name,
        sla_description=sla.sla_description,
        metric_type=sla.metric_type.value if sla.metric_type else "custom",
        metric_unit=sla.metric_unit.value if sla.metric_unit else "percentage",
        target_value=float(sla.target_value) if sla.target_value else 0,
        target_operator=sla.target_operator or ">=",
        warning_threshold=float(sla.warning_threshold) if sla.warning_threshold else None,
        severity=sla.severity.value if sla.severity else "medium",
        has_penalty=sla.has_penalty or False,
        penalty_type=sla.penalty_type,
        penalty_value=float(sla.penalty_value) if sla.penalty_value else None,
        penalty_description=sla.penalty_description,
        max_penalty_cap=float(sla.max_penalty_cap) if sla.max_penalty_cap else None,
        measurement_period=sla.measurement_period,
        is_active=sla.is_active,
        current_compliance_rate=float(sla.current_compliance_rate) if sla.current_compliance_rate else None,
        last_measured_at=sla.last_measured_at,
        consecutive_breaches=sla.consecutive_breaches or 0,
        source_text=sla.source_text,
        created_at=sla.created_at,
        updated_at=sla.updated_at,
    )


def performance_to_response(perf: SLAPerformance) -> SLAPerformanceResponse:
    """Convert SLAPerformance model to response schema."""
    return SLAPerformanceResponse(
        id=str(perf.id),
        sla_id=str(perf.sla_id),
        actual_value=float(perf.actual_value) if perf.actual_value else 0,
        measured_at=perf.measured_at,
        measurement_period_start=perf.measurement_period_start,
        measurement_period_end=perf.measurement_period_end,
        is_compliant=perf.is_compliant,
        deviation_percentage=float(perf.deviation_percentage) if perf.deviation_percentage else None,
        breach_severity=perf.breach_severity.value if perf.breach_severity else None,
        penalty_applied=perf.penalty_applied or False,
        penalty_amount=float(perf.penalty_amount) if perf.penalty_amount else None,
        credit_issued=float(perf.credit_issued) if perf.credit_issued else None,
        notes=perf.notes,
        recorded_by=perf.recorded_by,
        created_at=perf.created_at,
    )


def check_compliance(target_value: Decimal, actual_value: Decimal, operator: str) -> bool:
    """Check if actual value meets the SLA target."""
    if operator == ">=":
        return actual_value >= target_value
    elif operator == "<=":
        return actual_value <= target_value
    elif operator == ">":
        return actual_value > target_value
    elif operator == "<":
        return actual_value < target_value
    elif operator == "=":
        return actual_value == target_value
    return False


def calculate_deviation(target_value: Decimal, actual_value: Decimal, operator: str) -> Decimal:
    """Calculate percentage deviation from target."""
    if target_value == 0:
        return Decimal(0)

    if operator in [">=", ">"]:
        # For "greater than" targets, negative deviation means below target
        deviation = ((actual_value - target_value) / target_value) * 100
    else:
        # For "less than" targets, positive deviation means above target (bad)
        deviation = ((target_value - actual_value) / target_value) * 100

    return deviation


def determine_breach_severity(deviation: Decimal) -> BreachSeverity | None:
    """Determine breach severity based on deviation percentage."""
    abs_deviation = abs(deviation)
    if abs_deviation < 5:
        return BreachSeverity.MINOR
    elif abs_deviation < 15:
        return BreachSeverity.MODERATE
    elif abs_deviation < 30:
        return BreachSeverity.MAJOR
    else:
        return BreachSeverity.CRITICAL


@router.get("/{contract_id}", response_model=list[SLAWithPerformance])
async def get_contract_slas(
    contract_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    include_inactive: bool = False,
) -> list[SLAWithPerformance]:
    """Get all SLAs for a contract with recent performance history."""
    # First verify contract belongs to tenant
    contract_query = select(Contract).where(Contract.id == uuid_mod.UUID(contract_id))
    if tenant_id is not None:
        contract_query = contract_query.where(Contract.tenant_id == tenant_id)
    contract_result = await db.execute(contract_query)
    if not contract_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Contract not found")

    query = select(ContractSLA).where(
        ContractSLA.contract_id == uuid_mod.UUID(contract_id)
    )

    if not include_inactive:
        query = query.where(ContractSLA.is_active == True)

    query = query.order_by(ContractSLA.severity, ContractSLA.sla_name)

    result = await db.execute(query)
    slas = result.scalars().all()

    response = []
    for sla in slas:
        # Get recent performance (last 10)
        perf_result = await db.execute(
            select(SLAPerformance)
            .where(SLAPerformance.sla_id == sla.id)
            .order_by(SLAPerformance.measured_at.desc())
            .limit(10)
        )
        performances = perf_result.scalars().all()

        # Determine trend
        trend = None
        if len(performances) >= 3:
            recent = [p.is_compliant for p in performances[:3]]
            older = [p.is_compliant for p in performances[3:6]] if len(performances) >= 6 else []

            recent_rate = sum(recent) / len(recent)
            older_rate = sum(older) / len(older) if older else recent_rate

            if recent_rate > older_rate + 0.1:
                trend = "improving"
            elif recent_rate < older_rate - 0.1:
                trend = "declining"
            else:
                trend = "stable"

        sla_resp = sla_to_response(sla)
        response.append(SLAWithPerformance(
            **sla_resp.model_dump(),
            recent_performances=[performance_to_response(p) for p in performances],
            compliance_trend=trend,
        ))

    return response


@router.post("/{contract_id}", response_model=SLAResponse)
async def create_sla(
    contract_id: str,
    sla_data: SLACreate,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SLAResponse:
    """Create a new SLA for a contract."""
    # Verify contract exists and belongs to tenant
    contract_query = select(Contract).where(Contract.id == uuid_mod.UUID(contract_id))
    if tenant_id is not None:
        contract_query = contract_query.where(Contract.tenant_id == tenant_id)
    contract_result = await db.execute(contract_query)
    if not contract_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Contract not found")

    sla = ContractSLA(
        contract_id=uuid_mod.UUID(contract_id),
        source_clause_id=uuid_mod.UUID(sla_data.source_clause_id) if sla_data.source_clause_id else None,
        sla_name=sla_data.sla_name,
        sla_description=sla_data.sla_description,
        metric_type=SLAMetricType(sla_data.metric_type),
        metric_unit=SLAUnit(sla_data.metric_unit),
        target_value=sla_data.target_value,
        target_operator=sla_data.target_operator,
        warning_threshold=sla_data.warning_threshold,
        severity=SLASeverity(sla_data.severity),
        has_penalty=sla_data.has_penalty,
        penalty_type=sla_data.penalty_type,
        penalty_value=sla_data.penalty_value,
        penalty_description=sla_data.penalty_description,
        max_penalty_cap=sla_data.max_penalty_cap,
        measurement_period=sla_data.measurement_period,
        source_text=sla_data.source_text,
    )

    db.add(sla)
    await db.commit()
    await db.refresh(sla)

    return sla_to_response(sla)


@router.post("/{contract_id}/performance/{sla_id}", response_model=SLAPerformanceResponse)
async def log_sla_performance(
    contract_id: str,
    sla_id: str,
    perf_data: SLAPerformanceCreate,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SLAPerformanceResponse:
    """Log a performance measurement for an SLA."""
    # Verify contract belongs to tenant first
    contract_query = select(Contract).where(Contract.id == uuid_mod.UUID(contract_id))
    if tenant_id is not None:
        contract_query = contract_query.where(Contract.tenant_id == tenant_id)
    contract_result = await db.execute(contract_query)
    if not contract_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Contract not found")

    # Get the SLA
    result = await db.execute(
        select(ContractSLA).where(
            ContractSLA.id == uuid_mod.UUID(sla_id),
            ContractSLA.contract_id == uuid_mod.UUID(contract_id),
        )
    )
    sla = result.scalar_one_or_none()

    if not sla:
        raise HTTPException(status_code=404, detail="SLA not found")

    # Calculate compliance
    is_compliant = check_compliance(sla.target_value, perf_data.actual_value, sla.target_operator)
    deviation = calculate_deviation(sla.target_value, perf_data.actual_value, sla.target_operator)
    breach_severity = None if is_compliant else determine_breach_severity(deviation)

    # Calculate penalty if applicable
    penalty_amount = None
    if not is_compliant and sla.has_penalty and sla.penalty_value:
        if sla.penalty_type == "percentage":
            # Penalty as percentage of some base (simplified - just use the value)
            penalty_amount = sla.penalty_value
        else:
            penalty_amount = sla.penalty_value

        # Apply cap if exists
        if sla.max_penalty_cap and penalty_amount > sla.max_penalty_cap:
            penalty_amount = sla.max_penalty_cap

    # Create performance record
    measured_at = perf_data.measured_at or datetime.now()
    performance = SLAPerformance(
        sla_id=sla.id,
        actual_value=perf_data.actual_value,
        measured_at=measured_at,
        measurement_period_start=perf_data.measurement_period_start,
        measurement_period_end=perf_data.measurement_period_end,
        is_compliant=is_compliant,
        deviation_percentage=deviation,
        breach_severity=breach_severity,
        penalty_applied=penalty_amount is not None,
        penalty_amount=penalty_amount,
        notes=perf_data.notes,
        recorded_by=perf_data.recorded_by or current_user.username,
    )

    db.add(performance)

    # Update SLA status
    sla.last_measured_at = measured_at
    if is_compliant:
        sla.consecutive_breaches = 0
    else:
        sla.consecutive_breaches = (sla.consecutive_breaches or 0) + 1

    # Recalculate compliance rate (last 10 measurements)
    perf_result = await db.execute(
        select(SLAPerformance.is_compliant)
        .where(SLAPerformance.sla_id == sla.id)
        .order_by(SLAPerformance.measured_at.desc())
        .limit(10)
    )
    recent = [r[0] for r in perf_result.all()]
    if recent:
        sla.current_compliance_rate = Decimal(sum(recent) / len(recent) * 100)

    await db.commit()
    await db.refresh(performance)

    return performance_to_response(performance)


@router.get("/compliance/summary", response_model=SLAComplianceResponse)
async def get_sla_compliance(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    contract_id: str | None = None,
) -> SLAComplianceResponse:
    """Get SLA compliance summary across all contracts or a specific contract."""
    # Build query with tenant filter via contract join
    query = (
        select(ContractSLA)
        .join(Contract, ContractSLA.contract_id == Contract.id)
        .where(ContractSLA.is_active == True)
    )
    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)

    if contract_id:
        query = query.where(ContractSLA.contract_id == uuid_mod.UUID(contract_id))

    result = await db.execute(query)
    slas = result.scalars().all()

    if not slas:
        return SLAComplianceResponse(
            total_slas=0,
            total_active=0,
            overall_compliance_rate=0,
            by_metric_type={},
            by_severity={},
            contracts=[],
            total_breaches=0,
            total_penalties_this_period=0,
            critical_breaches=0,
        )

    # Aggregate by metric type and severity
    by_metric: dict[str, dict] = {}
    by_severity: dict[str, dict] = {}
    by_contract: dict[str, dict] = {}
    total_compliant = 0
    total_breaches = 0
    critical_breaches = 0
    total_penalties = Decimal(0)

    for sla in slas:
        metric_type = sla.metric_type.value if sla.metric_type else "custom"
        severity = sla.severity.value if sla.severity else "medium"
        contract_key = str(sla.contract_id)

        # Initialize dicts
        if metric_type not in by_metric:
            by_metric[metric_type] = {"total": 0, "compliant": 0}
        if severity not in by_severity:
            by_severity[severity] = {"total": 0, "compliant": 0}
        if contract_key not in by_contract:
            by_contract[contract_key] = {
                "total": 0, "compliant": 0, "breached": 0,
                "penalties": Decimal(0), "active_breaches": 0
            }

        # Count totals
        by_metric[metric_type]["total"] += 1
        by_severity[severity]["total"] += 1
        by_contract[contract_key]["total"] += 1

        # Check compliance (based on current rate)
        is_compliant = sla.current_compliance_rate and sla.current_compliance_rate >= 95

        if is_compliant:
            total_compliant += 1
            by_metric[metric_type]["compliant"] += 1
            by_severity[severity]["compliant"] += 1
            by_contract[contract_key]["compliant"] += 1
        else:
            by_contract[contract_key]["breached"] += 1

        if sla.consecutive_breaches and sla.consecutive_breaches > 0:
            total_breaches += 1
            by_contract[contract_key]["active_breaches"] += 1
            if severity == "critical":
                critical_breaches += 1

    # Calculate compliance rates
    total_slas = len(slas)
    overall_rate = (total_compliant / total_slas * 100) if total_slas > 0 else 0

    for metric_data in by_metric.values():
        metric_data["compliance_rate"] = (
            metric_data["compliant"] / metric_data["total"] * 100
        ) if metric_data["total"] > 0 else 0

    for severity_data in by_severity.values():
        severity_data["compliance_rate"] = (
            severity_data["compliant"] / severity_data["total"] * 100
        ) if severity_data["total"] > 0 else 0

    # Get contract filenames
    contract_ids = list(by_contract.keys())
    contract_names: dict[str, str] = {}
    if contract_ids:
        name_result = await db.execute(
            select(Contract.id, Contract.filename)
            .where(Contract.id.in_([uuid_mod.UUID(cid) for cid in contract_ids]))
        )
        for cid, fname in name_result.all():
            contract_names[str(cid)] = fname

    # Build contract list
    contracts = [
        SLAComplianceByContract(
            contract_id=cid,
            contract_filename=contract_names.get(cid, "Unknown"),
            total_slas=data["total"],
            compliant_slas=data["compliant"],
            breached_slas=data["breached"],
            compliance_rate=(data["compliant"] / data["total"] * 100) if data["total"] > 0 else 0,
            total_penalties=float(data["penalties"]),
            active_breaches=data["active_breaches"],
        )
        for cid, data in by_contract.items()
    ]

    return SLAComplianceResponse(
        total_slas=total_slas,
        total_active=total_slas,
        overall_compliance_rate=round(overall_rate, 2),
        by_metric_type=by_metric,
        by_severity=by_severity,
        contracts=contracts,
        total_breaches=total_breaches,
        total_penalties_this_period=float(total_penalties),
        critical_breaches=critical_breaches,
    )


@router.get("/breaches/active", response_model=SLABreachesResponse)
async def get_active_breaches(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SLABreachesResponse:
    """Get all currently active SLA breaches."""
    # Get SLAs with consecutive breaches > 0 - with tenant filter
    query = (
        select(ContractSLA, Contract.filename)
        .join(Contract, ContractSLA.contract_id == Contract.id)
        .where(
            ContractSLA.is_active == True,
            ContractSLA.consecutive_breaches > 0,
        )
        .order_by(ContractSLA.severity, ContractSLA.consecutive_breaches.desc())
    )
    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)
    result = await db.execute(query)

    breaches_by_severity: dict[str, list[SLABreachItem]] = {
        "critical": [], "high": [], "medium": [], "low": []
    }
    total_penalty_exposure = Decimal(0)

    for sla, filename in result.all():
        # Get latest performance record
        perf_result = await db.execute(
            select(SLAPerformance)
            .where(SLAPerformance.sla_id == sla.id)
            .order_by(SLAPerformance.measured_at.desc())
            .limit(1)
        )
        latest = perf_result.scalar_one_or_none()

        if latest:
            severity_key = sla.severity.value if sla.severity else "medium"
            breach_item = SLABreachItem(
                sla_id=str(sla.id),
                sla_name=sla.sla_name,
                contract_id=str(sla.contract_id),
                contract_filename=filename,
                metric_type=sla.metric_type.value if sla.metric_type else "custom",
                target_value=float(sla.target_value) if sla.target_value else 0,
                actual_value=float(latest.actual_value) if latest.actual_value else 0,
                deviation_percentage=float(latest.deviation_percentage) if latest.deviation_percentage else 0,
                breach_severity=latest.breach_severity.value if latest.breach_severity else "minor",
                measured_at=latest.measured_at,
                penalty_amount=float(latest.penalty_amount) if latest.penalty_amount else None,
                consecutive_breaches=sla.consecutive_breaches or 0,
            )
            breaches_by_severity[severity_key].append(breach_item)

            if sla.penalty_value:
                total_penalty_exposure += sla.penalty_value

    total_breaches = sum(len(b) for b in breaches_by_severity.values())

    return SLABreachesResponse(
        total_breaches=total_breaches,
        critical=breaches_by_severity["critical"],
        high=breaches_by_severity["high"],
        medium=breaches_by_severity["medium"],
        low=breaches_by_severity["low"],
        total_penalty_exposure=float(total_penalty_exposure),
    )


@router.get("/")
async def list_all_slas(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    metric_type: str | None = None,
    severity: str | None = None,
    has_breach: bool | None = None,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
):
    """List all SLAs with optional filters and pagination."""
    # Apply tenant filter via contract join
    query = (
        select(ContractSLA)
        .join(Contract, ContractSLA.contract_id == Contract.id)
        .where(ContractSLA.is_active == True)
    )
    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)

    if metric_type:
        query = query.where(ContractSLA.metric_type == SLAMetricType(metric_type))

    if severity:
        query = query.where(ContractSLA.severity == SLASeverity(severity))

    if has_breach is True:
        query = query.where(ContractSLA.consecutive_breaches > 0)
    elif has_breach is False:
        query = query.where(ContractSLA.consecutive_breaches == 0)

    # Count total before pagination
    from sqlalchemy import func as sa_func
    count_query = select(sa_func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply ordering and pagination
    offset = (page - 1) * page_size
    query = query.order_by(
        ContractSLA.severity,
        ContractSLA.consecutive_breaches.desc(),
    ).offset(offset).limit(page_size)

    result = await db.execute(query)
    slas = result.scalars().all()

    import math
    return {
        "items": [sla_to_response(sla) for sla in slas],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if page_size > 0 else 0,
    }


@router.put("/{contract_id}/{sla_id}", response_model=SLAResponse)
async def update_sla(
    contract_id: str,
    sla_id: str,
    sla_data: SLAUpdate,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SLAResponse:
    """Update an SLA. Requires admin role."""
    # Check admin role
    if current_user.role.value not in ["admin", "legal"]:
        raise HTTPException(
            status_code=403,
            detail="Only admin or legal users can update SLAs"
        )

    # Verify contract belongs to tenant
    contract_query = select(Contract).where(Contract.id == uuid_mod.UUID(contract_id))
    if tenant_id is not None:
        contract_query = contract_query.where(Contract.tenant_id == tenant_id)
    contract_result = await db.execute(contract_query)
    if not contract_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Contract not found")

    # Get the SLA
    result = await db.execute(
        select(ContractSLA).where(
            ContractSLA.id == uuid_mod.UUID(sla_id),
            ContractSLA.contract_id == uuid_mod.UUID(contract_id),
        )
    )
    sla = result.scalar_one_or_none()

    if not sla:
        raise HTTPException(status_code=404, detail="SLA not found")

    # Update fields
    update_dict = sla_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if value is not None:
            if field == "metric_type":
                setattr(sla, field, SLAMetricType(value))
            elif field == "metric_unit":
                setattr(sla, field, SLAUnit(value))
            elif field == "severity":
                setattr(sla, field, SLASeverity(value))
            else:
                setattr(sla, field, value)

    await db.commit()
    await db.refresh(sla)

    return sla_to_response(sla)


@router.delete("/{contract_id}/{sla_id}")
async def delete_sla(
    contract_id: str,
    sla_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Delete an SLA. Requires admin role."""
    # Check admin role
    if current_user.role.value not in ["admin", "legal"]:
        raise HTTPException(
            status_code=403,
            detail="Only admin or legal users can delete SLAs"
        )

    # Verify contract belongs to tenant
    contract_query = select(Contract).where(Contract.id == uuid_mod.UUID(contract_id))
    if tenant_id is not None:
        contract_query = contract_query.where(Contract.tenant_id == tenant_id)
    contract_result = await db.execute(contract_query)
    if not contract_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Contract not found")

    # Get the SLA
    result = await db.execute(
        select(ContractSLA).where(
            ContractSLA.id == uuid_mod.UUID(sla_id),
            ContractSLA.contract_id == uuid_mod.UUID(contract_id),
        )
    )
    sla = result.scalar_one_or_none()

    if not sla:
        raise HTTPException(status_code=404, detail="SLA not found")

    await db.delete(sla)
    await db.commit()

    return {"message": "SLA deleted successfully", "sla_id": sla_id}
