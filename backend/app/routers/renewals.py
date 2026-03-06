"""Renewal Management API endpoints."""

from datetime import date, datetime, timedelta
from typing import Annotated
from uuid import UUID
import hashlib

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser, CurrentTenantId
from app.database import get_db
from app.models import Contract, ContractStatus, ContractSLA, SLAPerformance
from app.models.obligation import Obligation
from app.models.key_date import ContractKeyDate
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


def apply_tenant_filter(query, tenant_id):
    """Apply tenant filter to a Contract query if tenant_id is set."""
    if tenant_id is not None:
        return query.where(Contract.tenant_id == tenant_id)
    return query


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
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
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
    query = apply_tenant_filter(query, tenant_id)

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
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
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
    query = apply_tenant_filter(query, tenant_id)

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
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get summary statistics for the renewal dashboard."""
    today = date.today()

    # Count total active contracts
    total_query = select(func.count(Contract.id)).where(
        Contract.status == ContractStatus.COMPLETED
    )
    total_query = apply_tenant_filter(total_query, tenant_id)
    total_result = await db.execute(total_query)
    total_active = total_result.scalar() or 0

    # Get contracts with expiration dates
    query = select(Contract).where(
        and_(
            Contract.status == ContractStatus.COMPLETED,
            Contract.expiration_date.isnot(None),
        )
    )
    query = apply_tenant_filter(query, tenant_id)
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
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
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
    # Get the contract with tenant filter
    query = select(Contract).where(Contract.id == contract_id)
    query = apply_tenant_filter(query, tenant_id)
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
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
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
    # Get the contract with tenant filter
    query = select(Contract).where(Contract.id == contract_id)
    query = apply_tenant_filter(query, tenant_id)
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


def _generate_ics_uid(event_type: str, event_id: str, event_date: date) -> str:
    """Generate a unique UID for an ICS event."""
    data = f"{event_type}-{event_id}-{event_date.isoformat()}"
    return hashlib.sha256(data.encode()).hexdigest()[:32] + "@clm.app"


def _format_ics_date(d: date) -> str:
    """Format a date for ICS (VALUE=DATE format)."""
    return d.strftime("%Y%m%d")


def _escape_ics_text(text: str) -> str:
    """Escape text for ICS format."""
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _build_ics_event(
    uid: str,
    summary: str,
    description: str,
    event_date: date,
    category: str = "CONTRACT",
    alarm_days_before: int = 7,
) -> str:
    """Build a single VEVENT block."""
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART;VALUE=DATE:{_format_ics_date(event_date)}",
        f"DTEND;VALUE=DATE:{_format_ics_date(event_date + timedelta(days=1))}",
        f"SUMMARY:{_escape_ics_text(summary)}",
        f"DESCRIPTION:{_escape_ics_text(description)}",
        f"CATEGORIES:{category}",
        "STATUS:CONFIRMED",
        "TRANSP:TRANSPARENT",
    ]

    # Add alarm if in future
    if event_date > date.today():
        alarm_date = event_date - timedelta(days=alarm_days_before)
        if alarm_date >= date.today():
            lines.extend([
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"DESCRIPTION:Reminder: {_escape_ics_text(summary)}",
                f"TRIGGER:-P{alarm_days_before}D",
                "END:VALARM",
            ])

    lines.append("END:VEVENT")
    return "\r\n".join(lines)


@router.get("/export/calendar.ics")
async def export_calendar_ics(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    include_expirations: bool = Query(True, description="Include contract expiration dates"),
    include_notice_deadlines: bool = Query(True, description="Include notice deadlines"),
    include_obligations: bool = Query(True, description="Include obligation deadlines"),
    include_key_dates: bool = Query(True, description="Include key dates"),
    days_ahead: int = Query(365, description="Number of days ahead to include", ge=30, le=730),
):
    """
    Export contract deadlines and key dates as an ICS calendar file.

    The exported calendar can be imported into Google Calendar, Outlook,
    Apple Calendar, or any other calendar application that supports ICS format.

    Returns events for:
    - Contract expiration dates
    - Notice deadlines (for auto-renewing contracts)
    - Obligation deadlines
    - Custom key dates
    """
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)

    events: list[str] = []

    # Get contracts with expiration dates
    if include_expirations or include_notice_deadlines:
        contracts_query = select(Contract).where(
            and_(
                Contract.status == ContractStatus.COMPLETED,
                Contract.expiration_date.isnot(None),
                Contract.expiration_date >= today,
                Contract.expiration_date <= cutoff,
            )
        )
        contracts_query = apply_tenant_filter(contracts_query, tenant_id)
        result = await db.execute(contracts_query)
        contracts = result.scalars().all()

        for contract in contracts:
            # Expiration date event
            if include_expirations and contract.expiration_date:
                uid = _generate_ics_uid("expiration", str(contract.id), contract.expiration_date)
                summary = f"Contract Expires: {contract.counterparty or contract.filename}"
                description = (
                    f"Contract: {contract.filename}\\n"
                    f"Counterparty: {contract.counterparty or 'N/A'}\\n"
                    f"Type: {contract.contract_type.value if contract.contract_type else 'N/A'}\\n"
                    f"Value: ${float(contract.contract_value):,.2f}" if contract.contract_value else ""
                )
                events.append(_build_ics_event(
                    uid=uid,
                    summary=summary,
                    description=description,
                    event_date=contract.expiration_date,
                    category="CONTRACT_EXPIRATION",
                    alarm_days_before=30,
                ))

            # Notice deadline event
            if include_notice_deadlines and contract.notice_period_days and contract.expiration_date:
                notice_date = contract.expiration_date - timedelta(days=contract.notice_period_days)
                if today <= notice_date <= cutoff:
                    uid = _generate_ics_uid("notice", str(contract.id), notice_date)
                    summary = f"Notice Deadline: {contract.counterparty or contract.filename}"
                    description = (
                        f"Last day to provide notice for contract renewal/termination\\n"
                        f"Contract: {contract.filename}\\n"
                        f"Counterparty: {contract.counterparty or 'N/A'}\\n"
                        f"Expiration: {contract.expiration_date.isoformat()}\\n"
                        f"Auto-Renewal: {'Yes' if contract.auto_renewal else 'No'}"
                    )
                    events.append(_build_ics_event(
                        uid=uid,
                        summary=summary,
                        description=description,
                        event_date=notice_date,
                        category="NOTICE_DEADLINE",
                        alarm_days_before=14,
                    ))

    # Get obligation deadlines
    if include_obligations:
        obligations_query = select(Obligation).join(
            Contract, Obligation.contract_id == Contract.id
        ).where(
            and_(
                Obligation.deadline.isnot(None),
                Obligation.deadline >= today,
                Obligation.deadline <= cutoff,
                Obligation.status != "completed",
            )
        )
        if tenant_id is not None:
            obligations_query = obligations_query.where(Contract.tenant_id == tenant_id)

        result = await db.execute(obligations_query)
        obligations = result.scalars().all()

        for obl in obligations:
            if obl.deadline:
                uid = _generate_ics_uid("obligation", str(obl.id), obl.deadline)
                priority = "CRITICAL: " if obl.is_critical else ""
                summary = f"{priority}Obligation Due: {obl.description[:50]}..."
                description = (
                    f"Obligation: {obl.description}\\n"
                    f"Type: {obl.obligation_type.value if obl.obligation_type else 'N/A'}\\n"
                    f"Status: {obl.status.value if obl.status else 'pending'}\\n"
                    f"Obligated Party: {obl.obligated_party or 'N/A'}"
                )
                events.append(_build_ics_event(
                    uid=uid,
                    summary=summary,
                    description=description,
                    event_date=obl.deadline,
                    category="OBLIGATION",
                    alarm_days_before=7,
                ))

    # Get key dates
    if include_key_dates:
        key_dates_query = select(ContractKeyDate).join(
            Contract, ContractKeyDate.contract_id == Contract.id
        ).where(
            and_(
                ContractKeyDate.event_date >= today,
                ContractKeyDate.event_date <= cutoff,
                ContractKeyDate.is_completed == False,
            )
        )
        if tenant_id is not None:
            key_dates_query = key_dates_query.where(Contract.tenant_id == tenant_id)

        result = await db.execute(key_dates_query)
        key_dates = result.scalars().all()

        for kd in key_dates:
            uid = _generate_ics_uid("keydate", str(kd.id), kd.event_date)
            summary = f"Key Date: {kd.event_name}"
            description = (
                f"Event: {kd.event_name}\\n"
                f"Type: {kd.event_type.value}\\n"
                f"Description: {kd.description or 'N/A'}\\n"
                f"Action Required: {kd.action_required or 'N/A'}"
            )
            events.append(_build_ics_event(
                uid=uid,
                summary=summary,
                description=description,
                event_date=kd.event_date,
                category=kd.event_type.value.upper(),
                alarm_days_before=kd.alert_days_before or 7,
            ))

    # Build full ICS file
    ics_content = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CLM//Contract Lifecycle Management//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:CLM Contract Deadlines",
        "X-WR-TIMEZONE:UTC",
    ])

    if events:
        ics_content += "\r\n" + "\r\n".join(events)

    ics_content += "\r\nEND:VCALENDAR\r\n"

    # Return as downloadable file
    filename = f"clm-calendar-{today.isoformat()}.ics"
    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
