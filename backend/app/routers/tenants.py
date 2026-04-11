"""Tenant management router (super-admin only)."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import SuperAdminUser, AdminUser, CurrentUser
from app.database import get_db
from app.models import Tenant, TenantPlan
from app.models.organization import Organization, OrganizationType, OrganizationLevel
from app.services import tenant_service


router = APIRouter(prefix="/api/tenants", tags=["Tenants"])


# =============================================================================
# Schemas
# =============================================================================


class TenantCreate(BaseModel):
    """Schema for creating a new tenant."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    plan: TenantPlan = TenantPlan.STARTER
    contact_email: str | None = None
    contact_name: str | None = None


class TenantUpdate(BaseModel):
    """Schema for updating a tenant."""

    name: str | None = None
    plan: TenantPlan | None = None
    contact_email: str | None = None
    contact_name: str | None = None
    contract_limit: int | None = None
    is_active: bool | None = None


class TenantResponse(BaseModel):
    """Schema for tenant response."""

    id: str
    name: str
    slug: str
    plan: str
    contract_limit: int | None
    contact_email: str | None
    contact_name: str | None
    is_active: bool
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, tenant: Tenant) -> "TenantResponse":
        return cls(
            id=str(tenant.id),
            name=tenant.name,
            slug=tenant.slug,
            plan=tenant.plan.value,
            contract_limit=tenant.get_contract_limit(),
            contact_email=tenant.contact_email,
            contact_name=tenant.contact_name,
            is_active=tenant.is_active,
            created_at=tenant.created_at.isoformat(),
            updated_at=tenant.updated_at.isoformat(),
        )


class TenantStatsResponse(BaseModel):
    """Schema for tenant statistics."""

    tenant_id: str
    tenant_name: str | None
    plan: str | None
    contract_count: int
    contract_limit: int | None
    user_count: int
    is_active: bool
    total_value: float = 0


# =============================================================================
# Helpers
# =============================================================================


async def _bootstrap_internal_org(db: AsyncSession, tenant: Tenant) -> None:
    """Create an internal Organization representing the tenant itself.

    The GovernanceBridgeService needs this to auto-create BusinessRelationships
    when contracts are uploaded: internal org ↔ counterparty org.
    """
    # Check if one already exists (idempotent)
    result = await db.execute(
        select(Organization.id).where(
            Organization.tenant_id == tenant.id,
            Organization.org_type == OrganizationType.INTERNAL.value,
        ).limit(1)
    )
    if result.scalar_one_or_none():
        return

    # Generate a unique code from tenant slug
    code = tenant.slug.upper().replace("-", "")[:10] + "-INT"

    org = Organization(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        name=tenant.name,
        code=code,
        org_type=OrganizationType.INTERNAL.value,
        organization_level=OrganizationLevel.HOLDING.value,
        is_active=True,
        primary_contact_name=tenant.contact_name,
        primary_contact_email=tenant.contact_email,
    )
    db.add(org)
    await db.flush()
    logging.info(f"Created internal org '{tenant.name}' ({code}) for tenant {tenant.slug}")


# =============================================================================
# Endpoints
# =============================================================================


@router.get("", response_model=list[TenantResponse])
async def list_tenants(
    current_user: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    include_inactive: bool = False,
) -> list[TenantResponse]:
    """List all tenants (super-admin only).

    Args:
        current_user: Authenticated super admin.
        db: Database session.
        include_inactive: Whether to include inactive tenants.

    Returns:
        List of all tenants.
    """
    tenants = await tenant_service.get_all_tenants(db, include_inactive=include_inactive)
    return [TenantResponse.from_model(t) for t in tenants]


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_data: TenantCreate,
    current_user: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TenantResponse:
    """Create a new tenant (super-admin only).

    Args:
        tenant_data: Tenant creation data.
        current_user: Authenticated super admin.
        db: Database session.

    Returns:
        The created tenant.
    """
    # Check if slug already exists
    existing = await tenant_service.get_tenant_by_slug(db, tenant_data.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant with slug '{tenant_data.slug}' already exists",
        )

    tenant = await tenant_service.create_tenant(
        db=db,
        name=tenant_data.name,
        slug=tenant_data.slug,
        plan=tenant_data.plan,
        contact_email=tenant_data.contact_email,
        contact_name=tenant_data.contact_name,
    )

    # Auto-provision enterprise integration configs for the new tenant
    try:
        from app.services.tenant_provisioner import provision_integrations
        await provision_integrations(db=db, tenant_id=tenant.id, tenant_name=tenant.name)
    except Exception as e:
        logging.warning(f"Integration provisioning failed for {tenant.name}: {e}")

    # Auto-create internal Organization so GovernanceBridgeService can
    # link contracts to relationships on upload
    try:
        await _bootstrap_internal_org(db, tenant)
    except Exception as e:
        logging.warning(f"Internal org bootstrap failed for {tenant.name}: {e}")

    return TenantResponse.from_model(tenant)


@router.get("/current", response_model=TenantResponse)
async def get_current_tenant(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TenantResponse:
    """Get the current user's tenant.

    Args:
        current_user: Authenticated user.
        db: Database session.

    Returns:
        The user's tenant.
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with a tenant",
        )

    tenant = await tenant_service.get_tenant_by_id(db, current_user.tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    return TenantResponse.from_model(tenant)


@router.get("/current/stats", response_model=TenantStatsResponse)
async def get_current_tenant_stats(
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TenantStatsResponse:
    """Get statistics for the current user's tenant.

    Args:
        current_user: Authenticated admin user.
        db: Database session.

    Returns:
        Tenant statistics.
    """
    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not associated with a tenant",
        )

    stats = await tenant_service.get_tenant_stats(db, current_user.tenant_id)
    return TenantStatsResponse(**stats)


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: uuid.UUID,
    current_user: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TenantResponse:
    """Get a tenant by ID (super-admin only).

    Args:
        tenant_id: The tenant's UUID.
        current_user: Authenticated super admin.
        db: Database session.

    Returns:
        The tenant.
    """
    tenant = await tenant_service.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return TenantResponse.from_model(tenant)


@router.get("/{tenant_id}/stats", response_model=TenantStatsResponse)
async def get_tenant_stats(
    tenant_id: uuid.UUID,
    current_user: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TenantStatsResponse:
    """Get statistics for a tenant (super-admin only).

    Args:
        tenant_id: The tenant's UUID.
        current_user: Authenticated super admin.
        db: Database session.

    Returns:
        Tenant statistics.
    """
    tenant = await tenant_service.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    stats = await tenant_service.get_tenant_stats(db, tenant_id)
    return TenantStatsResponse(**stats)


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: uuid.UUID,
    tenant_data: TenantUpdate,
    current_user: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TenantResponse:
    """Update a tenant (super-admin only).

    Args:
        tenant_id: The tenant's UUID.
        tenant_data: Fields to update.
        current_user: Authenticated super admin.
        db: Database session.

    Returns:
        The updated tenant.
    """
    tenant = await tenant_service.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    updated_tenant = await tenant_service.update_tenant(
        db=db,
        tenant=tenant,
        **tenant_data.model_dump(exclude_none=True),
    )
    return TenantResponse.from_model(updated_tenant)


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_tenant(
    tenant_id: uuid.UUID,
    current_user: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Deactivate a tenant (super-admin only).

    Note: This soft-deletes the tenant by setting is_active=False.

    Args:
        tenant_id: The tenant's UUID.
        current_user: Authenticated super admin.
        db: Database session.
    """
    tenant = await tenant_service.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    await tenant_service.update_tenant(db, tenant, is_active=False)


@router.post("/bootstrap-governance", status_code=status.HTTP_200_OK)
async def bootstrap_all_tenants_governance(
    current_user: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Backfill internal organizations for all existing tenants.

    Idempotent — skips tenants that already have an internal org.
    Enables GovernanceBridgeService to auto-link contracts to relationships.
    """
    tenants = await tenant_service.get_all_tenants(db, include_inactive=False)
    created = []
    skipped = []
    for tenant in tenants:
        result = await db.execute(
            select(Organization.id).where(
                Organization.tenant_id == tenant.id,
                Organization.org_type == OrganizationType.INTERNAL.value,
            ).limit(1)
        )
        if result.scalar_one_or_none():
            skipped.append(tenant.name)
            continue
        try:
            await _bootstrap_internal_org(db, tenant)
            created.append(tenant.name)
        except Exception as e:
            logging.warning(f"Bootstrap failed for {tenant.name}: {e}")

    await db.commit()
    return {
        "created": created,
        "skipped": skipped,
        "message": f"Bootstrapped {len(created)} tenants, {len(skipped)} already had internal orgs",
    }
