"""API endpoints for Service Portfolio management (Evaluetor features)."""

from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_user, require_role, CurrentTenantId, RequiredTenantId
from app.core.tenant import apply_tenant_filter
from app.models import User, Organization, BusinessRelationship
from app.models.service_portfolio import ServicePortfolio, RelationshipService, ServiceType, ServiceStatus
from app.schemas.service_portfolio import (
    ServicePortfolioCreate,
    ServicePortfolioUpdate,
    ServicePortfolioResponse,
    ServicePortfolioListResponse,
    RelationshipServiceCreate,
    RelationshipServiceResponse,
)

router = APIRouter(prefix="/api/service-portfolio", tags=["Service Portfolio"])


@router.get("", response_model=ServicePortfolioListResponse)
async def list_service_portfolios(
    tenant_id: CurrentTenantId,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    org_id: Optional[UUID] = None,
    service_type: Optional[ServiceType] = None,
    service_status: Optional[ServiceStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List service portfolios with filtering and pagination."""
    query = select(ServicePortfolio)
    query = apply_tenant_filter(query, tenant_id, ServicePortfolio)

    # Apply filters
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            or_(
                ServicePortfolio.name.ilike(search_filter),
                ServicePortfolio.code.ilike(search_filter),
                ServicePortfolio.description.ilike(search_filter),
            )
        )

    if org_id:
        query = query.where(ServicePortfolio.organization_id == org_id)

    if service_type:
        query = query.where(ServicePortfolio.service_type == service_type)

    if service_status:
        query = query.where(ServicePortfolio.status == service_status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(ServicePortfolio.name)

    result = await db.execute(query)
    items = result.scalars().all()

    return ServicePortfolioListResponse(
        items=[ServicePortfolioResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=ServicePortfolioResponse, status_code=status.HTTP_201_CREATED)
async def create_service_portfolio(
    data: ServicePortfolioCreate,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Create a new service portfolio entry."""
    # Verify organization exists and belongs to tenant
    org_query = select(Organization).where(Organization.id == data.organization_id)
    if tenant_id:
        org_query = org_query.where(Organization.tenant_id == tenant_id)
    org_result = await db.execute(org_query)
    if not org_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check for duplicate code within tenant
    existing_query = select(ServicePortfolio).where(
        ServicePortfolio.tenant_id == tenant_id,
        ServicePortfolio.code == data.code,
    )
    existing = await db.execute(existing_query)
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Service portfolio with code '{data.code}' already exists",
        )

    service = ServicePortfolio(tenant_id=tenant_id, **data.model_dump())
    db.add(service)
    await db.commit()
    await db.refresh(service)

    return ServicePortfolioResponse.model_validate(service)


# NOTE: /organization/{org_id} must be defined BEFORE /{service_id}
# to avoid FastAPI treating "organization" as a UUID path parameter.
@router.get("/organization/{org_id}", response_model=ServicePortfolioListResponse)
async def get_services_for_organization(
    org_id: UUID,
    tenant_id: CurrentTenantId,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service_type: Optional[ServiceType] = None,
    service_status: Optional[ServiceStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all services for a specific organization."""
    # Verify organization exists
    org_query = select(Organization).where(Organization.id == org_id)
    if tenant_id is not None:
        org_query = org_query.where(Organization.tenant_id == tenant_id)
    org_result = await db.execute(org_query)
    if not org_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    query = select(ServicePortfolio).where(ServicePortfolio.organization_id == org_id)
    query = apply_tenant_filter(query, tenant_id, ServicePortfolio)

    if service_type:
        query = query.where(ServicePortfolio.service_type == service_type)

    if service_status:
        query = query.where(ServicePortfolio.status == service_status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(ServicePortfolio.name)

    result = await db.execute(query)
    items = result.scalars().all()

    return ServicePortfolioListResponse(
        items=[ServicePortfolioResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{service_id}", response_model=ServicePortfolioResponse)
async def get_service_portfolio(
    service_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get service portfolio by ID."""
    query = select(ServicePortfolio).where(ServicePortfolio.id == service_id)
    query = apply_tenant_filter(query, tenant_id, ServicePortfolio)
    result = await db.execute(query)
    service = result.scalar_one_or_none()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service portfolio not found",
        )

    return ServicePortfolioResponse.model_validate(service)


@router.put("/{service_id}", response_model=ServicePortfolioResponse)
async def update_service_portfolio(
    service_id: UUID,
    data: ServicePortfolioUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Update a service portfolio entry."""
    query = select(ServicePortfolio).where(ServicePortfolio.id == service_id)
    query = apply_tenant_filter(query, tenant_id, ServicePortfolio)
    result = await db.execute(query)
    service = result.scalar_one_or_none()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service portfolio not found",
        )

    # Check for duplicate code if changing within same tenant
    if data.code and data.code != service.code:
        conflict_query = select(ServicePortfolio).where(
            ServicePortfolio.code == data.code,
            ServicePortfolio.id != service_id,
        )
        conflict_query = apply_tenant_filter(conflict_query, tenant_id, ServicePortfolio)
        existing = await db.execute(conflict_query)
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Service portfolio with code '{data.code}' already exists",
            )

    # Verify organization if changing
    if data.organization_id and data.organization_id != service.organization_id:
        org_query = select(Organization).where(Organization.id == data.organization_id)
        if tenant_id:
            org_query = org_query.where(Organization.tenant_id == tenant_id)
        org_result = await db.execute(org_query)
        if not org_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(service, field, value)

    await db.commit()
    await db.refresh(service)

    return ServicePortfolioResponse.model_validate(service)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service_portfolio(
    service_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"])),
):
    """Soft delete a service portfolio entry (sets status to deprecated)."""
    query = select(ServicePortfolio).where(ServicePortfolio.id == service_id)
    query = apply_tenant_filter(query, tenant_id, ServicePortfolio)
    result = await db.execute(query)
    service = result.scalar_one_or_none()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service portfolio not found",
        )

    # Soft delete: set status to deprecated
    service.status = ServiceStatus.DEPRECATED.value

    await db.commit()


@router.get("/{service_id}/relationships", response_model=List[RelationshipServiceResponse])
async def get_service_relationships(
    service_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all business relationships using this service."""
    # Verify service exists and belongs to tenant
    svc_query = select(ServicePortfolio).where(ServicePortfolio.id == service_id)
    svc_query = apply_tenant_filter(svc_query, tenant_id, ServicePortfolio)
    svc_result = await db.execute(svc_query)
    if not svc_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service portfolio not found",
        )

    query = select(RelationshipService).where(
        RelationshipService.service_portfolio_id == service_id
    )
    result = await db.execute(query)
    items = result.scalars().all()

    return [RelationshipServiceResponse.model_validate(item) for item in items]


@router.post(
    "/{service_id}/relationships",
    response_model=RelationshipServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def link_service_to_relationship(
    service_id: UUID,
    data: RelationshipServiceCreate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Link a service portfolio entry to a business relationship."""
    # Verify service exists and belongs to tenant
    svc_query = select(ServicePortfolio).where(ServicePortfolio.id == service_id)
    svc_query = apply_tenant_filter(svc_query, tenant_id, ServicePortfolio)
    svc_result = await db.execute(svc_query)
    if not svc_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service portfolio not found",
        )

    # Verify relationship exists and belongs to tenant
    rel_query = select(BusinessRelationship).where(
        BusinessRelationship.id == data.relationship_id
    )
    if tenant_id is not None:
        rel_query = rel_query.where(BusinessRelationship.tenant_id == tenant_id)
    rel_result = await db.execute(rel_query)
    if not rel_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business relationship not found",
        )

    # Check for existing link
    existing_query = select(RelationshipService).where(
        RelationshipService.service_portfolio_id == service_id,
        RelationshipService.relationship_id == data.relationship_id,
    )
    existing = await db.execute(existing_query)
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service is already linked to this relationship",
        )

    rel_service = RelationshipService(
        service_portfolio_id=service_id,
        **data.model_dump(),
    )
    db.add(rel_service)
    await db.commit()
    await db.refresh(rel_service)

    return RelationshipServiceResponse.model_validate(rel_service)


@router.delete(
    "/{service_id}/relationships/{rel_service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_service_from_relationship(
    service_id: UUID,
    rel_service_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "legal"])),
):
    """Unlink a service from a business relationship."""
    # Verify service exists and belongs to tenant
    svc_query = select(ServicePortfolio).where(ServicePortfolio.id == service_id)
    svc_query = apply_tenant_filter(svc_query, tenant_id, ServicePortfolio)
    svc_result = await db.execute(svc_query)
    if not svc_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service portfolio not found",
        )

    # Find and delete the relationship service link
    query = select(RelationshipService).where(
        RelationshipService.id == rel_service_id,
        RelationshipService.service_portfolio_id == service_id,
    )
    result = await db.execute(query)
    rel_service = result.scalar_one_or_none()

    if not rel_service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship service link not found",
        )

    await db.delete(rel_service)
    await db.commit()
