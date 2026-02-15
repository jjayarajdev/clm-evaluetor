"""Renewal Management API endpoints."""

from datetime import date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Contract, ContractStatus, ContractSLA, SLAPerformance
from app.schemas.renewal import (
    RenewalStatusUpdate,
    ContractRenewalInfo,
    RenewalCalendarResponse,
    AtRiskContract,
    AtRiskResponse,
    RenewalRecommendation,
    RenewalSummaryStats,
)

router = APIRouter(prefix="/api/renewals", tags=["renewals"])


def calculate_notice_deadline(expiration_date: date | None, notice_period_days: int | None) -> date | None:
    """Calculate the notice deadline based on expiration and notice period."""
    if not expiration_date:
        return None
    if not notice_period_days:
        return None
    return expiration_date - timedelta(days=notice_period_days)


def determine_renewal_window(expiration_date: date | None, today: date) -> str:
    """Determine which renewal window a contract falls into."""
    if not expiration_date:
        return "unknown"

    days_until = (expiration_date - today).days

    if days_until < 0:
        return "expired"
    elif days_until <= 30:
        return "30_days"
    elif days_until <= 60:
        return "60_days"
    elif days_until <= 90:
        return "90_days"
    else:
        return "beyond_90"


async def get_sla_stats_for_contract(db: AsyncSession, contract_id: UUID) -> tuple[float | None, int]:
    """Get SLA compliance rate and breach count for a contract."""
    # Get all active SLAs for this contract
    sla_query = select(ContractSLA).where(
        and_(
            ContractSLA.contract_id == contract_id,
            ContractSLA.is_active == True
        )
    )
    result = await db.execute(sla_query)
    slas = result.scalars().all()

    if not slas:
        return None, 0

    total_compliance = 0.0
    count_with_compliance = 0
    active_breaches = 0

    for sla in slas:
        if sla.current_compliance_rate is not None:
            total_compliance += float(sla.current_compliance_rate)
            count_with_compliance += 1
        if sla.consecutive_breaches > 0:
            active_breaches += sla.consecutive_breaches

    avg_compliance = total_compliance / count_with_compliance if count_with_compliance > 0 else None
    return avg_compliance, active_breaches


def build_contract_renewal_info(
    contract: Contract,
    today: date,
    sla_compliance: float | None = None,
    sla_breaches: int = 0
) -> ContractRenewalInfo:
    """Build renewal info response for a contract."""
    notice_deadline = calculate_notice_deadline(
        contract.expiration_date,
        contract.notice_period_days
    )

    days_until_expiration = None
    days_until_notice = None
    is_past_notice = False

    if contract.expiration_date:
        days_until_expiration = (contract.expiration_date - today).days

    if notice_deadline:
        days_until_notice = (notice_deadline - today).days
        is_past_notice = days_until_notice < 0

    renewal_window = determine_renewal_window(contract.expiration_date, today)

    # Check if past notice deadline - mark as critical
    if is_past_notice and days_until_expiration and days_until_expiration >= 0:
        renewal_window = "critical"

    # Get renewal_status from schema_data if stored there
    renewal_status = None
    if contract.schema_data and isinstance(contract.schema_data, dict):
        renewal_status = contract.schema_data.get("renewal_status")

    return ContractRenewalInfo(
        contract_id=str(contract.id),
        filename=contract.filename,
        counterparty=contract.counterparty,
        contract_type=contract.contract_type.value if contract.contract_type else None,
        contract_value=float(contract.contract_value) if contract.contract_value else None,
        effective_date=contract.effective_date,
        expiration_date=contract.expiration_date,
        notice_deadline=notice_deadline,
        auto_renewal=contract.auto_renewal,
        notice_period_days=contract.notice_period_days,
        renewal_term_months=contract.renewal_term_months,
        days_until_expiration=days_until_expiration,
        days_until_notice_deadline=days_until_notice,
        is_past_notice_deadline=is_past_notice,
        renewal_window=renewal_window,
        renewal_status=renewal_status,
        risk_level=contract.risk_level.value if contract.risk_level else None,
        sla_compliance_rate=sla_compliance,
        active_sla_breaches=sla_breaches,
    )


@router.get("/calendar", response_model=RenewalCalendarResponse)
async def get_renewal_calendar(
    db: AsyncSession = Depends(get_db),
):
    """
    Get renewal calendar showing contracts grouped by renewal window.

    Groups contracts into:
    - Expired: Past expiration date
    - Critical: Past notice deadline but not yet expired
    - Within 30 days: Expiring in 0-30 days
    - Within 60 days: Expiring in 31-60 days
    - Within 90 days: Expiring in 61-90 days
    """
    today = date.today()
    cutoff_90 = today + timedelta(days=90)

    # Get all contracts with expiration dates within 90 days or already expired (within last 30 days)
    past_cutoff = today - timedelta(days=30)

    query = select(Contract).where(
        and_(
            Contract.status == ContractStatus.COMPLETED,
            Contract.expiration_date.isnot(None),
            Contract.expiration_date >= past_cutoff,
            Contract.expiration_date <= cutoff_90,
        )
    ).order_by(Contract.expiration_date)

    result = await db.execute(query)
    contracts = result.scalars().all()

    # Group contracts by window
    expired = []
    critical = []
    within_30 = []
    within_60 = []
    within_90 = []

    total_value_at_risk = 0.0
    auto_renewal_count = 0
    requires_action_count = 0

    for contract in contracts:
        # Get SLA stats
        sla_compliance, sla_breaches = await get_sla_stats_for_contract(db, contract.id)

        info = build_contract_renewal_info(contract, today, sla_compliance, sla_breaches)

        # Accumulate stats
        if info.contract_value:
            total_value_at_risk += info.contract_value

        if info.auto_renewal:
            auto_renewal_count += 1

        # Check if action required (non-auto-renewal past notice)
        if info.is_past_notice_deadline and not info.auto_renewal:
            requires_action_count += 1

        # Sort into buckets
        if info.renewal_window == "expired":
            expired.append(info)
        elif info.renewal_window == "critical":
            critical.append(info)
        elif info.renewal_window == "30_days":
            within_30.append(info)
        elif info.renewal_window == "60_days":
            within_60.append(info)
        elif info.renewal_window == "90_days":
            within_90.append(info)

    return RenewalCalendarResponse(
        as_of_date=today,
        total_contracts=len(contracts),
        expired=expired,
        critical=critical,
        within_30_days=within_30,
        within_60_days=within_60,
        within_90_days=within_90,
        total_value_at_risk=total_value_at_risk,
        auto_renewal_count=auto_renewal_count,
        requires_action_count=requires_action_count,
    )


@router.get("/at-risk", response_model=AtRiskResponse)
async def get_at_risk_contracts(
    db: AsyncSession = Depends(get_db),
):
    """
    Get contracts that are at risk of unfavorable renewal.

    At-risk contracts are those that:
    - Are past their notice deadline but not yet expired
    - Have auto-renewal but may want to terminate
    - Have poor SLA compliance
    """
    today = date.today()

    # Get contracts with expiration dates in the future
    query = select(Contract).where(
        and_(
            Contract.status == ContractStatus.COMPLETED,
            Contract.expiration_date.isnot(None),
            Contract.expiration_date > today,
        )
    ).order_by(Contract.expiration_date)

    result = await db.execute(query)
    contracts = result.scalars().all()

    at_risk_contracts = []
    total_value = 0.0

    for contract in contracts:
        notice_deadline = calculate_notice_deadline(
            contract.expiration_date,
            contract.notice_period_days
        )

        # Check if past notice deadline
        if notice_deadline and notice_deadline < today:
            days_past = (today - notice_deadline).days

            # Gather risk factors
            risk_factors = []
            recommended_action = "review"

            # Factor: Past notice deadline
            risk_factors.append(f"Notice deadline passed {days_past} days ago")

            # Factor: Auto-renewal
            if contract.auto_renewal:
                risk_factors.append("Contract will auto-renew if no action taken")
                recommended_action = "urgent_review"
            else:
                risk_factors.append("Contract will expire without renewal action")
                recommended_action = "negotiate_extension"

            # Factor: High value
            if contract.contract_value and float(contract.contract_value) > 100000:
                risk_factors.append(f"High value contract: ${float(contract.contract_value):,.2f}")

            # Factor: SLA issues
            sla_compliance, sla_breaches = await get_sla_stats_for_contract(db, contract.id)
            if sla_breaches > 0:
                risk_factors.append(f"{sla_breaches} active SLA breaches")
            if sla_compliance is not None and sla_compliance < 90:
                risk_factors.append(f"Low SLA compliance: {sla_compliance:.1f}%")

            at_risk = AtRiskContract(
                contract_id=str(contract.id),
                filename=contract.filename,
                counterparty=contract.counterparty,
                contract_value=float(contract.contract_value) if contract.contract_value else None,
                expiration_date=contract.expiration_date,
                notice_deadline=notice_deadline,
                days_past_notice=days_past,
                auto_renewal=contract.auto_renewal,
                risk_level=contract.risk_level.value if contract.risk_level else None,
                risk_factors=risk_factors,
                recommended_action=recommended_action,
            )
            at_risk_contracts.append(at_risk)

            if contract.contract_value:
                total_value += float(contract.contract_value)

    return AtRiskResponse(
        total_at_risk=len(at_risk_contracts),
        total_value_at_risk=total_value,
        contracts=at_risk_contracts,
    )


@router.get("/summary", response_model=RenewalSummaryStats)
async def get_renewal_summary(
    db: AsyncSession = Depends(get_db),
):
    """Get summary statistics for the renewal dashboard."""
    today = date.today()

    # Count total active contracts
    total_query = select(func.count(Contract.id)).where(
        Contract.status == ContractStatus.COMPLETED
    )
    total_result = await db.execute(total_query)
    total_active = total_result.scalar() or 0

    # Get contracts with expiration dates
    query = select(Contract).where(
        and_(
            Contract.status == ContractStatus.COMPLETED,
            Contract.expiration_date.isnot(None),
        )
    )
    result = await db.execute(query)
    contracts = result.scalars().all()

    # Calculate stats
    expiring_30 = 0
    expiring_60 = 0
    expiring_90 = 0
    past_notice = 0
    auto_renewing = 0

    value_90_days = 0.0
    value_past_notice = 0.0

    by_renewal_status: dict[str, int] = {}
    by_contract_type: dict[str, dict] = {}

    for contract in contracts:
        days_until = (contract.expiration_date - today).days if contract.expiration_date else None

        if days_until is not None:
            if 0 <= days_until <= 30:
                expiring_30 += 1
            if 0 <= days_until <= 60:
                expiring_60 += 1
            if 0 <= days_until <= 90:
                expiring_90 += 1
                if contract.contract_value:
                    value_90_days += float(contract.contract_value)

        # Check notice deadline
        notice_deadline = calculate_notice_deadline(
            contract.expiration_date,
            contract.notice_period_days
        )
        if notice_deadline and notice_deadline < today and days_until and days_until > 0:
            past_notice += 1
            if contract.contract_value:
                value_past_notice += float(contract.contract_value)

        if contract.auto_renewal:
            auto_renewing += 1

        # Count by renewal status
        renewal_status = "pending_review"
        if contract.schema_data and isinstance(contract.schema_data, dict):
            renewal_status = contract.schema_data.get("renewal_status", "pending_review")
        by_renewal_status[renewal_status] = by_renewal_status.get(renewal_status, 0) + 1

        # Count by contract type
        ct = contract.contract_type.value if contract.contract_type else "unknown"
        if ct not in by_contract_type:
            by_contract_type[ct] = {"count": 0, "total_value": 0.0}
        by_contract_type[ct]["count"] += 1
        if contract.contract_value:
            by_contract_type[ct]["total_value"] += float(contract.contract_value)

    return RenewalSummaryStats(
        total_active_contracts=total_active,
        expiring_30_days=expiring_30,
        expiring_60_days=expiring_60,
        expiring_90_days=expiring_90,
        past_notice_deadline=past_notice,
        auto_renewing=auto_renewing,
        total_value_expiring_90_days=value_90_days,
        total_value_past_notice=value_past_notice,
        renewal_rate_last_12_months=None,  # Would require historical data
        avg_renewal_increase_pct=None,  # Would require historical data
        by_renewal_status=by_renewal_status,
        by_contract_type=by_contract_type,
    )


@router.put("/{contract_id}/status")
async def update_renewal_status(
    contract_id: UUID,
    update: RenewalStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update the renewal decision status for a contract.

    Valid statuses:
    - pending_review: No decision made yet
    - approved: Renewal approved
    - declined: Decided not to renew
    - auto_renewed: Contract auto-renewed
    - expired: Contract has expired
    - renegotiating: In renegotiation
    """
    # Get the contract
    query = select(Contract).where(Contract.id == contract_id)
    result = await db.execute(query)
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract {contract_id} not found"
        )

    # Update schema_data with renewal status
    if contract.schema_data is None:
        contract.schema_data = {}

    contract.schema_data["renewal_status"] = update.renewal_status
    contract.schema_data["renewal_decision_notes"] = update.decision_notes
    contract.schema_data["renewal_decided_by"] = update.decided_by
    contract.schema_data["renewal_decision_date"] = datetime.utcnow().isoformat()

    # If approved with new expiration date, update the contract
    if update.renewal_status == "approved" and update.new_expiration_date:
        contract.schema_data["previous_expiration_date"] = (
            contract.expiration_date.isoformat() if contract.expiration_date else None
        )
        contract.expiration_date = update.new_expiration_date

    await db.commit()
    await db.refresh(contract)

    return {
        "contract_id": str(contract.id),
        "renewal_status": update.renewal_status,
        "updated_at": datetime.utcnow().isoformat(),
    }


@router.get("/{contract_id}/recommendation", response_model=RenewalRecommendation)
async def get_renewal_recommendation(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get AI-generated renewal recommendation for a contract.

    Considers:
    - SLA compliance history
    - Obligation compliance
    - Total penalties paid
    - Contract value vs. market
    - Risk factors
    """
    # Get the contract
    query = select(Contract).where(Contract.id == contract_id)
    result = await db.execute(query)
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract {contract_id} not found"
        )

    # Gather metrics
    sla_compliance, sla_breaches = await get_sla_stats_for_contract(db, contract.id)

    # Get total penalties from SLA performances
    penalty_query = select(func.sum(SLAPerformance.penalty_amount)).join(
        ContractSLA,
        SLAPerformance.sla_id == ContractSLA.id
    ).where(
        and_(
            ContractSLA.contract_id == contract_id,
            SLAPerformance.penalty_applied == True
        )
    )
    penalty_result = await db.execute(penalty_query)
    total_penalties = float(penalty_result.scalar() or 0)

    # Calculate obligation compliance (simplified - would need actual logic)
    obligation_compliance = None  # Would query obligations table

    # Build factors
    factors = []
    suggested_actions = []
    negotiation_points = []

    # Analyze SLA performance
    if sla_compliance is not None:
        if sla_compliance >= 95:
            factors.append({
                "factor": "SLA Compliance",
                "impact": "positive",
                "details": f"Excellent compliance rate of {sla_compliance:.1f}%"
            })
        elif sla_compliance >= 85:
            factors.append({
                "factor": "SLA Compliance",
                "impact": "neutral",
                "details": f"Acceptable compliance rate of {sla_compliance:.1f}%"
            })
            negotiation_points.append("Request SLA improvement commitment")
        else:
            factors.append({
                "factor": "SLA Compliance",
                "impact": "negative",
                "details": f"Poor compliance rate of {sla_compliance:.1f}%"
            })
            negotiation_points.append("Demand SLA improvement or penalty increase")
            suggested_actions.append("Review SLA breaches with vendor")

    # Analyze penalties
    if total_penalties > 0:
        factors.append({
            "factor": "Penalties Paid",
            "impact": "negative",
            "details": f"${total_penalties:,.2f} in penalties accumulated"
        })
        negotiation_points.append("Negotiate penalty credits or reduced rates")

    # Analyze contract value
    if contract.contract_value:
        value = float(contract.contract_value)
        factors.append({
            "factor": "Contract Value",
            "impact": "neutral",
            "details": f"Annual value: ${value:,.2f}"
        })
        if value > 500000:
            suggested_actions.append("Engage procurement for competitive analysis")
            negotiation_points.append("Request volume discount")

    # Analyze risk level
    if contract.risk_level:
        risk = contract.risk_level.value
        if risk in ["high", "critical"]:
            factors.append({
                "factor": "Risk Assessment",
                "impact": "negative",
                "details": f"Contract flagged as {risk} risk"
            })
            suggested_actions.append("Conduct risk review before renewal")
        else:
            factors.append({
                "factor": "Risk Assessment",
                "impact": "positive",
                "details": f"Contract is {risk} risk"
            })

    # Determine recommendation
    recommendation = "renew"
    confidence = 0.7

    negative_count = sum(1 for f in factors if f["impact"] == "negative")
    positive_count = sum(1 for f in factors if f["impact"] == "positive")

    if negative_count > positive_count:
        if sla_compliance and sla_compliance < 70:
            recommendation = "terminate"
            confidence = 0.8
            suggested_actions.append("Evaluate alternative vendors")
        else:
            recommendation = "renegotiate"
            confidence = 0.75
            suggested_actions.append("Schedule vendor performance review")
    elif positive_count > negative_count:
        recommendation = "renew"
        confidence = 0.85
        suggested_actions.append("Proceed with standard renewal process")
    else:
        recommendation = "review_terms"
        confidence = 0.6
        suggested_actions.append("Conduct detailed contract review")

    # Add default actions if empty
    if not suggested_actions:
        suggested_actions.append("Review contract terms before decision")

    return RenewalRecommendation(
        contract_id=str(contract.id),
        filename=contract.filename,
        counterparty=contract.counterparty,
        recommendation=recommendation,
        confidence_score=confidence,
        factors=factors,
        contract_value=float(contract.contract_value) if contract.contract_value else None,
        sla_compliance_rate=sla_compliance,
        total_penalties_paid=total_penalties,
        obligation_compliance_rate=obligation_compliance,
        suggested_actions=suggested_actions,
        negotiation_points=negotiation_points if negotiation_points else None,
    )
