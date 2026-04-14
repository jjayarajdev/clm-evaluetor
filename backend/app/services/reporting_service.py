"""Compliance reporting service.

Business logic for obligation/SLA compliance calculations, trend analysis,
and report generation. Extracted from routers/reports.py.
"""

from datetime import date, datetime, timedelta

from sqlalchemy import select, func, and_, or_, case, literal
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Contract, ContractStatus, Obligation, ObligationStatus,
    ContractSLA, SLAPerformance,
)


async def get_obligations_in_period(
    db: AsyncSession,
    start_date: date,
    end_date: date,
    tenant_id=None,
    business_unit_id=None,
    user_role=None,
) -> list[tuple]:
    """Get obligations with activity in the date range."""
    query = select(Obligation, Contract).join(
        Contract,
        Obligation.contract_id == Contract.id
    ).where(
        and_(
            Contract.status == ContractStatus.COMPLETED,
            or_(
                and_(
                    Obligation.deadline >= start_date,
                    Obligation.deadline <= end_date,
                ),
                and_(
                    Obligation.last_compliance_date >= start_date,
                    Obligation.last_compliance_date <= end_date,
                ),
            )
        )
    )

    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)

    if business_unit_id and user_role not in ("admin", "super_admin"):
        query = query.where(
            or_(
                Contract.business_unit_id == business_unit_id,
                Contract.business_unit_id.is_(None),
            )
        )

    query = query.order_by(Obligation.deadline)
    result = await db.execute(query)
    return result.all()


async def get_sla_aggregates_in_period(
    db: AsyncSession,
    start_date: date,
    end_date: date,
    tenant_id=None,
    business_unit_id=None,
    user_role=None,
) -> list[dict]:
    """Get per-SLA aggregated performance stats in the date range."""
    query = (
        select(
            ContractSLA.id.label("sla_id"),
            ContractSLA.sla_name,
            ContractSLA.metric_type,
            ContractSLA.target_value,
            ContractSLA.current_compliance_rate,
            ContractSLA.severity,
            Contract.id.label("contract_id"),
            Contract.filename.label("contract_filename"),
            Contract.counterparty,
            func.count(SLAPerformance.id).label("total_count"),
            func.sum(case((SLAPerformance.is_compliant == True, 1), else_=0)).label("compliant_count"),
            func.sum(case((SLAPerformance.is_compliant == False, 1), else_=0)).label("breach_count"),
            func.coalesce(func.sum(
                case((SLAPerformance.penalty_applied == True, SLAPerformance.penalty_amount), else_=literal(0))
            ), 0).label("total_penalties"),
        )
        .join(ContractSLA, SLAPerformance.sla_id == ContractSLA.id)
        .join(Contract, ContractSLA.contract_id == Contract.id)
        .where(
            and_(
                Contract.status == ContractStatus.COMPLETED,
                SLAPerformance.measured_at >= datetime.combine(start_date, datetime.min.time()),
                SLAPerformance.measured_at <= datetime.combine(end_date, datetime.max.time()),
            )
        )
        .group_by(
            ContractSLA.id,
            ContractSLA.sla_name,
            ContractSLA.metric_type,
            ContractSLA.target_value,
            ContractSLA.current_compliance_rate,
            ContractSLA.severity,
            Contract.id,
            Contract.filename,
            Contract.counterparty,
        )
    )

    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)

    if business_unit_id and user_role not in ("admin", "super_admin"):
        query = query.where(
            or_(
                Contract.business_unit_id == business_unit_id,
                Contract.business_unit_id.is_(None),
            )
        )

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "sla_id": str(row.sla_id),
            "sla_name": row.sla_name,
            "metric_type": row.metric_type.value if row.metric_type else "unknown",
            "target_value": float(row.target_value) if row.target_value else 0,
            "current_compliance_rate": float(row.current_compliance_rate) if row.current_compliance_rate else None,
            "severity": row.severity.value if row.severity else "medium",
            "contract_id": str(row.contract_id),
            "contract_filename": row.contract_filename,
            "counterparty": row.counterparty,
            "total_count": row.total_count,
            "compliant_count": row.compliant_count,
            "breach_count": row.breach_count,
            "total_penalties": float(row.total_penalties),
        }
        for row in rows
    ]


def determine_trend(values: list[float]) -> str:
    """Determine trend direction from a list of values."""
    if len(values) < 2:
        return "stable"

    change = values[-1] - values[0]

    if change > 2:
        return "improving"
    elif change < -2:
        return "declining"
    else:
        return "stable"
