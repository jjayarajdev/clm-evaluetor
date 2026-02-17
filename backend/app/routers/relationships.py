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

router = APIRouter(prefix="/relationships", tags=["Relationships"])


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
            selectinload(BusinessRelationship.team_members).selectinload(RelationshipTeam.user),
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

    return _to_response(relationship, include_team=True)


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


# ===== Helper Functions =====

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
