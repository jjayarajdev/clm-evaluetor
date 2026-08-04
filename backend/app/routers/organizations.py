"""API endpoints for Organization management (Evaluetor features)."""

from uuid import UUID
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_user, require_permission, CurrentTenantId, RequiredTenantId
from app.core.tenant import apply_tenant_filter
from app.models import User, Organization, OrganizationType, OrganizationSize
from app.models.organization_officer import OrganizationOfficer, GovernanceRole, OfficerSide
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationListResponse,
    OrganizationHierarchyResponse,
    OrganizationTreeNode,
)
from app.schemas.organization_officer import (
    OfficerCreate,
    OfficerUpdate,
    OfficerResponse,
    OfficerListResponse,
)

router = APIRouter(prefix="/api/organizations", tags=["Organizations"])


async def _org_visibility(db: AsyncSession, current_user) :
    """BU-derived org visibility clause for this user (None = unrestricted)."""
    from app.core.bu_scope import org_bu_visibility_clause, resolve_visible_bu_ids

    return org_bu_visibility_clause(await resolve_visible_bu_ids(db, current_user))


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
    query = apply_tenant_filter(query, tenant_id, Organization)
    bu_clause = await _org_visibility(db, current_user)
    if bu_clause is not None:
        query = query.where(bu_clause)

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
    current_user: User = Depends(require_permission("organizations.write")),
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

    # Validate parent_organization_id if provided
    if data.parent_organization_id:
        parent_query = select(Organization).where(
            Organization.id == data.parent_organization_id,
            Organization.tenant_id == tenant_id,
        )
        parent_result = await db.execute(parent_query)
        if not parent_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent organization not found",
            )

    org = Organization(tenant_id=tenant_id, **data.model_dump())
    db.add(org)
    await db.commit()
    await db.refresh(org)

    return OrganizationResponse.model_validate(org)


# ===== Hierarchy Endpoints (must be registered before /{org_id} to avoid path conflicts) =====


def _build_tree_node(org: Organization, children_map: dict) -> OrganizationTreeNode:
    """Recursively build a tree node from an organization and its children lookup."""
    child_orgs = children_map.get(org.id, [])
    return OrganizationTreeNode(
        id=org.id,
        name=org.name,
        code=org.code,
        org_type=org.org_type,
        organization_level=org.organization_level,
        is_active=org.is_active,
        children=[_build_tree_node(c, children_map) for c in child_orgs],
    )


@router.get("/tree", response_model=List[OrganizationTreeNode])
async def get_organization_tree(
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a hierarchical tree of all organizations for the current tenant.

    Returns top-level organizations (those without a parent) with nested children.
    """
    query = select(Organization)
    query = apply_tenant_filter(query, tenant_id, Organization)
    bu_clause = await _org_visibility(db, current_user)
    if bu_clause is not None:
        query = query.where(bu_clause)
    query = query.order_by(Organization.name)

    result = await db.execute(query)
    all_orgs = result.scalars().all()

    # Build parent->children lookup. A visible org whose parent is NOT
    # visible (BU scoping) is promoted to root so it doesn't vanish.
    visible_ids = {org.id for org in all_orgs}
    children_map: dict = {}
    roots = []
    for org in all_orgs:
        if org.parent_organization_id and org.parent_organization_id in visible_ids:
            children_map.setdefault(org.parent_organization_id, []).append(org)
        else:
            roots.append(org)

    return [_build_tree_node(r, children_map) for r in roots]


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get organization by ID."""
    query = select(Organization).where(Organization.id == org_id)
    query = apply_tenant_filter(query, tenant_id, Organization)
    bu_clause = await _org_visibility(db, current_user)
    if bu_clause is not None:
        query = query.where(bu_clause)
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
    current_user: User = Depends(require_permission("organizations.write")),
):
    """Update an organization."""
    query = select(Organization).where(Organization.id == org_id)
    query = apply_tenant_filter(query, tenant_id, Organization)
    bu_clause = await _org_visibility(db, current_user)
    if bu_clause is not None:
        query = query.where(bu_clause)
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
        conflict_query = apply_tenant_filter(conflict_query, tenant_id, Organization)
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
    current_user: User = Depends(require_permission("organizations.delete")),
):
    """Delete or deactivate an organization."""
    query = select(Organization).where(Organization.id == org_id)
    query = apply_tenant_filter(query, tenant_id, Organization)
    bu_clause = await _org_visibility(db, current_user)
    if bu_clause is not None:
        query = query.where(bu_clause)
    result = await db.execute(query)
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    if hard_delete:
        # An organization referenced by relationships, contracts or child
        # organizations cannot be hard-deleted — those must be handled first.
        # (Soft delete / deactivate is always available.)
        from sqlalchemy import delete as sa_delete, func, or_

        from app.models.contract import Contract
        from app.models.organization_officer import OrganizationOfficer
        from app.models.relationship import BusinessRelationship

        rel_count = (
            await db.execute(
                select(func.count(BusinessRelationship.id)).where(
                    or_(
                        BusinessRelationship.org_a_id == org_id,
                        BusinessRelationship.org_b_id == org_id,
                    )
                )
            )
        ).scalar_one()
        contract_count = (
            await db.execute(
                select(func.count(Contract.id)).where(Contract.organization_id == org_id)
            )
        ).scalar_one()
        subsidiary_count = (
            await db.execute(
                select(func.count(Organization.id)).where(
                    Organization.parent_organization_id == org_id
                )
            )
        ).scalar_one()

        blockers = []
        if rel_count:
            blockers.append(f"{rel_count} business relationship(s)")
        if contract_count:
            blockers.append(f"{contract_count} contract(s)")
        if subsidiary_count:
            blockers.append(f"{subsidiary_count} subsidiary organization(s)")
        if blockers:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot delete this organization: {', '.join(blockers)} "
                    "still reference it. Remove or reassign them first, or "
                    "deactivate the organization instead."
                ),
            )

        # Officers are pure children — delete them with the org
        await db.execute(
            sa_delete(OrganizationOfficer).where(OrganizationOfficer.organization_id == org_id)
        )
        await db.delete(org)
    else:
        org.is_active = False

    await db.commit()


@router.get("/{org_id}/relationships", response_model=List[dict])
async def get_organization_relationships(
    org_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all business relationships for an organization."""
    from app.models import BusinessRelationship
    from app.core.bu_scope import relationship_bu_visibility_clause, resolve_visible_bu_ids
    from app.core.bu_scope import org_bu_visibility_clause

    visible_bus = await resolve_visible_bu_ids(db, current_user)
    query = select(Organization).where(Organization.id == org_id)
    query = apply_tenant_filter(query, tenant_id, Organization)
    org_clause = org_bu_visibility_clause(visible_bus)
    if org_clause is not None:
        query = query.where(org_clause)
    result = await db.execute(query)
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
    relationships_query = apply_tenant_filter(relationships_query, tenant_id, BusinessRelationship)
    rel_clause = relationship_bu_visibility_clause(visible_bus)
    if rel_clause is not None:
        relationships_query = relationships_query.where(rel_clause)
    result = await db.execute(relationships_query)
    relationships = result.scalars().all()

    return [
        {
            "id": str(r.id),
            "name": r.name,
            "relationship_type": r.relationship_type if isinstance(r.relationship_type, str) else r.relationship_type.value,
            "status": r.status if isinstance(r.status, str) else r.status.value,
            "health_score": r.health_score,
            "partner_org_id": str(r.org_b_id if r.org_a_id == org_id else r.org_a_id),
        }
        for r in relationships
    ]


# ===== Hierarchy Sub-Endpoints =====


@router.get("/{org_id}/subsidiaries", response_model=List[OrganizationResponse])
async def get_subsidiaries(
    org_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get direct child organizations (subsidiaries) of the given organization."""
    # Verify parent exists (and is BU-visible)
    bu_clause = await _org_visibility(db, current_user)
    parent_query = select(Organization).where(Organization.id == org_id)
    parent_query = apply_tenant_filter(parent_query, tenant_id, Organization)
    if bu_clause is not None:
        parent_query = parent_query.where(bu_clause)
    parent_result = await db.execute(parent_query)
    parent_org = parent_result.scalar_one_or_none()

    if not parent_org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Fetch children
    children_query = select(Organization).where(
        Organization.parent_organization_id == org_id,
    )
    children_query = apply_tenant_filter(children_query, tenant_id, Organization)
    if bu_clause is not None:
        children_query = children_query.where(bu_clause)
    children_query = children_query.order_by(Organization.name)

    result = await db.execute(children_query)
    children = result.scalars().all()

    return [OrganizationResponse.model_validate(c) for c in children]


@router.get("/{org_id}/hierarchy", response_model=OrganizationHierarchyResponse)
async def get_organization_hierarchy(
    org_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the full hierarchy context for an organization.

    Returns the organization itself, its parent chain (up to root), and its
    direct children.
    """
    # Fetch the target org (BU-visible only)
    bu_clause = await _org_visibility(db, current_user)
    org_query = select(Organization).where(Organization.id == org_id)
    org_query = apply_tenant_filter(org_query, tenant_id, Organization)
    if bu_clause is not None:
        org_query = org_query.where(bu_clause)
    result = await db.execute(org_query)
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Build parent chain (walk up the tree)
    parent_chain: List[Organization] = []
    current_parent_id = org.parent_organization_id
    visited = set()
    while current_parent_id and current_parent_id not in visited:
        visited.add(current_parent_id)
        parent_q = select(Organization).where(Organization.id == current_parent_id)
        parent_q = apply_tenant_filter(parent_q, tenant_id, Organization)
        if bu_clause is not None:
            # Chain truncates at an invisible ancestor (loop breaks on miss)
            parent_q = parent_q.where(bu_clause)
        parent_result = await db.execute(parent_q)
        parent = parent_result.scalar_one_or_none()
        if parent:
            parent_chain.append(parent)
            current_parent_id = parent.parent_organization_id
        else:
            break

    # parent_chain is currently [immediate_parent, ..., root] -- reverse to [root, ..., immediate_parent]
    # The immediate parent is the first element *before* reversing.
    immediate_parent = parent_chain[0] if parent_chain else None

    # Reverse so root is first in the chain
    parent_chain.reverse()

    # Direct children
    children_query = select(Organization).where(
        Organization.parent_organization_id == org_id,
    )
    children_query = apply_tenant_filter(children_query, tenant_id, Organization)
    if bu_clause is not None:
        children_query = children_query.where(bu_clause)
    children_query = children_query.order_by(Organization.name)
    children_result = await db.execute(children_query)
    children = children_result.scalars().all()

    return OrganizationHierarchyResponse(
        organization=OrganizationResponse.model_validate(org),
        parent=OrganizationResponse.model_validate(immediate_parent) if immediate_parent else None,
        parent_chain=[OrganizationResponse.model_validate(p) for p in parent_chain],
        children=[OrganizationResponse.model_validate(c) for c in children],
    )


# ===== Officer / Contact Endpoints =====


def _apply_officer_tenant_filter(query, tenant_id):
    """Apply tenant filter to OrganizationOfficer query."""
    if tenant_id is not None:
        return query.where(OrganizationOfficer.tenant_id == tenant_id)
    return query


@router.get("/{org_id}/officers", response_model=OfficerListResponse)
async def list_officers(
    org_id: UUID,
    tenant_id: CurrentTenantId,
    governance_role: Optional[GovernanceRole] = None,
    side: Optional[OfficerSide] = None,
    is_active: Optional[bool] = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List officers / contacts for an organization.

    Filterable by governance_role, side, and active status.
    """
    # Verify org exists (and is BU-visible)
    org_query = select(Organization).where(Organization.id == org_id)
    org_query = apply_tenant_filter(org_query, tenant_id, Organization)
    bu_clause = await _org_visibility(db, current_user)
    if bu_clause is not None:
        org_query = org_query.where(bu_clause)
    org_result = await db.execute(org_query)
    if not org_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    query = select(OrganizationOfficer).where(
        OrganizationOfficer.organization_id == org_id,
    )
    query = _apply_officer_tenant_filter(query, tenant_id)

    if governance_role is not None:
        query = query.where(OrganizationOfficer.governance_role == governance_role.value)

    if side is not None:
        query = query.where(OrganizationOfficer.side == side.value)

    if is_active is not None:
        query = query.where(OrganizationOfficer.is_active == is_active)

    query = query.order_by(OrganizationOfficer.name)

    result = await db.execute(query)
    items = result.scalars().all()

    return OfficerListResponse(
        items=[OfficerResponse.model_validate(o) for o in items],
        total=len(items),
    )


@router.post(
    "/{org_id}/officers",
    response_model=OfficerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_officer(
    org_id: UUID,
    data: OfficerCreate,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("organizations.write")),
):
    """Create a new officer / contact for an organization."""
    # Verify org exists, belongs to tenant, and is BU-visible
    org_query = select(Organization).where(
        Organization.id == org_id,
        Organization.tenant_id == tenant_id,
    )
    bu_clause = await _org_visibility(db, current_user)
    if bu_clause is not None:
        org_query = org_query.where(bu_clause)
    org_result = await db.execute(org_query)
    if not org_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    officer = OrganizationOfficer(
        tenant_id=tenant_id,
        organization_id=org_id,
        **data.model_dump(),
    )
    db.add(officer)
    await db.commit()
    await db.refresh(officer)

    return OfficerResponse.model_validate(officer)


@router.put("/{org_id}/officers/{officer_id}", response_model=OfficerResponse)
async def update_officer(
    org_id: UUID,
    officer_id: UUID,
    data: OfficerUpdate,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("organizations.write")),
):
    """Update an existing officer / contact."""
    from app.core.bu_scope import _org_contracts_visible, resolve_visible_bu_ids

    query = select(OrganizationOfficer).where(
        OrganizationOfficer.id == officer_id,
        OrganizationOfficer.organization_id == org_id,
    )
    query = _apply_officer_tenant_filter(query, tenant_id)
    visible_bus = await resolve_visible_bu_ids(db, current_user)
    if visible_bus is not None:
        query = query.where(_org_contracts_visible(OrganizationOfficer.organization_id, visible_bus))
    result = await db.execute(query)
    officer = result.scalar_one_or_none()

    if not officer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Officer not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(officer, field, value)

    await db.commit()
    await db.refresh(officer)

    return OfficerResponse.model_validate(officer)


@router.delete("/{org_id}/officers/{officer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_officer(
    org_id: UUID,
    officer_id: UUID,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("organizations.write")),
):
    """Deactivate an officer (soft delete)."""
    from app.core.bu_scope import _org_contracts_visible, resolve_visible_bu_ids

    query = select(OrganizationOfficer).where(
        OrganizationOfficer.id == officer_id,
        OrganizationOfficer.organization_id == org_id,
    )
    query = _apply_officer_tenant_filter(query, tenant_id)
    visible_bus = await resolve_visible_bu_ids(db, current_user)
    if visible_bus is not None:
        query = query.where(_org_contracts_visible(OrganizationOfficer.organization_id, visible_bus))
    result = await db.execute(query)
    officer = result.scalar_one_or_none()

    if not officer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Officer not found",
        )

    officer.is_active = False
    await db.commit()
