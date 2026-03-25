"""ServiceNow Integration Router - manage SNOW config, SLA sync, and mappings.

Provides tenant-scoped endpoints for configuring ServiceNow connections,
syncing SLA definitions, and mapping them to platform SLAs.
Super admin endpoints provide cross-tenant oversight.
"""

from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    AdminUser,
    CurrentTenantId,
    RequiredTenantId,
    SuperAdminUser,
    get_current_user,
)
from app.database import get_db
from app.models.integration import (
    IntegrationConfig,
    IntegrationLog,
    IntegrationSystem,
    IntegrationStatus,
)
from app.models.snow_sla_mapping import SnowSLAMapping
from app.models.user import User
from app.services.snow_sync_service import SnowSyncService

router = APIRouter(
    prefix="/api/integrations/servicenow",
    tags=["ServiceNow Integration"],
)


# ── Pydantic Schemas ──────────────────────────────────────────────────


class SnowCredentials(BaseModel):
    """ServiceNow credentials."""

    username: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    token_url: Optional[str] = None


class SnowConfigCreate(BaseModel):
    """Request body for creating/updating a ServiceNow config."""

    name: str = Field(..., max_length=200)
    base_url: str = Field(..., max_length=500, description="e.g. https://dev12345.service-now.com")
    auth_type: str = Field(default="basic", description="basic, oauth2, api_key")
    credentials: SnowCredentials = Field(default_factory=SnowCredentials)
    config: Optional[dict] = Field(default=None, description="Extra settings (assignment_group, api_version, etc.)")


class SnowConfigResponse(BaseModel):
    """ServiceNow config response."""

    id: UUID
    name: str
    base_url: str
    auth_type: str
    is_active: bool
    health_status: str
    last_health_check: Optional[datetime] = None
    last_health_message: Optional[str] = None
    total_requests: int
    failed_requests: int
    last_used_at: Optional[datetime] = None
    config: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SnowMappingResponse(BaseModel):
    """SLA mapping response."""

    id: UUID
    snow_sys_id: str
    snow_sla_name: Optional[str] = None
    snow_metric_type: Optional[str] = None
    snow_target: Optional[str] = None
    platform_sla_id: Optional[UUID] = None
    mapping_status: str
    last_synced_at: Optional[datetime] = None
    sync_metadata: Optional[dict] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MappingUpdate(BaseModel):
    """Request body for updating a mapping."""

    platform_sla_id: Optional[UUID] = None
    status: str = Field(..., description="mapped, ignored, pending, error")


class SyncResultResponse(BaseModel):
    """Sync operation result."""

    fetched: int
    created: int
    updated: int
    errors: int


class TestConnectionResponse(BaseModel):
    """Connection test result."""

    healthy: bool
    message: str


class AdminConfigOverview(BaseModel):
    """Super admin view of a tenant's SNOW config."""

    id: UUID
    tenant_id: Optional[UUID] = None
    name: str
    base_url: str
    is_active: bool
    health_status: str
    last_health_check: Optional[datetime] = None
    total_requests: int
    failed_requests: int
    mapping_count: int = 0

    model_config = {"from_attributes": True}


class AdminLogEntry(BaseModel):
    """Integration log entry for admin view."""

    id: UUID
    integration_id: UUID
    operation: str
    method: str
    endpoint: str
    status_code: Optional[int] = None
    is_success: bool
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    started_at: datetime

    model_config = {"from_attributes": True}


# ── Tenant Admin Endpoints ────────────────────────────────────────────


@router.get("/config", response_model=Optional[SnowConfigResponse])
async def get_snow_config(
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get ServiceNow configuration for the current tenant.

    Returns:
        The active ServiceNow config or null.
    """
    svc = SnowSyncService(db)
    config = await svc.get_tenant_config(tenant_id)
    if not config:
        return None
    return SnowConfigResponse.model_validate(config)


@router.post("/config", response_model=SnowConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_snow_config(
    body: SnowConfigCreate,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update ServiceNow configuration for the current tenant.

    If an active config already exists for this tenant, it will be updated.
    Otherwise a new config is created.

    Args:
        body: ServiceNow config details.

    Returns:
        Created or updated config.
    """
    # Look for existing config
    query = select(IntegrationConfig).where(
        IntegrationConfig.tenant_id == tenant_id,
        IntegrationConfig.system == IntegrationSystem.servicenow,
    )
    result = await db.execute(query)
    config = result.scalar_one_or_none()

    if config:
        # Update existing
        config.name = body.name
        config.base_url = body.base_url
        config.auth_type = body.auth_type
        config.credentials = body.credentials.model_dump(exclude_none=True)
        config.config = body.config
        config.is_active = True
    else:
        # Create new
        config = IntegrationConfig(
            id=uuid4(),
            tenant_id=tenant_id,
            system=IntegrationSystem.servicenow,
            name=body.name,
            base_url=body.base_url,
            auth_type=body.auth_type,
            credentials=body.credentials.model_dump(exclude_none=True),
            config=body.config,
            is_active=True,
            health_status=IntegrationStatus.unknown,
        )
        db.add(config)

    await db.flush()
    return SnowConfigResponse.model_validate(config)


@router.post("/config/test", response_model=TestConnectionResponse)
async def test_snow_connection(
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Test the ServiceNow connection for the current tenant.

    Returns:
        Connection health status.
    """
    svc = SnowSyncService(db)
    config = await svc.get_tenant_config(tenant_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ServiceNow configuration found for this tenant.",
        )

    try:
        result = await svc.test_connection(config)
        return TestConnectionResponse(**result)
    except Exception as e:
        return TestConnectionResponse(healthy=False, message=str(e))


@router.post("/sync", response_model=SyncResultResponse)
async def trigger_sla_sync(
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger SLA definition sync from ServiceNow.

    Fetches SLA definitions from ServiceNow and creates/updates
    local mapping records.

    Returns:
        Sync statistics.
    """
    svc = SnowSyncService(db)
    config = await svc.get_tenant_config(tenant_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ServiceNow configuration found for this tenant.",
        )

    try:
        stats = await svc.sync_sla_definitions(config)
        return SyncResultResponse(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Sync failed: {str(e)}",
        )


@router.get("/mappings", response_model=list[SnowMappingResponse])
async def list_sla_mappings(
    tenant_id: RequiredTenantId,
    config_id: Optional[UUID] = Query(default=None, description="Filter by integration config ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List SLA mappings for the current tenant.

    Args:
        config_id: Optional integration config ID filter.

    Returns:
        List of SLA mappings.
    """
    svc = SnowSyncService(db)
    mappings = await svc.get_mappings(tenant_id, config_id)
    return [SnowMappingResponse.model_validate(m) for m in mappings]


@router.put("/mappings/{mapping_id}", response_model=SnowMappingResponse)
async def update_sla_mapping(
    mapping_id: UUID,
    body: MappingUpdate,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an SLA mapping (link to platform SLA or set to ignored).

    Args:
        mapping_id: The mapping UUID.
        body: Update payload with platform_sla_id and status.

    Returns:
        Updated mapping.
    """
    svc = SnowSyncService(db)
    try:
        mapping = await svc.update_mapping(
            mapping_id=mapping_id,
            tenant_id=tenant_id,
            platform_sla_id=body.platform_sla_id,
            status=body.status,
        )
        return SnowMappingResponse.model_validate(mapping)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# ── Super Admin Endpoints ─────────────────────────────────────────────


@router.get("/admin/overview", response_model=list[AdminConfigOverview])
async def admin_overview(
    db: AsyncSession = Depends(get_db),
    current_user: SuperAdminUser = None,
):
    """Super admin: list all tenant ServiceNow configs with health status.

    Returns:
        List of all SNOW configs across tenants.
    """
    query = select(IntegrationConfig).where(
        IntegrationConfig.system == IntegrationSystem.servicenow,
    )
    result = await db.execute(query)
    configs = result.scalars().all()

    overview = []
    for config in configs:
        # Count mappings for this config
        count_result = await db.execute(
            select(func.count(SnowSLAMapping.id)).where(
                SnowSLAMapping.integration_config_id == config.id,
            )
        )
        mapping_count = count_result.scalar() or 0

        item = AdminConfigOverview(
            id=config.id,
            tenant_id=config.tenant_id,
            name=config.name,
            base_url=config.base_url,
            is_active=config.is_active,
            health_status=config.health_status.value if hasattr(config.health_status, 'value') else str(config.health_status),
            last_health_check=config.last_health_check,
            total_requests=config.total_requests,
            failed_requests=config.failed_requests,
            mapping_count=mapping_count,
        )
        overview.append(item)

    return overview


@router.get("/admin/logs", response_model=list[AdminLogEntry])
async def admin_logs(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: SuperAdminUser = None,
):
    """Super admin: get recent integration logs for ServiceNow.

    Args:
        limit: Number of log entries to return.

    Returns:
        Recent integration log entries.
    """
    # Get all SNOW config IDs
    config_query = select(IntegrationConfig.id).where(
        IntegrationConfig.system == IntegrationSystem.servicenow,
    )
    config_result = await db.execute(config_query)
    config_ids = [row[0] for row in config_result.all()]

    if not config_ids:
        return []

    # Get recent logs for those configs
    log_query = (
        select(IntegrationLog)
        .where(IntegrationLog.integration_id.in_(config_ids))
        .order_by(desc(IntegrationLog.started_at))
        .limit(limit)
    )
    log_result = await db.execute(log_query)
    logs = log_result.scalars().all()

    return [AdminLogEntry.model_validate(log) for log in logs]
