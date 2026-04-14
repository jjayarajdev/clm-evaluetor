"""Vendor performance scoring service.

Business logic for vendor scoring, compliance calculations, and risk assessment.
Extracted from routers/vendors.py to enable reuse and testing.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import apply_bu_filter
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
)

# Party roles that indicate VENDOR (you buy from them)
VENDOR_ROLES = {PartyRole.PROVIDER, PartyRole.VENDOR}
# Party roles that indicate CLIENT (you deliver to them)
CLIENT_ROLES = {PartyRole.CLIENT, PartyRole.CUSTOMER}

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
    normalized = name.lower().strip()
    for suffix in [", inc.", ", inc", " inc.", " inc", ", llc", " llc", ", ltd", " ltd", " corp", ", corp"]:
        if normalized.endswith(suffix):
            normalized = normalized[:-len(suffix)]
    return normalized


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


def calculate_composite_score(
    obligation_compliance: float,
    sla_compliance: float,
    responsiveness_score: float = 75.0,
    issue_rate_score: float = 80.0,
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


async def determine_counterparty_type(
    db: AsyncSession,
    counterparty_name: str,
    contract_ids: list[uuid.UUID],
) -> CounterpartyType:
    """Determine if a counterparty is a vendor or client."""
    if not contract_ids:
        return CounterpartyType.UNKNOWN

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

    vendor_count = sum(1 for p in parties if p.role in VENDOR_ROLES)
    client_count = sum(1 for p in parties if p.role in CLIENT_ROLES)

    if vendor_count > client_count:
        return CounterpartyType.VENDOR
    elif client_count > vendor_count:
        return CounterpartyType.CLIENT
    else:
        return CounterpartyType.UNKNOWN


async def get_vendor_contracts(
    db: AsyncSession,
    vendor_name: str,
    tenant_id=None,
    business_unit_id=None,
    user_role=None,
) -> list[Contract]:
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
    query = apply_bu_filter(query, business_unit_id, user_role)
    result = await db.execute(query)
    return list(result.scalars().all())


async def calculate_obligation_compliance(db: AsyncSession, contract_ids: list[uuid.UUID]) -> tuple[float, dict]:
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

    today = date.today()
    waived = sum(1 for o in obligations if o.status == ObligationStatus.WAIVED)
    in_progress = sum(1 for o in obligations if o.status == ObligationStatus.IN_PROGRESS)
    pending_future = sum(
        1 for o in obligations
        if o.status == ObligationStatus.PENDING
        and o.deadline and o.deadline > today
    )
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


async def calculate_sla_compliance(db: AsyncSession, contract_ids: list[uuid.UUID]) -> tuple[float, dict]:
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
    total_breaches = sum(1 for s in slas if s.consecutive_breaches > 0)
    critical_breaches = sum(1 for s in slas if s.consecutive_breaches > 0 and s.severity and s.severity.value == "critical")

    sla_ids = [s.id for s in slas]
    penalty_query = select(func.sum(SLAPerformance.penalty_amount)).where(
        and_(
            SLAPerformance.sla_id.in_(sla_ids),
            SLAPerformance.penalty_applied == True,
        )
    )
    penalty_result = await db.execute(penalty_query)
    total_penalties = float(penalty_result.scalar() or 0)

    compliance_rates = [float(s.current_compliance_rate) for s in slas if s.current_compliance_rate is not None]
    avg_compliance = sum(compliance_rates) / len(compliance_rates) if compliance_rates else 100.0

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


async def build_vendor_metrics(db: AsyncSession, vendor_name: str, contracts: list[Contract]) -> dict:
    """Build all metrics for a vendor."""
    contract_ids = [c.id for c in contracts]

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
        annual_spend=None,
        contract_types=contract_types,
        earliest_contract=min(effective_dates) if effective_dates else None,
        latest_expiration=max(expiration_dates) if expiration_dates else None,
    )

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

    score_breakdown = calculate_composite_score(obligation_rate, sla_rate)

    return {
        "contracts": contract_summary,
        "obligations": obligation_summary,
        "slas": sla_summary,
        "score_breakdown": score_breakdown,
        "active_breaches": sla_data["breaches"],
    }
