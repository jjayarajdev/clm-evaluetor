"""API endpoints for Business Unit management."""

from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_user, require_role, RequiredTenantId
from app.models import User, Role
from app.models.business_unit import BusinessUnit
from app.schemas.business_unit import (
    BusinessUnitCreate,
    BusinessUnitUpdate,
    BusinessUnitResponse,
    BusinessUnitListResponse,
    BusinessUnitWithHierarchy,
    BusinessUnitTree,
    BusinessUnitSummary,
)

router = APIRouter(prefix="/api/business-units", tags=["Business Units"])


async def _get_descendant_ids(db: AsyncSession, bu_id: UUID) -> set[UUID]:
    """Get all descendant BU IDs via a recursive query.

    Must not use BusinessUnit.get_all_child_ids() here: its recursive
    relationship walk triggers lazy loads outside the async greenlet
    (MissingGreenlet), which 500s the request.
    """
    result = await db.execute(
        text("""
            WITH RECURSIVE descendants AS (
                SELECT id FROM business_units WHERE parent_id = :bu_id
                UNION ALL
                SELECT b.id FROM business_units b
                JOIN descendants d ON b.parent_id = d.id
            )
            SELECT id FROM descendants
        """),
        {"bu_id": bu_id},
    )
    return {row[0] for row in result}


@router.get("", response_model=BusinessUnitListResponse)
async def list_business_units(
    tenant_id: RequiredTenantId,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_active: Optional[bool] = True,
    parent_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List business units with filtering and pagination."""
    query = select(BusinessUnit).where(BusinessUnit.tenant_id == tenant_id)

    # Apply filters
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            or_(
                BusinessUnit.name.ilike(search_filter),
                BusinessUnit.code.ilike(search_filter),
            )
        )

    if is_active is not None:
        query = query.where(BusinessUnit.is_active == is_active)

    if parent_id is not None:
        query = query.where(BusinessUnit.parent_id == parent_id)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(BusinessUnit.name)

    result = await db.execute(query)
    items = result.scalars().all()

    return BusinessUnitListResponse(
        items=[BusinessUnitResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/tree", response_model=List[BusinessUnitTree])
async def get_business_unit_tree(
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get business units as a hierarchical tree structure."""
    # Get all BUs for the tenant
    query = select(BusinessUnit).where(
        BusinessUnit.tenant_id == tenant_id,
        BusinessUnit.is_active == True,
    )
    result = await db.execute(query)
    all_bus = list(result.scalars().all())

    # Build a map of BUs by ID
    bu_map = {bu.id: bu for bu in all_bus}

    # Build tree structure
    def build_tree(bu: BusinessUnit) -> BusinessUnitTree:
        children = [
            build_tree(child)
            for child in all_bus
            if child.parent_id == bu.id
        ]
        return BusinessUnitTree(
            id=bu.id,
            name=bu.name,
            code=bu.code,
            description=bu.description,
            is_active=bu.is_active,
            head_user_id=bu.head_user_id,
            industry_profile_id=bu.industry_profile_id,
            effective_profile_name=bu.effective_profile_name,
            children=children,
        )

    # Get root BUs (no parent)
    root_bus = [bu for bu in all_bus if bu.parent_id is None]
    return [build_tree(bu) for bu in root_bus]


@router.post("", response_model=BusinessUnitResponse, status_code=status.HTTP_201_CREATED)
async def create_business_unit(
    data: BusinessUnitCreate,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Create a new business unit. Requires ADMIN role."""
    # Check for duplicate code within tenant
    existing_query = select(BusinessUnit).where(
        BusinessUnit.tenant_id == tenant_id,
        BusinessUnit.code == data.code,
    )
    existing = await db.execute(existing_query)
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Business unit with code '{data.code}' already exists",
        )

    # Validate parent_id if provided
    if data.parent_id:
        parent_query = select(BusinessUnit).where(
            BusinessUnit.id == data.parent_id,
            BusinessUnit.tenant_id == tenant_id,
        )
        parent = (await db.execute(parent_query)).scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent business unit not found",
            )

    # Validate head_user_id if provided
    if data.head_user_id:
        head_query = select(User).where(
            User.id == data.head_user_id,
            User.tenant_id == tenant_id,
        )
        head = (await db.execute(head_query)).scalar_one_or_none()
        if not head:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Head user not found",
            )

    bu = BusinessUnit(tenant_id=tenant_id, **data.model_dump())
    db.add(bu)
    await db.commit()
    await db.refresh(bu)

    return BusinessUnitResponse.model_validate(bu)


@router.get("/{bu_id}", response_model=BusinessUnitWithHierarchy)
async def get_business_unit(
    bu_id: UUID,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get business unit by ID with hierarchy info."""
    query = select(BusinessUnit).where(
        BusinessUnit.id == bu_id,
        BusinessUnit.tenant_id == tenant_id,
    )
    result = await db.execute(query)
    bu = result.scalar_one_or_none()

    if not bu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business unit not found",
        )

    # Get parent info
    parent_summary = None
    if bu.parent:
        parent_summary = BusinessUnitSummary.model_validate(bu.parent)

    # Get children
    children_query = select(BusinessUnit).where(
        BusinessUnit.parent_id == bu_id,
        BusinessUnit.is_active == True,
    )
    children_result = await db.execute(children_query)
    children = [BusinessUnitSummary.model_validate(c) for c in children_result.scalars().all()]

    return BusinessUnitWithHierarchy(
        **BusinessUnitResponse.model_validate(bu).model_dump(),
        parent=parent_summary,
        children=children,
        full_path=bu.full_path,
    )


@router.put("/{bu_id}", response_model=BusinessUnitResponse)
async def update_business_unit(
    bu_id: UUID,
    data: BusinessUnitUpdate,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Update a business unit. Requires ADMIN role."""
    query = select(BusinessUnit).where(
        BusinessUnit.id == bu_id,
        BusinessUnit.tenant_id == tenant_id,
    )
    result = await db.execute(query)
    bu = result.scalar_one_or_none()

    if not bu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business unit not found",
        )

    # Check for duplicate code if changing
    if data.code and data.code != bu.code:
        conflict_query = select(BusinessUnit).where(
            BusinessUnit.tenant_id == tenant_id,
            BusinessUnit.code == data.code,
            BusinessUnit.id != bu_id,
        )
        existing = await db.execute(conflict_query)
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Business unit with code '{data.code}' already exists",
            )

    # Validate parent_id if changing
    if data.parent_id is not None and data.parent_id != bu.parent_id:
        if data.parent_id == bu_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Business unit cannot be its own parent",
            )
        parent_query = select(BusinessUnit).where(
            BusinessUnit.id == data.parent_id,
            BusinessUnit.tenant_id == tenant_id,
        )
        parent = (await db.execute(parent_query)).scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent business unit not found",
            )
        # Check for circular reference
        if data.parent_id in await _get_descendant_ids(db, bu_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot set a child as parent (circular reference)",
            )

    # Validate head_user_id if changing
    if data.head_user_id is not None and data.head_user_id != bu.head_user_id:
        head_query = select(User).where(
            User.id == data.head_user_id,
            User.tenant_id == tenant_id,
        )
        head = (await db.execute(head_query)).scalar_one_or_none()
        if not head:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Head user not found",
            )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(bu, field, value)

    await db.commit()
    await db.refresh(bu)

    return BusinessUnitResponse.model_validate(bu)


@router.delete("/{bu_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_business_unit(
    bu_id: UUID,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
):
    """Deactivate a business unit. Requires ADMIN role."""
    query = select(BusinessUnit).where(
        BusinessUnit.id == bu_id,
        BusinessUnit.tenant_id == tenant_id,
    )
    result = await db.execute(query)
    bu = result.scalar_one_or_none()

    if not bu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business unit not found",
        )

    # Check for active children
    children_query = select(func.count()).select_from(BusinessUnit).where(
        BusinessUnit.parent_id == bu_id,
        BusinessUnit.is_active == True,
    )
    active_children = (await db.execute(children_query)).scalar() or 0
    if active_children > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot deactivate business unit with {active_children} active children",
        )

    # Soft delete (deactivate)
    bu.is_active = False
    await db.commit()


@router.get("/{bu_id}/users", response_model=List[dict])
async def get_business_unit_users(
    bu_id: UUID,
    tenant_id: RequiredTenantId,
    include_inactive: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get users assigned to a business unit."""
    # Verify BU exists
    bu_query = select(BusinessUnit).where(
        BusinessUnit.id == bu_id,
        BusinessUnit.tenant_id == tenant_id,
    )
    bu = (await db.execute(bu_query)).scalar_one_or_none()
    if not bu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business unit not found",
        )

    # Get users
    users_query = select(User).where(User.business_unit_id == bu_id)
    if not include_inactive:
        users_query = users_query.where(User.is_active == True)

    result = await db.execute(users_query)
    users = result.scalars().all()

    return [
        {
            "id": str(u.id),
            "username": u.username,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role.value,
            "is_active": u.is_active,
        }
        for u in users
    ]


@router.get("/{bu_id}/contracts", response_model=dict)
async def get_business_unit_contracts_summary(
    bu_id: UUID,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get summary of contracts in a business unit."""
    from app.models import Contract, ContractStatus

    # Verify BU exists
    bu_query = select(BusinessUnit).where(
        BusinessUnit.id == bu_id,
        BusinessUnit.tenant_id == tenant_id,
    )
    bu = (await db.execute(bu_query)).scalar_one_or_none()
    if not bu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business unit not found",
        )

    # Get contract counts by status
    count_query = select(
        func.count().label('total'),
        func.sum(func.cast(Contract.status == ContractStatus.COMPLETED, func.Integer())).label('completed'),
        func.sum(func.cast(Contract.status == ContractStatus.PROCESSING, func.Integer())).label('processing'),
        func.sum(func.cast(Contract.status == ContractStatus.PENDING, func.Integer())).label('pending'),
    ).where(Contract.business_unit_id == bu_id)

    result = (await db.execute(count_query)).first()

    return {
        "business_unit_id": str(bu_id),
        "business_unit_name": bu.name,
        "contracts": {
            "total": result.total or 0,
            "completed": result.completed or 0,
            "processing": result.processing or 0,
            "pending": result.pending or 0,
        },
    }


@router.patch("/{bu_id}/profile")
async def assign_bu_profile(
    bu_id: UUID,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
    profile_id: Optional[UUID] = Query(None, description="Industry profile ID, or null to inherit from tenant"),
):
    """Assign an industry profile to a business unit.

    Pass profile_id=null to clear the BU-level override and fall back to tenant profile.
    """
    from app.models.industry_profile import IndustryProfile

    query = select(BusinessUnit).where(
        BusinessUnit.id == bu_id,
        BusinessUnit.tenant_id == tenant_id,
    )
    bu = (await db.execute(query)).scalar_one_or_none()
    if not bu:
        raise HTTPException(status_code=404, detail="Business unit not found")

    if profile_id:
        # Validate profile exists
        profile = (await db.execute(
            select(IndustryProfile).where(IndustryProfile.id == profile_id)
        )).scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail="Industry profile not found")
        bu.industry_profile_id = profile_id
        profile_name = profile.name
    else:
        bu.industry_profile_id = None
        profile_name = None

    await db.commit()
    await db.refresh(bu)

    return {
        "business_unit": bu.name,
        "profile": profile_name,
        "profile_id": str(bu.industry_profile_id) if bu.industry_profile_id else None,
        "effective_profile": bu.effective_profile_name,
    }
