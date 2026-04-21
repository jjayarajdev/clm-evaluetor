"""Tenant management router (super-admin only)."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import SuperAdminUser, AdminUser, CurrentUser
from app.database import get_db
from app.models import Tenant, TenantPlan
from app.models.contract import Contract
from app.models.organization import Organization, OrganizationType, OrganizationLevel
from app.services import tenant_service

logger = logging.getLogger(__name__)


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


@router.delete("/{tenant_id}/purge", status_code=status.HTTP_200_OK)
async def purge_tenant(
    tenant_id: uuid.UUID,
    current_user: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    confirm: bool = Query(False, description="Must be true to proceed"),
) -> dict:
    """Permanently delete a tenant and ALL its data (super-admin only).

    This is irreversible. Deletes:
    - All contracts and cascaded data (clauses, obligations, SLAs, etc.)
    - All users, business units, organizations
    - All ChromaDB vectors
    - The tenant record itself
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add ?confirm=true to proceed with permanent deletion",
        )

    tenant = await tenant_service.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    tenant_name = tenant.name
    stats: dict = {"tenant": tenant_name, "deleted": {}}

    # ── Step 1: Pre-collect all ID sets to avoid nested subqueries ──
    async def _ids(sql: str) -> list:
        r = await db.execute(text(sql), {"tid": tenant_id})
        return [row[0] for row in r.fetchall()]

    contract_ids = await _ids("SELECT id FROM contracts WHERE tenant_id = :tid")
    user_ids = await _ids("SELECT id FROM users WHERE tenant_id = :tid")
    org_ids = await _ids("SELECT id FROM organizations WHERE tenant_id = :tid")
    br_ids = await _ids("SELECT id FROM business_relationships WHERE tenant_id = :tid")
    si_ids = await _ids(
        "SELECT si.id FROM survey_instances si JOIN business_relationships br ON si.relationship_id = br.id WHERE br.tenant_id = :tid"
    ) if br_ids else []
    ip_ids = await _ids(
        "SELECT ip.id FROM improvement_points ip JOIN business_relationships br ON ip.relationship_id = br.id WHERE br.tenant_id = :tid"
    ) if br_ids else []
    kpi_ids = await _ids(
        "SELECT k.id FROM kpis k JOIN business_relationships br ON k.relationship_id = br.id WHERE br.tenant_id = :tid"
    ) if br_ids else []

    stats["deleted"]["contracts"] = len(contract_ids)

    # ── Step 2: Delete ChromaDB vectors ──
    vectors_deleted = 0
    try:
        from app.services.vector_store import VectorStore
        vs = VectorStore()
        for cid in contract_ids:
            try:
                vectors_deleted += vs.delete_by_contract_id(str(cid))
            except Exception as e:
                logger.warning(f"Failed to delete vectors for contract {cid}: {e}")
    except Exception as e:
        logger.warning(f"ChromaDB cleanup skipped: {e}")
    stats["deleted"]["vectors"] = vectors_deleted

    # ── Step 3: Delete all tenant data using pre-collected ID arrays ──
    #    Uses = ANY(:ids) with pre-collected arrays instead of nested subqueries.
    #    asyncpg requires one statement per execute() call.
    tid = {"tid": tenant_id}
    cids = {"ids": contract_ids}
    uids = {"ids": user_ids}
    oids = {"ids": org_ids}
    bids = {"ids": br_ids}
    sids = {"ids": si_ids}
    ipids = {"ids": ip_ids}
    kpids = {"ids": kpi_ids}

    stmts: list[tuple[str, str, dict]] = [
        # ── Phase 0: Break circular / cross-table FKs ──
        ("_null_contracts", "UPDATE contracts SET business_relationship_id = NULL, previous_version_id = NULL, business_unit_id = NULL WHERE tenant_id = :tid", tid),
        ("_null_business_units", "UPDATE business_units SET head_user_id = NULL, parent_id = NULL WHERE tenant_id = :tid", tid),
        ("_null_organizations", "UPDATE organizations SET parent_organization_id = NULL, relationship_owner_id = NULL WHERE tenant_id = :tid", tid),

        # ── Phase 1: KG ──
        ("kg_relationships", "DELETE FROM kg_relationships WHERE tenant_id = :tid", tid),
        ("kg_entities", "DELETE FROM kg_entities WHERE tenant_id = :tid", tid),

        # ── Phase 2: Governance deepest children ──
        ("survey_responses", "DELETE FROM survey_responses WHERE survey_instance_id = ANY(:ids)", sids),
        ("external_access_tokens", "DELETE FROM external_access_tokens WHERE relationship_id = ANY(:ids)", bids),
        ("survey_instances", "DELETE FROM survey_instances WHERE relationship_id = ANY(:ids)", bids),
        ("perception_gaps", "DELETE FROM perception_gaps WHERE kpi_id = ANY(:ids)", kpids),
        ("improvement_actions", "DELETE FROM improvement_actions WHERE improvement_id = ANY(:ids)", ipids),
        ("improvement_points", "DELETE FROM improvement_points WHERE relationship_id = ANY(:ids)", bids),
        ("perception_scores", "DELETE FROM perception_scores WHERE scorer_org_id = ANY(:ids)", oids),
        ("kpis", "DELETE FROM kpis WHERE relationship_id = ANY(:ids)", bids),
        ("relationship_teams", "DELETE FROM relationship_teams WHERE relationship_id = ANY(:ids)", bids),
        ("relationship_services", "DELETE FROM relationship_services WHERE relationship_id = ANY(:ids)", bids),
        ("relationship_status_history", "DELETE FROM relationship_status_history WHERE tenant_id = :tid", tid),
        ("service_portfolios", "DELETE FROM service_portfolios WHERE tenant_id = :tid", tid),

        # ── Phase 3: Business relationships ──
        ("business_relationships", "DELETE FROM business_relationships WHERE tenant_id = :tid", tid),

        # ── Phase 4: Organization children then organizations ──
        ("organization_officers", "DELETE FROM organization_officers WHERE tenant_id = :tid", tid),
        ("external_users", "DELETE FROM external_users WHERE tenant_id = :tid", tid),
        ("organizations", "DELETE FROM organizations WHERE tenant_id = :tid", tid),

        # ── Phase 5: Contract children ──
        ("sla_alerts", "DELETE FROM sla_alerts WHERE contract_id = ANY(:ids)", cids),
        ("compliance_gaps", "DELETE FROM compliance_gaps WHERE contract_id = ANY(:ids)", cids),
        ("contract_slas", "DELETE FROM contract_slas WHERE contract_id = ANY(:ids)", cids),
        ("obligations", "DELETE FROM obligations WHERE contract_id = ANY(:ids)", cids),
        ("clauses", "DELETE FROM clauses WHERE contract_id = ANY(:ids)", cids),
        ("contract_parties", "DELETE FROM contract_parties WHERE contract_id = ANY(:ids)", cids),
        ("contract_key_dates", "DELETE FROM contract_key_dates WHERE contract_id = ANY(:ids)", cids),
        ("contract_financials", "DELETE FROM contract_financials WHERE contract_id = ANY(:ids)", cids),
        ("contract_liabilities", "DELETE FROM contract_liabilities WHERE contract_id = ANY(:ids)", cids),
        ("contract_preambles", "DELETE FROM contract_preambles WHERE contract_id = ANY(:ids)", cids),
        ("contract_definitions", "DELETE FROM contract_definitions WHERE contract_id = ANY(:ids)", cids),
        ("contract_exhibits", "DELETE FROM contract_exhibits WHERE contract_id = ANY(:ids)", cids),
        ("contract_clause_indicators", "DELETE FROM contract_clause_indicators WHERE contract_id = ANY(:ids)", cids),
        ("contract_comments", "DELETE FROM contract_comments WHERE contract_id = ANY(:ids)", cids),
        ("contract_process_steps", "DELETE FROM contract_process_steps WHERE contract_id = ANY(:ids)", cids),
        ("contract_links", "DELETE FROM contract_links WHERE parent_contract_id = ANY(:ids) OR child_contract_id = ANY(:ids)", cids),
        ("contract_shares", "DELETE FROM contract_shares WHERE contract_id = ANY(:ids)", cids),
        ("events", "DELETE FROM events WHERE contract_id = ANY(:ids)", cids),
        ("regulatory_obligations", "DELETE FROM regulatory_obligations WHERE contract_id = ANY(:ids)", cids),

        # ── Phase 6: Contract-scoped tables with tenant_id ──
        ("golden_set_contracts", "DELETE FROM golden_set_contracts WHERE tenant_id = :tid", tid),
        ("contract_processing_jobs", "DELETE FROM contract_processing_jobs WHERE tenant_id = :tid", tid),
        ("suggested_contract_links", "DELETE FROM suggested_contract_links WHERE tenant_id = :tid", tid),
        ("contract_documents", "DELETE FROM contract_documents WHERE tenant_id = :tid", tid),
        ("chat_sessions", "DELETE FROM chat_sessions WHERE tenant_id = :tid", tid),
        ("dashboard_cache", "DELETE FROM dashboard_cache WHERE tenant_id = :tid", tid),
        ("metric_snapshots", "DELETE FROM metric_snapshots WHERE tenant_id = :tid", tid),

        # ── Phase 7: Contracts ──
        ("contracts", "DELETE FROM contracts WHERE tenant_id = :tid", tid),

        # ── Phase 8: Tables referencing users (no tenant_id) ──
        ("alert_configs", "DELETE FROM alert_configs WHERE user_id = ANY(:ids)", uids),
        ("approval_requests", "DELETE FROM approval_requests WHERE approver_id = ANY(:ids) OR original_approver_id = ANY(:ids)", uids),
        ("approvers", "DELETE FROM approvers WHERE user_id = ANY(:ids) OR delegate_to = ANY(:ids)", uids),
        ("audit_logs", "DELETE FROM audit_logs WHERE user_id = ANY(:ids)", uids),
        ("extraction_verifications", "DELETE FROM extraction_verifications WHERE verified_by = ANY(:ids)", uids),

        # ── Phase 9: Remaining tenant-scoped ──
        ("notification_rules", "DELETE FROM notification_rules WHERE tenant_id = :tid", tid),
        ("snow_sla_mappings", "DELETE FROM snow_sla_mappings WHERE tenant_id = :tid", tid),
        ("industry_compliance_rules", "DELETE FROM industry_compliance_rules WHERE tenant_id = :tid", tid),
        ("clients", "DELETE FROM clients WHERE tenant_id = :tid", tid),
        ("integration_configs", "DELETE FROM integration_configs WHERE tenant_id = :tid", tid),

        # ── Phase 10: Users & business units ──
        ("users", "DELETE FROM users WHERE tenant_id = :tid", tid),
        ("business_units", "DELETE FROM business_units WHERE tenant_id = :tid", tid),

        # ── Phase 11: Tenant itself ──
        ("tenants", "DELETE FROM tenants WHERE id = :tid", tid),
    ]

    for tbl_name, sql, params in stmts:
        result = await db.execute(text(sql), params)
        if result.rowcount > 0 and not tbl_name.startswith("_null"):
            stats["deleted"][tbl_name] = result.rowcount

    await db.commit()
    logger.info(f"Purged tenant '{tenant_name}' ({tenant_id}): {stats['deleted']}")

    return stats


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


@router.post("/{tenant_id}/bridge-governance", status_code=status.HTTP_200_OK)
async def bridge_governance_for_tenant(
    tenant_id: uuid.UUID,
    current_user: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Run governance bridge on all contracts for a tenant.

    Creates business relationships, KPIs, improvement points, etc.
    for contracts that were uploaded before the internal org existed.

    - Unlinked contracts get the full bridge (relationship + KPIs + improvements).
    - Already-linked contracts get KPIs backfilled (idempotent, skips duplicates).
    """
    from app.services.governance_bridge import GovernanceBridgeService

    tenant = await tenant_service.get_tenant_by_id(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    bridge = GovernanceBridgeService(db)
    bridged = 0
    kpis_created = 0
    errors = []

    # Phase 1: Bridge unlinked contracts (full pipeline)
    result = await db.execute(
        select(Contract).where(
            Contract.tenant_id == tenant_id,
            Contract.business_relationship_id.is_(None),
        )
    )
    unlinked = result.scalars().all()

    for contract in unlinked:
        try:
            summary = await bridge.bridge_contract_to_governance(
                contract_id=contract.id,
                tenant_id=tenant_id,
            )
            await db.commit()
            if summary.get("relationship_created") or summary.get("relationship_matched"):
                bridged += 1
            kpis_created += summary.get("kpis_created", 0)
            if summary.get("errors"):
                errors.extend(summary["errors"])
        except Exception as e:
            logger.warning(f"Bridge failed for contract {contract.id}: {e}")
            errors.append(f"{contract.id}: {str(e)}")
            await db.rollback()

    # Phase 2: Backfill KPIs for already-linked contracts
    from app.models.relationship import BusinessRelationship
    result = await db.execute(
        select(Contract).where(
            Contract.tenant_id == tenant_id,
            Contract.business_relationship_id.isnot(None),
        )
    )
    linked = result.scalars().all()

    for contract in linked:
        try:
            # Load the relationship
            rel_result = await db.execute(
                select(BusinessRelationship).where(
                    BusinessRelationship.id == contract.business_relationship_id
                )
            )
            relationship = rel_result.scalar_one_or_none()
            if relationship:
                new_kpis = await bridge._create_kpis_from_slas(contract, relationship)
                kpis_created += len(new_kpis)
                await db.commit()
        except Exception as e:
            logger.warning(f"KPI backfill failed for contract {contract.id}: {e}")
            await db.rollback()

    return {
        "tenant": tenant.name,
        "unlinked_bridged": bridged,
        "kpis_created": kpis_created,
        "total_contracts": len(unlinked) + len(linked),
        "errors": errors[:10] if errors else [],
    }
