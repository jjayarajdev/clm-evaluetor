"""KPI perception scoring service.

Business logic for KPI enrichment, gap calculations, and response mapping.
Extracted from routers/kpis.py to enable reuse and testing.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    KPI,
    PerceptionScore,
    PerceptionGap,
    GapSeverity,
    BusinessRelationship,
    Organization,
)
from app.schemas.kpi import (
    KPIResponse,
    PerceptionScoreResponse,
    PerceptionGapResponse,
)


def apply_tenant_filter_kpi(query, tenant_id):
    """Apply tenant filter to KPI query via relationship/organization join.

    KPIs don't have tenant_id directly — scoped through:
    KPI → BusinessRelationship → Organization.tenant_id
    """
    if tenant_id is not None:
        query = query.join(
            BusinessRelationship, KPI.relationship_id == BusinessRelationship.id
        ).join(
            Organization, BusinessRelationship.org_a_id == Organization.id
        ).where(Organization.tenant_id == tenant_id)
    return query


async def enrich_kpi_response(kpi: KPI, db: AsyncSession) -> KPIResponse:
    """Enrich KPI with latest perception data."""
    response = KPIResponse.model_validate(kpi)

    # Get latest gap
    gap_result = await db.execute(
        select(PerceptionGap).where(
            PerceptionGap.kpi_id == kpi.id
        ).order_by(PerceptionGap.period.desc()).limit(1)
    )
    latest_gap = gap_result.scalar_one_or_none()

    if latest_gap:
        response.latest_internal_score = latest_gap.internal_score
        response.latest_external_score = latest_gap.external_score
        response.latest_gap = latest_gap.gap
        response.latest_gap_severity = latest_gap.gap_severity

    return response


async def recalculate_gap(kpi_id: UUID, period: str, db: AsyncSession) -> None:
    """Recalculate perception gap for a KPI and period.

    Only approved scores are included in gap calculations.
    """
    # Get only approved scores for this period
    scores_result = await db.execute(
        select(PerceptionScore).where(
            PerceptionScore.kpi_id == kpi_id,
            PerceptionScore.period == period,
            PerceptionScore.approval_status == "approved",
        )
    )
    scores = scores_result.scalars().all()

    internal_scores = [s.score for s in scores if s.is_internal]
    external_scores = [s.score for s in scores if not s.is_internal]

    internal_avg = sum(internal_scores) / len(internal_scores) if internal_scores else None
    external_avg = sum(external_scores) / len(external_scores) if external_scores else None

    gap = None
    severity = None
    requires_action = False

    if internal_avg is not None and external_avg is not None:
        gap = Decimal(str(round(float(internal_avg) - float(external_avg), 2)))
        severity = PerceptionGap.calculate_severity(gap)
        requires_action = severity in [GapSeverity.SIGNIFICANT, GapSeverity.CRITICAL]

    # Find or create gap record
    gap_result = await db.execute(
        select(PerceptionGap).where(
            PerceptionGap.kpi_id == kpi_id,
            PerceptionGap.period == period,
        )
    )
    gap_record = gap_result.scalar_one_or_none()

    if gap_record:
        gap_record.internal_score = Decimal(str(round(float(internal_avg), 2))) if internal_avg else None
        gap_record.external_score = Decimal(str(round(float(external_avg), 2))) if external_avg else None
        gap_record.gap = gap
        gap_record.gap_severity = severity
        gap_record.requires_action = requires_action
        gap_record.calculated_at = datetime.utcnow()
    else:
        gap_record = PerceptionGap(
            kpi_id=kpi_id,
            period=period,
            internal_score=Decimal(str(round(float(internal_avg), 2))) if internal_avg else None,
            external_score=Decimal(str(round(float(external_avg), 2))) if external_avg else None,
            gap=gap,
            gap_severity=severity,
            requires_action=requires_action,
        )
        db.add(gap_record)

    await db.commit()


def score_to_response(score: PerceptionScore) -> PerceptionScoreResponse:
    """Convert score model to response."""
    return PerceptionScoreResponse(
        id=score.id,
        kpi_id=score.kpi_id,
        scorer_org_id=score.scorer_org_id,
        scored_by_user_id=score.scored_by_user_id,
        score=score.score,
        period=score.period,
        comments=score.comments,
        is_internal=score.is_internal,
        scored_at=score.scored_at,
        approval_status=score.approval_status,
        approved_by=score.approved_by,
        approved_at=score.approved_at,
        approval_comments=score.approval_comments,
        scorer_org_name=score.scorer_org.name if score.scorer_org else None,
        scored_by_name=score.scored_by.full_name if score.scored_by else None,
        approver_name=score.approver.full_name if score.approver else None,
    )


def gap_to_response(gap: PerceptionGap, kpi: KPI = None) -> PerceptionGapResponse:
    """Convert gap model to response."""
    return PerceptionGapResponse(
        id=gap.id,
        kpi_id=gap.kpi_id,
        period=gap.period,
        internal_score=gap.internal_score,
        external_score=gap.external_score,
        gap=gap.gap,
        gap_severity=gap.gap_severity,
        requires_action=gap.requires_action,
        notes=gap.notes,
        calculated_at=gap.calculated_at,
        kpi_name=kpi.name if kpi else None,
        kpi_category=kpi.category if kpi else None,
    )
