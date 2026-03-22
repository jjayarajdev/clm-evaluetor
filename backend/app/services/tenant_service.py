"""Tenant service for multi-tenancy operations."""

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant, TenantPlan, User, Contract


# Predefined tenant UUIDs (must match migration)
ACME_TENANT_ID = uuid.UUID('10000000-0000-0000-0000-000000000001')
TECHSTART_TENANT_ID = uuid.UUID('10000000-0000-0000-0000-000000000002')
LEGALCO_TENANT_ID = uuid.UUID('10000000-0000-0000-0000-000000000003')


async def get_tenant_by_id(db: AsyncSession, tenant_id: uuid.UUID) -> Optional[Tenant]:
    """Get a tenant by ID."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()


async def get_tenant_by_slug(db: AsyncSession, slug: str) -> Optional[Tenant]:
    """Get a tenant by slug."""
    result = await db.execute(select(Tenant).where(Tenant.slug == slug))
    return result.scalar_one_or_none()


async def get_all_tenants(db: AsyncSession, include_inactive: bool = False) -> list[Tenant]:
    """Get all tenants."""
    query = select(Tenant)
    if not include_inactive:
        query = query.where(Tenant.is_active == True)
    query = query.order_by(Tenant.name)
    result = await db.execute(query)
    return list(result.scalars().all())


async def create_tenant(
    db: AsyncSession,
    name: str,
    slug: str,
    plan: TenantPlan = TenantPlan.STARTER,
    contact_email: Optional[str] = None,
    contact_name: Optional[str] = None,
) -> Tenant:
    """Create a new tenant."""
    tenant = Tenant(
        name=name,
        slug=slug.lower().replace(" ", "-"),
        plan=plan,
        contact_email=contact_email,
        contact_name=contact_name,
        is_active=True,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


async def update_tenant(
    db: AsyncSession,
    tenant: Tenant,
    **kwargs
) -> Tenant:
    """Update a tenant's attributes."""
    for key, value in kwargs.items():
        if hasattr(tenant, key) and value is not None:
            setattr(tenant, key, value)
    await db.commit()
    await db.refresh(tenant)
    return tenant


async def get_tenant_contract_count(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    """Get the number of contracts for a tenant."""
    result = await db.execute(
        select(Contract).where(Contract.tenant_id == tenant_id)
    )
    return len(result.scalars().all())


async def check_tenant_contract_limit(db: AsyncSession, tenant_id: uuid.UUID) -> tuple[bool, int, Optional[int]]:
    """
    Check if tenant can add more contracts.

    Returns:
        tuple: (can_add, current_count, limit)
    """
    tenant = await get_tenant_by_id(db, tenant_id)
    if not tenant:
        return False, 0, 0

    current_count = await get_tenant_contract_count(db, tenant_id)
    limit = tenant.get_contract_limit()

    if limit is None:  # Unlimited
        return True, current_count, None

    return current_count < limit, current_count, limit


async def get_tenant_users(db: AsyncSession, tenant_id: uuid.UUID) -> list[User]:
    """Get all users for a tenant."""
    result = await db.execute(
        select(User).where(User.tenant_id == tenant_id).order_by(User.username)
    )
    return list(result.scalars().all())


async def get_tenant_stats(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Get statistics for a tenant."""
    from app.models import Obligation, ContractSLA

    # Contract count
    contract_result = await db.execute(
        select(Contract).where(Contract.tenant_id == tenant_id)
    )
    contracts = contract_result.scalars().all()

    # User count
    user_result = await db.execute(
        select(User).where(User.tenant_id == tenant_id)
    )
    users = user_result.scalars().all()

    tenant = await get_tenant_by_id(db, tenant_id)

    # Total contract value
    total_value = sum(
        float(c.contract_value) for c in contracts if c.contract_value
    )

    return {
        "tenant_id": str(tenant_id),
        "tenant_name": tenant.name if tenant else None,
        "plan": tenant.plan.value if tenant else None,
        "contract_count": len(contracts),
        "contract_limit": tenant.get_contract_limit() if tenant else None,
        "user_count": len(users),
        "is_active": tenant.is_active if tenant else False,
        "total_value": total_value,
    }
