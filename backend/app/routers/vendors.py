"""Vendor Performance Scoring API endpoints.

Thin HTTP handlers delegating to vendor_service for business logic.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import CurrentUser, CurrentTenantId
from app.schemas.vendor import (
    CounterpartyType,
    VendorListItem,
    VendorListResponse,
    VendorPerformanceDetail,
    VendorCompareItem,
    VendorCompareResponse,
    AtRiskVendor,
    AtRiskVendorsResponse,
    VendorScorecard,
)
from app.services.vendor_service import (
    normalize_vendor_name,
    determine_risk_level,
    score_to_grade,
    determine_counterparty_type,
    get_vendor_contracts,
    build_vendor_metrics,
    AT_RISK_THRESHOLD,
    HIGH_RISK_THRESHOLD,
    CRITICAL_RISK_THRESHOLD,
)

router = APIRouter(prefix="/api/vendors", tags=["vendors"])


def _bu_args(current_user):
    """Extract BU filter args from current_user."""
    bu_id = current_user.business_unit_id if current_user else None
    role = current_user.role.value if current_user and current_user.role else None
    return bu_id, role


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
    """List all counterparties with performance scores."""
    from sqlalchemy import select, and_
    from app.core.tenant import apply_bu_filter
    from app.models import Contract, ContractStatus

    bu_id, role = _bu_args(current_user)

    # Get all unique counterparties
    query = select(Contract.counterparty).where(
        and_(
            Contract.status == ContractStatus.COMPLETED,
            Contract.counterparty.isnot(None),
        )
    )
    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)
    query = apply_bu_filter(query, bu_id, role)
    query = query.distinct()

    result = await db.execute(query)
    counterparties = [row[0] for row in result.all() if row[0]]

    # Build vendor list
    vendors = []
    total_exposure = 0.0
    at_risk_count = 0

    for counterparty in counterparties:
        contracts = await get_vendor_contracts(db, counterparty, tenant_id=tenant_id, business_unit_id=bu_id, user_role=role)
        if not contracts:
            continue

        if not include_inactive:
            active = [c for c in contracts if not c.expiration_date or c.expiration_date >= datetime.now().date()]
            if not active:
                continue

        contract_ids = [c.id for c in contracts]
        cp_type = await determine_counterparty_type(db, counterparty, contract_ids)

        if party_type == "vendor" and cp_type != CounterpartyType.VENDOR:
            if cp_type == CounterpartyType.CLIENT:
                continue
        elif party_type == "client" and cp_type != CounterpartyType.CLIENT:
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
    """Get vendors with performance score below threshold (< 60)."""
    vendor_response = await list_vendors(sort_by="score", sort_order="asc", include_inactive=False, db=db, current_user=current_user, tenant_id=tenant_id)

    bu_id, role = _bu_args(current_user)

    at_risk_vendors = []
    total_exposure = 0.0
    critical_count = 0
    high_count = 0

    for vendor in vendor_response.vendors:
        if not vendor.is_at_risk:
            continue

        contracts = await get_vendor_contracts(db, vendor.vendor_name, tenant_id=tenant_id, business_unit_id=bu_id, user_role=role)
        metrics = await build_vendor_metrics(db, vendor.vendor_name, contracts)

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
            primary_issues=issues[:5],
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
    """Compare multiple vendors side by side."""
    vendor_names = [v.strip() for v in vendors.split(",") if v.strip()]

    if len(vendor_names) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least 2 vendors required for comparison")
    if len(vendor_names) > 5:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum 5 vendors can be compared at once")

    bu_id, role = _bu_args(current_user)
    compare_items = []

    for vendor_name in vendor_names:
        contracts = await get_vendor_contracts(db, vendor_name, tenant_id=tenant_id, business_unit_id=bu_id, user_role=role)
        if not contracts:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Vendor '{vendor_name}' not found")

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
    """Get vendor scorecards for procurement dashboard."""
    vendor_response = await list_vendors(sort_by="exposure", sort_order="desc", include_inactive=False, db=db, current_user=current_user, tenant_id=tenant_id)

    scorecards = []
    strategic_threshold = vendor_response.total_exposure * 0.1

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
    """Get detailed performance profile for a specific vendor."""
    bu_id, role = _bu_args(current_user)
    contracts = await get_vendor_contracts(db, vendor_name, tenant_id=tenant_id, business_unit_id=bu_id, user_role=role)

    if not contracts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Vendor '{vendor_name}' not found")

    metrics = await build_vendor_metrics(db, vendor_name, contracts)
    score = metrics["score_breakdown"].weighted_total

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
        score_trend=None,
        previous_score=None,
        risk_factors=risk_factors,
        recommended_actions=recommendations,
        last_updated=datetime.utcnow(),
    )
