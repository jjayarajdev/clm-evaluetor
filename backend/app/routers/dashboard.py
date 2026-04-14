"""Dashboard router for role-specific dashboard data.

Thin HTTP handlers delegating to dashboard_service for business logic.
"""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, Integer, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, CurrentTenantId, require_role
from app.database import get_db
from app.models.clause import Clause, ClauseType, RiskLevel
from app.models.contract import Contract, ContractStatus
from app.models.obligation import Obligation, ObligationStatus
from app.models.financial import ContractFinancial
from app.models.exhibit import ContractExhibit, ExhibitFeeItem
from app.models.definition import ContractDefinition
from app.models.user import Role, User
from app.core.tenant import apply_bu_filter, apply_tenant_filter

from app.schemas.dashboard import (
    # Contract Summary
    ContractSummaryCard, ContractsSummaryResponse,
    # Admin
    AdminDashboardResponse,
    # Legal
    LegalDashboardResponse,
    # Procurement
    ProcurementDashboardResponse,
    # Intelligence
    ClauseBreakdown, ObligationItem, ObligationsMatrix,
    ContractKeyTerms, RiskSummary, ContractIntelligenceResponse,
    # Obligations Summary
    ObligationsByType, ObligationsSummaryResponse,
    # Clauses Summary
    ClauseByType, ClausesSummaryResponse,
    # Clauses Drill-Down
    ClauseDetail, ClausesByTypeResponse,
    # Clause Detail
    ClauseFullDetail,
    # Obligations Drill-Down
    ObligationDetail, ObligationsByTypeResponse,
    # Obligation Detail
    ObligationFullDetail,
    # Cockpit
    ContractCockpitResponse,
    # Obligations & Compliance
    ObligationsComplianceResponse,
    # Portfolio
    PortfolioDashboardResponse,
    # Definitions
    DefinitionItem, DefinitionsSummary,
    # Financials
    FinancialItem, FinancialsResponse,
    # Process
    ProcessStepItem, ProcessResponse,
    # Preamble
    PartyDetailItem, PreambleResponse,
    # Exhibits
    FeeItemResponse, ExhibitItem, ExhibitsResponse,
    # Insights & Activity
    InsightsResponse, ActivityResponse,
)

from app.services import dashboard_service

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


def _bu_args(current_user):
    """Extract BU filter args from current_user."""
    bu_id = current_user.business_unit_id if current_user else None
    role = current_user.role.value if current_user and current_user.role else None
    return bu_id, role


# ============== Contract Summary ==============


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

    query = (
        select(
            Contract,
            func.count(Clause.id.distinct()).label("clause_count"),
            func.count(Obligation.id.distinct()).label("obligation_count"),
        )
        .outerjoin(Clause, Contract.id == Clause.contract_id)
        .outerjoin(Obligation, Contract.id == Obligation.contract_id)
    )

    query = apply_tenant_filter(query, tenant_id, Contract)
    query = apply_bu_filter(query, current_user.business_unit_id, current_user.role.value if current_user.role else None)

    if client_id:
        query = query.where(Contract.client_id == uuid_lib.UUID(client_id))

    query = query.group_by(Contract.id).order_by(Contract.created_at.desc())
    result = await db.execute(query)

    cards = []
    by_status: dict[str, int] = {}
    by_risk: dict[str, int] = {}
    expiring_soon = 0

    for row in result.all():
        c = row[0]
        clause_count = row[1] or 0
        obligation_count = row[2] or 0

        status_val = c.status.value if c.status else "unknown"
        by_status[status_val] = by_status.get(status_val, 0) + 1

        risk_val = c.risk_level.value if c.risk_level else "unassessed"
        by_risk[risk_val] = by_risk.get(risk_val, 0) + 1

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


# ============== Role-Based Dashboards (delegated to service) ==============


@router.get("/admin", response_model=AdminDashboardResponse)
async def get_admin_dashboard(
    current_user: Annotated[User, Depends(require_role(Role.ADMIN))],
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminDashboardResponse:
    """Get admin dashboard data. Admin only."""
    bu_id, role = _bu_args(current_user)
    return await dashboard_service.get_admin_dashboard(db, tenant_id, bu_id, role)


@router.get("/legal", response_model=LegalDashboardResponse)
async def get_legal_dashboard(
    current_user: Annotated[User, Depends(require_role(Role.ADMIN, Role.LEGAL))],
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LegalDashboardResponse:
    """Get legal dashboard data. Admin and Legal users only."""
    bu_id, role = _bu_args(current_user)
    return await dashboard_service.get_legal_dashboard(db, tenant_id, bu_id, role, current_user.id)


@router.get("/procurement", response_model=ProcurementDashboardResponse)
async def get_procurement_dashboard(
    current_user: Annotated[User, Depends(require_role(Role.ADMIN, Role.PROCUREMENT))],
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProcurementDashboardResponse:
    """Get procurement dashboard data. Admin and Procurement users only."""
    bu_id, role = _bu_args(current_user)
    return await dashboard_service.get_procurement_dashboard(db, tenant_id, bu_id, role)


# ============== Contract Intelligence ==============


@router.get("/intelligence/{contract_id}", response_model=ContractIntelligenceResponse)
async def get_contract_intelligence(
    contract_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContractIntelligenceResponse:
    """Get comprehensive contract intelligence for a single contract."""
    import uuid

    query = select(Contract).where(Contract.id == uuid.UUID(contract_id))
    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)
    result = await db.execute(query)
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contract not found: {contract_id}")

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

    clause_breakdown = [
        ClauseBreakdown(
            clause_type=row[0].value if row[0] else "other",
            count=row[1],
            high_risk_count=row[2] or 0,
        )
        for row in clause_result.all()
    ]

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
            source_text=obl.source_text,
        )

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


# ============== Obligations Summary ==============


@router.get("/obligations-summary", response_model=ObligationsSummaryResponse)
async def get_obligations_summary(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    contract_id: str | None = None,
    client_id: str | None = None,
) -> ObligationsSummaryResponse:
    """Get summary of obligations, optionally filtered by contract or client."""
    import uuid as uuid_mod

    base_filter = []

    if tenant_id is not None:
        tenant_contracts_subquery = select(Contract.id).where(Contract.tenant_id == tenant_id)
        base_filter.append(Obligation.contract_id.in_(tenant_contracts_subquery))

    if contract_id:
        base_filter.append(Obligation.contract_id == uuid_mod.UUID(contract_id))
    elif client_id:
        from sqlalchemy import exists
        client_contracts = select(Contract.id).where(Contract.client_id == uuid_mod.UUID(client_id))
        if tenant_id is not None:
            client_contracts = client_contracts.where(Contract.tenant_id == tenant_id)
        base_filter.append(Obligation.contract_id.in_(client_contracts))

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
        ObligationsByType(obligation_type=obl_type, count=sum(parties.values()), by_party=parties)
        for obl_type, parties in type_dict.items()
    ]

    # By status
    status_query = select(Obligation.status, func.count(Obligation.id)).group_by(Obligation.status)
    if base_filter:
        status_query = status_query.where(*base_filter)
    status_result = await db.execute(status_query)
    by_status = {row[0].value: row[1] for row in status_result.all()}

    # By party
    party_query = select(Obligation.obligated_party, func.count(Obligation.id)).group_by(Obligation.obligated_party)
    if base_filter:
        party_query = party_query.where(*base_filter)
    party_result = await db.execute(party_query)
    by_party = {(row[0] or "Unknown"): row[1] for row in party_result.all()}

    # Total
    total_query = select(func.count(Obligation.id))
    if base_filter:
        total_query = total_query.where(*base_filter)
    total = (await db.execute(total_query)).scalar() or 0

    return ObligationsSummaryResponse(by_type=by_type, by_status=by_status, by_party=by_party, total=total)


# ============== Clauses Summary ==============


@router.get("/clauses-summary", response_model=ClausesSummaryResponse)
async def get_clauses_summary(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    contract_id: str | None = None,
    client_id: str | None = None,
) -> ClausesSummaryResponse:
    """Get summary of clauses, optionally filtered by contract or client."""
    import uuid as uuid_mod

    base_filter = []

    if tenant_id is not None:
        tenant_contracts_subquery = select(Contract.id).where(Contract.tenant_id == tenant_id)
        base_filter.append(Clause.contract_id.in_(tenant_contracts_subquery))

    if contract_id:
        base_filter.append(Clause.contract_id == uuid_mod.UUID(contract_id))
    elif client_id:
        client_contracts = select(Contract.id).where(Contract.client_id == uuid_mod.UUID(client_id))
        if tenant_id is not None:
            client_contracts = client_contracts.where(Contract.tenant_id == tenant_id)
        base_filter.append(Clause.contract_id.in_(client_contracts))

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

        by_type.append(ClauseByType(clause_type=clause_type, count=count, high_risk_count=high_risk))
        total += count
        high_risk_total += high_risk
        if clause_type != "other":
            classified += count

    by_type.sort(key=lambda x: (x.clause_type == "other", -x.count))

    return ClausesSummaryResponse(by_type=by_type, total=total, classified=classified, high_risk_total=high_risk_total)


# ============== Clauses Drill-Down ==============


@router.get("/clauses/by-type/{clause_type}", response_model=ClausesByTypeResponse)
async def get_clauses_by_type(
    clause_type: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    contract_id: str | None = None,
) -> ClausesByTypeResponse:
    """Get all clauses of a specific type with full details."""
    import uuid as uuid_mod

    try:
        clause_type_enum = ClauseType(clause_type)
    except ValueError:
        clause_type_enum = ClauseType.OTHER

    query = (
        select(Clause, Contract.filename, Contract.counterparty)
        .join(Contract, Clause.contract_id == Contract.id)
        .where(Clause.clause_type == clause_type_enum)
        .order_by(Clause.page_number.asc().nulls_last())
    )

    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)
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

    return ClausesByTypeResponse(clause_type=clause_type, clauses=clauses, total=len(clauses), high_risk_count=high_risk_count)


# ============== Clause Detail ==============


@router.get("/clauses/{clause_id}", response_model=ClauseFullDetail)
async def get_clause_detail(
    clause_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ClauseFullDetail:
    """Get full details for a specific clause."""
    import uuid as uuid_mod

    result = await db.execute(
        select(Clause, Contract.filename, Contract.counterparty, Contract.contract_type)
        .join(Contract, Clause.contract_id == Contract.id)
        .where(Clause.id == uuid_mod.UUID(clause_id))
    )

    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Clause not found")

    clause, filename, counterparty, contract_type = row

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
        text=clause.text,
        risk_level=clause.risk_level,
        risk_reason=clause.risk_reason,
        page_number=clause.page_number,
        section_number=clause.section_number,
        related_clauses=related_clauses,
    )


# ============== Obligations Drill-Down ==============


@router.get("/obligations/by-type/{obligation_type}", response_model=ObligationsByTypeResponse)
async def get_obligations_by_type(
    obligation_type: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ObligationsByTypeResponse:
    """Get all obligations of a specific type with full details."""
    from app.models.obligation import ObligationType

    try:
        obl_type_enum = ObligationType(obligation_type.lower())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid obligation type: {obligation_type}")

    query = (
        select(Obligation, Contract.filename, Contract.counterparty, Clause.text)
        .join(Contract, Obligation.contract_id == Contract.id)
        .outerjoin(Clause, Obligation.clause_id == Clause.id)
        .where(Obligation.obligation_type == obl_type_enum)
        .order_by(Obligation.deadline.asc().nulls_last())
    )

    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)

    result = await db.execute(query)

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

        party = obl.obligated_party or "Unknown"
        by_party[party] = by_party.get(party, 0) + 1
        stat = obl.status.value if obl.status else "pending"
        by_status[stat] = by_status.get(stat, 0) + 1

    return ObligationsByTypeResponse(
        obligation_type=obligation_type, obligations=obligations,
        total=len(obligations), by_party=by_party, by_status=by_status,
    )


# ============== Single Obligation Detail ==============


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
            Obligation, Contract.filename, Contract.counterparty, Contract.contract_type,
            Clause.id.label("clause_id"), Clause.clause_type, Clause.text,
            Clause.page_number, Clause.section_number, Clause.risk_level,
        )
        .join(Contract, Obligation.contract_id == Contract.id)
        .outerjoin(Clause, Obligation.clause_id == Clause.id)
        .where(Obligation.id == uuid_mod.UUID(obligation_id))
    )

    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Obligation not found: {obligation_id}")

    obl = row[0]
    return ObligationFullDetail(
        id=str(obl.id),
        contract_id=str(obl.contract_id),
        contract_filename=row[1],
        counterparty=row[2],
        contract_type=row[3].value if row[3] else None,
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
        clause_id=str(row[4]) if row[4] else None,
        clause_type=row[5].value if row[5] else None,
        clause_text=row[6],
        clause_page_number=row[7],
        clause_section_number=row[8],
        clause_risk_level=row[9].value if row[9] else None,
    )


# ============== Contract Cockpit (delegated to service) ==============


@router.get("/cockpit/{contract_id}", response_model=ContractCockpitResponse)
async def get_contract_cockpit(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContractCockpitResponse:
    """Get comprehensive contract cockpit dashboard."""
    result = await dashboard_service.get_contract_cockpit(db, contract_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Contract not found: {contract_id}")
    return result


# ============== Obligations & Compliance Dashboard (delegated to service) ==============


@router.get("/obligations-compliance", response_model=ObligationsComplianceResponse)
async def get_obligations_compliance_dashboard(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    contract_id: str | None = None,
    owner_filter: str | None = None,
    category_filter: str | None = None,
) -> ObligationsComplianceResponse:
    """Get Obligations & Compliance dashboard with RAG status tracking."""
    bu_id, role = _bu_args(current_user)
    return await dashboard_service.get_obligations_compliance(
        db, tenant_id, bu_id, role, contract_id, owner_filter, category_filter,
    )


# ============== Portfolio Dashboard (delegated to service) ==============


@router.get("/portfolio", response_model=PortfolioDashboardResponse)
async def get_portfolio_dashboard(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PortfolioDashboardResponse:
    """Get Portfolio Dashboard with cross-contract analytics."""
    bu_id, role = _bu_args(current_user)
    return await dashboard_service.get_portfolio_dashboard(db, tenant_id, bu_id, role)


# ============== Definitions ==============


@router.get("/definitions/{contract_id}", response_model=DefinitionsSummary)
async def get_contract_definitions(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DefinitionsSummary:
    """Get all definitions extracted from a specific contract."""
    import uuid as uuid_mod

    contract_result = await db.execute(
        select(Contract.filename).where(Contract.id == uuid_mod.UUID(contract_id))
    )
    contract_row = contract_result.first()
    if not contract_row:
        raise HTTPException(status_code=404, detail="Contract not found")

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
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Get summary of all definitions across contracts."""
    tenant_contracts = select(Contract.id)
    if tenant_id is not None:
        tenant_contracts = tenant_contracts.where(Contract.tenant_id == tenant_id)

    category_query = (
        select(ContractDefinition.category, func.count(ContractDefinition.id))
        .group_by(ContractDefinition.category)
    )
    if tenant_id is not None:
        category_query = category_query.where(ContractDefinition.contract_id.in_(tenant_contracts))
    category_result = await db.execute(category_query)

    by_category = {}
    total = 0
    for row in category_result.all():
        cat = row[0] or "uncategorized"
        by_category[cat] = row[1]
        total += row[1]

    contracts_query = select(func.count(func.distinct(ContractDefinition.contract_id)))
    if tenant_id is not None:
        contracts_query = contracts_query.where(ContractDefinition.contract_id.in_(tenant_contracts))
    contracts_with_definitions = (await db.execute(contracts_query)).scalar() or 0

    common_terms_query = (
        select(ContractDefinition.term_normalized, func.count(ContractDefinition.id).label("count"))
        .group_by(ContractDefinition.term_normalized)
        .order_by(func.count(ContractDefinition.id).desc())
        .limit(20)
    )
    if tenant_id is not None:
        common_terms_query = common_terms_query.where(ContractDefinition.contract_id.in_(tenant_contracts))
    common_terms_result = await db.execute(common_terms_query)

    common_terms = [{"term": row[0], "count": row[1]} for row in common_terms_result.all()]

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
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    """Search for a definition by term across all contracts."""
    normalized = term.lower().strip().replace('"', '').replace("'", "")

    query = (
        select(ContractDefinition, Contract.filename)
        .join(Contract, ContractDefinition.contract_id == Contract.id)
        .where(ContractDefinition.term_normalized.ilike(f"%{normalized}%"))
        .order_by(ContractDefinition.term)
        .limit(50)
    )
    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)
    result = await db.execute(query)

    return [
        {
            "id": str(defn.id),
            "contract_id": str(defn.contract_id),
            "contract_filename": filename,
            "term": defn.term,
            "definition_text": defn.definition_text,
            "category": defn.category,
            "section_reference": defn.section_reference,
        }
        for defn, filename in result.all()
    ]


@router.get("/definitions/compare/{term}", response_model=dict[str, Any])
async def compare_definitions(
    term: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Compare how a term is defined across different contracts."""
    normalized = term.lower().strip().replace('"', '').replace("'", "")

    query = (
        select(ContractDefinition, Contract.filename, Contract.counterparty, Contract.contract_type)
        .join(Contract, ContractDefinition.contract_id == Contract.id)
        .where(ContractDefinition.term_normalized == normalized)
        .order_by(Contract.created_at.desc())
    )
    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)
    result = await db.execute(query)

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
            definition_texts.add(defn.definition_text[:200])

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
    """Get all unique terms that have been defined across contracts."""
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

    return [
        {
            "term": row.display_term,
            "term_normalized": row.term_normalized,
            "occurrence_count": row.occurrence_count,
            "contract_count": row.contract_count,
            "has_variations": row.occurrence_count > row.contract_count,
        }
        for row in result.all()
    ]


# ============== Financials ==============


@router.get("/financials/{contract_id}", response_model=FinancialsResponse)
async def get_contract_financials(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FinancialsResponse:
    """Get all financial terms for a specific contract."""
    import uuid as uuid_mod

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
        financials=financials, total_value=total_value, currency=currency,
        by_fee_type=by_fee_type, penalties=penalties, total_penalties=total_penalties,
    )


# ============== Process Steps ==============


@router.get("/process/{contract_id}", response_model=ProcessResponse)
async def get_contract_process(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProcessResponse:
    """Get all process steps for a specific contract."""
    import uuid as uuid_mod
    from app.models.process_step import ContractProcessStep

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
        deps = [d.strip() for d in step.dependencies.split(",")] if step.dependencies else []
        delivs = [d.strip() for d in step.deliverables.split(",")] if step.deliverables else []

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
        contract_id=contract_id, steps=steps, total_steps=len(steps),
        estimated_duration_days=total_duration, by_responsible_party=by_responsible_party, sla_items=sla_items,
    )


# ============== Preamble ==============


@router.get("/preamble/{contract_id}", response_model=PreambleResponse)
async def get_contract_preamble(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PreambleResponse:
    """Get preamble/header data for a specific contract."""
    import uuid as uuid_mod
    from app.models.preamble import ContractPreamble, ContractPartyDetail

    result = await db.execute(
        select(ContractPreamble).where(ContractPreamble.contract_id == uuid_mod.UUID(contract_id))
    )
    preamble = result.scalar_one_or_none()

    if not preamble:
        return PreambleResponse(
            contract_id=contract_id, document_title=None, effective_date_text=None,
            background_summary=None, recitals_text=None, parties=[], has_preamble=False,
        )

    party_result = await db.execute(
        select(ContractPartyDetail)
        .where(ContractPartyDetail.preamble_id == preamble.id)
        .order_by(ContractPartyDetail.party_order)
    )

    parties = [
        PartyDetailItem(
            id=str(p.id), party_name=p.party_name, party_role=p.party_role,
            party_short_name=p.party_short_name, legal_form=p.legal_form,
            jurisdiction_of_incorporation=p.jurisdiction_of_incorporation,
            address=p.address, party_order=p.party_order,
        )
        for p in party_result.scalars().all()
    ]

    return PreambleResponse(
        contract_id=contract_id, document_title=preamble.document_title,
        effective_date_text=preamble.effective_date_text, background_summary=preamble.background_summary,
        recitals_text=preamble.recitals_text, parties=parties, has_preamble=True,
    )


# ============== Exhibits ==============


@router.get("/exhibits/{contract_id}", response_model=ExhibitsResponse)
async def get_contract_exhibits(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExhibitsResponse:
    """Get all exhibits/schedules for a specific contract."""
    import uuid as uuid_mod

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
        fee_result = await db.execute(
            select(ExhibitFeeItem)
            .where(ExhibitFeeItem.exhibit_id == exhibit.id)
            .order_by(ExhibitFeeItem.item_order)
        )
        fee_items = []
        exhibit_fee_total = 0.0

        for fee in fee_result.scalars().all():
            fee_items.append(FeeItemResponse(
                id=str(fee.id), item_name=fee.item_name, item_description=fee.item_description,
                quantity=fee.quantity, unit_price=float(fee.unit_price) if fee.unit_price else None,
                total_price=float(fee.total_price) if fee.total_price else None,
                currency=fee.currency or "USD", item_order=fee.item_order,
            ))
            if fee.total_price:
                exhibit_fee_total += float(fee.total_price)
                total_fee_value += float(fee.total_price)

        exhibit_type = exhibit.exhibit_type.value if exhibit.exhibit_type else "other"
        by_type[exhibit_type] = by_type.get(exhibit_type, 0) + 1

        if exhibit_type == "pricing" or fee_items:
            has_pricing = True

        exhibits.append(ExhibitItem(
            id=str(exhibit.id), exhibit_identifier=exhibit.exhibit_identifier,
            exhibit_type=exhibit_type, title=exhibit.title,
            description=exhibit.description[:500] + "..." if exhibit.description and len(exhibit.description) > 500 else exhibit.description,
            page_number=exhibit.page_number,
            source_text=exhibit.source_text[:300] + "..." if exhibit.source_text and len(exhibit.source_text) > 300 else exhibit.source_text,
            fee_items=fee_items,
            total_fee_value=exhibit_fee_total if exhibit_fee_total > 0 else None,
        ))

    return ExhibitsResponse(
        contract_id=contract_id, exhibits=exhibits, total_exhibits=len(exhibits),
        by_type=by_type, total_fee_value=total_fee_value, has_pricing_exhibits=has_pricing,
    )


@router.get("/exhibits-summary", response_model=dict[str, Any])
async def get_exhibits_summary(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Get summary of all exhibits across contracts."""
    type_result = await db.execute(
        select(ContractExhibit.exhibit_type, func.count(ContractExhibit.id))
        .group_by(ContractExhibit.exhibit_type)
    )
    by_type: dict[str, int] = {}
    total = 0
    for exhibit_type, count in type_result.all():
        by_type[exhibit_type.value if exhibit_type else "other"] = count
        total += count

    contracts_with_exhibits = (await db.execute(
        select(func.count(func.distinct(ContractExhibit.contract_id)))
    )).scalar() or 0

    fee_result = await db.execute(
        select(func.count(ExhibitFeeItem.id), func.sum(ExhibitFeeItem.total_price))
    )
    fee_row = fee_result.one()

    return {
        "total_exhibits": total,
        "by_type": by_type,
        "contracts_with_exhibits": contracts_with_exhibits,
        "total_fee_items": fee_row[0] or 0,
        "total_fee_value": float(fee_row[1]) if fee_row[1] else 0.0,
    }


# ============== Insights & Activity (delegated to service) ==============


@router.get("/insights", response_model=InsightsResponse)
async def get_dashboard_insights(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InsightsResponse:
    """Get AI-generated insights for dashboard."""
    return await dashboard_service.get_insights(db, tenant_id)


@router.get("/activity", response_model=ActivityResponse)
async def get_recent_activity(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 10,
) -> ActivityResponse:
    """Get recent activity for dashboard."""
    return await dashboard_service.get_activity(db, tenant_id, limit)
