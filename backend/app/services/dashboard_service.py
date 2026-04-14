"""Dashboard service.

Business logic for role-specific dashboards, portfolio analytics, and
contract intelligence aggregation. Extracted from routers/dashboard.py.

Supports optional dashboard cache: heavy endpoints check DashboardCache
first and store results on cache miss. Cache is invalidated by
contract/obligation mutations via invalidate_dashboard_cache().
"""

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, Integer, cast, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import apply_bu_filter, apply_tenant_filter
from app.models.audit import AuditLog, AuditAction
from app.models.clause import Clause, ClauseType, RiskLevel
from app.models.contract import Contract, ContractStatus, ContractType
from app.models.obligation import Obligation, ObligationStatus, ObligationOwner, ObligationCategory, RAGStatus
from app.models.clause_indicator import ContractClauseIndicator
from app.models.contract_link import ContractLink
from app.models.financial import ContractFinancial, ContractLiability
from app.models.key_date import ContractKeyDate
from app.models.party import ContractParty
from app.models.user import User

from app.schemas.dashboard import (
    # Admin
    ContractStats, UserStats, ActivityMetrics, IngestionStatus,
    AdminDashboardResponse,
    # Legal
    RiskOverview, ExpirationItem, ExpirationTimeline, HighRiskClause,
    LegalDashboardResponse,
    # Procurement
    SpendCommitment, VendorObligation, AutoRenewalRisk,
    ProcurementDashboardResponse,
    # Obligations & Compliance
    ComplianceObligationItem, RAGStatusSummary, ComplianceByCategory,
    ComplianceByOwner, ComplianceCalendarItem, ObligationsComplianceResponse,
    # Portfolio
    PortfolioContractSummary, PortfolioValueMetrics, PortfolioRiskMetrics,
    PortfolioObligationMetrics, PortfolioClauseMetrics, CounterpartyExposure,
    PortfolioDashboardResponse,
    # Cockpit
    CockpitParty, CockpitKeyDate, CockpitFinancial, CockpitLiability,
    CockpitObligation, CockpitClauseIndicators, CockpitLinkedContract,
    CockpitRiskSummary, ContractCockpitResponse,
    # Insights & Activity
    InsightItem, InsightsResponse,
    ActivityItem, ActivityResponse,
)
from app.services.metric_snapshot_service import (
    get_cached_dashboard,
    set_cached_dashboard,
)

logger = logging.getLogger(__name__)


def _bu_args(current_user):
    """Extract BU filter args from current_user."""
    bu_id = current_user.business_unit_id if current_user else None
    role = current_user.role.value if current_user and current_user.role else None
    return bu_id, role


def _cache_key_for_bu(bu_id, role) -> str:
    """Build cache sub-key from BU filter params."""
    return f"bu={bu_id or 'all'}|role={role or 'none'}"


# ============== Admin Dashboard ==============


async def get_admin_dashboard(
    db: AsyncSession, tenant_id, bu_id, role,
) -> AdminDashboardResponse:
    """Build admin dashboard data."""
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Contract stats by type
    type_query = select(Contract.contract_type, func.count(Contract.id)).group_by(Contract.contract_type)
    type_query = apply_tenant_filter(type_query, tenant_id, Contract)
    type_query = apply_bu_filter(type_query, bu_id, role)
    type_result = await db.execute(type_query)
    by_type = {(t.value if t else "unknown"): c for t, c in type_result.all()}

    # Contract stats by status
    status_query = select(Contract.status, func.count(Contract.id)).group_by(Contract.status)
    status_query = apply_tenant_filter(status_query, tenant_id, Contract)
    status_query = apply_bu_filter(status_query, bu_id, role)
    status_result = await db.execute(status_query)
    by_status = {s.value: c for s, c in status_result.all()}

    total_contracts = sum(by_status.values())

    # User stats
    user_query = select(User.role, User.is_active, func.count(User.id)).group_by(User.role, User.is_active)
    if tenant_id is not None:
        user_query = user_query.where(User.tenant_id == tenant_id)
    user_result = await db.execute(user_query)
    by_role: dict[str, int] = {}
    active_users = 0
    inactive_users = 0
    for user_role, is_active, count in user_result.all():
        by_role[user_role.value] = by_role.get(user_role.value, 0) + count
        if is_active:
            active_users += count
        else:
            inactive_users += count

    # Activity metrics
    async def _count_audit(action, since):
        q = (
            select(func.count(AuditLog.id))
            .where(AuditLog.action == action)
            .where(func.date(AuditLog.created_at) >= since)
        )
        if tenant_id is not None:
            q = q.join(User, AuditLog.user_id == User.id).where(User.tenant_id == tenant_id)
        return await db.scalar(q) or 0

    queries_7d = await _count_audit(AuditAction.QUERY_EXECUTE, week_ago)
    queries_30d = await _count_audit(AuditAction.QUERY_EXECUTE, month_ago)
    uploads_7d = await _count_audit(AuditAction.CONTRACT_UPLOAD, week_ago)
    uploads_30d = await _count_audit(AuditAction.CONTRACT_UPLOAD, month_ago)

    # Ingestion status
    ingestion = IngestionStatus(
        pending=by_status.get("pending", 0),
        processing=by_status.get("processing", 0),
        completed=by_status.get("completed", 0),
        failed=by_status.get("failed", 0),
    )

    # Recent failures
    failures_query = (
        select(Contract.id, Contract.filename, Contract.processing_error, Contract.updated_at)
        .where(Contract.status == ContractStatus.FAILED)
        .order_by(Contract.updated_at.desc())
        .limit(5)
    )
    failures_query = apply_tenant_filter(failures_query, tenant_id, Contract)
    failures_query = apply_bu_filter(failures_query, bu_id, role)
    failures_result = await db.execute(failures_query)
    recent_failures = [
        {
            "id": str(row.id),
            "filename": row.filename,
            "error": row.processing_error,
            "timestamp": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in failures_result.all()
    ]

    return AdminDashboardResponse(
        contract_stats=ContractStats(by_type=by_type, by_status=by_status, total=total_contracts),
        user_stats=UserStats(by_role=by_role, active=active_users, inactive=inactive_users, total=active_users + inactive_users),
        activity=ActivityMetrics(queries_7d=queries_7d, queries_30d=queries_30d, uploads_7d=uploads_7d, uploads_30d=uploads_30d),
        ingestion=ingestion,
        recent_failures=recent_failures,
    )


# ============== Legal Dashboard ==============


async def get_legal_dashboard(
    db: AsyncSession, tenant_id, bu_id, role, current_user_id,
) -> LegalDashboardResponse:
    """Build legal dashboard data."""
    today = date.today()

    # Risk distribution
    risk_query = (
        select(Contract.risk_level, func.count(Contract.id))
        .where(Contract.risk_level.isnot(None))
        .group_by(Contract.risk_level)
    )
    risk_query = apply_tenant_filter(risk_query, tenant_id, Contract)
    risk_query = apply_bu_filter(risk_query, bu_id, role)
    risk_result = await db.execute(risk_query)
    by_level = {r.value: c for r, c in risk_result.all()}

    # High risk contracts
    contracts_with_high_risk_clauses = (
        select(Clause.contract_id)
        .where(Clause.risk_level == RiskLevel.HIGH)
        .distinct()
    )

    high_risk_query = (
        select(Contract)
        .where(
            (Contract.risk_level.in_([RiskLevel.HIGH, RiskLevel.CRITICAL])) |
            (Contract.id.in_(contracts_with_high_risk_clauses))
        )
        .order_by(Contract.risk_score.desc().nulls_last())
        .limit(10)
    )
    high_risk_query = apply_tenant_filter(high_risk_query, tenant_id, Contract)
    high_risk_query = apply_bu_filter(high_risk_query, bu_id, role)
    high_risk_result = await db.execute(high_risk_query)

    high_risk_contracts = [
        {
            "id": str(c.id),
            "filename": c.filename,
            "counterparty": c.counterparty,
            "risk_score": c.risk_score,
            "risk_level": c.risk_level.value if c.risk_level else None,
        }
        for c in high_risk_result.scalars().all()
    ]

    # Expiration timeline
    async def _get_expirations(start: date, end: date) -> list[ExpirationItem]:
        exp_query = (
            select(Contract)
            .where(Contract.expiration_date >= start)
            .where(Contract.expiration_date <= end)
            .order_by(Contract.expiration_date.asc())
        )
        exp_query = apply_tenant_filter(exp_query, tenant_id, Contract)
        exp_query = apply_bu_filter(exp_query, bu_id, role)
        result = await db.execute(exp_query)
        return [
            ExpirationItem(
                contract_id=str(c.id),
                filename=c.filename,
                counterparty=c.counterparty,
                expiration_date=c.expiration_date,
                days_remaining=(c.expiration_date - today).days,
            )
            for c in result.scalars().all()
        ]

    next_30 = await _get_expirations(today, today + timedelta(days=30))
    next_60 = await _get_expirations(today + timedelta(days=31), today + timedelta(days=60))
    next_90 = await _get_expirations(today + timedelta(days=61), today + timedelta(days=90))

    # High risk clauses
    clause_query = (
        select(Clause, Contract.filename)
        .join(Contract, Clause.contract_id == Contract.id)
        .where(Clause.risk_level == RiskLevel.HIGH)
        .order_by(Clause.created_at.desc())
        .limit(20)
    )
    clause_query = apply_tenant_filter(clause_query, tenant_id, Contract)
    clause_query = apply_bu_filter(clause_query, bu_id, role)
    clauses_result = await db.execute(clause_query)
    high_risk_clauses = [
        HighRiskClause(
            clause_id=str(clause.id),
            contract_id=str(clause.contract_id),
            contract_filename=filename,
            clause_type=clause.clause_type.value if clause.clause_type else "unknown",
            risk_level=clause.risk_level.value if clause.risk_level else "unknown",
            excerpt=clause.text[:200] + "..." if len(clause.text) > 200 else clause.text,
        )
        for clause, filename in clauses_result.all()
    ]

    # Recent activity for current user
    activity_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.user_id == current_user_id)
        .where(AuditLog.action.in_([AuditAction.QUERY_EXECUTE, AuditAction.CONTRACT_VIEW]))
        .order_by(AuditLog.created_at.desc())
        .limit(10)
    )
    recent_activity = [
        {
            "action": log.action.value,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "timestamp": log.created_at.isoformat(),
        }
        for log in activity_result.scalars().all()
    ]

    return LegalDashboardResponse(
        risk_overview=RiskOverview(by_level=by_level, high_risk_contracts=high_risk_contracts),
        expiration_timeline=ExpirationTimeline(next_30_days=next_30, next_60_days=next_60, next_90_days=next_90),
        high_risk_clauses=high_risk_clauses,
        recent_activity=recent_activity,
    )


# ============== Procurement Dashboard ==============


async def get_procurement_dashboard(
    db: AsyncSession, tenant_id, bu_id, role,
) -> ProcurementDashboardResponse:
    """Build procurement dashboard data."""
    today = date.today()

    # Spend commitments by vendor
    spend_query = (
        select(
            Contract.counterparty,
            func.sum(Contract.contract_value),
            func.count(Contract.id),
            Contract.currency,
        )
        .where(Contract.counterparty.isnot(None))
        .where(Contract.contract_value.isnot(None))
        .group_by(Contract.counterparty, Contract.currency)
        .order_by(func.sum(Contract.contract_value).desc())
        .limit(20)
    )
    spend_query = apply_tenant_filter(spend_query, tenant_id, Contract)
    spend_query = apply_bu_filter(spend_query, bu_id, role)
    spend_result = await db.execute(spend_query)
    spend_commitments = [
        SpendCommitment(
            counterparty=row[0] or "Unknown",
            total_value=row[1] or Decimal(0),
            contract_count=row[2],
            currency=row[3],
        )
        for row in spend_result.all()
    ]

    # Upcoming obligations (next 30 days)
    obl_query = (
        select(Obligation, Contract.filename, Contract.counterparty)
        .join(Contract, Obligation.contract_id == Contract.id)
        .where(Obligation.status == ObligationStatus.PENDING)
        .where(Obligation.deadline >= today)
        .where(Obligation.deadline <= today + timedelta(days=30))
        .order_by(Obligation.deadline.asc())
        .limit(20)
    )
    obl_query = apply_tenant_filter(obl_query, tenant_id, Contract)
    obl_query = apply_bu_filter(obl_query, bu_id, role)
    obligations_result = await db.execute(obl_query)
    upcoming_obligations = [
        VendorObligation(
            obligation_id=str(obl.id),
            contract_id=str(obl.contract_id),
            contract_filename=filename,
            counterparty=counterparty,
            description=obl.description[:100] + "..." if len(obl.description) > 100 else obl.description,
            deadline=obl.deadline,
            days_remaining=(obl.deadline - today).days if obl.deadline else None,
            status=obl.status.value,
        )
        for obl, filename, counterparty in obligations_result.all()
    ]

    # Auto-renewal risks
    renewal_query = (
        select(Contract)
        .where(Contract.auto_renewal == True)
        .where(Contract.expiration_date.isnot(None))
        .order_by(Contract.expiration_date.asc())
        .limit(20)
    )
    renewal_query = apply_tenant_filter(renewal_query, tenant_id, Contract)
    renewal_query = apply_bu_filter(renewal_query, bu_id, role)
    renewal_result = await db.execute(renewal_query)

    auto_renewal_risks = []
    for contract in renewal_result.scalars().all():
        notice_deadline = None
        days_until_notice = None
        urgency = "FUTURE"

        if contract.expiration_date and contract.notice_period_days:
            notice_deadline = contract.expiration_date - timedelta(days=contract.notice_period_days)
            days_until_notice = (notice_deadline - today).days

            if days_until_notice < 0:
                urgency = "IMMEDIATE"
            elif days_until_notice < 7:
                urgency = "IMMEDIATE"
            elif days_until_notice < 30:
                urgency = "SOON"
            elif days_until_notice < 90:
                urgency = "UPCOMING"

        auto_renewal_risks.append(
            AutoRenewalRisk(
                contract_id=str(contract.id),
                filename=contract.filename,
                counterparty=contract.counterparty,
                expiration_date=contract.expiration_date,
                notice_period_days=contract.notice_period_days,
                notice_deadline=notice_deadline,
                days_until_notice=days_until_notice,
                urgency=urgency,
            )
        )

    # Vendor summary
    vendor_query = (
        select(Contract.counterparty, func.count(Contract.id))
        .where(Contract.counterparty.isnot(None))
        .group_by(Contract.counterparty)
        .order_by(func.count(Contract.id).desc())
        .limit(20)
    )
    vendor_query = apply_tenant_filter(vendor_query, tenant_id, Contract)
    vendor_query = apply_bu_filter(vendor_query, bu_id, role)
    vendor_result = await db.execute(vendor_query)
    vendor_summary = {row[0]: row[1] for row in vendor_result.all()}

    return ProcurementDashboardResponse(
        spend_commitments=spend_commitments,
        upcoming_obligations=upcoming_obligations,
        auto_renewal_risks=auto_renewal_risks,
        vendor_summary=vendor_summary,
    )


# ============== Obligations & Compliance Dashboard ==============


async def get_obligations_compliance(
    db: AsyncSession, tenant_id, bu_id, role,
    contract_id=None, owner_filter=None, category_filter=None,
) -> ObligationsComplianceResponse:
    """Build obligations & compliance dashboard."""
    import uuid as uuid_mod

    today = date.today()

    # Build base query with tenant filter
    base_query = select(
        Obligation,
        Contract.filename,
        Contract.counterparty,
    ).join(Contract, Obligation.contract_id == Contract.id)
    base_query = apply_tenant_filter(base_query, tenant_id, Contract)
    base_query = apply_bu_filter(base_query, bu_id, role)

    if contract_id:
        base_query = base_query.where(Obligation.contract_id == uuid_mod.UUID(contract_id))

    if owner_filter:
        try:
            owner_enum = ObligationOwner(owner_filter.lower())
            base_query = base_query.where(Obligation.owner_type == owner_enum)
        except ValueError:
            pass

    if category_filter:
        try:
            category_enum = ObligationCategory(category_filter.lower())
            base_query = base_query.where(Obligation.category == category_enum)
        except ValueError:
            pass

    result = await db.execute(base_query.order_by(Obligation.deadline.asc().nulls_last()))
    rows = result.all()

    # Process all obligations
    all_obligations: list[ComplianceObligationItem] = []
    overdue_obligations: list[ComplianceObligationItem] = []
    critical_upcoming: list[ComplianceObligationItem] = []

    rag_counts = {"green": 0, "amber": 0, "red": 0, "not_assessed": 0}
    status_counts: dict[str, int] = {}
    category_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "green": 0, "amber": 0, "red": 0, "not_assessed": 0})
    owner_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "green": 0, "amber": 0, "red": 0, "not_assessed": 0, "overdue": 0})
    frequency_counts: dict[str, int] = defaultdict(int)
    calendar_data: dict[date, list[ComplianceObligationItem]] = defaultdict(list)
    contracts_rag: dict[str, set[str]] = defaultdict(set)

    for obl, filename, counterparty in rows:
        days_until = None
        if obl.deadline:
            days_until = (obl.deadline - today).days

        item = ComplianceObligationItem(
            id=str(obl.id),
            contract_id=str(obl.contract_id),
            contract_filename=filename,
            counterparty=counterparty,
            description=obl.description[:150] + "..." if len(obl.description) > 150 else obl.description,
            owner=obl.owner_type.value if obl.owner_type else "unspecified",
            category=obl.category.value if obl.category else None,
            frequency=obl.frequency.value if obl.frequency else None,
            deadline=obl.deadline,
            days_until_deadline=days_until,
            status=obl.status.value if obl.status else "pending",
            rag_status=obl.rag_status.value if obl.rag_status else "not_assessed",
            is_critical=obl.is_critical or False,
            priority=obl.priority,
            last_compliance_date=obl.last_compliance_date,
            next_compliance_due=obl.next_compliance_due,
        )
        all_obligations.append(item)

        # RAG counts
        rag_key = obl.rag_status.value if obl.rag_status else "not_assessed"
        rag_counts[rag_key] = rag_counts.get(rag_key, 0) + 1

        # Status counts
        status_key = obl.status.value if obl.status else "pending"
        status_counts[status_key] = status_counts.get(status_key, 0) + 1

        # Category stats
        cat_key = obl.category.value if obl.category else "other"
        category_stats[cat_key]["total"] += 1
        category_stats[cat_key][rag_key] += 1

        # Owner stats
        owner_key = obl.owner_type.value if obl.owner_type else "unspecified"
        owner_stats[owner_key]["total"] += 1
        owner_stats[owner_key][rag_key] += 1
        if obl.status == ObligationStatus.OVERDUE:
            owner_stats[owner_key]["overdue"] += 1

        # Frequency counts
        freq_key = obl.frequency.value if obl.frequency else "unspecified"
        frequency_counts[freq_key] += 1

        # Calendar data (next 30 days)
        if obl.deadline and 0 <= days_until <= 30:
            calendar_data[obl.deadline].append(item)

        # Track RAG by contract
        contracts_rag[str(obl.contract_id)].add(rag_key)

        # Overdue obligations
        if obl.status == ObligationStatus.OVERDUE or (days_until is not None and days_until < 0):
            overdue_obligations.append(item)

        # Critical upcoming (within 7 days)
        if obl.is_critical and days_until is not None and 0 <= days_until <= 7:
            critical_upcoming.append(item)

    # Calculate RAG summary
    total_obligations = sum(rag_counts.values())
    compliance_rate = (rag_counts["green"] / total_obligations * 100) if total_obligations > 0 else 0.0

    rag_summary = RAGStatusSummary(
        green=rag_counts["green"],
        amber=rag_counts["amber"],
        red=rag_counts["red"],
        not_assessed=rag_counts["not_assessed"],
        total=total_obligations,
        compliance_rate=round(compliance_rate, 1),
    )

    # Build category breakdown
    by_category = []
    for cat, stats in sorted(category_stats.items()):
        cat_total = stats["total"]
        cat_compliance = (stats["green"] / cat_total * 100) if cat_total > 0 else 0.0
        by_category.append(ComplianceByCategory(
            category=cat,
            total=cat_total,
            green=stats["green"],
            amber=stats["amber"],
            red=stats["red"],
            not_assessed=stats["not_assessed"],
            compliance_rate=round(cat_compliance, 1),
        ))

    # Build owner breakdown
    by_owner = []
    for owner, stats in sorted(owner_stats.items()):
        by_owner.append(ComplianceByOwner(
            owner=owner,
            total=stats["total"],
            green=stats["green"],
            amber=stats["amber"],
            red=stats["red"],
            overdue=stats["overdue"],
        ))

    # Build calendar
    calendar = []
    for cal_date in sorted(calendar_data.keys()):
        calendar.append(ComplianceCalendarItem(
            date=cal_date,
            obligation_count=len(calendar_data[cal_date]),
            obligations=calendar_data[cal_date],
        ))

    # Contract exposure
    contracts_with_red = sum(1 for rags in contracts_rag.values() if "red" in rags)
    contracts_with_amber = sum(1 for rags in contracts_rag.values() if "amber" in rags and "red" not in rags)

    # Top risk contracts
    contract_risk_scores: dict[str, dict] = {}
    for obl, filename, counterparty in rows:
        cid = str(obl.contract_id)
        if cid not in contract_risk_scores:
            contract_risk_scores[cid] = {
                "contract_id": cid,
                "filename": filename,
                "counterparty": counterparty,
                "red": 0,
                "amber": 0,
                "overdue": 0,
            }
        rag = obl.rag_status.value if obl.rag_status else "not_assessed"
        if rag == "red":
            contract_risk_scores[cid]["red"] += 1
        elif rag == "amber":
            contract_risk_scores[cid]["amber"] += 1
        if obl.status == ObligationStatus.OVERDUE:
            contract_risk_scores[cid]["overdue"] += 1

    top_risk_contracts = sorted(
        contract_risk_scores.values(),
        key=lambda x: (x["red"], x["amber"], x["overdue"]),
        reverse=True,
    )[:10]

    return ObligationsComplianceResponse(
        rag_summary=rag_summary,
        status_summary=status_counts,
        overdue_obligations=overdue_obligations[:20],
        critical_upcoming=critical_upcoming[:10],
        by_category=by_category,
        by_owner=by_owner,
        by_frequency=dict(frequency_counts),
        calendar=calendar,
        contracts_with_red=contracts_with_red,
        contracts_with_amber=contracts_with_amber,
        top_risk_contracts=top_risk_contracts,
    )


# ============== Portfolio Dashboard ==============


async def get_portfolio_dashboard(
    db: AsyncSession, tenant_id, bu_id, role,
) -> PortfolioDashboardResponse:
    """Build portfolio dashboard with cross-contract analytics."""
    today = date.today()

    # Get all contracts with obligation counts
    contracts_query = (
        select(
            Contract,
            func.count(Obligation.id.distinct()).label("obl_count"),
            func.sum(func.cast(Obligation.rag_status == RAGStatus.RED, Integer)).label("red_count"),
        )
        .outerjoin(Obligation, Contract.id == Obligation.contract_id)
        .group_by(Contract.id)
        .order_by(Contract.created_at.desc())
    )
    contracts_query = apply_tenant_filter(contracts_query, tenant_id, Contract)
    contracts_query = apply_bu_filter(contracts_query, bu_id, role)
    contracts_result = await db.execute(contracts_query)

    contracts_data = []
    total_value = Decimal(0)
    value_by_currency: dict[str, Decimal] = defaultdict(Decimal)
    value_by_type: dict[str, Decimal] = defaultdict(Decimal)
    value_by_counterparty: dict[str, Decimal] = defaultdict(Decimal)
    contracts_by_status: dict[str, int] = defaultdict(int)
    contracts_by_type: dict[str, int] = defaultdict(int)
    risk_by_level: dict[str, int] = defaultdict(int)
    contracts_with_value = 0

    for row in contracts_result.all():
        contract = row[0]
        obl_count = row[1] or 0
        red_count = row[2] or 0

        days_until = None
        if contract.expiration_date:
            days_until = (contract.expiration_date - today).days

        contracts_data.append({
            "contract": contract,
            "obl_count": obl_count,
            "red_count": red_count,
            "days_until": days_until,
        })

        status_val = contract.status.value if contract.status else "unknown"
        contracts_by_status[status_val] += 1

        type_val = contract.contract_type.value if contract.contract_type else "unknown"
        contracts_by_type[type_val] += 1

        risk_val = contract.risk_level.value if contract.risk_level else "unassessed"
        risk_by_level[risk_val] += 1

        if contract.contract_value:
            val = contract.contract_value
            total_value += val
            contracts_with_value += 1
            currency = contract.currency or "USD"
            value_by_currency[currency] += val
            value_by_type[type_val] += val
            if contract.counterparty:
                value_by_counterparty[contract.counterparty] += val

    total_contracts = len(contracts_data)

    # Value metrics
    avg_value = float(total_value / contracts_with_value) if contracts_with_value > 0 else 0.0
    value_metrics = PortfolioValueMetrics(
        total_value=float(total_value),
        by_currency={k: float(v) for k, v in value_by_currency.items()},
        by_type={k: float(v) for k, v in value_by_type.items()},
        by_counterparty={k: float(v) for k, v in sorted(value_by_counterparty.items(), key=lambda x: x[1], reverse=True)[:10]},
        average_contract_value=avg_value,
        contracts_with_value=contracts_with_value,
    )

    # Risk metrics
    high_risk = risk_by_level.get("high", 0) + risk_by_level.get("critical", 0)
    expiring_30d = sum(1 for c in contracts_data if c["days_until"] is not None and 0 <= c["days_until"] <= 30)
    expiring_90d = sum(1 for c in contracts_data if c["days_until"] is not None and 0 <= c["days_until"] <= 90)
    auto_renewal_count = sum(1 for c in contracts_data if c["contract"].auto_renewal)

    # Clause indicators
    tenant_contract_ids = {c["contract"].id for c in contracts_data}
    indicators_query = select(ContractClauseIndicator)
    if tenant_id is not None:
        indicators_query = indicators_query.where(
            ContractClauseIndicator.contract_id.in_(tenant_contract_ids)
        )
    indicators_result = await db.execute(indicators_query)
    indicators_list = indicators_result.scalars().all()
    missing_key_count = sum(
        1 for ind in indicators_list
        if not ind.has_limitation_of_liability or not ind.has_indemnification
    )

    risk_metrics = PortfolioRiskMetrics(
        by_risk_level=dict(risk_by_level),
        high_risk_count=high_risk,
        critical_count=risk_by_level.get("critical", 0),
        contracts_expiring_30d=expiring_30d,
        contracts_expiring_90d=expiring_90d,
        auto_renewal_count=auto_renewal_count,
        missing_key_clauses=missing_key_count,
    )

    # Obligation metrics
    obl_query = (
        select(
            Obligation.owner_type,
            Obligation.status,
            Obligation.rag_status,
            func.count(Obligation.id),
        )
        .group_by(Obligation.owner_type, Obligation.status, Obligation.rag_status)
    )
    if tenant_id is not None:
        obl_query = obl_query.where(Obligation.contract_id.in_(tenant_contract_ids))
    obl_result = await db.execute(obl_query)

    obl_by_owner: dict[str, int] = defaultdict(int)
    obl_by_status: dict[str, int] = defaultdict(int)
    obl_by_rag: dict[str, int] = defaultdict(int)
    total_obls = 0

    for owner, status, rag, count in obl_result.all():
        owner_key = owner.value if owner else "unspecified"
        status_key = status.value if status else "pending"
        rag_key = rag.value if rag else "not_assessed"
        obl_by_owner[owner_key] += count
        obl_by_status[status_key] += count
        obl_by_rag[rag_key] += count
        total_obls += count

    overdue_count = obl_by_status.get("overdue", 0)
    green_count = obl_by_rag.get("green", 0)
    compliance_rate = (green_count / total_obls * 100) if total_obls > 0 else 0.0

    obligation_metrics = PortfolioObligationMetrics(
        total_obligations=total_obls,
        by_owner=dict(obl_by_owner),
        by_status=dict(obl_by_status),
        by_rag=dict(obl_by_rag),
        overdue_count=overdue_count,
        compliance_rate=round(compliance_rate, 1),
    )

    # Clause coverage metrics
    contracts_with_ind = len(indicators_list)
    total_coverage = 0.0
    missing_by_clause: dict[str, int] = defaultdict(int)

    critical_clauses = [
        ("limitation_of_liability", "has_limitation_of_liability"),
        ("indemnification", "has_indemnification"),
        ("confidentiality", "has_confidentiality"),
        ("termination_for_cause", "has_termination_for_cause"),
        ("governing_law", "has_governing_law"),
        ("force_majeure", "has_force_majeure"),
    ]

    for ind in indicators_list:
        summary = ind.to_summary_dict()
        total_coverage += summary.get("coverage_percentage", 0)
        for clause_name, attr_name in critical_clauses:
            if not getattr(ind, attr_name, None):
                missing_by_clause[clause_name] += 1

    avg_coverage = (total_coverage / contracts_with_ind) if contracts_with_ind > 0 else 0.0

    clause_metrics = PortfolioClauseMetrics(
        contracts_with_indicators=contracts_with_ind,
        average_clause_coverage=round(avg_coverage, 1),
        missing_critical_by_clause=dict(missing_by_clause),
    )

    # Counterparty exposure
    counterparty_data: dict[str, dict] = {}
    for cd in contracts_data:
        contract = cd["contract"]
        cp = contract.counterparty or "Unknown"

        if cp not in counterparty_data:
            counterparty_data[cp] = {
                "counterparty": cp,
                "contract_count": 0,
                "total_value": 0.0,
                "currency": contract.currency,
                "risk_scores": [],
                "expiring_soon": 0,
                "red_obligations": 0,
            }

        counterparty_data[cp]["contract_count"] += 1
        if contract.contract_value:
            counterparty_data[cp]["total_value"] += float(contract.contract_value)
        if contract.risk_score:
            counterparty_data[cp]["risk_scores"].append(contract.risk_score)
        if cd["days_until"] is not None and 0 <= cd["days_until"] <= 30:
            counterparty_data[cp]["expiring_soon"] += 1
        counterparty_data[cp]["red_obligations"] += cd["red_count"]

    top_counterparties = []
    for cp, data in sorted(counterparty_data.items(), key=lambda x: x[1]["total_value"], reverse=True)[:10]:
        avg_risk = sum(data["risk_scores"]) / len(data["risk_scores"]) if data["risk_scores"] else 0.0
        top_counterparties.append(CounterpartyExposure(
            counterparty=cp,
            contract_count=data["contract_count"],
            total_value=data["total_value"],
            currency=data["currency"],
            risk_score=round(avg_risk, 1),
            expiring_soon=data["expiring_soon"],
            red_obligations=data["red_obligations"],
        ))

    # Expiring contracts
    expiring_contracts = []
    for cd in sorted(contracts_data, key=lambda x: x["days_until"] if x["days_until"] is not None else 9999):
        if cd["days_until"] is not None and 0 <= cd["days_until"] <= 90:
            contract = cd["contract"]
            expiring_contracts.append(PortfolioContractSummary(
                contract_id=str(contract.id),
                filename=contract.filename,
                contract_type=contract.contract_type.value if contract.contract_type else None,
                counterparty=contract.counterparty,
                status=contract.status.value,
                risk_level=contract.risk_level.value if contract.risk_level else None,
                contract_value=float(contract.contract_value) if contract.contract_value else None,
                currency=contract.currency,
                effective_date=contract.effective_date,
                expiration_date=contract.expiration_date,
                days_until_expiration=cd["days_until"],
                obligation_count=cd["obl_count"],
                red_obligations=cd["red_count"],
                has_auto_renewal=contract.auto_renewal or False,
            ))
            if len(expiring_contracts) >= 10:
                break

    # Recently added
    recently_added = []
    for cd in contracts_data[:10]:
        contract = cd["contract"]
        recently_added.append(PortfolioContractSummary(
            contract_id=str(contract.id),
            filename=contract.filename,
            contract_type=contract.contract_type.value if contract.contract_type else None,
            counterparty=contract.counterparty,
            status=contract.status.value,
            risk_level=contract.risk_level.value if contract.risk_level else None,
            contract_value=float(contract.contract_value) if contract.contract_value else None,
            currency=contract.currency,
            effective_date=contract.effective_date,
            expiration_date=contract.expiration_date,
            days_until_expiration=cd["days_until"],
            obligation_count=cd["obl_count"],
            red_obligations=cd["red_count"],
            has_auto_renewal=contract.auto_renewal or False,
        ))

    # Generate alerts
    alerts = []
    if expiring_30d > 0:
        alerts.append({"type": "expiration", "severity": "high", "message": f"{expiring_30d} contract(s) expiring within 30 days", "count": expiring_30d})
    if overdue_count > 0:
        alerts.append({"type": "obligation", "severity": "critical", "message": f"{overdue_count} overdue obligation(s) require attention", "count": overdue_count})
    if high_risk > 0:
        alerts.append({"type": "risk", "severity": "high", "message": f"{high_risk} high-risk contract(s) in portfolio", "count": high_risk})
    if missing_key_count > 0:
        alerts.append({"type": "clause", "severity": "medium", "message": f"{missing_key_count} contract(s) missing critical clauses", "count": missing_key_count})

    return PortfolioDashboardResponse(
        total_contracts=total_contracts,
        contracts_by_status=dict(contracts_by_status),
        contracts_by_type=dict(contracts_by_type),
        value_metrics=value_metrics,
        risk_metrics=risk_metrics,
        obligation_metrics=obligation_metrics,
        clause_metrics=clause_metrics,
        top_counterparties=top_counterparties,
        expiring_contracts=expiring_contracts,
        recently_added=recently_added,
        alerts=alerts,
    )


# ============== Contract Cockpit ==============


async def get_contract_cockpit(
    db: AsyncSession, contract_id: str,
) -> ContractCockpitResponse:
    """Build comprehensive contract cockpit dashboard."""
    import uuid as uuid_mod

    today = date.today()

    result = await db.execute(
        select(Contract).where(Contract.id == uuid_mod.UUID(contract_id))
    )
    contract = result.scalar_one_or_none()

    if not contract:
        return None  # Router handles 404

    # Days until expiration
    days_until_expiration = None
    notice_deadline = None
    if contract.expiration_date:
        days_until_expiration = (contract.expiration_date - today).days
        if contract.notice_period_days:
            notice_deadline = contract.expiration_date - timedelta(days=contract.notice_period_days)

    # Parties
    parties_result = await db.execute(
        select(ContractParty)
        .where(ContractParty.contract_id == contract.id)
        .order_by(ContractParty.is_primary.desc())
    )
    parties = [
        CockpitParty(
            legal_name=p.legal_name,
            role=p.role.value if p.role else "other",
            short_name=p.short_name,
            entity_type=p.entity_type,
            jurisdiction=p.jurisdiction,
            is_primary=p.is_primary or False,
        )
        for p in parties_result.scalars().all()
    ]

    # Key dates
    dates_result = await db.execute(
        select(ContractKeyDate)
        .where(ContractKeyDate.contract_id == contract.id)
        .order_by(ContractKeyDate.event_date.asc())
    )
    key_dates = []
    for kd in dates_result.scalars().all():
        days_until = (kd.event_date - today).days if kd.event_date else 0
        urgency = "FUTURE"
        if days_until < 0:
            urgency = "OVERDUE"
        elif days_until <= 7:
            urgency = "IMMEDIATE"
        elif days_until <= 30:
            urgency = "SOON"
        elif days_until <= 90:
            urgency = "UPCOMING"

        key_dates.append(CockpitKeyDate(
            event_name=kd.event_name,
            event_type=kd.event_type.value if kd.event_type else "custom",
            event_date=kd.event_date,
            days_until=days_until,
            action_required=kd.action_required,
            alert_days_before=kd.alert_days_before,
            urgency=urgency,
        ))

    # Financials
    fin_result = await db.execute(
        select(ContractFinancial).where(ContractFinancial.contract_id == contract.id)
    )
    financials = []
    penalties = []
    for f in fin_result.scalars().all():
        item = CockpitFinancial(
            fee_type=f.fee_type.value if f.fee_type else "other",
            description=f.fee_description,
            amount=float(f.fee_amount) if f.fee_amount else (float(f.penalty_amount) if f.penalty_amount else None),
            currency=f.currency,
            frequency=f.invoicing_frequency,
            payment_terms=f.payment_terms.value if f.payment_terms else None,
            is_penalty=f.is_penalty or False,
        )
        if f.is_penalty:
            penalties.append(item)
        else:
            financials.append(item)

    total_value = float(contract.contract_value) if contract.contract_value else None

    # Liabilities
    liab_result = await db.execute(
        select(ContractLiability).where(ContractLiability.contract_id == contract.id)
    )
    liabilities = []
    primary_liability_cap = None
    for li in liab_result.scalars().all():
        item = CockpitLiability(
            cap_type=li.liability_cap_type.value if li.liability_cap_type else None,
            cap_amount=float(li.liability_cap_amount) if li.liability_cap_amount else None,
            cap_currency=li.liability_cap_currency,
            description=li.liability_cap_description,
            is_mutual=li.mutual_indemnification or False,
            indemnifying_party=li.indemnifying_party,
            insurance_required=li.insurance_required or False,
        )
        liabilities.append(item)
        if not primary_liability_cap and li.liability_cap_type and not li.indemnifying_party:
            primary_liability_cap = item

    # Obligations
    obl_result = await db.execute(
        select(Obligation)
        .where(Obligation.contract_id == contract.id)
        .order_by(Obligation.deadline.asc().nulls_last())
    )

    provider_obligations = []
    client_obligations = []
    mutual_obligations = []
    obl_stats: dict[str, int] = {"pending": 0, "in_progress": 0, "completed": 0, "overdue": 0}
    rag_stats: dict[str, int] = {"green": 0, "amber": 0, "red": 0, "not_assessed": 0}

    for obl in obl_result.scalars().all():
        item = CockpitObligation(
            id=str(obl.id),
            description=obl.description[:200] + "..." if len(obl.description) > 200 else obl.description,
            owner=obl.owner_type.value if obl.owner_type else "unspecified",
            category=obl.category.value if obl.category else None,
            frequency=obl.frequency.value if obl.frequency else None,
            deadline=obl.deadline,
            status=obl.status.value if obl.status else "pending",
            rag_status=obl.rag_status.value if obl.rag_status else "not_assessed",
            is_critical=obl.is_critical or False,
            priority=obl.priority,
        )

        if obl.owner_type == ObligationOwner.PROVIDER:
            provider_obligations.append(item)
        elif obl.owner_type == ObligationOwner.CLIENT:
            client_obligations.append(item)
        elif obl.owner_type == ObligationOwner.MUTUAL:
            mutual_obligations.append(item)
        else:
            provider_obligations.append(item)

        stat_key = obl.status.value if obl.status else "pending"
        obl_stats[stat_key] = obl_stats.get(stat_key, 0) + 1
        rag_key = obl.rag_status.value if obl.rag_status else "not_assessed"
        rag_stats[rag_key] = rag_stats.get(rag_key, 0) + 1

    obligation_stats = {**obl_stats, **{f"rag_{k}": v for k, v in rag_stats.items()}}

    # Clause indicators
    ind_result = await db.execute(
        select(ContractClauseIndicator).where(ContractClauseIndicator.contract_id == contract.id)
    )
    indicators = ind_result.scalar_one_or_none()

    clause_indicators = None
    if indicators:
        clause_indicators = CockpitClauseIndicators(
            confidentiality_ip={
                "confidentiality": indicators.has_confidentiality,
                "mutual_confidentiality": indicators.has_mutual_confidentiality,
                "ip_ownership": indicators.has_ip_ownership,
                "ip_license": indicators.has_ip_license,
                "work_for_hire": indicators.has_work_for_hire,
            },
            liability_indemnity={
                "limitation_of_liability": indicators.has_limitation_of_liability,
                "liability_cap": indicators.has_liability_cap,
                "indemnification": indicators.has_indemnification,
                "mutual_indemnification": indicators.has_mutual_indemnification,
                "warranty_disclaimer": indicators.has_warranty_disclaimer,
            },
            termination_renewal={
                "termination_for_cause": indicators.has_termination_for_cause,
                "termination_for_convenience": indicators.has_termination_for_convenience,
                "termination_notice_period": indicators.has_termination_notice_period,
                "auto_renewal": indicators.has_auto_renewal,
                "renewal_notice_requirement": indicators.has_renewal_notice_requirement,
                "survival_clause": indicators.has_survival_clause,
            },
            compliance_regulatory={
                "force_majeure": indicators.has_force_majeure,
                "governing_law": indicators.has_governing_law,
                "dispute_resolution": indicators.has_dispute_resolution,
                "arbitration": indicators.has_arbitration,
                "data_protection": indicators.has_data_protection,
                "gdpr_compliance": indicators.has_gdpr_compliance,
                "anticorruption": indicators.has_anticorruption,
                "export_control": indicators.has_export_control,
            },
            business_restrictions={
                "non_compete": indicators.has_non_compete,
                "non_solicit": indicators.has_non_solicit,
                "exclusivity": indicators.has_exclusivity,
                "most_favored_nation": indicators.has_most_favored_nation,
            },
            operational={
                "insurance_requirement": indicators.has_insurance_requirement,
                "audit_rights": indicators.has_audit_rights,
                "service_levels": indicators.has_service_levels,
                "change_control": indicators.has_change_control,
                "assignment_restriction": indicators.has_assignment_restriction,
                "subcontracting_restriction": indicators.has_subcontracting_restriction,
            },
            payment={
                "payment_terms": indicators.has_payment_terms,
                "late_payment_interest": indicators.has_late_payment_interest,
                "price_escalation": indicators.has_price_escalation,
            },
            coverage_stats=indicators.to_summary_dict() if indicators else {},
        )

    # Linked contracts
    parent_links_result = await db.execute(
        select(ContractLink, Contract.filename)
        .join(Contract, ContractLink.parent_contract_id == Contract.id)
        .where(ContractLink.child_contract_id == contract.id)
    )
    parent_contracts = [
        CockpitLinkedContract(
            contract_id=str(link.parent_contract_id),
            filename=filename,
            link_type=link.link_type.value if link.link_type else "related",
            direction="parent",
            effective_date=link.effective_date,
            reference_number=link.reference_number,
            is_active=link.is_active,
        )
        for link, filename in parent_links_result.all()
    ]

    child_links_result = await db.execute(
        select(ContractLink, Contract.filename)
        .join(Contract, ContractLink.child_contract_id == Contract.id)
        .where(ContractLink.parent_contract_id == contract.id)
    )
    child_contracts = [
        CockpitLinkedContract(
            contract_id=str(link.child_contract_id),
            filename=filename,
            link_type=link.link_type.value if link.link_type else "related",
            direction="child",
            effective_date=link.effective_date,
            reference_number=link.reference_number,
            is_active=link.is_active,
        )
        for link, filename in child_links_result.all()
    ]

    # High-risk clauses count
    high_risk_count = await db.scalar(
        select(func.count(Clause.id))
        .where(Clause.contract_id == contract.id)
        .where(Clause.risk_level == RiskLevel.HIGH)
    ) or 0

    # Risk summary
    overdue_count = obl_stats.get("overdue", 0)
    expiring_soon = days_until_expiration is not None and 0 <= days_until_expiration <= 30

    missing_critical = []
    if indicators:
        if not indicators.has_limitation_of_liability:
            missing_critical.append("Limitation of Liability")
        if not indicators.has_indemnification:
            missing_critical.append("Indemnification")
        if not indicators.has_confidentiality:
            missing_critical.append("Confidentiality")
        if not indicators.has_governing_law:
            missing_critical.append("Governing Law")

    risk_factors = []
    if high_risk_count > 0:
        risk_factors.append(f"{high_risk_count} high-risk clauses identified")
    if overdue_count > 0:
        risk_factors.append(f"{overdue_count} overdue obligations")
    if expiring_soon:
        risk_factors.append("Contract expiring within 30 days")
    if contract.auto_renewal and notice_deadline:
        days_to_notice = (notice_deadline - today).days
        if days_to_notice <= 14:
            risk_factors.append(f"Auto-renewal notice deadline in {days_to_notice} days")
    if missing_critical:
        risk_factors.append(f"Missing clauses: {', '.join(missing_critical[:3])}")

    risk_summary = CockpitRiskSummary(
        overall_risk_level=contract.risk_level.value if contract.risk_level else None,
        risk_score=contract.risk_score,
        high_risk_clause_count=high_risk_count,
        overdue_obligations=overdue_count,
        expiring_soon=expiring_soon,
        missing_critical_clauses=missing_critical,
        risk_factors=risk_factors,
    )

    return ContractCockpitResponse(
        contract_id=contract_id,
        filename=contract.filename,
        contract_type=contract.contract_type.value if contract.contract_type else None,
        status=contract.status.value,
        counterparty=contract.counterparty,
        effective_date=contract.effective_date,
        expiration_date=contract.expiration_date,
        days_until_expiration=days_until_expiration,
        contract_value=total_value,
        currency=contract.currency,
        governing_law=contract.governing_law,
        jurisdiction=contract.jurisdiction,
        auto_renewal=contract.auto_renewal,
        notice_period_days=contract.notice_period_days,
        notice_deadline=notice_deadline,
        parties=parties,
        key_dates=key_dates,
        total_contract_value=total_value,
        financials=financials,
        penalties=penalties,
        liabilities=liabilities,
        primary_liability_cap=primary_liability_cap,
        provider_obligations=provider_obligations,
        client_obligations=client_obligations,
        mutual_obligations=mutual_obligations,
        obligation_stats=obligation_stats,
        clause_indicators=clause_indicators,
        parent_contracts=parent_contracts,
        child_contracts=child_contracts,
        risk_summary=risk_summary,
        has_schema_data=bool(contract.schema_data),
        schema_id=contract.schema_id,
    )


# ============== Insights ==============


async def get_insights(
    db: AsyncSession, tenant_id,
) -> InsightsResponse:
    """Build AI-generated insights for dashboard."""
    from app.models.sla import ContractSLA

    today = date.today()
    insights: list[InsightItem] = []

    # 1. Renewal Opportunity
    expiring_query = select(
        func.count(Contract.id),
        func.coalesce(func.sum(Contract.contract_value), 0)
    ).where(
        Contract.expiration_date.isnot(None),
        Contract.expiration_date <= today + timedelta(days=30),
        Contract.expiration_date > today,
    )
    if tenant_id:
        expiring_query = expiring_query.where(Contract.tenant_id == tenant_id)

    expiring_result = await db.execute(expiring_query)
    expiring_row = expiring_result.one()
    expiring_count = expiring_row[0] or 0
    expiring_value = float(expiring_row[1]) if expiring_row[1] else 0

    if expiring_count > 0:
        value_str = f"${expiring_value/1000000:.1f}M" if expiring_value >= 1000000 else f"${expiring_value/1000:.0f}K" if expiring_value >= 1000 else f"${expiring_value:.0f}"
        insights.append(InsightItem(
            title="Renewal Opportunity",
            description=f"{expiring_count} contract{'s' if expiring_count > 1 else ''} expiring in 30 days worth {value_str}. Consider early renewal negotiations.",
            action="/renewals?window=30",
            action_label="View renewals",
            variant="info"
        ))

    # 2. Compliance Alert
    sla_query = select(func.count(ContractSLA.id)).where(
        ContractSLA.consecutive_breaches > 0
    ).join(Contract, ContractSLA.contract_id == Contract.id)
    if tenant_id:
        sla_query = sla_query.where(Contract.tenant_id == tenant_id)

    breached_sla_count = await db.scalar(sla_query) or 0

    if breached_sla_count > 0:
        insights.append(InsightItem(
            title="Compliance Alert",
            description=f"{breached_sla_count} SLA{'s' if breached_sla_count > 1 else ''} currently breaching target{'s' if breached_sla_count > 1 else ''}. Review and escalate.",
            action="/compliance",
            action_label="Review compliance",
            variant="warning"
        ))

    # 3. Overdue Obligations
    overdue_query = select(func.count(Obligation.id)).where(
        Obligation.deadline < today,
        Obligation.status.notin_([ObligationStatus.COMPLETED, ObligationStatus.WAIVED])
    )
    if tenant_id:
        overdue_query = overdue_query.join(Contract).where(Contract.tenant_id == tenant_id)

    overdue_count = await db.scalar(overdue_query) or 0

    if overdue_count > 0:
        insights.append(InsightItem(
            title="Overdue Obligations",
            description=f"{overdue_count} obligation{'s' if overdue_count > 1 else ''} past due date. Immediate action required.",
            action="/obligations?status=overdue",
            action_label="View overdue",
            variant="warning"
        ))

    # 4. High Risk Contracts
    high_risk_query = select(func.count(Contract.id)).where(
        Contract.risk_level.in_(["high", "critical"])
    )
    if tenant_id:
        high_risk_query = high_risk_query.where(Contract.tenant_id == tenant_id)

    high_risk_count = await db.scalar(high_risk_query) or 0

    if high_risk_count > 0:
        insights.append(InsightItem(
            title="Risk Assessment",
            description=f"{high_risk_count} high-risk contract{'s' if high_risk_count > 1 else ''} identified. Review risk mitigation strategies.",
            action="/contracts?risk=high",
            action_label="View risks",
            variant="warning"
        ))

    if not insights:
        insights.append(InsightItem(
            title="All Clear",
            description="No critical issues detected. All contracts and obligations are on track.",
            action="/contracts",
            action_label="View contracts",
            variant="success"
        ))

    return InsightsResponse(insights=insights)


# ============== Activity ==============


async def get_activity(
    db: AsyncSession, tenant_id, limit: int = 10,
) -> ActivityResponse:
    """Build recent activity feed for dashboard."""
    from app.models.sla import ContractSLA, SLAPerformance

    now = datetime.now(timezone.utc)

    def time_ago(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = now - dt
        seconds = diff.total_seconds()
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m ago"
        elif seconds < 86400:
            return f"{int(seconds / 3600)}h ago"
        else:
            return f"{int(seconds / 86400)}d ago"

    timed_activities: list[tuple[datetime, ActivityItem]] = []

    # Audit logs
    audit_query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit * 2)
    if tenant_id:
        audit_query = audit_query.join(User, AuditLog.user_id == User.id).where(User.tenant_id == tenant_id)

    audit_result = await db.execute(audit_query)
    for log in audit_result.scalars().all():
        details = log.details or {}
        ts = log.created_at.replace(tzinfo=timezone.utc) if log.created_at.tzinfo is None else log.created_at

        if log.action == AuditAction.CONTRACT_UPLOAD:
            timed_activities.append((ts, ActivityItem(
                icon="document", title="Contract uploaded",
                subtitle=details.get("filename", "Unknown file"),
                time=time_ago(log.created_at), color="blue"
            )))
        elif log.action == AuditAction.CONTRACT_VIEW:
            if details.get("action") == "deep_analysis_queued":
                timed_activities.append((ts, ActivityItem(
                    icon="sparkles", title="Analysis started",
                    subtitle=details.get("filename", "Contract analysis"),
                    time=time_ago(log.created_at), color="blue"
                )))
        elif log.action == AuditAction.CONTRACT_UPDATE:
            timed_activities.append((ts, ActivityItem(
                icon="pencil", title="Contract updated",
                subtitle=details.get("filename", "Contract modified"),
                time=time_ago(log.created_at), color="gray"
            )))

    # Obligation completions
    completed_query = select(Obligation).where(
        Obligation.status == ObligationStatus.COMPLETED
    ).order_by(Obligation.updated_at.desc()).limit(limit)
    if tenant_id:
        completed_query = completed_query.join(Contract).where(Contract.tenant_id == tenant_id)

    completed_result = await db.execute(completed_query)
    for obl in completed_result.scalars().all():
        ts = obl.updated_at or obl.created_at
        if ts:
            ts = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
        else:
            ts = datetime.min.replace(tzinfo=timezone.utc)
        timed_activities.append((ts, ActivityItem(
            icon="check", title="Obligation completed",
            subtitle=obl.description[:50] + "..." if len(obl.description) > 50 else obl.description,
            time=time_ago(ts), color="green"
        )))

    # SLA breaches
    breach_query = (
        select(SLAPerformance)
        .join(ContractSLA, SLAPerformance.sla_id == ContractSLA.id)
        .where(SLAPerformance.is_compliant == False)
        .order_by(SLAPerformance.measured_at.desc())
        .limit(3)
    )
    if tenant_id:
        breach_query = breach_query.join(Contract, ContractSLA.contract_id == Contract.id).where(Contract.tenant_id == tenant_id)

    breach_result = await db.execute(breach_query)
    for perf in breach_result.scalars().all():
        ts = perf.measured_at
        if ts:
            ts = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
        else:
            ts = datetime.min.replace(tzinfo=timezone.utc)
        timed_activities.append((ts, ActivityItem(
            icon="warning", title="SLA breach detected",
            subtitle=f"Target missed — actual {perf.actual_value}",
            time=time_ago(ts), color="red"
        )))

    # Recently processed contracts
    recent_contracts_query = select(Contract).where(
        Contract.status == ContractStatus.COMPLETED
    ).order_by(Contract.updated_at.desc()).limit(5)
    if tenant_id:
        recent_contracts_query = recent_contracts_query.where(Contract.tenant_id == tenant_id)

    recent_result = await db.execute(recent_contracts_query)
    for c in recent_result.scalars().all():
        ts = c.updated_at or c.created_at
        if ts:
            ts = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts
        else:
            ts = datetime.min.replace(tzinfo=timezone.utc)
        timed_activities.append((ts, ActivityItem(
            icon="document", title="Contract analyzed",
            subtitle=c.filename[:50] if c.filename else "Unknown",
            time=time_ago(ts), color="blue"
        )))

    timed_activities.sort(key=lambda x: x[0], reverse=True)
    activities = [item for _, item in timed_activities[:limit]]

    return ActivityResponse(activities=activities)


# ============== Cache-Through Wrappers ==============


async def get_admin_dashboard_cached(
    db: AsyncSession, tenant_id, bu_id, role,
) -> AdminDashboardResponse:
    """Admin dashboard with cache-through."""
    cache_key = _cache_key_for_bu(bu_id, role)
    cached = await get_cached_dashboard(db, tenant_id, "admin", cache_key)
    if cached:
        return AdminDashboardResponse(**cached)

    result = await get_admin_dashboard(db, tenant_id, bu_id, role)
    await set_cached_dashboard(db, tenant_id, "admin", result.model_dump(mode="json"), cache_key)
    return result


async def get_legal_dashboard_cached(
    db: AsyncSession, tenant_id, bu_id, role, current_user_id,
) -> LegalDashboardResponse:
    """Legal dashboard with cache-through."""
    cache_key = _cache_key_for_bu(bu_id, role)
    cached = await get_cached_dashboard(db, tenant_id, "legal", cache_key)
    if cached:
        return LegalDashboardResponse(**cached)

    result = await get_legal_dashboard(db, tenant_id, bu_id, role, current_user_id)
    await set_cached_dashboard(db, tenant_id, "legal", result.model_dump(mode="json"), cache_key)
    return result


async def get_procurement_dashboard_cached(
    db: AsyncSession, tenant_id, bu_id, role,
) -> ProcurementDashboardResponse:
    """Procurement dashboard with cache-through."""
    cache_key = _cache_key_for_bu(bu_id, role)
    cached = await get_cached_dashboard(db, tenant_id, "procurement", cache_key)
    if cached:
        return ProcurementDashboardResponse(**cached)

    result = await get_procurement_dashboard(db, tenant_id, bu_id, role)
    await set_cached_dashboard(db, tenant_id, "procurement", result.model_dump(mode="json"), cache_key)
    return result


async def get_portfolio_dashboard_cached(
    db: AsyncSession, tenant_id, bu_id, role,
) -> PortfolioDashboardResponse:
    """Portfolio dashboard with cache-through."""
    cache_key = _cache_key_for_bu(bu_id, role)
    cached = await get_cached_dashboard(db, tenant_id, "portfolio", cache_key)
    if cached:
        return PortfolioDashboardResponse(**cached)

    result = await get_portfolio_dashboard(db, tenant_id, bu_id, role)
    await set_cached_dashboard(db, tenant_id, "portfolio", result.model_dump(mode="json"), cache_key)
    return result


async def get_obligations_compliance_cached(
    db: AsyncSession, tenant_id, bu_id, role,
    contract_id=None, owner_filter=None, category_filter=None,
) -> ObligationsComplianceResponse:
    """Obligations compliance with cache-through."""
    cache_key = f"{_cache_key_for_bu(bu_id, role)}|cid={contract_id}|own={owner_filter}|cat={category_filter}"
    cached = await get_cached_dashboard(db, tenant_id, "obligations", cache_key)
    if cached:
        return ObligationsComplianceResponse(**cached)

    result = await get_obligations_compliance(
        db, tenant_id, bu_id, role, contract_id, owner_filter, category_filter,
    )
    await set_cached_dashboard(db, tenant_id, "obligations", result.model_dump(mode="json"), cache_key)
    return result
