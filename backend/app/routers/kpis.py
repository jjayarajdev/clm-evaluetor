"""API endpoints for KPI management (Evaluetor features)."""

from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_current_user, require_role, CurrentUser, CurrentTenantId
from app.models import (
    User,
    KPI,
    KPICategory,
    KPIMeasurementType,
    PerceptionScore,
    PerceptionGap,
    GapSeverity,
    ScoreApprovalStatus,
    BusinessRelationship,
    Organization,
)
from app.schemas.kpi import (
    KPICreate,
    KPIUpdate,
    KPIResponse,
    KPIListResponse,
    PerceptionScoreCreate,
    PerceptionScoreResponse,
    PerceptionScoreListResponse,
    PerceptionGapResponse,
    PerceptionGapListResponse,
    GapSummary,
    ScoreApprovalAction,
    PendingApprovalResponse,
)

router = APIRouter(prefix="/api/kpis", tags=["KPIs"])


def apply_tenant_filter_kpi(query, tenant_id):
    """Apply tenant filter to KPI query via relationship/organization join."""
    if tenant_id is not None:
        # Filter by checking if the KPI's relationship's organization belongs to tenant
        query = query.join(
            BusinessRelationship, KPI.relationship_id == BusinessRelationship.id
        ).join(
            Organization, BusinessRelationship.org_a_id == Organization.id
        ).where(Organization.tenant_id == tenant_id)
    return query


# ===== KPI CRUD =====

@router.get("", response_model=KPIListResponse)
async def list_kpis(
    relationship_id: Optional[UUID] = None,
    category: Optional[KPICategory] = None,
    is_active: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """List KPIs with optional filtering."""
    query = select(KPI)
    query = apply_tenant_filter_kpi(query, tenant_id)

    if relationship_id:
        query = query.where(KPI.relationship_id == relationship_id)

    if category:
        query = query.where(KPI.category == category)

    if is_active is not None:
        query = query.where(KPI.is_active == is_active)

    query = query.order_by(KPI.category, KPI.name)

    result = await db.execute(query)
    kpis = result.scalars().all()

    # Enrich with latest scores
    items = []
    for kpi in kpis:
        response = await _enrich_kpi_response(kpi, db)
        items.append(response)

    return KPIListResponse(items=items, total=len(items))


@router.post("", response_model=KPIResponse, status_code=status.HTTP_201_CREATED)
async def create_kpi(
    data: KPICreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """Create a new KPI."""
    # Verify relationship exists
    relationship = await db.get(BusinessRelationship, data.relationship_id)
    if not relationship:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Relationship not found",
        )

    kpi = KPI(**data.model_dump())
    db.add(kpi)
    await db.commit()
    await db.refresh(kpi)

    return await _enrich_kpi_response(kpi, db)


# ===== Score Approval Workflow =====

@router.get("/pending-approvals", response_model=List[PendingApprovalResponse])
async def list_pending_approvals(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """List perception scores awaiting approval.

    Available to admin and legal roles who can act as approvers.
    """
    # Check that user has approval permission (admin or legal role)
    from app.models.user import Role
    if not current_user.is_super_admin and current_user.role not in [Role.ADMIN, Role.LEGAL]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin and legal users can view pending approvals",
        )

    query = (
        select(PerceptionScore)
        .where(PerceptionScore.approval_status == "pending_approval")
        .options(
            selectinload(PerceptionScore.scorer_org),
            selectinload(PerceptionScore.scored_by),
            selectinload(PerceptionScore.kpi).selectinload(KPI.relationship),
        )
        .order_by(PerceptionScore.scored_at.desc())
    )

    # Apply tenant filter via KPI -> relationship -> org
    if tenant_id is not None:
        query = query.join(KPI, PerceptionScore.kpi_id == KPI.id).join(
            BusinessRelationship, KPI.relationship_id == BusinessRelationship.id
        ).join(
            Organization, BusinessRelationship.org_a_id == Organization.id
        ).where(Organization.tenant_id == tenant_id)

    result = await db.execute(query)
    scores = result.scalars().all()

    items = []
    for s in scores:
        items.append(PendingApprovalResponse(
            id=s.id,
            kpi_id=s.kpi_id,
            kpi_name=s.kpi.name if s.kpi else None,
            kpi_category=s.kpi.category if s.kpi else None,
            relationship_id=s.kpi.relationship_id if s.kpi else None,
            relationship_name=s.kpi.relationship.name if s.kpi and s.kpi.relationship else None,
            scorer_org_id=s.scorer_org_id,
            scored_by_user_id=s.scored_by_user_id,
            score=s.score,
            period=s.period,
            comments=s.comments,
            is_internal=s.is_internal,
            scored_at=s.scored_at,
            approval_status=s.approval_status,
            scorer_org_name=s.scorer_org.name if s.scorer_org else None,
            scored_by_name=s.scored_by.full_name if s.scored_by else None,
        ))

    return items


@router.get("/{kpi_id}", response_model=KPIResponse)
async def get_kpi(
    kpi_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """Get KPI by ID."""
    query = select(KPI).where(KPI.id == kpi_id)
    query = apply_tenant_filter_kpi(query, tenant_id)
    result = await db.execute(query)
    kpi = result.scalar_one_or_none()
    if not kpi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KPI not found",
        )

    return await _enrich_kpi_response(kpi, db)


@router.put("/{kpi_id}", response_model=KPIResponse)
async def update_kpi(
    kpi_id: UUID,
    data: KPIUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """Update a KPI."""
    query = select(KPI).where(KPI.id == kpi_id)
    query = apply_tenant_filter_kpi(query, tenant_id)
    result = await db.execute(query)
    kpi = result.scalar_one_or_none()
    if not kpi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KPI not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(kpi, field, value)

    await db.commit()
    await db.refresh(kpi)

    return await _enrich_kpi_response(kpi, db)


@router.delete("/{kpi_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kpi(
    kpi_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """Delete a KPI (soft delete)."""
    query = select(KPI).where(KPI.id == kpi_id)
    query = apply_tenant_filter_kpi(query, tenant_id)
    result = await db.execute(query)
    kpi = result.scalar_one_or_none()
    if not kpi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KPI not found",
        )

    kpi.is_active = False
    await db.commit()


# ===== Perception Scores =====

@router.get("/{kpi_id}/scores", response_model=PerceptionScoreListResponse)
async def list_perception_scores(
    kpi_id: UUID,
    period: Optional[str] = None,
    is_internal: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """List perception scores for a KPI."""
    # Verify KPI exists and belongs to tenant
    query = select(KPI).where(KPI.id == kpi_id)
    query = apply_tenant_filter_kpi(query, tenant_id)
    result = await db.execute(query)
    kpi = result.scalar_one_or_none()
    if not kpi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KPI not found",
        )

    query = select(PerceptionScore).where(
        PerceptionScore.kpi_id == kpi_id
    ).options(
        selectinload(PerceptionScore.scorer_org),
        selectinload(PerceptionScore.scored_by),
        selectinload(PerceptionScore.approver),
    )

    if period:
        query = query.where(PerceptionScore.period == period)

    if is_internal is not None:
        query = query.where(PerceptionScore.is_internal == is_internal)

    query = query.order_by(PerceptionScore.scored_at.desc())

    result = await db.execute(query)
    scores = result.scalars().all()

    return PerceptionScoreListResponse(
        items=[_score_to_response(s) for s in scores],
        total=len(scores),
    )


@router.post("/{kpi_id}/scores", response_model=PerceptionScoreResponse, status_code=status.HTTP_201_CREATED)
async def submit_perception_score(
    kpi_id: UUID,
    data: PerceptionScoreCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """Submit a perception score for a KPI."""
    # Get KPI with relationship
    result = await db.execute(
        select(KPI).where(KPI.id == kpi_id).options(
            selectinload(KPI.relationship)
        )
    )
    kpi = result.scalar_one_or_none()

    if not kpi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KPI not found",
        )

    # Determine scorer organization based on internal flag
    # For internal scores, use the "our side" org (org_a typically)
    # For external scores, use the "their side" org (org_b typically)
    if data.is_internal:
        scorer_org_id = kpi.relationship.org_a_id
    else:
        scorer_org_id = kpi.relationship.org_b_id

    score = PerceptionScore(
        kpi_id=kpi_id,
        scorer_org_id=scorer_org_id,
        scored_by_user_id=current_user.id,
        score=data.score,
        period=data.period,
        comments=data.comments,
        is_internal=data.is_internal,
        approval_status="pending_approval",
    )

    db.add(score)
    await db.commit()
    await db.refresh(score)

    # Recalculate gap for this period
    await _recalculate_gap(kpi_id, data.period, db)

    # Reload with relationships
    result = await db.execute(
        select(PerceptionScore).where(PerceptionScore.id == score.id).options(
            selectinload(PerceptionScore.scorer_org),
            selectinload(PerceptionScore.scored_by),
            selectinload(PerceptionScore.approver),
        )
    )
    score = result.scalar_one()

    return _score_to_response(score)


# ===== Score Approval Workflow =====

@router.post("/{kpi_id}/scores/{score_id}/approve", response_model=PerceptionScoreResponse)
async def approve_perception_score(
    kpi_id: UUID,
    score_id: UUID,
    data: ScoreApprovalAction,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """Approve a pending perception score.

    Only admin and legal roles can approve scores.
    After approval, the gap for this KPI/period is recalculated.
    """
    from app.models.user import Role
    if not current_user.is_super_admin and current_user.role not in [Role.ADMIN, Role.LEGAL]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin and legal users can approve scores",
        )

    result = await db.execute(
        select(PerceptionScore).where(
            PerceptionScore.id == score_id,
            PerceptionScore.kpi_id == kpi_id,
        ).options(
            selectinload(PerceptionScore.scorer_org),
            selectinload(PerceptionScore.scored_by),
            selectinload(PerceptionScore.approver),
        )
    )
    score = result.scalar_one_or_none()

    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Score not found",
        )

    if score.approval_status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Score is not pending approval (current status: {score.approval_status})",
        )

    score.approval_status = "approved"
    score.approved_by = current_user.id
    score.approved_at = datetime.utcnow()
    score.approval_comments = data.comments

    await db.commit()
    await db.refresh(score)

    # Recalculate gap now that this score is approved
    await _recalculate_gap(kpi_id, score.period, db)

    # Reload with relationships
    result = await db.execute(
        select(PerceptionScore).where(PerceptionScore.id == score.id).options(
            selectinload(PerceptionScore.scorer_org),
            selectinload(PerceptionScore.scored_by),
            selectinload(PerceptionScore.approver),
        )
    )
    score = result.scalar_one()

    return _score_to_response(score)


@router.post("/{kpi_id}/scores/{score_id}/reject", response_model=PerceptionScoreResponse)
async def reject_perception_score(
    kpi_id: UUID,
    score_id: UUID,
    data: ScoreApprovalAction,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """Reject a pending perception score.

    Only admin and legal roles can reject scores.
    Rejected scores are excluded from gap calculations.
    """
    from app.models.user import Role
    if not current_user.is_super_admin and current_user.role not in [Role.ADMIN, Role.LEGAL]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin and legal users can reject scores",
        )

    result = await db.execute(
        select(PerceptionScore).where(
            PerceptionScore.id == score_id,
            PerceptionScore.kpi_id == kpi_id,
        ).options(
            selectinload(PerceptionScore.scorer_org),
            selectinload(PerceptionScore.scored_by),
            selectinload(PerceptionScore.approver),
        )
    )
    score = result.scalar_one_or_none()

    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Score not found",
        )

    if score.approval_status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Score is not pending approval (current status: {score.approval_status})",
        )

    score.approval_status = "rejected"
    score.approved_by = current_user.id
    score.approved_at = datetime.utcnow()
    score.approval_comments = data.comments

    await db.commit()
    await db.refresh(score)

    # Reload with relationships
    result = await db.execute(
        select(PerceptionScore).where(PerceptionScore.id == score.id).options(
            selectinload(PerceptionScore.scorer_org),
            selectinload(PerceptionScore.scored_by),
            selectinload(PerceptionScore.approver),
        )
    )
    score = result.scalar_one()

    return _score_to_response(score)


# ===== Perception Gaps =====

@router.get("/{kpi_id}/gaps", response_model=PerceptionGapListResponse)
async def list_perception_gaps(
    kpi_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """List perception gaps for a KPI."""
    query = select(KPI).where(KPI.id == kpi_id)
    query = apply_tenant_filter_kpi(query, tenant_id)
    result = await db.execute(query)
    kpi = result.scalar_one_or_none()
    if not kpi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KPI not found",
        )

    result = await db.execute(
        select(PerceptionGap).where(
            PerceptionGap.kpi_id == kpi_id
        ).order_by(PerceptionGap.period.desc())
    )
    gaps = result.scalars().all()

    # Get unique periods
    periods = list(set(g.period for g in gaps))
    periods.sort(reverse=True)

    return PerceptionGapListResponse(
        items=[_gap_to_response(g, kpi) for g in gaps],
        total=len(gaps),
        periods=periods,
    )


# ===== Relationship-level endpoints =====

@router.get("/relationship/{rel_id}/gaps", response_model=PerceptionGapListResponse)
async def list_relationship_gaps(
    rel_id: UUID,
    period: Optional[str] = None,
    severity: Optional[GapSeverity] = None,
    requires_action: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """List all perception gaps for a relationship."""
    # Get KPIs for relationship
    kpi_query = select(KPI.id).where(
        KPI.relationship_id == rel_id,
        KPI.is_active == True,
    )

    query = select(PerceptionGap).where(
        PerceptionGap.kpi_id.in_(kpi_query)
    ).options(
        selectinload(PerceptionGap.kpi)
    )

    if period:
        query = query.where(PerceptionGap.period == period)

    if severity:
        query = query.where(PerceptionGap.gap_severity == severity)

    if requires_action is not None:
        query = query.where(PerceptionGap.requires_action == requires_action)

    query = query.order_by(PerceptionGap.gap_severity.desc(), PerceptionGap.period.desc())

    result = await db.execute(query)
    gaps = result.scalars().all()

    # Get unique periods
    periods = list(set(g.period for g in gaps))
    periods.sort(reverse=True)

    return PerceptionGapListResponse(
        items=[_gap_to_response(g, g.kpi) for g in gaps],
        total=len(gaps),
        periods=periods,
    )


@router.get("/relationship/{rel_id}/summary", response_model=GapSummary)
async def get_gap_summary(
    rel_id: UUID,
    period: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
):
    """Get summary of perception gaps for a relationship in a period."""
    # Get KPIs for relationship
    kpi_result = await db.execute(
        select(KPI).where(
            KPI.relationship_id == rel_id,
            KPI.is_active == True,
        )
    )
    kpis = kpi_result.scalars().all()

    # Get gaps for period
    kpi_ids = [k.id for k in kpis]
    gap_result = await db.execute(
        select(PerceptionGap).where(
            PerceptionGap.kpi_id.in_(kpi_ids),
            PerceptionGap.period == period,
        ).options(selectinload(PerceptionGap.kpi))
    )
    gaps = gap_result.scalars().all()

    # Calculate summary
    critical = sum(1 for g in gaps if g.gap_severity == GapSeverity.CRITICAL)
    significant = sum(1 for g in gaps if g.gap_severity == GapSeverity.SIGNIFICANT)
    moderate = sum(1 for g in gaps if g.gap_severity == GapSeverity.MODERATE)
    minor = sum(1 for g in gaps if g.gap_severity == GapSeverity.MINOR)

    avg_gap = None
    worst_gap = None
    worst_kpi = None
    if gaps:
        valid_gaps = [g for g in gaps if g.gap is not None]
        if valid_gaps:
            avg_gap = sum(abs(g.gap) for g in valid_gaps) / len(valid_gaps)
            worst = max(valid_gaps, key=lambda g: abs(g.gap))
            worst_gap = worst.gap
            worst_kpi = worst.kpi.name if worst.kpi else None

    return GapSummary(
        relationship_id=rel_id,
        period=period,
        total_kpis=len(kpis),
        scored_kpis=len(gaps),
        critical_gaps=critical,
        significant_gaps=significant,
        moderate_gaps=moderate,
        minor_gaps=minor,
        average_gap=Decimal(str(round(avg_gap, 2))) if avg_gap else None,
        worst_gap_kpi_name=worst_kpi,
        worst_gap_value=worst_gap,
    )


# ===== Helper Functions =====

async def _enrich_kpi_response(kpi: KPI, db: AsyncSession) -> KPIResponse:
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


async def _recalculate_gap(kpi_id: UUID, period: str, db: AsyncSession) -> None:
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


def _score_to_response(score: PerceptionScore) -> PerceptionScoreResponse:
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


def _gap_to_response(gap: PerceptionGap, kpi: KPI = None) -> PerceptionGapResponse:
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
