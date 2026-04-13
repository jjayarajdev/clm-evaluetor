"""Vendor Performance Scoring API endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import CurrentUser, CurrentTenantId
from app.models import (
    Contract, ContractStatus, ContractSLA, SLAPerformance,
    Obligation, ObligationStatus, RAGStatus,
)
from app.models.party import ContractParty, PartyRole
from app.schemas.vendor import (
    CounterpartyType,
    VendorScoreBreakdown,
    VendorContractSummary,
    VendorObligationSummary,
    VendorSLASummary,
    VendorListItem,
    VendorListResponse,
    VendorPerformanceDetail,
    VendorCompareItem,
    VendorCompareResponse,
    AtRiskVendor,
    AtRiskVendorsResponse,
    VendorScorecard,
)

# Party roles that indicate VENDOR (you buy from them)
VENDOR_ROLES = {PartyRole.PROVIDER, PartyRole.VENDOR}
# Party roles that indicate CLIENT (you deliver to them)
CLIENT_ROLES = {PartyRole.CLIENT, PartyRole.CUSTOMER}

router = APIRouter(prefix="/api/vendors", tags=["vendors"])

# Score weights
OBLIGATION_WEIGHT = 0.40
SLA_WEIGHT = 0.30
RESPONSIVENESS_WEIGHT = 0.20
ISSUE_RATE_WEIGHT = 0.10

# Risk thresholds
AT_RISK_THRESHOLD = 60
HIGH_RISK_THRESHOLD = 40
CRITICAL_RISK_THRESHOLD = 25


def normalize_vendor_name(name: str | None) -> str:
    """Normalize vendor name for consistent matching."""
    if not name:
        return "unknown"
    # Lowercase, strip whitespace, remove common suffixes
    normalized = name.lower().strip()
    for suffix in [", inc.", ", inc", " inc.", " inc", ", llc", " llc", ", ltd", " ltd", " corp", ", corp"]:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
    return normalized


async def determine_counterparty_type(
    db: AsyncSession,
    counterparty_name: str,
    contract_ids: list[UUID],
) -> CounterpartyType:
    """
    Determine if a counterparty is a vendor (you buy from) or client (you deliver to).

    Logic:
    1. Check ContractParty records for this counterparty
    2. If is_primary=False (they are the counterparty), check their role
    3. PROVIDER/VENDOR roles → they are a vendor (you buy from them)
    4. CLIENT/CUSTOMER roles → they are a client (you deliver to them)
    5. If no party data, return UNKNOWN
    """
    if not contract_ids:
        return CounterpartyType.UNKNOWN

    # Query party records for these contracts where party is NOT primary (i.e., counterparty)
    normalized = normalize_vendor_name(counterparty_name)
    query = select(ContractParty).where(
        and_(
            ContractParty.contract_id.in_(contract_ids),
            ContractParty.is_primary == False,
            func.lower(ContractParty.legal_name).ilike(f"%{normalized}%"),
        )
    )
    result = await db.execute(query)
    parties = list(result.scalars().all())

    if not parties:
        # Try matching without name filter - just get non-primary parties
        query = select(ContractParty).where(
            and_(
                ContractParty.contract_id.in_(contract_ids),
                ContractParty.is_primary == False,
            )
        )
        result = await db.execute(query)
        parties = list(result.scalars().all())

    if not parties:
        return CounterpartyType.UNKNOWN

    # Count roles
    vendor_count = sum(1 for p in parties if p.role in VENDOR_ROLES)
    client_count = sum(1 for p in parties if p.role in CLIENT_ROLES)

    if vendor_count > client_count:
        return CounterpartyType.VENDOR
    elif client_count > vendor_count:
        return CounterpartyType.CLIENT
    else:
        return CounterpartyType.UNKNOWN


def determine_risk_level(score: float) -> str:
    """Determine risk level from score."""
    if score >= 80:
        return "low"
    elif score >= 60:
        return "medium"
    elif score >= 40:
        return "high"
    else:
        return "critical"


def score_to_grade(score: float) -> str:
    """Convert score to letter grade."""
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"


async def get_vendor_contracts(db: AsyncSession, vendor_name: str, tenant_id=None) -> list[Contract]:
    """Get all contracts for a vendor."""
    normalized = normalize_vendor_name(vendor_name)

    query = select(Contract).where(
        and_(
            Contract.status == ContractStatus.COMPLETED,
            func.lower(Contract.counterparty).ilike(f"%{normalized}%"),
        )
    )
    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def calculate_obligation_compliance(db: AsyncSession, contract_ids: list[UUID]) -> tuple[float, dict]:
    """Calculate obligation compliance rate for given contracts."""
    if not contract_ids:
        return 100.0, {"total": 0, "completed": 0, "overdue": 0, "by_status": {}, "by_rag": {}, "critical_overdue": 0}

    query = select(Obligation).where(Obligation.contract_id.in_(contract_ids))
    result = await db.execute(query)
    obligations = list(result.scalars().all())

    if not obligations:
        return 100.0, {"total": 0, "completed": 0, "overdue": 0, "by_status": {}, "by_rag": {}, "critical_overdue": 0}

    total = len(obligations)
    completed = sum(1 for o in obligations if o.status == ObligationStatus.COMPLETED)
    overdue = sum(1 for o in obligations if o.status == ObligationStatus.OVERDUE)
    critical_overdue = sum(1 for o in obligations if o.status == ObligationStatus.OVERDUE and o.rag_status == RAGStatus.RED)

    by_status = {}
    by_rag = {}
    for o in obligations:
        status_val = o.status.value if o.status else "unknown"
        by_status[status_val] = by_status.get(status_val, 0) + 1

        rag_val = o.rag_status.value if o.rag_status else "not_assessed"
        by_rag[rag_val] = by_rag.get(rag_val, 0) + 1

    # Compliance rate: (completed + in_progress) / assessable
    # Exclude waived and pending obligations with future deadlines
    from datetime import date
    today = date.today()
    waived = sum(1 for o in obligations if o.status == ObligationStatus.WAIVED)
    in_progress = sum(1 for o in obligations if o.status == ObligationStatus.IN_PROGRESS)
    pending_future = sum(1 for o in obligations
                         if o.status == ObligationStatus.PENDING
                         and o.deadline and o.deadline > today)
    assessable = total - waived - pending_future
    compliance_rate = ((completed + in_progress) / assessable * 100) if assessable > 0 else 100.0

    return compliance_rate, {
        "total": total,
        "completed": completed,
        "overdue": overdue,
        "by_status": by_status,
        "by_rag": by_rag,
        "critical_overdue": critical_overdue,
    }


async def calculate_sla_compliance(db: AsyncSession, contract_ids: list[UUID]) -> tuple[float, dict]:
    """Calculate SLA compliance rate for given contracts."""
    if not contract_ids:
        return 100.0, {"total": 0, "active": 0, "breaches": 0, "critical_breaches": 0, "penalties": 0.0, "by_metric": {}}

    query = select(ContractSLA).where(ContractSLA.contract_id.in_(contract_ids))
    result = await db.execute(query)
    slas = list(result.scalars().all())

    if not slas:
        return 100.0, {"total": 0, "active": 0, "breaches": 0, "critical_breaches": 0, "penalties": 0.0, "by_metric": {}}

    total = len(slas)
    active = sum(1 for s in slas if s.is_active)
    # Count unique SLAs currently breaching, not cumulative breach counts
    total_breaches = sum(1 for s in slas if s.consecutive_breaches > 0)
    critical_breaches = sum(1 for s in slas if s.consecutive_breaches > 0 and s.severity and s.severity.value == "critical")

    # Get penalties
    sla_ids = [s.id for s in slas]
    penalty_query = select(func.sum(SLAPerformance.penalty_amount)).where(
        and_(
            SLAPerformance.sla_id.in_(sla_ids),
            SLAPerformance.penalty_applied == True,
        )
    )
    penalty_result = await db.execute(penalty_query)
    total_penalties = float(penalty_result.scalar() or 0)

    # Calculate average compliance rate
    compliance_rates = [float(s.current_compliance_rate) for s in slas if s.current_compliance_rate is not None]
    avg_compliance = sum(compliance_rates) / len(compliance_rates) if compliance_rates else 100.0

    # By metric type
    by_metric = {}
    for s in slas:
        metric = s.metric_type.value if s.metric_type else "unknown"
        if metric not in by_metric:
            by_metric[metric] = {"total": 0, "compliant": 0, "compliance_rate": 0}
        by_metric[metric]["total"] += 1
        if s.current_compliance_rate and float(s.current_compliance_rate) >= 95:
            by_metric[metric]["compliant"] += 1

    for metric in by_metric:
        total_m = by_metric[metric]["total"]
        compliant_m = by_metric[metric]["compliant"]
        by_metric[metric]["compliance_rate"] = (compliant_m / total_m * 100) if total_m > 0 else 0

    return avg_compliance, {
        "total": total,
        "active": active,
        "breaches": total_breaches,
        "critical_breaches": critical_breaches,
        "penalties": total_penalties,
        "by_metric": by_metric,
    }


def calculate_composite_score(
    obligation_compliance: float,
    sla_compliance: float,
    responsiveness_score: float = 75.0,  # Default - would need actual data
    issue_rate_score: float = 80.0,  # Default - would need actual data
) -> VendorScoreBreakdown:
    """Calculate composite vendor score."""
    weighted_total = (
        obligation_compliance * OBLIGATION_WEIGHT +
        sla_compliance * SLA_WEIGHT +
        responsiveness_score * RESPONSIVENESS_WEIGHT +
        issue_rate_score * ISSUE_RATE_WEIGHT
    )

    return VendorScoreBreakdown(
        obligation_compliance_score=obligation_compliance,
        obligation_compliance_weight=OBLIGATION_WEIGHT,
        sla_compliance_score=sla_compliance,
        sla_compliance_weight=SLA_WEIGHT,
        responsiveness_score=responsiveness_score,
        responsiveness_weight=RESPONSIVENESS_WEIGHT,
        issue_rate_score=issue_rate_score,
        issue_rate_weight=ISSUE_RATE_WEIGHT,
        weighted_total=round(weighted_total, 2),
    )


async def build_vendor_metrics(db: AsyncSession, vendor_name: str, contracts: list[Contract]) -> dict:
    """Build all metrics for a vendor."""
    contract_ids = [c.id for c in contracts]

    # Contract summary
    total_value = sum(float(c.contract_value) for c in contracts if c.contract_value)
    active_contracts = [c for c in contracts if not c.expiration_date or c.expiration_date >= datetime.now().date()]

    contract_types = {}
    for c in contracts:
        ct = c.contract_type.value if c.contract_type else "unknown"
        contract_types[ct] = contract_types.get(ct, 0) + 1

    effective_dates = [c.effective_date for c in contracts if c.effective_date]
    expiration_dates = [c.expiration_date for c in contracts if c.expiration_date]

    contract_summary = VendorContractSummary(
        total_contracts=len(contracts),
        active_contracts=len(active_contracts),
        expired_contracts=len(contracts) - len(active_contracts),
        total_value=total_value,
        annual_spend=None,  # Would need financial data
        contract_types=contract_types,
        earliest_contract=min(effective_dates) if effective_dates else None,
        latest_expiration=max(expiration_dates) if expiration_dates else None,
    )

    # Obligation compliance
    obligation_rate, obligation_data = await calculate_obligation_compliance(db, contract_ids)
    obligation_summary = VendorObligationSummary(
        total_obligations=obligation_data["total"],
        completed_obligations=obligation_data["completed"],
        overdue_obligations=obligation_data["overdue"],
        compliance_rate=obligation_rate,
        by_status=obligation_data["by_status"],
        by_rag=obligation_data["by_rag"],
        critical_overdue=obligation_data["critical_overdue"],
    )

    # SLA compliance
    sla_rate, sla_data = await calculate_sla_compliance(db, contract_ids)
    sla_summary = VendorSLASummary(
        total_slas=sla_data["total"],
        active_slas=sla_data["active"],
        compliance_rate=sla_rate,
        total_breaches=sla_data["breaches"],
        critical_breaches=sla_data["critical_breaches"],
        total_penalties=sla_data["penalties"],
        by_metric_type=sla_data["by_metric"],
    )

    # Calculate composite score
    score_breakdown = calculate_composite_score(obligation_rate, sla_rate)

    return {
        "contracts": contract_summary,
        "obligations": obligation_summary,
        "slas": sla_summary,
        "score_breakdown": score_breakdown,
        "active_breaches": sla_data["breaches"],
    }


@router.get("", response_model=VendorListResponse)
async def list_vendors(
    sort_by: str = Query("score", pattern="^(score|name|exposure|contracts)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    party_type: str = Query("all", pattern="^(all|vendor|client)$", description="Filter by counterparty type"),
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """
    List all counterparties with performance scores.

    Aggregates data from all contracts by counterparty name.

    - **party_type**: Filter by type - 'vendor' (you buy from), 'client' (you deliver to), or 'all'
    - **sort_by**: Sort field - score, name, exposure, contracts
    - **sort_order**: asc or desc
    - **include_inactive**: Include counterparties with only expired contracts
    """
    # Get all unique counterparties
    query = select(Contract.counterparty).where(
        and_(
            Contract.status == ContractStatus.COMPLETED,
            Contract.counterparty.isnot(None),
        )
    )
    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)
    query = query.distinct()

    result = await db.execute(query)
    counterparties = [row[0] for row in result.all() if row[0]]

    # Build vendor list
    vendors = []
    total_exposure = 0.0
    at_risk_count = 0

    for counterparty in counterparties:
        contracts = await get_vendor_contracts(db, counterparty, tenant_id=tenant_id)
        if not contracts:
            continue

        if not include_inactive:
            # Treat contracts with no expiration date as active (they haven't expired)
            active = [c for c in contracts if not c.expiration_date or c.expiration_date >= datetime.now().date()]
            if not active:
                continue

        # Determine counterparty type
        contract_ids = [c.id for c in contracts]
        cp_type = await determine_counterparty_type(db, counterparty, contract_ids)

        # Filter by party_type if specified
        if party_type == "vendor" and cp_type != CounterpartyType.VENDOR:
            # Skip if filtering for vendors and this isn't a vendor
            # But include UNKNOWN in vendor view (legacy behavior)
            if cp_type == CounterpartyType.CLIENT:
                continue
        elif party_type == "client" and cp_type != CounterpartyType.CLIENT:
            # Skip if filtering for clients and this isn't a client
            if cp_type == CounterpartyType.VENDOR:
                continue

        metrics = await build_vendor_metrics(db, counterparty, contracts)

        score = metrics["score_breakdown"].weighted_total
        exposure = metrics["contracts"].total_value
        total_exposure += exposure

        is_at_risk = score < AT_RISK_THRESHOLD
        if is_at_risk:
            at_risk_count += 1

        vendor_item = VendorListItem(
            vendor_name=counterparty,
            normalized_name=normalize_vendor_name(counterparty),
            party_type=cp_type,
            performance_score=score,
            risk_level=determine_risk_level(score),
            is_at_risk=is_at_risk,
            contract_count=metrics["contracts"].total_contracts,
            total_exposure=exposure,
            sla_compliance_rate=metrics["slas"].compliance_rate,
            obligation_compliance_rate=metrics["obligations"].compliance_rate,
            active_breaches=metrics["active_breaches"],
            last_updated=datetime.utcnow(),
        )
        vendors.append(vendor_item)

    # Sort vendors
    reverse = sort_order == "desc"
    if sort_by == "score":
        vendors.sort(key=lambda v: v.performance_score, reverse=reverse)
    elif sort_by == "name":
        vendors.sort(key=lambda v: v.vendor_name.lower(), reverse=reverse)
    elif sort_by == "exposure":
        vendors.sort(key=lambda v: v.total_exposure, reverse=reverse)
    elif sort_by == "contracts":
        vendors.sort(key=lambda v: v.contract_count, reverse=reverse)

    return VendorListResponse(
        total_vendors=len(vendors),
        at_risk_count=at_risk_count,
        total_exposure=total_exposure,
        vendors=vendors,
    )


@router.get("/at-risk", response_model=AtRiskVendorsResponse)
async def get_at_risk_vendors(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """
    Get vendors with performance score below threshold (< 60).

    These vendors require attention due to compliance or SLA issues.
    """
    # Get all vendors first
    vendor_response = await list_vendors(sort_by="score", sort_order="asc", include_inactive=False, db=db, current_user=current_user, tenant_id=tenant_id)

    at_risk_vendors = []
    total_exposure = 0.0
    critical_count = 0
    high_count = 0

    for vendor in vendor_response.vendors:
        if not vendor.is_at_risk:
            continue

        # Get detailed metrics
        contracts = await get_vendor_contracts(db, vendor.vendor_name, tenant_id=tenant_id)
        metrics = await build_vendor_metrics(db, vendor.vendor_name, contracts)

        # Identify primary issues
        issues = []
        if metrics["obligations"].compliance_rate < 70:
            issues.append(f"Low obligation compliance: {metrics['obligations'].compliance_rate:.1f}%")
        if metrics["slas"].compliance_rate < 80:
            issues.append(f"Low SLA compliance: {metrics['slas'].compliance_rate:.1f}%")
        if metrics["slas"].total_breaches > 0:
            issues.append(f"{metrics['slas'].total_breaches} active SLA breaches")
        if metrics["obligations"].overdue_obligations > 0:
            issues.append(f"{metrics['obligations'].overdue_obligations} overdue obligations")
        if metrics["slas"].total_penalties > 0:
            issues.append(f"${metrics['slas'].total_penalties:,.2f} in penalties")

        # Determine recommended action
        if vendor.performance_score < CRITICAL_RISK_THRESHOLD:
            recommended_action = "Immediate contract review and potential termination"
            critical_count += 1
        elif vendor.performance_score < HIGH_RISK_THRESHOLD:
            recommended_action = "Escalate to vendor management for remediation plan"
            high_count += 1
        else:
            recommended_action = "Schedule performance review meeting"

        at_risk = AtRiskVendor(
            vendor_name=vendor.vendor_name,
            performance_score=vendor.performance_score,
            risk_level=vendor.risk_level,
            primary_issues=issues[:5],  # Top 5 issues
            contracts_affected=vendor.contract_count,
            exposure_at_risk=vendor.total_exposure,
            obligation_compliance=metrics["obligations"].compliance_rate,
            sla_compliance=metrics["slas"].compliance_rate,
            active_breaches=metrics["slas"].total_breaches,
            overdue_obligations=metrics["obligations"].overdue_obligations,
            recommended_action=recommended_action,
        )
        at_risk_vendors.append(at_risk)
        total_exposure += vendor.total_exposure

    return AtRiskVendorsResponse(
        total_at_risk=len(at_risk_vendors),
        total_exposure_at_risk=total_exposure,
        critical_count=critical_count,
        high_count=high_count,
        vendors=at_risk_vendors,
    )


@router.get("/compare", response_model=VendorCompareResponse)
async def compare_vendors(
    vendors: str = Query(..., description="Comma-separated vendor names"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """
    Compare multiple vendors side by side.

    Pass vendor names as comma-separated values.
    """
    vendor_names = [v.strip() for v in vendors.split(",") if v.strip()]

    if len(vendor_names) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 vendors required for comparison"
        )

    if len(vendor_names) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 5 vendors can be compared at once"
        )

    compare_items = []

    for vendor_name in vendor_names:
        contracts = await get_vendor_contracts(db, vendor_name, tenant_id=tenant_id)
        if not contracts:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vendor '{vendor_name}' not found"
            )

        metrics = await build_vendor_metrics(db, vendor_name, contracts)

        item = VendorCompareItem(
            vendor_name=vendor_name,
            performance_score=metrics["score_breakdown"].weighted_total,
            obligation_compliance=metrics["obligations"].compliance_rate,
            sla_compliance=metrics["slas"].compliance_rate,
            total_exposure=metrics["contracts"].total_value,
            contract_count=metrics["contracts"].total_contracts,
            active_breaches=metrics["slas"].total_breaches,
            risk_level=determine_risk_level(metrics["score_breakdown"].weighted_total),
        )
        compare_items.append(item)

    # Find best/worst
    best_overall = max(compare_items, key=lambda x: x.performance_score).vendor_name
    worst_overall = min(compare_items, key=lambda x: x.performance_score).vendor_name
    best_sla = max(compare_items, key=lambda x: x.sla_compliance).vendor_name
    best_obligation = max(compare_items, key=lambda x: x.obligation_compliance).vendor_name
    highest_exposure = max(compare_items, key=lambda x: x.total_exposure).vendor_name

    return VendorCompareResponse(
        vendors=compare_items,
        comparison_date=datetime.utcnow(),
        best_overall=best_overall,
        worst_overall=worst_overall,
        best_sla_compliance=best_sla,
        best_obligation_compliance=best_obligation,
        highest_exposure=highest_exposure,
    )


@router.get("/scorecard", response_model=list[VendorScorecard])
async def get_vendor_scorecards(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """
    Get vendor scorecards for procurement dashboard.

    Returns simplified scorecard view for top vendors by exposure.
    """
    vendor_response = await list_vendors(sort_by="exposure", sort_order="desc", include_inactive=False, db=db, current_user=current_user, tenant_id=tenant_id)

    scorecards = []
    strategic_threshold = vendor_response.total_exposure * 0.1  # Top 10% by exposure

    for vendor in vendor_response.vendors[:limit]:
        scorecard = VendorScorecard(
            vendor_name=vendor.vendor_name,
            score=vendor.performance_score,
            grade=score_to_grade(vendor.performance_score),
            contracts=vendor.contract_count,
            exposure=vendor.total_exposure,
            sla_compliance=vendor.sla_compliance_rate or 0,
            obligation_compliance=vendor.obligation_compliance_rate or 0,
            is_strategic=vendor.total_exposure >= strategic_threshold,
            is_at_risk=vendor.is_at_risk,
            needs_review=vendor.is_at_risk or vendor.active_breaches > 0,
        )
        scorecards.append(scorecard)

    return scorecards


@router.get("/{vendor_name}/performance", response_model=VendorPerformanceDetail)
async def get_vendor_performance(
    vendor_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """
    Get detailed performance profile for a specific vendor.

    Includes full breakdown of scores, contracts, obligations, and SLAs.
    """
    contracts = await get_vendor_contracts(db, vendor_name, tenant_id=tenant_id)

    if not contracts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor '{vendor_name}' not found"
        )

    metrics = await build_vendor_metrics(db, vendor_name, contracts)
    score = metrics["score_breakdown"].weighted_total

    # Build risk factors and recommendations
    risk_factors = []
    recommendations = []

    if metrics["obligations"].compliance_rate < 80:
        risk_factors.append(f"Obligation compliance below target: {metrics['obligations'].compliance_rate:.1f}%")
        recommendations.append("Implement regular obligation tracking meetings")

    if metrics["slas"].compliance_rate < 90:
        risk_factors.append(f"SLA compliance needs improvement: {metrics['slas'].compliance_rate:.1f}%")
        recommendations.append("Review SLA terms and establish improvement plan")

    if metrics["slas"].total_breaches > 0:
        risk_factors.append(f"{metrics['slas'].total_breaches} active SLA breaches")
        recommendations.append("Address active SLA breaches immediately")

    if metrics["obligations"].overdue_obligations > 0:
        risk_factors.append(f"{metrics['obligations'].overdue_obligations} overdue obligations")
        recommendations.append("Escalate overdue obligations to vendor")

    if metrics["slas"].total_penalties > 0:
        risk_factors.append(f"${metrics['slas'].total_penalties:,.2f} in accumulated penalties")
        recommendations.append("Review penalty credits and negotiate remediation")

    if not risk_factors:
        risk_factors.append("No significant risk factors identified")
        recommendations.append("Continue monitoring performance")

    return VendorPerformanceDetail(
        vendor_name=vendor_name,
        normalized_name=normalize_vendor_name(vendor_name),
        performance_score=score,
        risk_level=determine_risk_level(score),
        is_at_risk=score < AT_RISK_THRESHOLD,
        score_breakdown=metrics["score_breakdown"],
        contracts=metrics["contracts"],
        obligations=metrics["obligations"],
        slas=metrics["slas"],
        score_trend=None,  # Would need historical data
        previous_score=None,
        risk_factors=risk_factors,
        recommended_actions=recommendations,
        last_updated=datetime.utcnow(),
    )
