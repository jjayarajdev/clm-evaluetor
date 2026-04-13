"""Post-Signing Dashboard API endpoints."""

from datetime import date, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, CurrentTenantId
from app.core.tenant import apply_bu_filter, apply_tenant_filter
from app.database import get_db
from app.models import (
    Contract, ContractStatus, Obligation, ObligationStatus, RAGStatus,
    ContractSLA, SLAPerformance,
)
from app.schemas.postsigning import (
    ObligationWidget,
    SLAWidget,
    RenewalWidget,
    VendorWidget,
    MilestoneWidget,
    ComplianceWidget,
    PostSigningDashboard,
)

router = APIRouter(prefix="/api/dashboard/postsigning", tags=["postsigning-dashboard"])


@router.get("", response_model=PostSigningDashboard)
async def get_postsigning_dashboard(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Get complete post-signing dashboard data.

    Aggregates data from obligations, SLAs, renewals, vendors, and milestones
    into a single response optimized for dashboard rendering.
    """
    today = date.today()
    now = datetime.utcnow()

    # ============ CONTRACTS SUMMARY ============
    contract_query = select(Contract).where(
        Contract.status == ContractStatus.COMPLETED
    )
    contract_query = apply_tenant_filter(contract_query, tenant_id, Contract)
    contract_query = apply_bu_filter(contract_query, current_user.business_unit_id, current_user.role.value if current_user.role else None)
    contract_result = await db.execute(contract_query)
    contracts = list(contract_result.scalars().all())

    total_contracts = len(contracts)
    total_value = sum(float(c.contract_value) for c in contracts if c.contract_value)

    # ============ OBLIGATIONS WIDGET ============
    obl_query = select(Obligation).join(
        Contract, Obligation.contract_id == Contract.id
    ).where(Contract.status == ContractStatus.COMPLETED)
    obl_query = apply_tenant_filter(obl_query, tenant_id, Contract)
    obl_query = apply_bu_filter(obl_query, current_user.business_unit_id, current_user.role.value if current_user.role else None)
    obl_result = await db.execute(obl_query)
    obligations = list(obl_result.scalars().all())

    obl_total = len(obligations)
    obl_completed = sum(1 for o in obligations if o.status == ObligationStatus.COMPLETED)
    obl_in_progress = sum(1 for o in obligations if o.status == ObligationStatus.IN_PROGRESS)
    obl_overdue = sum(1 for o in obligations if o.status == ObligationStatus.OVERDUE)

    # At-risk: pending + due within 7 days (use deadline field)
    obl_at_risk = sum(1 for o in obligations
                      if o.status == ObligationStatus.PENDING
                      and o.deadline
                      and 0 <= (o.deadline - today).days <= 7)

    obl_green = sum(1 for o in obligations if o.rag_status == RAGStatus.GREEN)
    obl_amber = sum(1 for o in obligations if o.rag_status == RAGStatus.AMBER)
    obl_red = sum(1 for o in obligations if o.rag_status == RAGStatus.RED)

    waived = sum(1 for o in obligations if o.status == ObligationStatus.WAIVED)
    # For compliance rate, only consider obligations that are due (deadline passed or no deadline)
    # Exclude pending obligations with future deadlines — they haven't come due yet
    pending_future = sum(1 for o in obligations
                         if o.status == ObligationStatus.PENDING
                         and o.deadline and o.deadline > today)
    assessable = obl_total - waived - pending_future
    obl_compliance = ((obl_completed + obl_in_progress) / assessable * 100) if assessable > 0 else 100.0

    # Urgent obligations (use deadline field)
    urgent_obls = [o for o in obligations if o.status == ObligationStatus.OVERDUE or
                   (o.status == ObligationStatus.PENDING and o.deadline and (o.deadline - today).days <= 3)]
    urgent_obls.sort(key=lambda o: o.deadline or date.max)

    urgent_items = [
        {
            "id": str(o.id),
            "title": o.description[:100] if o.description else "No description",
            "due_date": o.deadline.isoformat() if o.deadline else None,
            "status": o.status.value if o.status else "pending",
            "rag": o.rag_status.value if o.rag_status else None,
        }
        for o in urgent_obls[:5]
    ]

    obligations_widget = ObligationWidget(
        total=obl_total,
        completed=obl_completed,
        in_progress=obl_in_progress,
        overdue=obl_overdue,
        at_risk=obl_at_risk,
        compliance_rate=round(obl_compliance, 2),
        green=obl_green,
        amber=obl_amber,
        red=obl_red,
        urgent_items=urgent_items,
    )

    # ============ SLA WIDGET ============
    sla_query = select(ContractSLA).join(
        Contract, ContractSLA.contract_id == Contract.id
    ).where(Contract.status == ContractStatus.COMPLETED)
    sla_query = apply_tenant_filter(sla_query, tenant_id, Contract)
    sla_query = apply_bu_filter(sla_query, current_user.business_unit_id, current_user.role.value if current_user.role else None)
    sla_result = await db.execute(sla_query)
    slas = list(sla_result.scalars().all())

    sla_total = len(slas)
    sla_active = sum(1 for s in slas if s.is_active)
    sla_breached = sum(1 for s in slas if s.consecutive_breaches > 0)
    sla_compliant = sla_active - sla_breached

    critical_breaches = sum(1 for s in slas
                           if s.consecutive_breaches > 0
                           and s.severity and s.severity.value == "critical")

    compliance_rates = [float(s.current_compliance_rate) for s in slas if s.current_compliance_rate is not None]
    sla_compliance = sum(compliance_rates) / len(compliance_rates) if compliance_rates else 100.0

    # Get MTD penalties (filtered by tenant)
    mtd_start = date(today.year, today.month, 1)
    penalty_query = select(func.sum(SLAPerformance.penalty_amount)).join(
        ContractSLA, SLAPerformance.sla_id == ContractSLA.id
    ).join(
        Contract, ContractSLA.contract_id == Contract.id
    ).where(
        and_(
            SLAPerformance.penalty_applied == True,
            SLAPerformance.measured_at >= datetime.combine(mtd_start, datetime.min.time()),
        )
    )
    if tenant_id is not None:
        penalty_query = penalty_query.where(Contract.tenant_id == tenant_id)
    penalty_query = apply_bu_filter(penalty_query, current_user.business_unit_id, current_user.role.value if current_user.role else None)
    penalty_result = await db.execute(penalty_query)
    total_penalties_mtd = float(penalty_result.scalar() or 0)

    # Recent breaches with performance details
    breached_slas = [s for s in slas if s.consecutive_breaches > 0]
    breached_slas.sort(key=lambda s: s.consecutive_breaches, reverse=True)

    recent_breaches = []
    for s in breached_slas[:10]:  # Get top 10 for better coverage
        # Get contract info
        contract = next((c for c in contracts if c.id == s.contract_id), None)

        # Get latest performance record for actual values
        perf_query = select(SLAPerformance).where(
            SLAPerformance.sla_id == s.id
        ).order_by(SLAPerformance.measured_at.desc()).limit(1)
        perf_result = await db.execute(perf_query)
        latest_perf = perf_result.scalar_one_or_none()

        recent_breaches.append({
            "sla_id": str(s.id),
            "sla_name": s.sla_name,
            "contract_id": str(s.contract_id),
            "contract": contract.filename if contract else "Unknown",
            "breaches": s.consecutive_breaches,
            "severity": s.severity.value if s.severity else "medium",
            "metric_type": s.metric_type.value if s.metric_type else "custom",
            "target_value": float(s.target_value) if s.target_value else None,
            "actual_value": float(latest_perf.actual_value) if latest_perf and latest_perf.actual_value else None,
            "deviation": float(latest_perf.deviation_percentage) if latest_perf and latest_perf.deviation_percentage else None,
            "measured_at": latest_perf.measured_at.isoformat() if latest_perf and latest_perf.measured_at else None,
            "penalty_amount": float(latest_perf.penalty_amount) if latest_perf and latest_perf.penalty_amount else None,
        })

    sla_widget = SLAWidget(
        total_slas=sla_total,
        active_slas=sla_active,
        compliant=sla_compliant,
        breached=sla_breached,
        compliance_rate=round(sla_compliance, 2),
        critical_breaches=critical_breaches,
        total_penalties_mtd=total_penalties_mtd,
        recent_breaches=recent_breaches,
    )

    # ============ RENEWAL WIDGET ============
    expiring_30 = []
    expiring_60 = []
    expiring_90 = []
    past_notice = []

    for c in contracts:
        if not c.expiration_date:
            continue

        days_until = (c.expiration_date - today).days

        if days_until < 0:
            continue  # Already expired

        if days_until <= 30:
            expiring_30.append(c)
        if days_until <= 60:
            expiring_60.append(c)
        if days_until <= 90:
            expiring_90.append(c)

        # Check notice deadline
        if c.notice_period_days:
            notice_deadline = c.expiration_date - timedelta(days=c.notice_period_days)
            if notice_deadline < today and days_until > 0:
                past_notice.append(c)

    value_at_risk = sum(float(c.contract_value) for c in expiring_90 if c.contract_value)

    # Upcoming renewals
    upcoming = sorted(expiring_90, key=lambda c: c.expiration_date or date.max)[:5]
    upcoming_renewals = [
        {
            "contract_id": str(c.id),
            "filename": c.filename,
            "counterparty": c.counterparty,
            "expiration_date": c.expiration_date.isoformat() if c.expiration_date else None,
            "value": float(c.contract_value) if c.contract_value else None,
            "auto_renewal": c.auto_renewal,
        }
        for c in upcoming
    ]

    renewal_widget = RenewalWidget(
        expiring_30_days=len(expiring_30),
        expiring_60_days=len(expiring_60),
        expiring_90_days=len(expiring_90),
        past_notice_deadline=len(past_notice),
        total_value_at_risk=value_at_risk,
        upcoming_renewals=upcoming_renewals,
    )

    # ============ VENDOR WIDGET ============
    # Get unique counterparties
    counterparties = list(set(c.counterparty for c in contracts if c.counterparty))

    vendor_scores = []
    for cp in counterparties:
        cp_contracts = [c for c in contracts if c.counterparty == cp]
        cp_contract_ids = [c.id for c in cp_contracts]

        # Get obligations for this vendor
        cp_obls = [o for o in obligations if o.contract_id in cp_contract_ids]
        cp_completed = sum(1 for o in cp_obls if o.status == ObligationStatus.COMPLETED)
        cp_total = len(cp_obls)
        obl_rate = (cp_completed / cp_total * 100) if cp_total > 0 else 100

        # Get SLAs for this vendor
        cp_slas = [s for s in slas if s.contract_id in cp_contract_ids]
        cp_sla_rates = [float(s.current_compliance_rate) for s in cp_slas if s.current_compliance_rate is not None]
        sla_rate = sum(cp_sla_rates) / len(cp_sla_rates) if cp_sla_rates else 100

        # Simple score calculation
        score = obl_rate * 0.5 + sla_rate * 0.5
        vendor_scores.append({
            "name": cp,
            "score": round(score, 2),
            "contracts": len(cp_contracts),
        })

    vendor_scores.sort(key=lambda v: v["score"], reverse=True)

    at_risk_vendors = sum(1 for v in vendor_scores if v["score"] < 60)
    avg_score = sum(v["score"] for v in vendor_scores) / len(vendor_scores) if vendor_scores else 0

    vendor_widget = VendorWidget(
        total_vendors=len(counterparties),
        at_risk_vendors=at_risk_vendors,
        avg_performance_score=round(avg_score, 2),
        top_performers=vendor_scores[:3],
        bottom_performers=vendor_scores[-3:][::-1] if len(vendor_scores) >= 3 else vendor_scores[::-1],
    )

    # ============ MILESTONE WIDGET ============
    # Milestones are obligations with deadlines
    milestones = [o for o in obligations if o.deadline]
    ms_total = len(milestones)
    ms_completed = sum(1 for o in milestones if o.status == ObligationStatus.COMPLETED)
    ms_overdue = sum(1 for o in milestones if o.status == ObligationStatus.OVERDUE)
    ms_at_risk = sum(1 for o in milestones
                     if o.status == ObligationStatus.PENDING
                     and o.deadline and 0 <= (o.deadline - today).days <= 7)

    ms_completion_rate = (ms_completed / ms_total * 100) if ms_total > 0 else 100

    # Due this week
    week_end = today + timedelta(days=7)
    due_this_week_obls = [o for o in milestones
                          if o.deadline and today <= o.deadline <= week_end
                          and o.status != ObligationStatus.COMPLETED]
    due_this_week_obls.sort(key=lambda o: o.deadline or date.max)

    due_this_week = [
        {
            "id": str(o.id),
            "title": o.description[:100] if o.description else "No description",
            "due_date": o.deadline.isoformat() if o.deadline else None,
            "status": o.status.value if o.status else "pending",
        }
        for o in due_this_week_obls[:5]
    ]

    milestone_widget = MilestoneWidget(
        total_milestones=ms_total,
        completed=ms_completed,
        at_risk=ms_at_risk,
        overdue=ms_overdue,
        completion_rate=round(ms_completion_rate, 2),
        due_this_week=due_this_week,
    )

    # ============ COMPLIANCE WIDGET ============
    overall_compliance = obl_compliance * 0.6 + sla_compliance * 0.4

    # Contracts at risk: high overdue count or low completion rate
    contracts_at_risk = 0
    for c in contracts:
        c_obls = [o for o in obligations if o.contract_id == c.id]
        c_overdue = sum(1 for o in c_obls if o.status == ObligationStatus.OVERDUE)
        if c_overdue >= 2 or (len(c_obls) > 0 and c_overdue / len(c_obls) > 0.3):
            contracts_at_risk += 1

    # High priority actions
    high_priority = obl_overdue + sla_breached + len(past_notice)

    compliance_widget = ComplianceWidget(
        overall_compliance_rate=round(overall_compliance, 2),
        obligation_compliance_rate=round(obl_compliance, 2),
        sla_compliance_rate=round(sla_compliance, 2),
        trend=None,  # Would need historical data
        change_from_last_month=None,
        contracts_at_risk=contracts_at_risk,
        high_priority_actions=high_priority,
    )

    # ============ PRIORITY ACTIONS ============
    priority_actions = []

    # Add overdue obligations
    for o in urgent_obls[:3]:
        priority_actions.append({
            "type": "obligation",
            "severity": "high" if o.status == ObligationStatus.OVERDUE else "medium",
            "title": f"{'Overdue' if o.status == ObligationStatus.OVERDUE else 'Upcoming'}: {o.description[:50] if o.description else 'Obligation'}",
            "action": "Review and complete obligation",
            "due_date": o.deadline.isoformat() if o.deadline else None,
        })

    # Add critical SLA breaches
    for breach in recent_breaches[:2]:
        if breach["severity"] == "critical":
            priority_actions.append({
                "type": "sla",
                "severity": "critical",
                "title": f"SLA Breach: {breach['sla_name']}",
                "action": "Escalate and remediate immediately",
                "contract": breach["contract"],
            })

    # Add past notice deadline renewals
    for c in past_notice[:2]:
        priority_actions.append({
            "type": "renewal",
            "severity": "high",
            "title": f"Renewal: {c.filename}",
            "action": "Make renewal decision - past notice deadline",
            "expiration": c.expiration_date.isoformat() if c.expiration_date else None,
        })

    contracts_needing_attention = contracts_at_risk + len(past_notice)

    return PostSigningDashboard(
        generated_at=now,
        as_of_date=today,
        obligations=obligations_widget,
        slas=sla_widget,
        renewals=renewal_widget,
        vendors=vendor_widget,
        milestones=milestone_widget,
        compliance=compliance_widget,
        total_contracts=total_contracts,
        total_value=total_value,
        contracts_needing_attention=contracts_needing_attention,
        priority_actions=priority_actions[:10],
    )


@router.get("/obligations")
async def get_obligation_details(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    status: str = None,
    rag: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed obligation list with optional filters."""
    query = select(Obligation, Contract).join(
        Contract, Obligation.contract_id == Contract.id
    ).where(Contract.status == ContractStatus.COMPLETED)
    query = apply_tenant_filter(query, tenant_id, Contract)
    query = apply_bu_filter(query, current_user.business_unit_id, current_user.role.value if current_user.role else None)

    if status:
        query = query.where(Obligation.status == ObligationStatus(status))
    if rag:
        query = query.where(Obligation.rag_status == RAGStatus(rag))

    query = query.order_by(Obligation.deadline)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "id": str(o.id),
            "contract_id": str(c.id),
            "contract_filename": c.filename,
            "counterparty": c.counterparty,
            "title": o.description[:100] if o.description else "No description",
            "description": o.description,
            "category": o.category.value if o.category else None,
            "owner": o.obligated_party,
            "due_date": o.deadline.isoformat() if o.deadline else None,
            "status": o.status.value if o.status else "pending",
            "rag_status": o.rag_status.value if o.rag_status else None,
        }
        for o, c in rows
    ]


@router.get("/slas")
async def get_sla_details(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    breached_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed SLA list with optional filters."""
    query = select(ContractSLA, Contract).join(
        Contract, ContractSLA.contract_id == Contract.id
    ).where(
        and_(
            Contract.status == ContractStatus.COMPLETED,
            ContractSLA.is_active == True,
        )
    )
    query = apply_tenant_filter(query, tenant_id, Contract)
    query = apply_bu_filter(query, current_user.business_unit_id, current_user.role.value if current_user.role else None)

    if breached_only:
        query = query.where(ContractSLA.consecutive_breaches > 0)

    query = query.order_by(ContractSLA.consecutive_breaches.desc())

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "id": str(s.id),
            "contract_id": str(c.id),
            "contract_filename": c.filename,
            "counterparty": c.counterparty,
            "sla_name": s.sla_name,
            "metric_type": s.metric_type.value if s.metric_type else None,
            "target_value": float(s.target_value) if s.target_value else None,
            "compliance_rate": float(s.current_compliance_rate) if s.current_compliance_rate else None,
            "consecutive_breaches": s.consecutive_breaches,
            "severity": s.severity.value if s.severity else "medium",
            "has_penalty": s.has_penalty,
        }
        for s, c in rows
    ]
