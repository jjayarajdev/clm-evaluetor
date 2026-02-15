"""API endpoints for Improvement Point management (Evaluetor features)."""

from uuid import UUID
from datetime import datetime, date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_current_user, require_role
from app.models import (
    User,
    ImprovementPoint,
    ImprovementAction,
    ImprovementPriority,
    ImprovementStatus,
    ImprovementSource,
    ActionStatus,
    BusinessRelationship,
    KPI,
    PerceptionGap,
    GapSeverity,
)
from app.schemas.improvement import (
    ImprovementCreate,
    ImprovementUpdate,
    ImprovementResponse,
    ImprovementListResponse,
    ImprovementSummary,
    ActionCreate,
    ActionUpdate,
    ActionResponse,
)

router = APIRouter(prefix="/improvements", tags=["Improvements"])


# ===== Improvement CRUD =====

@router.get("", response_model=ImprovementListResponse)
async def list_improvements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    relationship_id: Optional[UUID] = None,
    status: Optional[List[ImprovementStatus]] = Query(None),
    priority: Optional[List[ImprovementPriority]] = Query(None),
    owner_id: Optional[UUID] = None,
    kpi_id: Optional[UUID] = None,
    overdue_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List improvement points with filtering and pagination."""
    query = select(ImprovementPoint).options(
        selectinload(ImprovementPoint.owner),
        selectinload(ImprovementPoint.kpi),
        selectinload(ImprovementPoint.relationship),
    )

    if relationship_id:
        query = query.where(ImprovementPoint.relationship_id == relationship_id)

    if status:
        query = query.where(ImprovementPoint.status.in_(status))

    if priority:
        query = query.where(ImprovementPoint.priority.in_(priority))

    if owner_id:
        query = query.where(ImprovementPoint.owner_id == owner_id)

    if kpi_id:
        query = query.where(ImprovementPoint.kpi_id == kpi_id)

    if overdue_only:
        query = query.where(
            and_(
                ImprovementPoint.due_date < date.today(),
                ImprovementPoint.status.in_([ImprovementStatus.OPEN, ImprovementStatus.IN_PROGRESS]),
            )
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination and ordering
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    query = query.order_by(
        ImprovementPoint.priority.desc(),
        ImprovementPoint.due_date.asc().nullslast(),
        ImprovementPoint.created_at.desc(),
    )

    result = await db.execute(query)
    items = result.scalars().all()

    return ImprovementListResponse(
        items=[await _to_response(i, db) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=ImprovementResponse, status_code=status.HTTP_201_CREATED)
async def create_improvement(
    data: ImprovementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Create a new improvement point."""
    # Verify relationship exists
    relationship = await db.get(BusinessRelationship, data.relationship_id)
    if not relationship:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Relationship not found",
        )

    # Verify KPI if provided
    if data.kpi_id:
        kpi = await db.get(KPI, data.kpi_id)
        if not kpi:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="KPI not found",
            )

    improvement = ImprovementPoint(**data.model_dump())
    db.add(improvement)
    await db.commit()
    await db.refresh(improvement)

    # Reload with relationships
    result = await db.execute(
        select(ImprovementPoint).where(ImprovementPoint.id == improvement.id).options(
            selectinload(ImprovementPoint.owner),
            selectinload(ImprovementPoint.kpi),
            selectinload(ImprovementPoint.relationship),
        )
    )
    improvement = result.scalar_one()

    return await _to_response(improvement, db)


@router.get("/{improvement_id}", response_model=ImprovementResponse)
async def get_improvement(
    improvement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get improvement point by ID."""
    result = await db.execute(
        select(ImprovementPoint).where(ImprovementPoint.id == improvement_id).options(
            selectinload(ImprovementPoint.owner),
            selectinload(ImprovementPoint.kpi),
            selectinload(ImprovementPoint.relationship),
            selectinload(ImprovementPoint.actions).selectinload(ImprovementAction.owner),
        )
    )
    improvement = result.scalar_one_or_none()

    if not improvement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Improvement point not found",
        )

    return await _to_response(improvement, db, include_actions=True)


@router.put("/{improvement_id}", response_model=ImprovementResponse)
async def update_improvement(
    improvement_id: UUID,
    data: ImprovementUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Update an improvement point."""
    result = await db.execute(
        select(ImprovementPoint).where(ImprovementPoint.id == improvement_id).options(
            selectinload(ImprovementPoint.owner),
            selectinload(ImprovementPoint.kpi),
            selectinload(ImprovementPoint.relationship),
        )
    )
    improvement = result.scalar_one_or_none()

    if not improvement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Improvement point not found",
        )

    update_data = data.model_dump(exclude_unset=True)

    # Handle status transitions
    if "status" in update_data:
        new_status = update_data["status"]
        if new_status == ImprovementStatus.IN_PROGRESS and not improvement.started_at:
            improvement.started_at = datetime.utcnow()
        elif new_status == ImprovementStatus.COMPLETED:
            improvement.completed_at = datetime.utcnow()

    for field, value in update_data.items():
        setattr(improvement, field, value)

    await db.commit()
    await db.refresh(improvement)

    return await _to_response(improvement, db)


@router.delete("/{improvement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_improvement(
    improvement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Delete an improvement point (sets status to cancelled)."""
    improvement = await db.get(ImprovementPoint, improvement_id)
    if not improvement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Improvement point not found",
        )

    improvement.status = ImprovementStatus.CANCELLED
    await db.commit()


# ===== Actions =====

@router.get("/{improvement_id}/actions", response_model=List[ActionResponse])
async def list_actions(
    improvement_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List actions for an improvement point."""
    improvement = await db.get(ImprovementPoint, improvement_id)
    if not improvement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Improvement point not found",
        )

    result = await db.execute(
        select(ImprovementAction).where(
            ImprovementAction.improvement_id == improvement_id
        ).options(
            selectinload(ImprovementAction.owner)
        ).order_by(ImprovementAction.sequence.asc().nullslast(), ImprovementAction.created_at)
    )
    actions = result.scalars().all()

    return [_action_to_response(a) for a in actions]


@router.post("/{improvement_id}/actions", response_model=ActionResponse, status_code=status.HTTP_201_CREATED)
async def add_action(
    improvement_id: UUID,
    data: ActionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Add an action to an improvement point."""
    improvement = await db.get(ImprovementPoint, improvement_id)
    if not improvement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Improvement point not found",
        )

    action = ImprovementAction(
        improvement_id=improvement_id,
        **data.model_dump(),
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)

    # Reload with owner
    result = await db.execute(
        select(ImprovementAction).where(ImprovementAction.id == action.id).options(
            selectinload(ImprovementAction.owner)
        )
    )
    action = result.scalar_one()

    return _action_to_response(action)


@router.put("/{improvement_id}/actions/{action_id}", response_model=ActionResponse)
async def update_action(
    improvement_id: UUID,
    action_id: UUID,
    data: ActionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Update an action."""
    result = await db.execute(
        select(ImprovementAction).where(
            ImprovementAction.id == action_id,
            ImprovementAction.improvement_id == improvement_id,
        ).options(selectinload(ImprovementAction.owner))
    )
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found",
        )

    update_data = data.model_dump(exclude_unset=True)

    # Handle status transitions
    if "status" in update_data:
        new_status = update_data["status"]
        if new_status == ActionStatus.IN_PROGRESS and not action.started_at:
            action.started_at = datetime.utcnow()
        elif new_status == ActionStatus.COMPLETED:
            action.completed_at = datetime.utcnow()

    for field, value in update_data.items():
        setattr(action, field, value)

    await db.commit()
    await db.refresh(action)

    return _action_to_response(action)


@router.delete("/{improvement_id}/actions/{action_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_action(
    improvement_id: UUID,
    action_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Delete an action."""
    result = await db.execute(
        select(ImprovementAction).where(
            ImprovementAction.id == action_id,
            ImprovementAction.improvement_id == improvement_id,
        )
    )
    action = result.scalar_one_or_none()

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found",
        )

    await db.delete(action)
    await db.commit()


# ===== Summary =====

@router.get("/relationship/{rel_id}/summary", response_model=ImprovementSummary)
async def get_improvement_summary(
    rel_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get summary of improvements for a relationship."""
    result = await db.execute(
        select(ImprovementPoint).where(ImprovementPoint.relationship_id == rel_id)
    )
    improvements = result.scalars().all()

    today = date.today()

    return ImprovementSummary(
        relationship_id=rel_id,
        total=len(improvements),
        open=sum(1 for i in improvements if i.status == ImprovementStatus.OPEN),
        in_progress=sum(1 for i in improvements if i.status == ImprovementStatus.IN_PROGRESS),
        blocked=sum(1 for i in improvements if i.status == ImprovementStatus.BLOCKED),
        completed=sum(1 for i in improvements if i.status == ImprovementStatus.COMPLETED),
        cancelled=sum(1 for i in improvements if i.status == ImprovementStatus.CANCELLED),
        overdue=sum(1 for i in improvements if i.due_date and i.due_date < today and i.status in [ImprovementStatus.OPEN, ImprovementStatus.IN_PROGRESS]),
        critical_priority=sum(1 for i in improvements if i.priority == ImprovementPriority.CRITICAL and i.status not in [ImprovementStatus.COMPLETED, ImprovementStatus.CANCELLED]),
        high_priority=sum(1 for i in improvements if i.priority == ImprovementPriority.HIGH and i.status not in [ImprovementStatus.COMPLETED, ImprovementStatus.CANCELLED]),
    )


# ===== Auto-generate from gaps =====

@router.post("/generate-from-gaps", response_model=List[ImprovementResponse])
async def generate_from_gaps(
    relationship_id: UUID,
    period: str = Query(...),
    min_severity: GapSeverity = Query(GapSeverity.SIGNIFICANT),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Auto-generate improvement points from perception gaps."""
    # Get gaps that meet severity threshold
    kpi_query = select(KPI.id).where(KPI.relationship_id == relationship_id)

    severity_order = {
        GapSeverity.MINOR: 0,
        GapSeverity.MODERATE: 1,
        GapSeverity.SIGNIFICANT: 2,
        GapSeverity.CRITICAL: 3,
    }
    min_severity_val = severity_order[min_severity]
    valid_severities = [s for s, v in severity_order.items() if v >= min_severity_val]

    result = await db.execute(
        select(PerceptionGap).where(
            PerceptionGap.kpi_id.in_(kpi_query),
            PerceptionGap.period == period,
            PerceptionGap.gap_severity.in_(valid_severities),
        ).options(selectinload(PerceptionGap.kpi))
    )
    gaps = result.scalars().all()

    created = []
    for gap in gaps:
        # Check if improvement already exists for this gap
        existing = await db.execute(
            select(ImprovementPoint).where(ImprovementPoint.gap_id == gap.id)
        )
        if existing.scalar_one_or_none():
            continue

        # Create improvement
        priority = ImprovementPriority.HIGH if gap.gap_severity == GapSeverity.CRITICAL else ImprovementPriority.MEDIUM

        improvement = ImprovementPoint(
            relationship_id=relationship_id,
            kpi_id=gap.kpi_id,
            gap_id=gap.id,
            title=f"Address {gap.kpi.name} perception gap ({period})",
            description=f"Internal score: {gap.internal_score}, External score: {gap.external_score}, Gap: {gap.gap}",
            source=ImprovementSource.PERCEPTION_GAP,
            priority=priority,
            status=ImprovementStatus.OPEN,
        )
        db.add(improvement)
        await db.flush()
        created.append(improvement)

    await db.commit()

    # Reload with relationships
    responses = []
    for imp in created:
        result = await db.execute(
            select(ImprovementPoint).where(ImprovementPoint.id == imp.id).options(
                selectinload(ImprovementPoint.owner),
                selectinload(ImprovementPoint.kpi),
                selectinload(ImprovementPoint.relationship),
            )
        )
        imp = result.scalar_one()
        responses.append(await _to_response(imp, db))

    return responses


# ===== Helper Functions =====

async def _to_response(
    improvement: ImprovementPoint,
    db: AsyncSession,
    include_actions: bool = False,
) -> ImprovementResponse:
    """Convert improvement model to response."""
    # Count actions
    action_count_result = await db.execute(
        select(func.count()).where(ImprovementAction.improvement_id == improvement.id)
    )
    action_count = action_count_result.scalar() or 0

    completed_action_result = await db.execute(
        select(func.count()).where(
            ImprovementAction.improvement_id == improvement.id,
            ImprovementAction.status == ActionStatus.COMPLETED,
        )
    )
    completed_action_count = completed_action_result.scalar() or 0

    progress = 0
    if action_count > 0:
        progress = int((completed_action_count / action_count) * 100)

    response = ImprovementResponse(
        id=improvement.id,
        relationship_id=improvement.relationship_id,
        kpi_id=improvement.kpi_id,
        gap_id=improvement.gap_id,
        title=improvement.title,
        description=improvement.description,
        source=improvement.source,
        priority=improvement.priority,
        status=improvement.status,
        owner_id=improvement.owner_id,
        assigned_org_id=improvement.assigned_org_id,
        due_date=improvement.due_date,
        target_outcome=improvement.target_outcome,
        started_at=improvement.started_at,
        completed_at=improvement.completed_at,
        actual_outcome=improvement.actual_outcome,
        impact_score=improvement.impact_score,
        created_at=improvement.created_at,
        updated_at=improvement.updated_at,
        progress_percentage=progress,
        action_count=action_count,
        completed_action_count=completed_action_count,
        owner_name=improvement.owner.full_name if improvement.owner else None,
        kpi_name=improvement.kpi.name if improvement.kpi else None,
        relationship_name=improvement.relationship.name if improvement.relationship else None,
    )

    if include_actions and hasattr(improvement, 'actions'):
        response.actions = [_action_to_response(a) for a in improvement.actions]

    return response


def _action_to_response(action: ImprovementAction) -> ActionResponse:
    """Convert action model to response."""
    return ActionResponse(
        id=action.id,
        improvement_id=action.improvement_id,
        description=action.description,
        status=action.status,
        sequence=action.sequence,
        owner_id=action.owner_id,
        due_date=action.due_date,
        started_at=action.started_at,
        completed_at=action.completed_at,
        notes=action.notes,
        blocker_reason=action.blocker_reason,
        created_at=action.created_at,
        updated_at=action.updated_at,
        owner_name=action.owner.full_name if action.owner else None,
    )
