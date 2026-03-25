"""API endpoints for Business Relationship management (Evaluetor features)."""

from uuid import UUID
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.deps import get_current_user, require_role, CurrentTenantId, RequiredTenantId
from app.models import (
    User,
    Organization,
    BusinessRelationship,
    RelationshipTeam,
    RelationshipType,
    RelationshipStatus,
    TeamRole,
    RelationshipStatusHistory,
    PerformanceStatus,
)
from app.schemas.relationship import (
    RelationshipCreate,
    RelationshipUpdate,
    RelationshipResponse,
    RelationshipListResponse,
    TeamMemberCreate,
    TeamMemberUpdate,
    TeamMemberResponse,
    HealthScoreResponse,
    HealthScoreBreakdown,
)
from app.schemas.relationship_history import (
    RelationshipHistoryCreate,
    RelationshipHistoryResponse,
    RelationshipHistoryListResponse,
    PerformanceTrendPoint,
    PerformanceTrendResponse,
)

router = APIRouter(prefix="/api/relationships", tags=["Relationships"])


def apply_tenant_filter(query, tenant_id):
    """Apply tenant filter to BusinessRelationship query if tenant_id is set."""
    if tenant_id is not None:
        return query.where(BusinessRelationship.tenant_id == tenant_id)
    return query


@router.get("", response_model=RelationshipListResponse)
async def list_relationships(
    tenant_id: CurrentTenantId,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    relationship_type: Optional[RelationshipType] = None,
    status: Optional[RelationshipStatus] = None,
    org_id: Optional[UUID] = None,
    my_relationships: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List business relationships with filtering and pagination."""
    query = select(BusinessRelationship).options(
        selectinload(BusinessRelationship.org_a),
        selectinload(BusinessRelationship.org_b),
    )
    query = apply_tenant_filter(query, tenant_id)

    # Filter by organization
    if org_id:
        query = query.where(
            or_(
                BusinessRelationship.org_a_id == org_id,
                BusinessRelationship.org_b_id == org_id,
            )
        )

    # Filter by user's relationships (where they're a team member)
    if my_relationships:
        team_subquery = select(RelationshipTeam.relationship_id).where(
            RelationshipTeam.user_id == current_user.id,
            RelationshipTeam.is_active == True,
        )
        query = query.where(BusinessRelationship.id.in_(team_subquery))

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            or_(
                BusinessRelationship.name.ilike(search_filter),
            )
        )

    if relationship_type:
        query = query.where(BusinessRelationship.relationship_type == relationship_type)

    if status:
        query = query.where(BusinessRelationship.status == status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(BusinessRelationship.created_at.desc())

    result = await db.execute(query)
    items = result.scalars().all()

    return RelationshipListResponse(
        items=[_to_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
async def create_relationship(
    data: RelationshipCreate,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Create a new business relationship."""
    # Validate organizations exist
    org_a = await db.get(Organization, data.org_a_id)
    org_b = await db.get(Organization, data.org_b_id)

    if not org_a:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization A not found: {data.org_a_id}",
        )
    if not org_b:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization B not found: {data.org_b_id}",
        )

    if data.org_a_id == data.org_b_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create relationship between same organization",
        )

    relationship = BusinessRelationship(tenant_id=tenant_id, **data.model_dump())
    relationship.status = RelationshipStatus.ACTIVE

    db.add(relationship)
    await db.commit()
    await db.refresh(relationship)

    # Reload with organizations
    result = await db.execute(
        select(BusinessRelationship)
        .where(BusinessRelationship.id == relationship.id)
        .options(
            selectinload(BusinessRelationship.org_a),
            selectinload(BusinessRelationship.org_b),
        )
    )
    relationship = result.scalar_one()

    return _to_response(relationship)


@router.get("/{rel_id}", response_model=RelationshipResponse)
async def get_relationship(
    rel_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get relationship by ID."""
    query = (
        select(BusinessRelationship)
        .where(BusinessRelationship.id == rel_id)
        .options(
            selectinload(BusinessRelationship.org_a),
            selectinload(BusinessRelationship.org_b),
        )
    )
    query = apply_tenant_filter(query, tenant_id)
    result = await db.execute(query)
    relationship = result.scalar_one_or_none()

    if not relationship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )

    # Load team members separately (dynamic relationship can't use selectinload)
    team_query = (
        select(RelationshipTeam)
        .where(RelationshipTeam.relationship_id == rel_id, RelationshipTeam.is_active == True)
        .options(selectinload(RelationshipTeam.user))
    )
    team_result = await db.execute(team_query)
    team_members = team_result.scalars().all()

    response = _to_response(relationship, include_team=False)
    response.team_members = [_team_to_response(m) for m in team_members]
    return response


@router.put("/{rel_id}", response_model=RelationshipResponse)
async def update_relationship(
    rel_id: UUID,
    data: RelationshipUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Update a relationship."""
    query = (
        select(BusinessRelationship)
        .where(BusinessRelationship.id == rel_id)
        .options(
            selectinload(BusinessRelationship.org_a),
            selectinload(BusinessRelationship.org_b),
        )
    )
    query = apply_tenant_filter(query, tenant_id)
    result = await db.execute(query)
    relationship = result.scalar_one_or_none()

    if not relationship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(relationship, field, value)

    await db.commit()
    await db.refresh(relationship)

    return _to_response(relationship)


# ===== Team Management =====

@router.get("/{rel_id}/team", response_model=List[TeamMemberResponse])
async def get_team_members(
    rel_id: UUID,
    active_only: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get team members for a relationship."""
    query = select(RelationshipTeam).where(
        RelationshipTeam.relationship_id == rel_id
    ).options(selectinload(RelationshipTeam.user))

    if active_only:
        query = query.where(RelationshipTeam.is_active == True)

    result = await db.execute(query)
    members = result.scalars().all()

    return [_team_to_response(m) for m in members]


@router.post("/{rel_id}/team", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_team_member(
    rel_id: UUID,
    data: TeamMemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Add a team member to a relationship."""
    # Verify relationship exists
    relationship = await db.get(BusinessRelationship, rel_id)
    if not relationship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )

    # Verify user exists
    user = await db.get(User, data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    # Check if already a member
    existing = await db.execute(
        select(RelationshipTeam).where(
            RelationshipTeam.relationship_id == rel_id,
            RelationshipTeam.user_id == data.user_id,
            RelationshipTeam.is_active == True,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a team member",
        )

    member = RelationshipTeam(
        relationship_id=rel_id,
        **data.model_dump(),
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    # Reload with user
    result = await db.execute(
        select(RelationshipTeam)
        .where(RelationshipTeam.id == member.id)
        .options(selectinload(RelationshipTeam.user))
    )
    member = result.scalar_one()

    return _team_to_response(member)


@router.put("/{rel_id}/team/{member_id}", response_model=TeamMemberResponse)
async def update_team_member(
    rel_id: UUID,
    member_id: UUID,
    data: TeamMemberUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Update a team member."""
    result = await db.execute(
        select(RelationshipTeam)
        .where(
            RelationshipTeam.id == member_id,
            RelationshipTeam.relationship_id == rel_id,
        )
        .options(selectinload(RelationshipTeam.user))
    )
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    update_data = data.model_dump(exclude_unset=True)

    # Handle deactivation
    if update_data.get("is_active") is False:
        update_data["left_at"] = datetime.utcnow()

    for field, value in update_data.items():
        setattr(member, field, value)

    await db.commit()
    await db.refresh(member)

    return _team_to_response(member)


@router.delete("/{rel_id}/team/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    rel_id: UUID,
    member_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Remove a team member (soft delete)."""
    result = await db.execute(
        select(RelationshipTeam).where(
            RelationshipTeam.id == member_id,
            RelationshipTeam.relationship_id == rel_id,
        )
    )
    member = result.scalar_one_or_none()

    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    member.is_active = False
    member.left_at = datetime.utcnow()
    await db.commit()


# ===== Health Score =====

@router.get("/{rel_id}/health", response_model=HealthScoreResponse)
async def get_health_score(
    rel_id: UUID,
    recalculate: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get health score for a relationship."""
    relationship = await db.get(BusinessRelationship, rel_id)

    if not relationship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )

    # TODO: Implement actual health score calculation service
    # For now, return cached or default score
    breakdown = HealthScoreBreakdown(
        compliance_score=None,
        sla_score=None,
        perception_score=None,
        improvement_score=None,
        overall_score=relationship.health_score or 0,
        calculated_at=relationship.last_health_calculation or datetime.utcnow(),
    )

    return HealthScoreResponse(
        relationship_id=rel_id,
        health_score=relationship.health_score or 0,
        breakdown=breakdown,
        trend=None,
        factors=None,
    )


# ===== Performance Status History =====

@router.get("/{rel_id}/history", response_model=RelationshipHistoryListResponse)
async def list_status_history(
    rel_id: UUID,
    tenant_id: CurrentTenantId,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List relationship performance status history entries (paginated, newest first)."""
    # Verify relationship exists
    rel_query = select(BusinessRelationship).where(BusinessRelationship.id == rel_id)
    rel_query = apply_tenant_filter(rel_query, tenant_id)
    rel_result = await db.execute(rel_query)
    relationship = rel_result.scalar_one_or_none()
    if not relationship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )

    # Count total
    count_query = select(func.count()).select_from(RelationshipStatusHistory).where(
        RelationshipStatusHistory.relationship_id == rel_id
    )
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch paginated results
    offset = (page - 1) * page_size
    query = (
        select(RelationshipStatusHistory)
        .where(RelationshipStatusHistory.relationship_id == rel_id)
        .options(selectinload(RelationshipStatusHistory.recorded_by_user))
        .order_by(RelationshipStatusHistory.recorded_date.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(query)
    items = result.scalars().all()

    return RelationshipHistoryListResponse(
        items=[_history_to_response(h) for h in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


@router.post("/{rel_id}/history", response_model=RelationshipHistoryResponse, status_code=status.HTTP_201_CREATED)
async def record_status_history(
    rel_id: UUID,
    data: RelationshipHistoryCreate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually record a relationship performance status entry."""
    # Verify relationship exists and belongs to tenant
    rel_query = select(BusinessRelationship).where(BusinessRelationship.id == rel_id)
    rel_query = apply_tenant_filter(rel_query, tenant_id)
    rel_result = await db.execute(rel_query)
    relationship = rel_result.scalar_one_or_none()
    if not relationship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )

    # If no previous_status is provided, look up the latest entry
    previous_status = data.previous_status
    if previous_status is None:
        latest_query = (
            select(RelationshipStatusHistory)
            .where(RelationshipStatusHistory.relationship_id == rel_id)
            .order_by(RelationshipStatusHistory.recorded_date.desc())
            .limit(1)
        )
        latest_result = await db.execute(latest_query)
        latest = latest_result.scalar_one_or_none()
        if latest:
            previous_status = latest.status

    # Determine tenant_id for the record
    record_tenant_id = tenant_id if tenant_id else relationship.tenant_id

    history = RelationshipStatusHistory(
        tenant_id=record_tenant_id,
        relationship_id=rel_id,
        status=data.status.value,
        previous_status=previous_status.value if previous_status else None,
        overall_score=data.overall_score,
        period=data.period,
        recorded_by=current_user.id,
        notes=data.notes,
        trigger=data.trigger or "manual",
    )

    db.add(history)
    await db.commit()
    await db.refresh(history)

    # Reload with relationships
    result = await db.execute(
        select(RelationshipStatusHistory)
        .where(RelationshipStatusHistory.id == history.id)
        .options(selectinload(RelationshipStatusHistory.recorded_by_user))
    )
    history = result.scalar_one()

    return _history_to_response(history)


@router.get("/{rel_id}/performance-trend", response_model=PerformanceTrendResponse)
async def get_performance_trend(
    rel_id: UUID,
    tenant_id: CurrentTenantId,
    limit: int = Query(12, ge=1, le=100, description="Max number of periods to return"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get performance trend data for charting.

    Returns a list of {period, score, status} sorted by period ascending.
    """
    # Verify relationship exists
    rel_query = select(BusinessRelationship).where(BusinessRelationship.id == rel_id)
    rel_query = apply_tenant_filter(rel_query, tenant_id)
    rel_result = await db.execute(rel_query)
    relationship = rel_result.scalar_one_or_none()
    if not relationship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found",
        )

    # Get history entries sorted by period
    query = (
        select(RelationshipStatusHistory)
        .where(RelationshipStatusHistory.relationship_id == rel_id)
        .order_by(RelationshipStatusHistory.period.asc(), RelationshipStatusHistory.recorded_date.asc())
    )
    result = await db.execute(query)
    entries = result.scalars().all()

    # Deduplicate by period (take the latest entry for each period)
    period_map = {}
    for entry in entries:
        period_map[entry.period] = entry

    # Sort by period and limit
    sorted_periods = sorted(period_map.keys())
    if len(sorted_periods) > limit:
        sorted_periods = sorted_periods[-limit:]

    trend = []
    for period in sorted_periods:
        entry = period_map[period]
        trend.append(PerformanceTrendPoint(
            period=period,
            score=entry.overall_score,
            status=entry.status,
        ))

    return PerformanceTrendResponse(
        relationship_id=rel_id,
        trend=trend,
        total_entries=len(entries),
    )


# ===== Helper Functions =====

def _history_to_response(history: RelationshipStatusHistory) -> RelationshipHistoryResponse:
    """Convert history model to response schema."""
    return RelationshipHistoryResponse(
        id=history.id,
        tenant_id=history.tenant_id,
        relationship_id=history.relationship_id,
        status=history.status,
        previous_status=history.previous_status,
        overall_score=history.overall_score,
        period=history.period,
        recorded_date=history.recorded_date,
        recorded_by=history.recorded_by,
        notes=history.notes,
        trigger=history.trigger,
        created_at=history.created_at,
        recorded_by_name=history.recorded_by_user.full_name if history.recorded_by_user else None,
    )


def _to_response(relationship: BusinessRelationship, include_team: bool = False) -> RelationshipResponse:
    """Convert relationship model to response schema."""
    from app.schemas.organization import OrganizationSummary

    response = RelationshipResponse(
        id=relationship.id,
        org_a_id=relationship.org_a_id,
        org_b_id=relationship.org_b_id,
        relationship_type=relationship.relationship_type,
        status=relationship.status,
        name=relationship.name,
        description=relationship.description,
        health_score=relationship.health_score,
        last_health_calculation=relationship.last_health_calculation,
        governance_tier=relationship.governance_tier,
        governance_config=relationship.governance_config,
        start_date=relationship.start_date,
        review_frequency_days=relationship.review_frequency_days,
        next_review_date=relationship.next_review_date,
        created_at=relationship.created_at,
        updated_at=relationship.updated_at,
    )

    if relationship.org_a:
        response.org_a = OrganizationSummary(
            id=relationship.org_a.id,
            name=relationship.org_a.name,
            code=relationship.org_a.code,
            org_type=relationship.org_a.org_type,
        )

    if relationship.org_b:
        response.org_b = OrganizationSummary(
            id=relationship.org_b.id,
            name=relationship.org_b.name,
            code=relationship.org_b.code,
            org_type=relationship.org_b.org_type,
        )

    if include_team and hasattr(relationship, 'team_members'):
        response.team_members = [_team_to_response(m) for m in relationship.team_members if m.is_active]

    return response


def _team_to_response(member: RelationshipTeam) -> TeamMemberResponse:
    """Convert team member model to response schema."""
    return TeamMemberResponse(
        id=member.id,
        relationship_id=member.relationship_id,
        user_id=member.user_id,
        role=member.role,
        responsibilities=member.responsibilities,
        is_primary=member.is_primary,
        is_active=member.is_active,
        joined_at=member.joined_at,
        left_at=member.left_at,
        user_name=member.user.full_name if member.user else None,
    )
