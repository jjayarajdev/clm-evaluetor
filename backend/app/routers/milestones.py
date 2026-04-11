"""Milestone Health Dashboard API endpoints."""

from datetime import date, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, CurrentTenantId
from app.core.tenant import apply_tenant_filter
from app.database import get_db
from app.models import (
    Contract, ContractStatus, Obligation, ObligationStatus, RAGStatus,
    ContractSLA,
)
from app.schemas.milestone import (
    MilestoneItem,
    MilestonesByStatus,
    MilestonesByTimeBucket,
    MilestoneHealthResponse,
    AtRiskContractItem,
    AtRiskContractsResponse,
    PortfolioComplianceMetrics,
    MilestoneOwnerAssignment,
)

router = APIRouter(prefix="/api/milestones", tags=["milestones"])


def determine_time_bucket(due_date: date | None, today: date) -> str:
    """Determine which time bucket a milestone falls into."""
    if not due_date:
        return "future"

    days_until = (due_date - today).days

    if days_until < 0:
        return "overdue"
    elif days_until <= 7:
        return "this_week"
    elif days_until <= 14:
        return "next_week"
    elif days_until <= 30:
        return "this_month"
    else:
        return "future"


def is_milestone_at_risk(obligation: Obligation, today: date) -> bool:
    """
    Determine if a milestone is at risk.

    At-risk criteria:
    - Due within 7 days AND status is still pending
    - RAG status is amber or red
    """
    if obligation.status in [ObligationStatus.COMPLETED, ObligationStatus.WAIVED]:
        return False

    # Check RAG status
    if obligation.rag_status in [RAGStatus.AMBER, RAGStatus.RED]:
        return True

    # Check if approaching deadline with no progress
    if obligation.deadline:
        days_until = (obligation.deadline - today).days
        if days_until <= 7 and obligation.status == ObligationStatus.PENDING:
            return True

    return False


async def build_milestone_item(
    obligation: Obligation,
    contract: Contract,
    today: date,
) -> MilestoneItem:
    """Build a MilestoneItem from an Obligation."""
    days_until = None
    days_overdue = None

    if obligation.deadline:
        diff = (obligation.deadline - today).days
        if diff >= 0:
            days_until = diff
        else:
            days_overdue = abs(diff)

    time_bucket = determine_time_bucket(obligation.deadline, today)
    at_risk = is_milestone_at_risk(obligation, today)

    return MilestoneItem(
        milestone_id=str(obligation.id),
        contract_id=str(contract.id),
        contract_filename=contract.filename,
        counterparty=contract.counterparty,
        title=obligation.description[:100] if obligation.description else "No description",
        description=obligation.description,
        category=obligation.category.value if obligation.category else None,
        owner=obligation.obligated_party,
        due_date=obligation.deadline,
        completed_date=obligation.last_compliance_date,
        status=obligation.status.value if obligation.status else "pending",
        rag_status=obligation.rag_status.value if obligation.rag_status else None,
        is_at_risk=at_risk,
        days_until_due=days_until,
        days_overdue=days_overdue,
        time_bucket=time_bucket,
    )


@router.get("/health", response_model=MilestoneHealthResponse)
async def get_milestone_health(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get milestone health dashboard showing all milestones across the portfolio.

    Milestones are treated as obligations with due dates.
    """
    today = date.today()

    # Get all obligations with their contracts - with tenant filter
    query = select(Obligation, Contract).join(
        Contract,
        Obligation.contract_id == Contract.id
    ).where(
        Contract.status == ContractStatus.COMPLETED
    ).order_by(Obligation.deadline)
    query = apply_tenant_filter(query, tenant_id, Contract)

    result = await db.execute(query)
    rows = result.all()

    # Initialize counters
    by_status = {
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
        "overdue": 0,
        "waived": 0,
    }

    by_time = {
        "overdue": [],
        "this_week": [],
        "next_week": [],
        "this_month": [],
        "future": [],
    }

    at_risk_milestones = []

    for obligation, contract in rows:
        milestone = await build_milestone_item(obligation, contract, today)

        # Count by status
        status_key = milestone.status
        if status_key in by_status:
            by_status[status_key] += 1

        # Group by time bucket
        if milestone.time_bucket in by_time:
            by_time[milestone.time_bucket].append(milestone)

        # Track at-risk
        if milestone.is_at_risk:
            at_risk_milestones.append(milestone)

    total = len(rows)
    completed = by_status["completed"]
    overdue = by_status["overdue"]

    # Calculate rates
    completion_rate = (completed / (completed + overdue) * 100) if (completed + overdue) > 0 else 100.0
    on_track = completed + by_status["in_progress"]
    on_track_rate = (on_track / total * 100) if total > 0 else 100.0

    return MilestoneHealthResponse(
        as_of_date=today,
        total_milestones=total,
        by_status=MilestonesByStatus(**by_status),
        at_risk_count=len(at_risk_milestones),
        at_risk_milestones=at_risk_milestones[:20],  # Top 20
        by_time_bucket=MilestonesByTimeBucket(**by_time),
        completion_rate=round(completion_rate, 2),
        on_track_rate=round(on_track_rate, 2),
    )


@router.get("/at-risk-contracts", response_model=AtRiskContractsResponse)
async def get_at_risk_contracts(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get contracts that are at risk based on milestone/obligation status.

    A contract is at-risk if it has:
    - Multiple overdue obligations
    - Low completion rate
    - Active SLA breaches
    """
    today = date.today()

    # Get all completed contracts - with tenant filter
    query = select(Contract).where(
        Contract.status == ContractStatus.COMPLETED
    )
    query = apply_tenant_filter(query, tenant_id, Contract)
    result = await db.execute(query)
    contracts = result.scalars().all()

    at_risk_contracts = []
    total_value = 0.0
    critical_count = 0
    high_count = 0

    for contract in contracts:
        # Get obligations for this contract
        obl_query = select(Obligation).where(Obligation.contract_id == contract.id)
        obl_result = await db.execute(obl_query)
        obligations = list(obl_result.scalars().all())

        if not obligations:
            continue

        # Calculate metrics
        total_obl = len(obligations)
        completed_obl = sum(1 for o in obligations if o.status == ObligationStatus.COMPLETED)
        overdue_obl = sum(1 for o in obligations if o.status == ObligationStatus.OVERDUE)
        at_risk_obl = sum(1 for o in obligations if is_milestone_at_risk(o, today))

        completion_rate = (completed_obl / total_obl * 100) if total_obl > 0 else 100.0

        # Get SLA stats
        sla_query = select(ContractSLA).where(
            and_(
                ContractSLA.contract_id == contract.id,
                ContractSLA.is_active == True,
            )
        )
        sla_result = await db.execute(sla_query)
        slas = list(sla_result.scalars().all())

        sla_compliance = None
        active_breaches = 0
        if slas:
            compliance_rates = [float(s.current_compliance_rate) for s in slas if s.current_compliance_rate is not None]
            sla_compliance = sum(compliance_rates) / len(compliance_rates) if compliance_rates else None
            active_breaches = sum(s.consecutive_breaches for s in slas)

        # Calculate risk score
        risk_score = 100
        risk_factors = []

        if overdue_obl > 0:
            risk_score -= min(overdue_obl * 15, 40)
            risk_factors.append(f"{overdue_obl} overdue obligations")

        if at_risk_obl > 0:
            risk_score -= min(at_risk_obl * 10, 30)
            risk_factors.append(f"{at_risk_obl} at-risk obligations")

        if completion_rate < 50:
            risk_score -= 20
            risk_factors.append(f"Low completion rate: {completion_rate:.1f}%")

        if active_breaches > 0:
            risk_score -= min(active_breaches * 10, 30)
            risk_factors.append(f"{active_breaches} active SLA breaches")

        if sla_compliance and sla_compliance < 80:
            risk_score -= 15
            risk_factors.append(f"Low SLA compliance: {sla_compliance:.1f}%")

        risk_score = max(0, risk_score)

        # Determine risk level
        if risk_score >= 80:
            risk_level = "low"
        elif risk_score >= 60:
            risk_level = "medium"
        elif risk_score >= 40:
            risk_level = "high"
            high_count += 1
        else:
            risk_level = "critical"
            critical_count += 1

        # Only include if at-risk (score < 80)
        if risk_score < 80:
            # Determine recommended action
            if risk_level == "critical":
                recommended_action = "Immediate escalation required - schedule urgent review"
            elif risk_level == "high":
                recommended_action = "Prioritize remediation of overdue items"
            else:
                recommended_action = "Monitor closely and address at-risk items"

            at_risk_item = AtRiskContractItem(
                contract_id=str(contract.id),
                filename=contract.filename,
                counterparty=contract.counterparty,
                contract_type=contract.contract_type.value if contract.contract_type else None,
                contract_value=float(contract.contract_value) if contract.contract_value else None,
                risk_score=risk_score,
                risk_level=risk_level,
                risk_factors=risk_factors,
                total_milestones=total_obl,
                overdue_milestones=overdue_obl,
                at_risk_milestones=at_risk_obl,
                completion_rate=completion_rate,
                sla_compliance_rate=sla_compliance,
                active_breaches=active_breaches,
                recommended_action=recommended_action,
            )
            at_risk_contracts.append(at_risk_item)

            if contract.contract_value:
                total_value += float(contract.contract_value)

    # Sort by risk score (lowest first = most at risk)
    at_risk_contracts.sort(key=lambda x: x.risk_score)

    return AtRiskContractsResponse(
        total_at_risk=len(at_risk_contracts),
        critical_count=critical_count,
        high_count=high_count,
        total_value_at_risk=total_value,
        contracts=at_risk_contracts,
    )


@router.get("/portfolio-compliance", response_model=PortfolioComplianceMetrics)
async def get_portfolio_compliance(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get portfolio-level compliance metrics across all contracts.
    """
    today = date.today()

    # Count contracts - with tenant filter
    contract_query = select(func.count(Contract.id)).where(
        Contract.status == ContractStatus.COMPLETED
    )
    contract_query = apply_tenant_filter(contract_query, tenant_id, Contract)
    contract_result = await db.execute(contract_query)
    total_contracts = contract_result.scalar() or 0

    # Get all obligations - with tenant filter
    obl_query = select(Obligation).join(
        Contract,
        Obligation.contract_id == Contract.id
    ).where(
        Contract.status == ContractStatus.COMPLETED
    )
    obl_query = apply_tenant_filter(obl_query, tenant_id, Contract)
    obl_result = await db.execute(obl_query)
    obligations = list(obl_result.scalars().all())

    total_obligations = len(obligations)

    # Count by status and RAG
    by_status = {}
    by_rag = {}
    completed = 0
    overdue = 0
    at_risk_obligations = 0

    for obl in obligations:
        status_val = obl.status.value if obl.status else "pending"
        by_status[status_val] = by_status.get(status_val, 0) + 1

        rag_val = obl.rag_status.value if obl.rag_status else "not_assessed"
        by_rag[rag_val] = by_rag.get(rag_val, 0) + 1

        if obl.status == ObligationStatus.COMPLETED:
            completed += 1
        elif obl.status == ObligationStatus.OVERDUE:
            overdue += 1

        if is_milestone_at_risk(obl, today):
            at_risk_obligations += 1

    # Calculate obligation compliance rate
    waived = by_status.get("waived", 0)
    denominator = total_obligations - waived
    obligation_compliance = (completed / denominator * 100) if denominator > 0 else 100.0

    # Get SLA stats - with tenant filter via contract join
    if tenant_id is not None:
        sla_query = (
            select(ContractSLA)
            .join(Contract, ContractSLA.contract_id == Contract.id)
            .where(ContractSLA.is_active == True)
            .where(Contract.tenant_id == tenant_id)
        )
    else:
        sla_query = select(ContractSLA).where(ContractSLA.is_active == True)
    sla_result = await db.execute(sla_query)
    slas = list(sla_result.scalars().all())

    total_slas = len(slas)
    slas_breached = sum(1 for s in slas if s.consecutive_breaches > 0)

    compliance_rates = [float(s.current_compliance_rate) for s in slas if s.current_compliance_rate is not None]
    sla_compliance = sum(compliance_rates) / len(compliance_rates) if compliance_rates else 100.0

    # Overall compliance (weighted)
    overall_compliance = (obligation_compliance * 0.6 + sla_compliance * 0.4)

    # Count at-risk contracts - call internal helper to avoid recursion issues
    at_risk_response = await get_at_risk_contracts(current_user, tenant_id, db)
    contracts_at_risk = at_risk_response.total_at_risk

    return PortfolioComplianceMetrics(
        as_of_date=today,
        total_contracts=total_contracts,
        total_obligations=total_obligations,
        total_slas=total_slas,
        obligation_compliance_rate=round(obligation_compliance, 2),
        sla_compliance_rate=round(sla_compliance, 2),
        overall_compliance_rate=round(overall_compliance, 2),
        obligations_by_status=by_status,
        obligations_by_rag=by_rag,
        contracts_at_risk=contracts_at_risk,
        obligations_at_risk=at_risk_obligations,
        slas_breached=slas_breached,
        compliance_trend=None,  # Would need historical data
        previous_compliance_rate=None,
    )


@router.put("/{milestone_id}/owner")
async def assign_milestone_owner(
    milestone_id: UUID,
    assignment: MilestoneOwnerAssignment,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Assign an owner to a milestone (obligation).
    """
    # Get obligation with tenant check via contract join
    query = (
        select(Obligation)
        .join(Contract, Obligation.contract_id == Contract.id)
        .where(Obligation.id == milestone_id)
    )
    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)
    result = await db.execute(query)
    obligation = result.scalar_one_or_none()

    if not obligation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Milestone {milestone_id} not found"
        )

    obligation.obligated_party = assignment.owner
    if assignment.notes:
        existing_notes = obligation.compliance_notes or ""
        obligation.compliance_notes = f"{existing_notes}\n[Owner Assignment] {assignment.notes}".strip()

    await db.commit()

    return {
        "milestone_id": str(milestone_id),
        "owner": assignment.owner,
        "updated_at": datetime.utcnow().isoformat(),
    }
