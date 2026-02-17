"""API endpoints for Organization management (Evaluetor features)."""

from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_user, require_role, CurrentTenantId, RequiredTenantId
from app.models import User, Organization, OrganizationType, OrganizationSize
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationListResponse,
)

router = APIRouter(prefix="/organizations", tags=["Organizations"])


def apply_tenant_filter(query, tenant_id):
    """Apply tenant filter to Organization query if tenant_id is set."""
    if tenant_id is not None:
        return query.where(Organization.tenant_id == tenant_id)
    return query


@router.get("", response_model=OrganizationListResponse)
async def list_organizations(
    tenant_id: CurrentTenantId,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    org_type: Optional[OrganizationType] = None,
    industry: Optional[str] = None,
    region: Optional[str] = None,
    is_active: Optional[bool] = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List organizations with filtering and pagination."""
    query = select(Organization)
    query = apply_tenant_filter(query, tenant_id)

    # Apply filters
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            or_(
                Organization.name.ilike(search_filter),
                Organization.code.ilike(search_filter),
            )
        )

    if org_type:
        query = query.where(Organization.org_type == org_type)

    if industry:
        query = query.where(Organization.industry.ilike(f"%{industry}%"))

    if region:
        query = query.where(Organization.region.ilike(f"%{region}%"))

    if is_active is not None:
        query = query.where(Organization.is_active == is_active)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(Organization.name)

    result = await db.execute(query)
    items = result.scalars().all()

    return OrganizationListResponse(
        items=[OrganizationResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    data: OrganizationCreate,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Create a new organization."""
    # Check for duplicate code within tenant
    existing_query = select(Organization).where(
        Organization.tenant_id == tenant_id,
        Organization.code == data.code
    )
    existing = await db.execute(existing_query)
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Organization with code '{data.code}' already exists",
        )

    org = Organization(tenant_id=tenant_id, **data.model_dump())
    db.add(org)
    await db.commit()
    await db.refresh(org)

    return OrganizationResponse.model_validate(org)


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get organization by ID."""
    query = select(Organization).where(Organization.id == org_id)
    query = apply_tenant_filter(query, tenant_id)
    result = await db.execute(query)
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    return OrganizationResponse.model_validate(org)


@router.put("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: UUID,
    data: OrganizationUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Update an organization."""
    query = select(Organization).where(Organization.id == org_id)
    query = apply_tenant_filter(query, tenant_id)
    result = await db.execute(query)
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check for duplicate code if changing within same tenant
    if data.code and data.code != org.code:
        conflict_query = select(Organization).where(
            Organization.code == data.code,
            Organization.id != org_id,
        )
        conflict_query = apply_tenant_filter(conflict_query, tenant_id)
        existing = await db.execute(conflict_query)
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Organization with code '{data.code}' already exists",
            )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(org, field, value)

    await db.commit()
    await db.refresh(org)

    return OrganizationResponse.model_validate(org)


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: UUID,
    tenant_id: CurrentTenantId,
    hard_delete: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Delete or deactivate an organization."""
    query = select(Organization).where(Organization.id == org_id)
    query = apply_tenant_filter(query, tenant_id)
    result = await db.execute(query)
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    if hard_delete:
        # Check for linked relationships
        # TODO: Add check for business relationships
        await db.delete(org)
    else:
        org.is_active = False

    await db.commit()


@router.get("/{org_id}/relationships", response_model=List[dict])
async def get_organization_relationships(
    org_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all business relationships for an organization."""
    from app.models import BusinessRelationship

    result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Get relationships where org is either party
    relationships_query = select(BusinessRelationship).where(
        or_(
            BusinessRelationship.org_a_id == org_id,
            BusinessRelationship.org_b_id == org_id,
        )
    )
    result = await db.execute(relationships_query)
    relationships = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "name": r.name,
            "relationship_type": r.relationship_type.value,
            "status": r.status.value,
            "health_score": r.health_score,
            "partner_org_id": str(r.org_b_id if r.org_a_id == org_id else r.org_a_id),
        }
        for r in relationships
    ]
