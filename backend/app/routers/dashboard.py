"""Dashboard router for role-specific dashboard data."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select, Integer, cast, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, CurrentTenantId, require_role
from app.database import get_db
from app.models.audit import AuditLog, AuditAction
from app.models.clause import Clause, ClauseType, RiskLevel
from app.models.contract import Contract, ContractStatus, ContractType
from app.models.obligation import Obligation, ObligationStatus, ObligationOwner, ObligationCategory, RAGStatus
from app.models.financial import ContractFinancial, ContractLiability, FeeType, LiabilityCapType
from app.models.clause_indicator import ContractClauseIndicator
from app.models.party import ContractParty
from app.models.key_date import ContractKeyDate, DateEventType
from app.models.contract_link import ContractLink, LinkType
from app.models.definition import ContractDefinition
from app.models.exhibit import ContractExhibit, ExhibitFeeItem, ExhibitType
from app.models.user import Role, User

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


def apply_tenant_filter(query, tenant_id):
    """Apply tenant filter to a Contract query if tenant_id is set."""
    if tenant_id is not None:
        return query.where(Contract.tenant_id == tenant_id)
    return query


# ============== Contract Summary for Dashboard ==============


class ContractSummaryCard(BaseModel):
    """Summary card for a single contract."""

    id: str
    filename: str
    contract_type: str | None
    counterparty: str | None
    status: str
    risk_level: str | None
    risk_score: int | None
    clause_count: int
    obligation_count: int
    expiration_date: date | None
    days_until_expiration: int | None


class ContractsSummaryResponse(BaseModel):
    """Summary of all contracts for dashboard."""

    contracts: list[ContractSummaryCard]
    total_contracts: int
    by_status: dict[str, int]
    by_risk: dict[str, int]
    expiring_soon: int  # contracts expiring in 30 days


@router.get("/contracts-summary", response_model=ContractsSummaryResponse)
async def get_contracts_summary(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    client_id: str | None = None,
) -> ContractsSummaryResponse:
    """Get summary of all contracts for dashboard cards."""
    import uuid as uuid_lib
    today = date.today()

    # Build query
    query = (
        select(
            Contract,
            func.count(Clause.id.distinct()).label("clause_count"),
            func.count(Obligation.id.distinct()).label("obligation_count"),
        )
        .outerjoin(Clause, Contract.id == Clause.contract_id)
        .outerjoin(Obligation, Contract.id == Obligation.contract_id)
    )

    # Apply tenant filter
    query = apply_tenant_filter(query, tenant_id)

    # Filter by client if specified
    if client_id:
        query = query.where(Contract.client_id == uuid_lib.UUID(client_id))

    query = query.group_by(Contract.id).order_by(Contract.created_at.desc())

    # Get contracts with clause and obligation counts
    result = await db.execute(query)

    cards = []
    by_status: dict[str, int] = {}
    by_risk: dict[str, int] = {}
    expiring_soon = 0

    for row in result.all():
        c = row[0]
        clause_count = row[1] or 0
        obligation_count = row[2] or 0

        # Count by status
        status_val = c.status.value if c.status else "unknown"
        by_status[status_val] = by_status.get(status_val, 0) + 1

        # Count by risk
        risk_val = c.risk_level.value if c.risk_level else "unassessed"
        by_risk[risk_val] = by_risk.get(risk_val, 0) + 1

        # Days until expiration
        days_until = None
        if c.expiration_date:
            days_until = (c.expiration_date - today).days
            if 0 <= days_until <= 30:
                expiring_soon += 1

        cards.append(ContractSummaryCard(
            id=str(c.id),
            filename=c.filename,
            contract_type=c.contract_type.value if c.contract_type else None,
            counterparty=c.counterparty,
            status=status_val,
            risk_level=c.risk_level.value if c.risk_level else None,
            risk_score=c.risk_score,
            clause_count=clause_count,
            obligation_count=obligation_count,
            expiration_date=c.expiration_date,
            days_until_expiration=days_until,
        ))

    return ContractsSummaryResponse(
        contracts=cards,
        total_contracts=len(cards),
        by_status=by_status,
        by_risk=by_risk,
        expiring_soon=expiring_soon,
    )


# ============== Admin Dashboard ==============


class ContractStats(BaseModel):
    """Contract statistics by category."""

    by_type: dict[str, int]
    by_status: dict[str, int]
    total: int


class UserStats(BaseModel):
    """User statistics."""

    by_role: dict[str, int]
    active: int
    inactive: int
    total: int


class ActivityMetrics(BaseModel):
    """Activity metrics over time."""

    queries_7d: int
    queries_30d: int
    uploads_7d: int
    uploads_30d: int


class IngestionStatus(BaseModel):
    """Document ingestion queue status."""

    pending: int
    processing: int
    completed: int
    failed: int


class AdminDashboardResponse(BaseModel):
    """Admin dashboard data."""

    contract_stats: ContractStats
    user_stats: UserStats
    activity: ActivityMetrics
    ingestion: IngestionStatus
    recent_failures: list[dict[str, Any]]


@router.get("/admin", response_model=AdminDashboardResponse)
async def get_admin_dashboard(
    current_user: Annotated[User, Depends(require_role(Role.ADMIN))],
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminDashboardResponse:
    """Get admin dashboard data.

    Includes contract stats, user stats, activity metrics, and ingestion status.
    Admin only.
    """
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Contract stats by type
    type_query = select(Contract.contract_type, func.count(Contract.id)).group_by(Contract.contract_type)
    type_query = apply_tenant_filter(type_query, tenant_id)
    type_result = await db.execute(type_query)
    by_type = {(t.value if t else "unknown"): c for t, c in type_result.all()}

    # Contract stats by status
    status_query = select(Contract.status, func.count(Contract.id)).group_by(Contract.status)
    status_query = apply_tenant_filter(status_query, tenant_id)
    status_result = await db.execute(status_query)
    by_status = {s.value: c for s, c in status_result.all()}

    # Total contracts
    total_contracts = sum(by_status.values())

    # User stats
    user_result = await db.execute(
        select(User.role, User.is_active, func.count(User.id))
        .group_by(User.role, User.is_active)
    )
    by_role: dict[str, int] = {}
    active_users = 0
    inactive_users = 0
    for role, is_active, count in user_result.all():
        by_role[role.value] = by_role.get(role.value, 0) + count
        if is_active:
            active_users += count
        else:
            inactive_users += count

    # Activity metrics
    queries_7d = await db.scalar(
        select(func.count(AuditLog.id))
        .where(AuditLog.action == AuditAction.QUERY_EXECUTE)
        .where(func.date(AuditLog.created_at) >= week_ago)
    ) or 0

    queries_30d = await db.scalar(
        select(func.count(AuditLog.id))
        .where(AuditLog.action == AuditAction.QUERY_EXECUTE)
        .where(func.date(AuditLog.created_at) >= month_ago)
    ) or 0

    uploads_7d = await db.scalar(
        select(func.count(AuditLog.id))
        .where(AuditLog.action == AuditAction.CONTRACT_UPLOAD)
        .where(func.date(AuditLog.created_at) >= week_ago)
    ) or 0

    uploads_30d = await db.scalar(
        select(func.count(AuditLog.id))
        .where(AuditLog.action == AuditAction.CONTRACT_UPLOAD)
        .where(func.date(AuditLog.created_at) >= month_ago)
    ) or 0

    # Ingestion status
    ingestion = IngestionStatus(
        pending=by_status.get("pending", 0),
        processing=by_status.get("processing", 0),
        completed=by_status.get("completed", 0),
        failed=by_status.get("failed", 0),
    )

    # Recent failures
    failures_result = await db.execute(
        select(Contract.id, Contract.filename, Contract.processing_error, Contract.updated_at)
        .where(Contract.status == ContractStatus.FAILED)
        .order_by(Contract.updated_at.desc())
        .limit(5)
    )
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
        contract_stats=ContractStats(
            by_type=by_type,
            by_status=by_status,
            total=total_contracts,
        ),
        user_stats=UserStats(
            by_role=by_role,
            active=active_users,
            inactive=inactive_users,
            total=active_users + inactive_users,
        ),
        activity=ActivityMetrics(
            queries_7d=queries_7d,
            queries_30d=queries_30d,
            uploads_7d=uploads_7d,
            uploads_30d=uploads_30d,
        ),
        ingestion=ingestion,
        recent_failures=recent_failures,
    )


# ============== Legal Dashboard ==============


class RiskOverview(BaseModel):
    """Risk distribution overview."""

    by_level: dict[str, int]
    high_risk_contracts: list[dict[str, Any]]


class ExpirationItem(BaseModel):
    """Contract expiration item."""

    contract_id: str
    filename: str
    counterparty: str | None
    expiration_date: date
    days_remaining: int


class ExpirationTimeline(BaseModel):
    """Expiration timeline."""

    next_30_days: list[ExpirationItem]
    next_60_days: list[ExpirationItem]
    next_90_days: list[ExpirationItem]


class HighRiskClause(BaseModel):
    """High risk clause item."""

    clause_id: str
    contract_id: str
    contract_filename: str
    clause_type: str
    risk_level: str
    excerpt: str


class LegalDashboardResponse(BaseModel):
    """Legal dashboard data."""

    risk_overview: RiskOverview
    expiration_timeline: ExpirationTimeline
    high_risk_clauses: list[HighRiskClause]
    recent_activity: list[dict[str, Any]]


@router.get("/legal", response_model=LegalDashboardResponse)
async def get_legal_dashboard(
    current_user: Annotated[User, Depends(require_role(Role.ADMIN, Role.LEGAL))],
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LegalDashboardResponse:
    """Get legal dashboard data.

    Includes risk overview, expiration timeline, and high-risk clauses.
    Admin and Legal users only.
    """
    today = date.today()

    # Risk distribution
    risk_query = (
        select(Contract.risk_level, func.count(Contract.id))
        .where(Contract.risk_level.isnot(None))
        .group_by(Contract.risk_level)
    )
    risk_query = apply_tenant_filter(risk_query, tenant_id)
    risk_result = await db.execute(risk_query)
    by_level = {r.value: c for r, c in risk_result.all()}

    # High risk contracts - include contracts with HIGH/CRITICAL risk level
    # OR contracts that have high-risk clauses
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
    high_risk_query = apply_tenant_filter(high_risk_query, tenant_id)
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
    async def get_expirations(start: date, end: date) -> list[ExpirationItem]:
        exp_query = (
            select(Contract)
            .where(Contract.expiration_date >= start)
            .where(Contract.expiration_date <= end)
            .order_by(Contract.expiration_date.asc())
        )
        exp_query = apply_tenant_filter(exp_query, tenant_id)
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

    next_30 = await get_expirations(today, today + timedelta(days=30))
    next_60 = await get_expirations(today + timedelta(days=31), today + timedelta(days=60))
    next_90 = await get_expirations(today + timedelta(days=61), today + timedelta(days=90))

    # High risk clauses
    clause_query = (
        select(Clause, Contract.filename)
        .join(Contract, Clause.contract_id == Contract.id)
        .where(Clause.risk_level == RiskLevel.HIGH)
        .order_by(Clause.created_at.desc())
        .limit(20)
    )
    clause_query = apply_tenant_filter(clause_query, tenant_id)
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
        .where(AuditLog.user_id == current_user.id)
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
        risk_overview=RiskOverview(
            by_level=by_level,
            high_risk_contracts=high_risk_contracts,
        ),
        expiration_timeline=ExpirationTimeline(
            next_30_days=next_30,
            next_60_days=next_60,
            next_90_days=next_90,
        ),
        high_risk_clauses=high_risk_clauses,
        recent_activity=recent_activity,
    )


# ============== Procurement Dashboard ==============


class SpendCommitment(BaseModel):
    """Spend commitment by vendor."""

    counterparty: str
    total_value: Decimal
    contract_count: int
    currency: str | None


class VendorObligation(BaseModel):
    """Upcoming vendor obligation."""

    obligation_id: str
    contract_id: str
    contract_filename: str
    counterparty: str | None
    description: str
    deadline: date | None
    days_remaining: int | None
    status: str


class AutoRenewalRisk(BaseModel):
    """Auto-renewal risk item."""

    contract_id: str
    filename: str
    counterparty: str | None
    expiration_date: date | None
    notice_period_days: int | None
    notice_deadline: date | None
    days_until_notice: int | None
    urgency: str


class ProcurementDashboardResponse(BaseModel):
    """Procurement dashboard data."""

    spend_commitments: list[SpendCommitment]
    upcoming_obligations: list[VendorObligation]
    auto_renewal_risks: list[AutoRenewalRisk]
    vendor_summary: dict[str, int]


@router.get("/procurement", response_model=ProcurementDashboardResponse)
async def get_procurement_dashboard(
    current_user: Annotated[User, Depends(require_role(Role.ADMIN, Role.PROCUREMENT))],
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProcurementDashboardResponse:
    """Get procurement dashboard data.

    Includes spend commitments, vendor obligations, and auto-renewal risks.
    Admin and Procurement users only.
    """
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
    spend_query = apply_tenant_filter(spend_query, tenant_id)
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
    obl_query = apply_tenant_filter(obl_query, tenant_id)
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
    renewal_query = apply_tenant_filter(renewal_query, tenant_id)
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

    # Vendor summary (contracts per vendor)
    vendor_result = await db.execute(
        select(Contract.counterparty, func.count(Contract.id))
        .where(Contract.counterparty.isnot(None))
        .group_by(Contract.counterparty)
        .order_by(func.count(Contract.id).desc())
        .limit(20)
    )
    vendor_summary = {row[0]: row[1] for row in vendor_result.all()}

    return ProcurementDashboardResponse(
        spend_commitments=spend_commitments,
        upcoming_obligations=upcoming_obligations,
        auto_renewal_risks=auto_renewal_risks,
        vendor_summary=vendor_summary,
    )


# ============== Contract Intelligence Dashboard ==============


class ClauseBreakdown(BaseModel):
    """Clause type breakdown."""

    clause_type: str
    count: int
    high_risk_count: int


class ObligationItem(BaseModel):
    """Single obligation item."""

    id: str
    description: str
    obligation_type: str
    obligated_party: str | None
    beneficiary_party: str | None
    deadline: date | None
    status: str


class ObligationsMatrix(BaseModel):
    """Obligations grouped by party."""

    provider_obligations: list[ObligationItem]
    client_obligations: list[ObligationItem]
    total_count: int


class ContractKeyTerms(BaseModel):
    """Key contract terms."""

    contract_type: str | None
    counterparty: str | None
    effective_date: date | None
    expiration_date: date | None
    contract_value: float | None
    currency: str | None
    jurisdiction: str | None
    notice_period_days: int | None
    auto_renewal: bool | None


class RiskSummary(BaseModel):
    """Risk summary for contract."""

    risk_level: str | None
    risk_score: int | None
    high_risk_clauses: list[dict]


class ContractIntelligenceResponse(BaseModel):
    """Comprehensive contract intelligence data."""

    contract_id: str
    filename: str
    key_terms: ContractKeyTerms
    clause_breakdown: list[ClauseBreakdown]
    obligations_matrix: ObligationsMatrix
    risk_summary: RiskSummary
    extraction_status: dict[str, int]


@router.get("/intelligence/{contract_id}", response_model=ContractIntelligenceResponse)
async def get_contract_intelligence(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContractIntelligenceResponse:
    """Get comprehensive contract intelligence for a single contract.

    Returns extracted clauses, obligations matrix, key terms, and risks.
    """
    import uuid

    # Get contract
    result = await db.execute(
        select(Contract).where(Contract.id == uuid.UUID(contract_id))
    )
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Key terms
    key_terms = ContractKeyTerms(
        contract_type=contract.contract_type.value if contract.contract_type else None,
        counterparty=contract.counterparty,
        effective_date=contract.effective_date,
        expiration_date=contract.expiration_date,
        contract_value=float(contract.contract_value) if contract.contract_value else None,
        currency=contract.currency,
        jurisdiction=contract.jurisdiction,
        notice_period_days=contract.notice_period_days,
        auto_renewal=contract.auto_renewal,
    )

    # Clause breakdown
    clause_result = await db.execute(
        select(
            Clause.clause_type,
            func.count(Clause.id).label("count"),
            func.sum(func.cast(Clause.risk_level == RiskLevel.HIGH, Integer)).label("high_risk")
        )
        .where(Clause.contract_id == contract.id)
        .group_by(Clause.clause_type)
        .order_by(func.count(Clause.id).desc())
    )

    clause_breakdown = []
    for row in clause_result.all():
        clause_breakdown.append(ClauseBreakdown(
            clause_type=row[0].value if row[0] else "other",
            count=row[1],
            high_risk_count=row[2] or 0,
        ))

    # Obligations matrix
    obligations_result = await db.execute(
        select(Obligation)
        .where(Obligation.contract_id == contract.id)
        .order_by(Obligation.obligation_type)
    )
    obligations = obligations_result.scalars().all()

    provider_obligations = []
    client_obligations = []

    for obl in obligations:
        item = ObligationItem(
            id=str(obl.id),
            description=obl.description,
            obligation_type=obl.obligation_type.value if obl.obligation_type else "other",
            obligated_party=obl.obligated_party,
            beneficiary_party=obl.beneficiary_party,
            deadline=obl.deadline,
            status=obl.status.value if obl.status else "pending",
        )

        # Categorize by obligated party
        party = (obl.obligated_party or "").lower()
        if "provider" in party or "clasp" in party or "vendor" in party:
            provider_obligations.append(item)
        else:
            client_obligations.append(item)

    obligations_matrix = ObligationsMatrix(
        provider_obligations=provider_obligations,
        client_obligations=client_obligations,
        total_count=len(obligations),
    )

    # High risk clauses
    high_risk_result = await db.execute(
        select(Clause)
        .where(Clause.contract_id == contract.id)
        .where(Clause.risk_level == RiskLevel.HIGH)
        .limit(10)
    )
    high_risk_clauses = [
        {
            "id": str(c.id),
            "clause_type": c.clause_type.value if c.clause_type else "other",
            "excerpt": c.text[:200] + "..." if len(c.text) > 200 else c.text,
            "risk_reason": c.risk_reason,
        }
        for c in high_risk_result.scalars().all()
    ]

    risk_summary = RiskSummary(
        risk_level=contract.risk_level.value if contract.risk_level else None,
        risk_score=contract.risk_score,
        high_risk_clauses=high_risk_clauses,
    )

    # Extraction status
    total_clauses = await db.execute(
        select(func.count(Clause.id)).where(Clause.contract_id == contract.id)
    )
    classified_clauses = await db.execute(
        select(func.count(Clause.id))
        .where(Clause.contract_id == contract.id)
        .where(Clause.clause_type != ClauseType.OTHER)
    )

    extraction_status = {
        "total_clauses": total_clauses.scalar() or 0,
        "classified_clauses": classified_clauses.scalar() or 0,
        "total_obligations": len(obligations),
    }

    return ContractIntelligenceResponse(
        contract_id=contract_id,
        filename=contract.filename,
        key_terms=key_terms,
        clause_breakdown=clause_breakdown,
        obligations_matrix=obligations_matrix,
        risk_summary=risk_summary,
        extraction_status=extraction_status,
    )


# ============== Obligations Summary Dashboard ==============


class ObligationsByType(BaseModel):
    """Obligations grouped by type."""

    obligation_type: str
    count: int
    by_party: dict[str, int]


class ObligationsSummaryResponse(BaseModel):
    """Summary of all obligations across contracts."""

    by_type: list[ObligationsByType]
    by_status: dict[str, int]
    by_party: dict[str, int]
    total: int


@router.get("/obligations-summary", response_model=ObligationsSummaryResponse)
async def get_obligations_summary(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    contract_id: str | None = None,
    client_id: str | None = None,
) -> ObligationsSummaryResponse:
    """Get summary of obligations, optionally filtered by contract or client."""
    import uuid as uuid_mod

    # Build base query with optional contract/client filter
    base_filter = []
    if contract_id:
        base_filter.append(Obligation.contract_id == uuid_mod.UUID(contract_id))
    elif client_id:
        # Get contracts for this client and filter obligations
        from sqlalchemy import exists
        base_filter.append(
            Obligation.contract_id.in_(
                select(Contract.id).where(Contract.client_id == uuid_mod.UUID(client_id))
            )
        )

    # By type with party breakdown
    type_query = select(
        Obligation.obligation_type,
        Obligation.obligated_party,
        func.count(Obligation.id)
    ).group_by(Obligation.obligation_type, Obligation.obligated_party)

    if base_filter:
        type_query = type_query.where(*base_filter)

    type_result = await db.execute(type_query)

    type_dict: dict[str, dict[str, int]] = {}
    for row in type_result.all():
        obl_type = row[0].value if row[0] else "other"
        party = row[1] or "Unknown"
        count = row[2]

        if obl_type not in type_dict:
            type_dict[obl_type] = {}
        type_dict[obl_type][party] = count

    by_type = [
        ObligationsByType(
            obligation_type=obl_type,
            count=sum(parties.values()),
            by_party=parties,
        )
        for obl_type, parties in type_dict.items()
    ]

    # By status
    status_query = select(Obligation.status, func.count(Obligation.id)).group_by(Obligation.status)
    if base_filter:
        status_query = status_query.where(*base_filter)
    status_result = await db.execute(status_query)
    by_status = {row[0].value: row[1] for row in status_result.all()}

    # By party (total)
    party_query = select(Obligation.obligated_party, func.count(Obligation.id)).group_by(Obligation.obligated_party)
    if base_filter:
        party_query = party_query.where(*base_filter)
    party_result = await db.execute(party_query)
    by_party = {(row[0] or "Unknown"): row[1] for row in party_result.all()}

    # Total
    total_query = select(func.count(Obligation.id))
    if base_filter:
        total_query = total_query.where(*base_filter)
    total_result = await db.execute(total_query)
    total = total_result.scalar() or 0

    return ObligationsSummaryResponse(
        by_type=by_type,
        by_status=by_status,
        by_party=by_party,
        total=total,
    )


# ============== Clauses Summary Dashboard ==============


class ClauseByType(BaseModel):
    """Clause count by type."""

    clause_type: str
    count: int
    high_risk_count: int


class ClausesSummaryResponse(BaseModel):
    """Summary of all clauses across contracts."""

    by_type: list[ClauseByType]
    total: int
    classified: int
    high_risk_total: int


@router.get("/clauses-summary", response_model=ClausesSummaryResponse)
async def get_clauses_summary(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    contract_id: str | None = None,
    client_id: str | None = None,
) -> ClausesSummaryResponse:
    """Get summary of clauses, optionally filtered by contract or client."""
    import uuid as uuid_mod
    from app.models.clause import Clause, ClauseType

    # Build base query with optional contract/client filter
    base_filter = []
    if contract_id:
        base_filter.append(Clause.contract_id == uuid_mod.UUID(contract_id))
    elif client_id:
        # Get contracts for this client and filter clauses
        base_filter.append(
            Clause.contract_id.in_(
                select(Contract.id).where(Contract.client_id == uuid_mod.UUID(client_id))
            )
        )

    # By type with high risk count
    type_query = select(
        Clause.clause_type,
        func.count(Clause.id),
        func.sum(case((Clause.risk_level == "high", 1), else_=0))
    ).group_by(Clause.clause_type)

    if base_filter:
        type_query = type_query.where(*base_filter)

    type_result = await db.execute(type_query)

    by_type = []
    total = 0
    classified = 0
    high_risk_total = 0

    for row in type_result.all():
        clause_type = row[0].value if row[0] else "other"
        count = row[1]
        high_risk = row[2] or 0

        by_type.append(ClauseByType(
            clause_type=clause_type,
            count=count,
            high_risk_count=high_risk,
        ))

        total += count
        high_risk_total += high_risk
        if clause_type != "other":
            classified += count

    # Sort by count descending, but keep "other" at the end
    by_type.sort(key=lambda x: (x.clause_type == "other", -x.count))

    return ClausesSummaryResponse(
        by_type=by_type,
        total=total,
        classified=classified,
        high_risk_total=high_risk_total,
    )


# ============== Clauses Drill-Down ==============


class ClauseDetail(BaseModel):
    """Detailed clause info for drill-down."""

    id: str
    contract_id: str
    contract_filename: str
    counterparty: str | None
    clause_type: str
    text: str
    risk_level: str | None
    page_number: int | None
    section_number: str | None


class ClausesByTypeResponse(BaseModel):
    """Response for clauses filtered by type."""

    clause_type: str
    clauses: list[ClauseDetail]
    total: int
    high_risk_count: int


@router.get("/clauses/by-type/{clause_type}", response_model=ClausesByTypeResponse)
async def get_clauses_by_type(
    clause_type: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    contract_id: str | None = None,
) -> ClausesByTypeResponse:
    """Get all clauses of a specific type with full details."""
    from app.models.clause import Clause, ClauseType
    from app.models.contract import Contract
    import uuid as uuid_mod

    # Map string to enum
    try:
        clause_type_enum = ClauseType(clause_type)
    except ValueError:
        clause_type_enum = ClauseType.OTHER

    # Build query
    query = (
        select(Clause, Contract.filename, Contract.counterparty)
        .join(Contract, Clause.contract_id == Contract.id)
        .where(Clause.clause_type == clause_type_enum)
        .order_by(Clause.page_number.asc().nulls_last())
    )

    if contract_id:
        query = query.where(Clause.contract_id == uuid_mod.UUID(contract_id))

    result = await db.execute(query)

    clauses = []
    high_risk_count = 0

    for clause, filename, counterparty in result.all():
        clauses.append(ClauseDetail(
            id=str(clause.id),
            contract_id=str(clause.contract_id),
            contract_filename=filename,
            counterparty=counterparty,
            clause_type=clause.clause_type.value if clause.clause_type else "other",
            text=clause.text[:500] + "..." if len(clause.text) > 500 else clause.text,
            risk_level=clause.risk_level,
            page_number=clause.page_number,
            section_number=clause.section_number,
        ))

        if clause.risk_level == "high":
            high_risk_count += 1

    return ClausesByTypeResponse(
        clause_type=clause_type,
        clauses=clauses,
        total=len(clauses),
        high_risk_count=high_risk_count,
    )


# ============== Clause Detail ==============


class ClauseFullDetail(BaseModel):
    """Full clause details for detail page."""

    id: str
    contract_id: str
    contract_filename: str
    contract_type: str | None
    counterparty: str | None
    clause_type: str
    text: str  # Full text, not truncated
    risk_level: str | None
    risk_reason: str | None
    page_number: int | None
    section_number: str | None
    # Related clauses in the same contract
    related_clauses: list[dict[str, Any]]


@router.get("/clauses/{clause_id}", response_model=ClauseFullDetail)
async def get_clause_detail(
    clause_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ClauseFullDetail:
    """Get full details for a specific clause."""
    from app.models.clause import Clause
    from app.models.contract import Contract
    import uuid as uuid_mod

    # Get the clause with contract info
    result = await db.execute(
        select(Clause, Contract.filename, Contract.counterparty, Contract.contract_type)
        .join(Contract, Clause.contract_id == Contract.id)
        .where(Clause.id == uuid_mod.UUID(clause_id))
    )

    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Clause not found")

    clause, filename, counterparty, contract_type = row

    # Get related clauses from the same contract (excluding this one)
    related_result = await db.execute(
        select(Clause)
        .where(Clause.contract_id == clause.contract_id)
        .where(Clause.id != clause.id)
        .order_by(Clause.page_number.asc().nulls_last())
        .limit(10)
    )

    related_clauses = [
        {
            "id": str(c.id),
            "clause_type": c.clause_type.value if c.clause_type else "other",
            "text": c.text[:200] + "..." if len(c.text) > 200 else c.text,
            "risk_level": c.risk_level,
            "page_number": c.page_number,
        }
        for c in related_result.scalars().all()
    ]

    return ClauseFullDetail(
        id=str(clause.id),
        contract_id=str(clause.contract_id),
        contract_filename=filename,
        contract_type=contract_type.value if contract_type else None,
        counterparty=counterparty,
        clause_type=clause.clause_type.value if clause.clause_type else "other",
        text=clause.text,  # Full text
        risk_level=clause.risk_level,
        risk_reason=clause.risk_reason,
        page_number=clause.page_number,
        section_number=clause.section_number,
        related_clauses=related_clauses,
    )


# ============== Obligations Drill-Down ==============


class ObligationDetail(BaseModel):
    """Detailed obligation info for drill-down."""

    id: str
    contract_id: str
    contract_filename: str
    counterparty: str | None
    description: str
    obligation_type: str
    obligated_party: str | None
    beneficiary_party: str | None
    deadline: date | None
    status: str
    source_clause_text: str | None


class ObligationsByTypeResponse(BaseModel):
    """Response for obligations filtered by type."""

    obligation_type: str
    obligations: list[ObligationDetail]
    total: int
    by_party: dict[str, int]
    by_status: dict[str, int]


@router.get("/obligations/by-type/{obligation_type}", response_model=ObligationsByTypeResponse)
async def get_obligations_by_type(
    obligation_type: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ObligationsByTypeResponse:
    """Get all obligations of a specific type with full details."""
    from app.models.obligation import ObligationType

    # Map string to enum
    try:
        obl_type_enum = ObligationType(obligation_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid obligation type: {obligation_type}",
        )

    # Get obligations with contract info and clause text
    result = await db.execute(
        select(Obligation, Contract.filename, Contract.counterparty, Clause.text)
        .join(Contract, Obligation.contract_id == Contract.id)
        .outerjoin(Clause, Obligation.clause_id == Clause.id)
        .where(Obligation.obligation_type == obl_type_enum)
        .order_by(Obligation.deadline.asc().nulls_last())
    )

    obligations = []
    by_party: dict[str, int] = {}
    by_status: dict[str, int] = {}

    for obl, filename, counterparty, clause_text in result.all():
        source_text = None
        if clause_text:
            source_text = clause_text[:300] + "..." if len(clause_text) > 300 else clause_text

        obligations.append(ObligationDetail(
            id=str(obl.id),
            contract_id=str(obl.contract_id),
            contract_filename=filename,
            counterparty=counterparty,
            description=obl.description,
            obligation_type=obl.obligation_type.value if obl.obligation_type else "other",
            obligated_party=obl.obligated_party,
            beneficiary_party=obl.beneficiary_party,
            deadline=obl.deadline,
            status=obl.status.value if obl.status else "pending",
            source_clause_text=source_text,
        ))

        # Tally by party
        party = obl.obligated_party or "Unknown"
        by_party[party] = by_party.get(party, 0) + 1

        # Tally by status
        stat = obl.status.value if obl.status else "pending"
        by_status[stat] = by_status.get(stat, 0) + 1

    return ObligationsByTypeResponse(
        obligation_type=obligation_type,
        obligations=obligations,
        total=len(obligations),
        by_party=by_party,
        by_status=by_status,
    )


# ============== Single Obligation Detail ==============


class ObligationFullDetail(BaseModel):
    """Full obligation details for the detail page."""

    id: str
    contract_id: str
    contract_filename: str
    counterparty: str | None
    contract_type: str | None

    # Obligation info
    description: str
    obligation_type: str
    obligated_party: str | None
    beneficiary_party: str | None
    deadline: date | None
    deadline_type: str | None
    recurrence_pattern: str | None
    relative_deadline_text: str | None
    status: str
    consequence_of_breach: str | None
    trigger_condition: str | None
    source_text: str | None  # Direct source from obligation

    # Source clause info (if linked to a clause)
    clause_id: str | None
    clause_type: str | None
    clause_text: str | None
    clause_page_number: int | None
    clause_section_number: str | None
    clause_risk_level: str | None


@router.get("/obligations/{obligation_id}", response_model=ObligationFullDetail)
async def get_obligation_detail(
    obligation_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ObligationFullDetail:
    """Get full details for a single obligation."""
    import uuid as uuid_mod

    result = await db.execute(
        select(
            Obligation,
            Contract.filename,
            Contract.counterparty,
            Contract.contract_type,
            Clause.id.label("clause_id"),
            Clause.clause_type,
            Clause.text,
            Clause.page_number,
            Clause.section_number,
            Clause.risk_level,
        )
        .join(Contract, Obligation.contract_id == Contract.id)
        .outerjoin(Clause, Obligation.clause_id == Clause.id)
        .where(Obligation.id == uuid_mod.UUID(obligation_id))
    )

    row = result.one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Obligation not found: {obligation_id}",
        )

    obl = row[0]
    filename = row[1]
    counterparty = row[2]
    contract_type = row[3]
    clause_id = row[4]
    clause_type = row[5]
    clause_text = row[6]
    clause_page = row[7]
    clause_section = row[8]
    clause_risk = row[9]

    return ObligationFullDetail(
        id=str(obl.id),
        contract_id=str(obl.contract_id),
        contract_filename=filename,
        counterparty=counterparty,
        contract_type=contract_type.value if contract_type else None,
        description=obl.description,
        obligation_type=obl.obligation_type.value if obl.obligation_type else "other",
        obligated_party=obl.obligated_party,
        beneficiary_party=obl.beneficiary_party,
        deadline=obl.deadline,
        deadline_type=obl.deadline_type.value if obl.deadline_type else None,
        recurrence_pattern=obl.recurrence_pattern,
        relative_deadline_text=obl.relative_deadline_text,
        status=obl.status.value if obl.status else "pending",
        consequence_of_breach=obl.consequence_of_breach,
        trigger_condition=obl.trigger_condition,
        source_text=obl.source_text,
        clause_id=str(clause_id) if clause_id else None,
        clause_type=clause_type.value if clause_type else None,
        clause_text=clause_text,
        clause_page_number=clause_page,
        clause_section_number=clause_section,
        clause_risk_level=clause_risk.value if clause_risk else None,
    )


# ============== Contract Cockpit Dashboard (Phase 3) ==============
# Comprehensive single-contract view using canonical data model


class CockpitParty(BaseModel):
    """Party information for cockpit."""

    legal_name: str
    role: str
    short_name: str | None
    entity_type: str | None
    jurisdiction: str | None
    is_primary: bool


class CockpitKeyDate(BaseModel):
    """Key date for cockpit timeline."""

    event_name: str
    event_type: str
    event_date: date
    days_until: int
    action_required: str | None
    alert_days_before: int | None
    urgency: str  # OVERDUE, IMMEDIATE, SOON, UPCOMING, FUTURE


class CockpitFinancial(BaseModel):
    """Financial term for cockpit."""

    fee_type: str
    description: str | None
    amount: float | None
    currency: str | None
    frequency: str | None
    payment_terms: str | None
    is_penalty: bool


class CockpitLiability(BaseModel):
    """Liability term for cockpit."""

    cap_type: str | None
    cap_amount: float | None
    cap_currency: str | None
    description: str | None
    is_mutual: bool
    indemnifying_party: str | None
    insurance_required: bool


class CockpitObligation(BaseModel):
    """Obligation for cockpit matrix."""

    id: str
    description: str
    owner: str  # provider, client, mutual
    category: str | None
    frequency: str | None
    deadline: date | None
    status: str
    rag_status: str
    is_critical: bool
    priority: int | None


class CockpitClauseIndicators(BaseModel):
    """Clause presence indicators for cockpit risk view."""

    # Grouped by category
    confidentiality_ip: dict[str, bool | None]
    liability_indemnity: dict[str, bool | None]
    termination_renewal: dict[str, bool | None]
    compliance_regulatory: dict[str, bool | None]
    business_restrictions: dict[str, bool | None]
    operational: dict[str, bool | None]
    payment: dict[str, bool | None]

    coverage_stats: dict[str, list[str] | float]  # present, absent, unknown lists and coverage_percentage


class CockpitLinkedContract(BaseModel):
    """Linked contract for relationship view."""

    contract_id: str
    filename: str
    link_type: str
    direction: str  # parent, child
    effective_date: date | None
    reference_number: str | None
    is_active: bool


class CockpitRiskSummary(BaseModel):
    """Risk summary for cockpit."""

    overall_risk_level: str | None
    risk_score: int | None
    high_risk_clause_count: int
    overdue_obligations: int
    expiring_soon: bool
    missing_critical_clauses: list[str]
    risk_factors: list[str]


class ContractCockpitResponse(BaseModel):
    """Comprehensive contract cockpit dashboard response."""

    # Contract identity
    contract_id: str
    filename: str
    contract_type: str | None
    status: str

    # Key metadata
    counterparty: str | None
    effective_date: date | None
    expiration_date: date | None
    days_until_expiration: int | None
    contract_value: float | None
    currency: str | None
    governing_law: str | None
    jurisdiction: str | None

    # Renewal info
    auto_renewal: bool | None
    notice_period_days: int | None
    notice_deadline: date | None

    # Parties
    parties: list[CockpitParty]

    # Timeline
    key_dates: list[CockpitKeyDate]

    # Financials
    total_contract_value: float | None
    financials: list[CockpitFinancial]
    penalties: list[CockpitFinancial]

    # Liabilities
    liabilities: list[CockpitLiability]
    primary_liability_cap: CockpitLiability | None

    # Obligations matrix
    provider_obligations: list[CockpitObligation]
    client_obligations: list[CockpitObligation]
    mutual_obligations: list[CockpitObligation]
    obligation_stats: dict[str, int]  # by status, by rag_status

    # Clause indicators (risk view)
    clause_indicators: CockpitClauseIndicators | None

    # Linked contracts
    parent_contracts: list[CockpitLinkedContract]
    child_contracts: list[CockpitLinkedContract]

    # Risk summary
    risk_summary: CockpitRiskSummary

    # Schema data (raw)
    has_schema_data: bool
    schema_id: str | None


@router.get("/cockpit/{contract_id}", response_model=ContractCockpitResponse)
async def get_contract_cockpit(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContractCockpitResponse:
    """Get comprehensive contract cockpit dashboard.

    Returns all canonical data for a single contract:
    - Contract metadata and key terms
    - Parties involved
    - Timeline with key dates
    - Financial terms and penalties
    - Liability caps and indemnification
    - Obligations matrix by owner
    - Clause presence indicators
    - Linked contracts (parent/child)
    - Risk summary and factors
    """
    import uuid as uuid_mod

    today = date.today()

    # Get contract with relationships
    result = await db.execute(
        select(Contract).where(Contract.id == uuid_mod.UUID(contract_id))
    )
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Days until expiration
    days_until_expiration = None
    notice_deadline = None
    if contract.expiration_date:
        days_until_expiration = (contract.expiration_date - today).days
        if contract.notice_period_days:
            notice_deadline = contract.expiration_date - timedelta(days=contract.notice_period_days)

    # Get parties
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

    # Get key dates
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

    # Get financials
    fin_result = await db.execute(
        select(ContractFinancial)
        .where(ContractFinancial.contract_id == contract.id)
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

    # Get liabilities
    liab_result = await db.execute(
        select(ContractLiability)
        .where(ContractLiability.contract_id == contract.id)
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
        # First non-indemnification liability is primary cap
        if not primary_liability_cap and li.liability_cap_type and not li.indemnifying_party:
            primary_liability_cap = item

    # Get obligations
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

        # Categorize by owner
        if obl.owner_type == ObligationOwner.PROVIDER:
            provider_obligations.append(item)
        elif obl.owner_type == ObligationOwner.CLIENT:
            client_obligations.append(item)
        elif obl.owner_type == ObligationOwner.MUTUAL:
            mutual_obligations.append(item)
        else:
            # Default to provider if unspecified
            provider_obligations.append(item)

        # Stats
        stat_key = obl.status.value if obl.status else "pending"
        obl_stats[stat_key] = obl_stats.get(stat_key, 0) + 1

        rag_key = obl.rag_status.value if obl.rag_status else "not_assessed"
        rag_stats[rag_key] = rag_stats.get(rag_key, 0) + 1

    obligation_stats = {**obl_stats, **{f"rag_{k}": v for k, v in rag_stats.items()}}

    # Get clause indicators
    ind_result = await db.execute(
        select(ContractClauseIndicator)
        .where(ContractClauseIndicator.contract_id == contract.id)
    )
    indicators = ind_result.scalar_one_or_none()

    clause_indicators = None
    if indicators:
        # Group indicators by category
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

    # Get linked contracts
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

    # Get high-risk clauses count
    high_risk_count = await db.scalar(
        select(func.count(Clause.id))
        .where(Clause.contract_id == contract.id)
        .where(Clause.risk_level == RiskLevel.HIGH)
    ) or 0

    # Build risk summary
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


# ============== Obligations & Compliance Dashboard (Phase 4) ==============
# Portfolio-wide view of all obligations with RAG status tracking


class ComplianceObligationItem(BaseModel):
    """Single obligation for compliance tracking."""

    id: str
    contract_id: str
    contract_filename: str
    counterparty: str | None
    description: str
    owner: str
    category: str | None
    frequency: str | None
    deadline: date | None
    days_until_deadline: int | None
    status: str
    rag_status: str
    is_critical: bool
    priority: int | None
    last_compliance_date: date | None
    next_compliance_due: date | None


class RAGStatusSummary(BaseModel):
    """RAG status summary across all obligations."""

    green: int
    amber: int
    red: int
    not_assessed: int
    total: int
    compliance_rate: float  # Percentage of green


class ComplianceByCategory(BaseModel):
    """Compliance stats grouped by category."""

    category: str
    total: int
    green: int
    amber: int
    red: int
    not_assessed: int
    compliance_rate: float


class ComplianceByOwner(BaseModel):
    """Compliance stats grouped by owner."""

    owner: str
    total: int
    green: int
    amber: int
    red: int
    overdue: int


class ComplianceCalendarItem(BaseModel):
    """Item for compliance calendar view."""

    date: date
    obligation_count: int
    obligations: list[ComplianceObligationItem]


class ObligationsComplianceResponse(BaseModel):
    """Obligations & Compliance Dashboard response."""

    # Summary stats
    rag_summary: RAGStatusSummary
    status_summary: dict[str, int]  # pending, in_progress, completed, overdue, waived

    # Critical items
    overdue_obligations: list[ComplianceObligationItem]
    critical_upcoming: list[ComplianceObligationItem]  # Critical within 7 days

    # Breakdown views
    by_category: list[ComplianceByCategory]
    by_owner: list[ComplianceByOwner]
    by_frequency: dict[str, int]

    # Calendar view (next 30 days)
    calendar: list[ComplianceCalendarItem]

    # Contract exposure
    contracts_with_red: int
    contracts_with_amber: int
    top_risk_contracts: list[dict[str, Any]]


@router.get("/obligations-compliance", response_model=ObligationsComplianceResponse)
async def get_obligations_compliance_dashboard(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    contract_id: str | None = None,
    owner_filter: str | None = None,
    category_filter: str | None = None,
) -> ObligationsComplianceResponse:
    """Get Obligations & Compliance dashboard.

    Provides portfolio-wide view of obligations with RAG status tracking,
    compliance calendar, and risk exposure by contract.

    Args:
        contract_id: Optional filter by specific contract.
        owner_filter: Optional filter by owner (provider, client, mutual).
        category_filter: Optional filter by category.
    """
    import uuid as uuid_mod
    from collections import defaultdict

    today = date.today()

    # Build base query with tenant filter
    base_query = select(
        Obligation,
        Contract.filename,
        Contract.counterparty,
    ).join(Contract, Obligation.contract_id == Contract.id)
    base_query = apply_tenant_filter(base_query, tenant_id)

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
    contracts_rag: dict[str, set[str]] = defaultdict(set)  # contract_id -> set of rag statuses

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

    # Top risk contracts (most red/amber obligations)
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


# ============== Portfolio Dashboard (Phase 5) ==============
# Cross-contract analytics and portfolio-level metrics


class PortfolioContractSummary(BaseModel):
    """Contract summary for portfolio view."""

    contract_id: str
    filename: str
    contract_type: str | None
    counterparty: str | None
    status: str
    risk_level: str | None
    contract_value: float | None
    currency: str | None
    effective_date: date | None
    expiration_date: date | None
    days_until_expiration: int | None
    obligation_count: int
    red_obligations: int
    has_auto_renewal: bool


class PortfolioValueMetrics(BaseModel):
    """Portfolio value metrics."""

    total_value: float
    by_currency: dict[str, float]
    by_type: dict[str, float]
    by_counterparty: dict[str, float]
    average_contract_value: float
    contracts_with_value: int


class PortfolioRiskMetrics(BaseModel):
    """Portfolio risk metrics."""

    by_risk_level: dict[str, int]
    high_risk_count: int
    critical_count: int
    contracts_expiring_30d: int
    contracts_expiring_90d: int
    auto_renewal_count: int
    missing_key_clauses: int


class PortfolioObligationMetrics(BaseModel):
    """Portfolio obligation metrics."""

    total_obligations: int
    by_owner: dict[str, int]
    by_status: dict[str, int]
    by_rag: dict[str, int]
    overdue_count: int
    compliance_rate: float


class PortfolioClauseMetrics(BaseModel):
    """Portfolio clause coverage metrics."""

    contracts_with_indicators: int
    average_clause_coverage: float
    missing_critical_by_clause: dict[str, int]  # clause_name -> count of contracts missing


class CounterpartyExposure(BaseModel):
    """Exposure to a single counterparty."""

    counterparty: str
    contract_count: int
    total_value: float
    currency: str | None
    risk_score: float  # Weighted average
    expiring_soon: int
    red_obligations: int


class PortfolioDashboardResponse(BaseModel):
    """Portfolio Dashboard response."""

    # Overview
    total_contracts: int
    contracts_by_status: dict[str, int]
    contracts_by_type: dict[str, int]

    # Value metrics
    value_metrics: PortfolioValueMetrics

    # Risk metrics
    risk_metrics: PortfolioRiskMetrics

    # Obligation metrics
    obligation_metrics: PortfolioObligationMetrics

    # Clause coverage
    clause_metrics: PortfolioClauseMetrics

    # Counterparty exposure
    top_counterparties: list[CounterpartyExposure]

    # Timeline
    expiring_contracts: list[PortfolioContractSummary]
    recently_added: list[PortfolioContractSummary]

    # Alerts
    alerts: list[dict[str, Any]]


@router.get("/portfolio", response_model=PortfolioDashboardResponse)
async def get_portfolio_dashboard(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PortfolioDashboardResponse:
    """Get Portfolio Dashboard with cross-contract analytics.

    Provides:
    - Portfolio value and exposure metrics
    - Risk distribution across contracts
    - Obligation compliance rates
    - Clause coverage analysis
    - Counterparty concentration
    - Timeline of expirations
    """
    from collections import defaultdict

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
    contracts_query = apply_tenant_filter(contracts_query, tenant_id)
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

        # Aggregate by status
        status_val = contract.status.value if contract.status else "unknown"
        contracts_by_status[status_val] += 1

        # Aggregate by type
        type_val = contract.contract_type.value if contract.contract_type else "unknown"
        contracts_by_type[type_val] += 1

        # Aggregate by risk
        risk_val = contract.risk_level.value if contract.risk_level else "unassessed"
        risk_by_level[risk_val] += 1

        # Value aggregation
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

    # Count contracts missing key clauses
    indicators_result = await db.execute(select(ContractClauseIndicator))
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
    obl_result = await db.execute(
        select(
            Obligation.owner_type,
            Obligation.status,
            Obligation.rag_status,
            func.count(Obligation.id),
        )
        .group_by(Obligation.owner_type, Obligation.status, Obligation.rag_status)
    )

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

    # Recently added contracts
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
        alerts.append({
            "type": "expiration",
            "severity": "high",
            "message": f"{expiring_30d} contract(s) expiring within 30 days",
            "count": expiring_30d,
        })
    if overdue_count > 0:
        alerts.append({
            "type": "obligation",
            "severity": "critical",
            "message": f"{overdue_count} overdue obligation(s) require attention",
            "count": overdue_count,
        })
    if high_risk > 0:
        alerts.append({
            "type": "risk",
            "severity": "high",
            "message": f"{high_risk} high-risk contract(s) in portfolio",
            "count": high_risk,
        })
    if missing_key_count > 0:
        alerts.append({
            "type": "clause",
            "severity": "medium",
            "message": f"{missing_key_count} contract(s) missing critical clauses",
            "count": missing_key_count,
        })

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


# ============== Definitions Dashboard ==============


class DefinitionItem(BaseModel):
    """Single definition for display."""

    id: str
    term: str
    definition_text: str
    category: str | None
    section_reference: str | None
    page_number: int | None
    cross_references: list[str]


class DefinitionsSummary(BaseModel):
    """Summary of definitions for a contract."""

    contract_id: str
    contract_filename: str
    definitions: list[DefinitionItem]
    total: int
    by_category: dict[str, int]


class DefinitionsByCategory(BaseModel):
    """Definitions grouped by category across all contracts."""

    category: str
    definitions: list[dict[str, Any]]
    total: int


@router.get("/definitions/{contract_id}", response_model=DefinitionsSummary)
async def get_contract_definitions(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DefinitionsSummary:
    """Get all definitions extracted from a specific contract."""
    import uuid as uuid_mod

    # Get contract info
    contract_result = await db.execute(
        select(Contract.filename).where(Contract.id == uuid_mod.UUID(contract_id))
    )
    contract_row = contract_result.first()
    if not contract_row:
        raise HTTPException(status_code=404, detail="Contract not found")

    # Get definitions
    result = await db.execute(
        select(ContractDefinition)
        .where(ContractDefinition.contract_id == uuid_mod.UUID(contract_id))
        .order_by(ContractDefinition.term)
    )

    definitions = []
    by_category: dict[str, int] = {}

    for defn in result.scalars().all():
        cross_refs = []
        if defn.cross_references:
            cross_refs = [r.strip() for r in defn.cross_references.split(",")]

        definitions.append(DefinitionItem(
            id=str(defn.id),
            term=defn.term,
            definition_text=defn.definition_text,
            category=defn.category,
            section_reference=defn.section_reference,
            page_number=defn.page_number,
            cross_references=cross_refs,
        ))

        cat = defn.category or "uncategorized"
        by_category[cat] = by_category.get(cat, 0) + 1

    return DefinitionsSummary(
        contract_id=contract_id,
        contract_filename=contract_row[0],
        definitions=definitions,
        total=len(definitions),
        by_category=by_category,
    )


@router.get("/definitions-summary", response_model=dict[str, Any])
async def get_definitions_summary(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Get summary of all definitions across contracts."""
    # Count by category
    category_result = await db.execute(
        select(
            ContractDefinition.category,
            func.count(ContractDefinition.id),
        )
        .group_by(ContractDefinition.category)
    )

    by_category = {}
    total = 0
    for row in category_result.all():
        cat = row[0] or "uncategorized"
        count = row[1]
        by_category[cat] = count
        total += count

    # Count contracts with definitions
    contracts_result = await db.execute(
        select(func.count(func.distinct(ContractDefinition.contract_id)))
    )
    contracts_with_definitions = contracts_result.scalar() or 0

    # Get most common terms
    common_terms_result = await db.execute(
        select(
            ContractDefinition.term_normalized,
            func.count(ContractDefinition.id).label("count"),
        )
        .group_by(ContractDefinition.term_normalized)
        .order_by(func.count(ContractDefinition.id).desc())
        .limit(20)
    )

    common_terms = [
        {"term": row[0], "count": row[1]}
        for row in common_terms_result.all()
    ]

    return {
        "total": total,
        "by_category": by_category,
        "contracts_with_definitions": contracts_with_definitions,
        "common_terms": common_terms,
    }


@router.get("/definitions/search/{term}", response_model=list[dict[str, Any]])
async def search_definitions(
    term: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    """Search for a definition by term across all contracts."""
    # Search by normalized term (case-insensitive)
    normalized = term.lower().strip().replace('"', '').replace("'", "")

    result = await db.execute(
        select(ContractDefinition, Contract.filename)
        .join(Contract, ContractDefinition.contract_id == Contract.id)
        .where(ContractDefinition.term_normalized.ilike(f"%{normalized}%"))
        .order_by(ContractDefinition.term)
        .limit(50)
    )

    definitions = []
    for defn, filename in result.all():
        definitions.append({
            "id": str(defn.id),
            "contract_id": str(defn.contract_id),
            "contract_filename": filename,
            "term": defn.term,
            "definition_text": defn.definition_text,
            "category": defn.category,
            "section_reference": defn.section_reference,
        })

    return definitions


@router.get("/definitions/compare/{term}", response_model=dict[str, Any])
async def compare_definitions(
    term: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Compare how a term is defined across different contracts.

    Returns grouped definitions showing variations in how the same term
    is defined in different contracts.
    """
    # Search by normalized term (exact match for comparison)
    normalized = term.lower().strip().replace('"', '').replace("'", "")

    result = await db.execute(
        select(ContractDefinition, Contract.filename, Contract.counterparty, Contract.contract_type)
        .join(Contract, ContractDefinition.contract_id == Contract.id)
        .where(ContractDefinition.term_normalized == normalized)
        .order_by(Contract.created_at.desc())
    )

    definitions = []
    definition_texts = set()

    for defn, filename, counterparty, contract_type in result.all():
        definitions.append({
            "id": str(defn.id),
            "contract_id": str(defn.contract_id),
            "contract_filename": filename,
            "counterparty": counterparty,
            "contract_type": contract_type.value if contract_type else None,
            "term": defn.term,
            "definition_text": defn.definition_text,
            "category": defn.category,
            "section_reference": defn.section_reference,
        })
        if defn.definition_text:
            definition_texts.add(defn.definition_text[:200])  # Compare first 200 chars

    return {
        "term": term,
        "total_occurrences": len(definitions),
        "unique_definitions": len(definition_texts),
        "has_variations": len(definition_texts) > 1,
        "definitions": definitions,
    }


@router.get("/definitions/all-terms", response_model=list[dict[str, Any]])
async def get_all_defined_terms(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Get all unique terms that have been defined across contracts.

    Returns terms sorted by frequency (most common first).
    """
    result = await db.execute(
        select(
            ContractDefinition.term_normalized,
            func.min(ContractDefinition.term).label("display_term"),
            func.count(ContractDefinition.id).label("occurrence_count"),
            func.count(func.distinct(ContractDefinition.contract_id)).label("contract_count"),
        )
        .group_by(ContractDefinition.term_normalized)
        .order_by(func.count(ContractDefinition.id).desc())
        .limit(limit)
    )

    terms = []
    for row in result.all():
        terms.append({
            "term": row.display_term,
            "term_normalized": row.term_normalized,
            "occurrence_count": row.occurrence_count,
            "contract_count": row.contract_count,
            "has_variations": row.occurrence_count > row.contract_count,  # Multiple definitions in some contracts
        })

    return terms


# ============== Financials Dashboard ==============


class FinancialItem(BaseModel):
    """Single financial item for display."""

    id: str
    fee_type: str
    fee_description: str | None
    fee_amount: float | None
    currency: str
    quantity: int | None
    unit_price: float | None
    payment_terms: str | None
    payment_terms_days: int | None
    invoicing_frequency: str | None
    is_penalty: bool
    penalty_type: str | None
    penalty_trigger: str | None
    penalty_amount: float | None
    penalty_percentage: float | None
    section_reference: str | None


class FinancialsResponse(BaseModel):
    """Financials summary for a contract."""

    financials: list[FinancialItem]
    total_value: float
    currency: str
    by_fee_type: dict[str, int]
    penalties: list[FinancialItem]
    total_penalties: float


@router.get("/financials/{contract_id}", response_model=FinancialsResponse)
async def get_contract_financials(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FinancialsResponse:
    """Get all financial terms for a specific contract."""
    import uuid as uuid_mod

    # Get financials
    result = await db.execute(
        select(ContractFinancial)
        .where(ContractFinancial.contract_id == uuid_mod.UUID(contract_id))
        .order_by(ContractFinancial.is_penalty, ContractFinancial.fee_type)
    )

    financials = []
    penalties = []
    total_value = 0.0
    total_penalties = 0.0
    by_fee_type: dict[str, int] = {}
    currency = "USD"

    for fin in result.scalars().all():
        item = FinancialItem(
            id=str(fin.id),
            fee_type=fin.fee_type.value if fin.fee_type else "other",
            fee_description=fin.fee_description,
            fee_amount=float(fin.fee_amount) if fin.fee_amount else None,
            currency=fin.currency or "USD",
            quantity=fin.quantity,
            unit_price=float(fin.unit_price) if fin.unit_price else None,
            payment_terms=fin.payment_terms.value if fin.payment_terms else None,
            payment_terms_days=fin.payment_terms_days,
            invoicing_frequency=fin.invoicing_frequency,
            is_penalty=fin.is_penalty,
            penalty_type=fin.penalty_type.value if fin.penalty_type else None,
            penalty_trigger=fin.penalty_trigger,
            penalty_amount=float(fin.penalty_amount) if fin.penalty_amount else None,
            penalty_percentage=float(fin.penalty_percentage) if fin.penalty_percentage else None,
            section_reference=fin.section_reference,
        )

        financials.append(item)
        currency = fin.currency or currency

        if fin.is_penalty:
            penalties.append(item)
            if fin.penalty_amount:
                total_penalties += float(fin.penalty_amount)
        else:
            if fin.fee_amount:
                total_value += float(fin.fee_amount)
            elif fin.quantity and fin.unit_price:
                total_value += float(fin.quantity * fin.unit_price)

            fee_type = fin.fee_type.value if fin.fee_type else "other"
            by_fee_type[fee_type] = by_fee_type.get(fee_type, 0) + 1

    return FinancialsResponse(
        financials=financials,
        total_value=total_value,
        currency=currency,
        by_fee_type=by_fee_type,
        penalties=penalties,
        total_penalties=total_penalties,
    )


# ============== Process Steps Dashboard ==============


class ProcessStepItem(BaseModel):
    """Single process step for display."""

    id: str
    step_number: int
    step_name: str
    step_type: str
    description: str | None
    responsible_party: str | None
    duration_days: int | None
    sla_days: int | None
    dependencies: list[str]
    deliverables: list[str]
    status: str
    source_text: str | None


class ProcessResponse(BaseModel):
    """Process steps summary for a contract."""

    contract_id: str
    steps: list[ProcessStepItem]
    total_steps: int
    estimated_duration_days: int
    by_responsible_party: dict[str, int]
    sla_items: int


@router.get("/process/{contract_id}", response_model=ProcessResponse)
async def get_contract_process(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProcessResponse:
    """Get all process steps for a specific contract."""
    import uuid as uuid_mod
    from app.models.process_step import ContractProcessStep

    # Get process steps
    result = await db.execute(
        select(ContractProcessStep)
        .where(ContractProcessStep.contract_id == uuid_mod.UUID(contract_id))
        .order_by(ContractProcessStep.step_number)
    )

    steps = []
    total_duration = 0
    by_responsible_party: dict[str, int] = {}
    sla_items = 0

    for step in result.scalars().all():
        deps = []
        if step.dependencies:
            deps = [d.strip() for d in step.dependencies.split(",")]

        delivs = []
        if step.deliverables:
            delivs = [d.strip() for d in step.deliverables.split(",")]

        steps.append(ProcessStepItem(
            id=str(step.id),
            step_number=step.step_number,
            step_name=step.step_name,
            step_type=step.step_type.value if step.step_type else "other",
            description=step.description,
            responsible_party=step.responsible_party,
            duration_days=step.duration_days,
            sla_days=step.sla_days,
            dependencies=deps,
            deliverables=delivs,
            status=step.status.value if step.status else "pending",
            source_text=step.source_text[:300] + "..." if step.source_text and len(step.source_text) > 300 else step.source_text,
        ))

        if step.duration_days:
            total_duration += step.duration_days

        if step.sla_days:
            sla_items += 1

        party = step.responsible_party or "Unassigned"
        by_responsible_party[party] = by_responsible_party.get(party, 0) + 1

    return ProcessResponse(
        contract_id=contract_id,
        steps=steps,
        total_steps=len(steps),
        estimated_duration_days=total_duration,
        by_responsible_party=by_responsible_party,
        sla_items=sla_items,
    )


# ============== Preamble/Header Dashboard ==============


class PartyDetailItem(BaseModel):
    """Single party detail for display."""

    id: str
    party_name: str
    party_role: str | None
    party_short_name: str | None
    legal_form: str | None
    jurisdiction_of_incorporation: str | None
    address: str | None
    party_order: int


class PreambleResponse(BaseModel):
    """Preamble data for a contract."""

    contract_id: str
    document_title: str | None
    effective_date_text: str | None
    background_summary: str | None
    recitals_text: str | None
    parties: list[PartyDetailItem]
    has_preamble: bool


@router.get("/preamble/{contract_id}", response_model=PreambleResponse)
async def get_contract_preamble(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PreambleResponse:
    """Get preamble/header data for a specific contract."""
    import uuid as uuid_mod
    from app.models.preamble import ContractPreamble, ContractPartyDetail

    # Get preamble
    result = await db.execute(
        select(ContractPreamble)
        .where(ContractPreamble.contract_id == uuid_mod.UUID(contract_id))
    )
    preamble = result.scalar_one_or_none()

    if not preamble:
        return PreambleResponse(
            contract_id=contract_id,
            document_title=None,
            effective_date_text=None,
            background_summary=None,
            recitals_text=None,
            parties=[],
            has_preamble=False,
        )

    # Get party details
    party_result = await db.execute(
        select(ContractPartyDetail)
        .where(ContractPartyDetail.preamble_id == preamble.id)
        .order_by(ContractPartyDetail.party_order)
    )
    party_details = party_result.scalars().all()

    parties = [
        PartyDetailItem(
            id=str(p.id),
            party_name=p.party_name,
            party_role=p.party_role,
            party_short_name=p.party_short_name,
            legal_form=p.legal_form,
            jurisdiction_of_incorporation=p.jurisdiction_of_incorporation,
            address=p.address,
            party_order=p.party_order,
        )
        for p in party_details
    ]

    return PreambleResponse(
        contract_id=contract_id,
        document_title=preamble.document_title,
        effective_date_text=preamble.effective_date_text,
        background_summary=preamble.background_summary,
        recitals_text=preamble.recitals_text,
        parties=parties,
        has_preamble=True,
    )


# ============== Exhibits/Schedules Dashboard ==============


class FeeItemResponse(BaseModel):
    """Single fee item for display."""

    id: str
    item_name: str
    item_description: str | None
    quantity: int | None
    unit_price: float | None
    total_price: float | None
    currency: str
    item_order: int


class ExhibitItem(BaseModel):
    """Single exhibit/schedule for display."""

    id: str
    exhibit_identifier: str
    exhibit_type: str
    title: str | None
    description: str | None
    page_number: int | None
    source_text: str | None
    fee_items: list[FeeItemResponse]
    total_fee_value: float | None


class ExhibitsResponse(BaseModel):
    """Exhibits summary for a contract."""

    contract_id: str
    exhibits: list[ExhibitItem]
    total_exhibits: int
    by_type: dict[str, int]
    total_fee_value: float
    has_pricing_exhibits: bool


@router.get("/exhibits/{contract_id}", response_model=ExhibitsResponse)
async def get_contract_exhibits(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExhibitsResponse:
    """Get all exhibits/schedules for a specific contract."""
    import uuid as uuid_mod

    # Get exhibits with fee items
    result = await db.execute(
        select(ContractExhibit)
        .where(ContractExhibit.contract_id == uuid_mod.UUID(contract_id))
        .order_by(ContractExhibit.page_number.asc().nulls_last(), ContractExhibit.exhibit_identifier)
    )

    exhibits = []
    by_type: dict[str, int] = {}
    total_fee_value = 0.0
    has_pricing = False

    for exhibit in result.scalars().all():
        # Get fee items for this exhibit
        fee_result = await db.execute(
            select(ExhibitFeeItem)
            .where(ExhibitFeeItem.exhibit_id == exhibit.id)
            .order_by(ExhibitFeeItem.item_order)
        )
        fee_items = []
        exhibit_fee_total = 0.0

        for fee in fee_result.scalars().all():
            fee_items.append(FeeItemResponse(
                id=str(fee.id),
                item_name=fee.item_name,
                item_description=fee.item_description,
                quantity=fee.quantity,
                unit_price=float(fee.unit_price) if fee.unit_price else None,
                total_price=float(fee.total_price) if fee.total_price else None,
                currency=fee.currency or "USD",
                item_order=fee.item_order,
            ))
            if fee.total_price:
                exhibit_fee_total += float(fee.total_price)
                total_fee_value += float(fee.total_price)

        exhibit_type = exhibit.exhibit_type.value if exhibit.exhibit_type else "other"
        by_type[exhibit_type] = by_type.get(exhibit_type, 0) + 1

        if exhibit_type == "pricing" or fee_items:
            has_pricing = True

        exhibits.append(ExhibitItem(
            id=str(exhibit.id),
            exhibit_identifier=exhibit.exhibit_identifier,
            exhibit_type=exhibit_type,
            title=exhibit.title,
            description=exhibit.description[:500] + "..." if exhibit.description and len(exhibit.description) > 500 else exhibit.description,
            page_number=exhibit.page_number,
            source_text=exhibit.source_text[:300] + "..." if exhibit.source_text and len(exhibit.source_text) > 300 else exhibit.source_text,
            fee_items=fee_items,
            total_fee_value=exhibit_fee_total if exhibit_fee_total > 0 else None,
        ))

    return ExhibitsResponse(
        contract_id=contract_id,
        exhibits=exhibits,
        total_exhibits=len(exhibits),
        by_type=by_type,
        total_fee_value=total_fee_value,
        has_pricing_exhibits=has_pricing,
    )


@router.get("/exhibits-summary", response_model=dict[str, Any])
async def get_exhibits_summary(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Get summary of all exhibits across contracts."""
    # Count by type
    type_result = await db.execute(
        select(ContractExhibit.exhibit_type, func.count(ContractExhibit.id))
        .group_by(ContractExhibit.exhibit_type)
    )
    by_type: dict[str, int] = {}
    total = 0
    for exhibit_type, count in type_result.all():
        type_val = exhibit_type.value if exhibit_type else "other"
        by_type[type_val] = count
        total += count

    # Count contracts with exhibits
    contracts_result = await db.execute(
        select(func.count(func.distinct(ContractExhibit.contract_id)))
    )
    contracts_with_exhibits = contracts_result.scalar() or 0

    # Total fee items and value
    fee_result = await db.execute(
        select(
            func.count(ExhibitFeeItem.id),
            func.sum(ExhibitFeeItem.total_price)
        )
    )
    fee_row = fee_result.one()
    total_fee_items = fee_row[0] or 0
    total_fee_value = float(fee_row[1]) if fee_row[1] else 0.0

    return {
        "total_exhibits": total,
        "by_type": by_type,
        "contracts_with_exhibits": contracts_with_exhibits,
        "total_fee_items": total_fee_items,
        "total_fee_value": total_fee_value,
    }


# ============== AI Insights Endpoint ==============


class InsightItem(BaseModel):
    """Single insight item."""
    title: str
    description: str
    action: str
    action_label: str
    variant: str  # info, warning, success


class InsightsResponse(BaseModel):
    """AI Insights response."""
    insights: list[InsightItem]


@router.get("/insights", response_model=InsightsResponse)
async def get_dashboard_insights(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InsightsResponse:
    """Get AI-generated insights for dashboard."""
    from app.models.sla import ContractSLA

    insights: list[InsightItem] = []
    today = date.today()

    # 1. Renewal Opportunity - contracts expiring in 30 days
    expiring_query = select(
        func.count(Contract.id),
        func.coalesce(func.sum(Contract.total_value), 0)
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

    # 2. Compliance Alert - SLA breaches
    sla_query = select(func.count(ContractSLA.id)).where(
        ContractSLA.compliance_status == "red"
    )
    if tenant_id:
        sla_query = sla_query.join(Contract).where(Contract.tenant_id == tenant_id)

    sla_result = await db.execute(sla_query)
    critical_slas = sla_result.scalar() or 0

    if critical_slas > 0:
        insights.append(InsightItem(
            title="Compliance Alert",
            description=f"{critical_slas} critical SLA breach{'es' if critical_slas > 1 else ''} need{'s' if critical_slas == 1 else ''} attention.",
            action="/compliance",
            action_label="Review compliance",
            variant="warning"
        ))

    # 3. Overdue Obligations
    overdue_query = select(func.count(Obligation.id)).where(
        Obligation.due_date < today,
        Obligation.status != ObligationStatus.COMPLETED
    )
    if tenant_id:
        overdue_query = overdue_query.join(Contract).where(Contract.tenant_id == tenant_id)

    overdue_result = await db.execute(overdue_query)
    overdue_count = overdue_result.scalar() or 0

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

    high_risk_result = await db.execute(high_risk_query)
    high_risk_count = high_risk_result.scalar() or 0

    if high_risk_count > 0:
        insights.append(InsightItem(
            title="Risk Assessment",
            description=f"{high_risk_count} high-risk contract{'s' if high_risk_count > 1 else ''} identified. Review risk mitigation strategies.",
            action="/contracts?risk=high",
            action_label="View risks",
            variant="warning"
        ))

    # If no insights, add a positive one
    if not insights:
        insights.append(InsightItem(
            title="All Clear",
            description="No critical issues detected. All contracts and obligations are on track.",
            action="/contracts",
            action_label="View contracts",
            variant="success"
        ))

    return InsightsResponse(insights=insights)


# ============== Recent Activity Endpoint ==============


class ActivityItem(BaseModel):
    """Single activity item."""
    icon: str
    title: str
    subtitle: str
    time: str
    color: str


class ActivityResponse(BaseModel):
    """Recent activity response."""
    activities: list[ActivityItem]


@router.get("/activity", response_model=ActivityResponse)
async def get_recent_activity(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 10,
) -> ActivityResponse:
    """Get recent activity for dashboard."""
    from datetime import datetime, timezone

    activities: list[ActivityItem] = []
    now = datetime.now(timezone.utc)

    def time_ago(dt: datetime) -> str:
        """Convert datetime to human-readable time ago."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = now - dt
        seconds = diff.total_seconds()
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            mins = int(seconds / 60)
            return f"{mins}m ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}h ago"
        else:
            days = int(seconds / 86400)
            return f"{days}d ago"

    # Get recent audit logs
    audit_query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit * 2)
    if tenant_id:
        audit_query = audit_query.where(AuditLog.tenant_id == tenant_id)

    audit_result = await db.execute(audit_query)
    audit_logs = audit_result.scalars().all()

    for log in audit_logs:
        if len(activities) >= limit:
            break

        details = log.details or {}

        if log.action == AuditAction.CONTRACT_UPLOAD:
            activities.append(ActivityItem(
                icon="document",
                title="Contract uploaded",
                subtitle=details.get("filename", "Unknown file"),
                time=time_ago(log.created_at),
                color="blue"
            ))
        elif log.action == AuditAction.CONTRACT_VIEW:
            if details.get("action") == "deep_analysis_queued":
                activities.append(ActivityItem(
                    icon="sparkles",
                    title="Analysis started",
                    subtitle=details.get("filename", "Contract analysis"),
                    time=time_ago(log.created_at),
                    color="blue"
                ))
        elif log.action == AuditAction.CONTRACT_UPDATE:
            activities.append(ActivityItem(
                icon="pencil",
                title="Contract updated",
                subtitle=details.get("filename", "Contract modified"),
                time=time_ago(log.created_at),
                color="gray"
            ))

    # Get recent obligation completions
    completed_query = select(Obligation).where(
        Obligation.status == ObligationStatus.COMPLETED
    ).order_by(Obligation.updated_at.desc()).limit(5)
    if tenant_id:
        completed_query = completed_query.join(Contract).where(Contract.tenant_id == tenant_id)

    completed_result = await db.execute(completed_query)
    completed_obligations = completed_result.scalars().all()

    for obl in completed_obligations:
        if len(activities) >= limit:
            break
        activities.append(ActivityItem(
            icon="check",
            title="Obligation completed",
            subtitle=obl.title[:50] + "..." if len(obl.title) > 50 else obl.title,
            time=time_ago(obl.updated_at) if obl.updated_at else "recently",
            color="green"
        ))

    # Sort by time (most recent first) - simplified approach
    # In production, you'd want to properly sort by actual timestamps
    activities = activities[:limit]

    return ActivityResponse(activities=activities)
