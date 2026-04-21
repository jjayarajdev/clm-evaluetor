"""SharePoint Integration Router — connect, browse, and import contracts.

Provides tenant-scoped endpoints for:
1. Configuring SharePoint connection (Azure AD credentials)
2. Browsing sites, document libraries, and folders
3. Importing contracts from a SharePoint folder into the platform
4. Checking import job status
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
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
from app.database import get_db, async_session_maker
from app.models.integration import (
    IntegrationConfig,
    IntegrationLog,
    IntegrationSystem,
    IntegrationStatus,
)
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/integrations/sharepoint",
    tags=["SharePoint Integration"],
)


# ── Pydantic Schemas ──────────────────────────────────────────────────


class SharePointCredentials(BaseModel):
    """Azure AD app registration credentials for SharePoint access."""

    azure_tenant_id: str = Field(..., description="Azure AD tenant ID (directory ID)")
    client_id: str = Field(..., description="App registration client ID")
    client_secret: str = Field(..., description="App registration client secret")


class SharePointConfigCreate(BaseModel):
    """Request body for creating/updating a SharePoint config."""

    name: str = Field(default="SharePoint", max_length=200)
    credentials: SharePointCredentials
    config: Optional[dict] = Field(
        default=None,
        description="Extra settings (default_site_id, default_drive_id, sync_interval_minutes, etc.)",
    )


class SharePointConfigResponse(BaseModel):
    """SharePoint config response (credentials redacted)."""

    id: UUID
    name: str
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
    # Expose non-secret credential fields
    azure_tenant_id: Optional[str] = None

    model_config = {"from_attributes": True}


class TestConnectionResponse(BaseModel):
    """Connection test result."""

    healthy: bool
    message: str


class SiteResponse(BaseModel):
    """SharePoint site."""

    id: str
    name: str
    display_name: Optional[str] = None
    web_url: Optional[str] = None


class DriveResponse(BaseModel):
    """SharePoint document library (drive)."""

    id: str
    name: str
    description: Optional[str] = None
    web_url: Optional[str] = None
    item_count: Optional[int] = None


class FolderItemResponse(BaseModel):
    """A file or folder in SharePoint."""

    id: str
    name: str
    size: Optional[int] = None
    is_folder: bool
    mime_type: Optional[str] = None
    last_modified: Optional[str] = None
    web_url: Optional[str] = None
    child_count: Optional[int] = None


class ImportRequest(BaseModel):
    """Request to import files from a SharePoint folder."""

    drive_id: str = Field(..., description="Document library (drive) ID")
    folder_path: str = Field(default="root", description="Folder path to import from")
    recursive: bool = Field(default=True, description="Include subfolders")
    file_types: list[str] = Field(
        default=[".pdf", ".docx"],
        description="File extensions to import",
    )
    client_id: Optional[str] = Field(default=None, description="Assign to this client")


class ImportStatusResponse(BaseModel):
    """Import job status."""

    job_id: str
    status: str  # pending, running, completed, failed
    total_files: int
    imported: int
    skipped: int
    failed: int
    errors: list[str]
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


# In-memory job tracker (simple for now — could be Redis/DB later)
_import_jobs: dict[str, dict] = {}


# ── Helpers ────────────────────────────────────────────────────────────


def _config_to_response(config: IntegrationConfig) -> SharePointConfigResponse:
    """Convert IntegrationConfig to response model with redacted credentials."""
    creds = config.credentials or {}
    return SharePointConfigResponse(
        id=config.id,
        name=config.name,
        is_active=config.is_active,
        health_status=config.health_status.value if hasattr(config.health_status, "value") else str(config.health_status),
        last_health_check=config.last_health_check,
        last_health_message=config.last_health_message,
        total_requests=config.total_requests,
        failed_requests=config.failed_requests,
        last_used_at=config.last_used_at,
        config=config.config,
        created_at=config.created_at,
        updated_at=config.updated_at,
        azure_tenant_id=creds.get("azure_tenant_id"),
    )


async def _get_sharepoint_client(db: AsyncSession, tenant_id: UUID):
    """Get a configured SharePoint client for this tenant."""
    from app.integrations.sharepoint import SharePointClient

    query = select(IntegrationConfig).where(
        IntegrationConfig.tenant_id == tenant_id,
        IntegrationConfig.system == IntegrationSystem.sharepoint,
        IntegrationConfig.is_active.is_(True),
    )
    result = await db.execute(query)
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No SharePoint configuration found. Please configure SharePoint first.",
        )

    return SharePointClient(config, db)


# ── Configuration Endpoints ────────────────────────────────────────────


@router.get("/config", response_model=Optional[SharePointConfigResponse])
async def get_sharepoint_config(
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = None,
):
    """Get SharePoint configuration for the current tenant."""
    query = select(IntegrationConfig).where(
        IntegrationConfig.tenant_id == tenant_id,
        IntegrationConfig.system == IntegrationSystem.sharepoint,
    )
    result = await db.execute(query)
    config = result.scalar_one_or_none()

    if not config:
        return None

    return _config_to_response(config)


@router.post("/config", response_model=SharePointConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_sharepoint_config(
    body: SharePointConfigCreate,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = None,
):
    """Create or update SharePoint configuration for the current tenant."""
    query = select(IntegrationConfig).where(
        IntegrationConfig.tenant_id == tenant_id,
        IntegrationConfig.system == IntegrationSystem.sharepoint,
    )
    result = await db.execute(query)
    config = result.scalar_one_or_none()

    creds = body.credentials.model_dump()

    if config:
        config.name = body.name
        config.credentials = creds
        config.config = body.config
        config.is_active = True
        config.base_url = "https://graph.microsoft.com/v1.0"
        config.auth_type = "oauth2"
    else:
        config = IntegrationConfig(
            id=uuid4(),
            tenant_id=tenant_id,
            system=IntegrationSystem.sharepoint,
            name=body.name,
            base_url="https://graph.microsoft.com/v1.0",
            auth_type="oauth2",
            credentials=creds,
            config=body.config,
            is_active=True,
            health_status=IntegrationStatus.unknown,
        )
        db.add(config)

    await db.flush()
    await db.commit()
    return _config_to_response(config)


@router.post("/config/test", response_model=TestConnectionResponse)
async def test_sharepoint_connection(
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = None,
):
    """Test the SharePoint connection for the current tenant."""
    try:
        sp = await _get_sharepoint_client(db, tenant_id)
        async with sp:
            healthy = await sp.health_check()

        # Update health status
        config = sp.config
        config.health_status = IntegrationStatus.healthy if healthy else IntegrationStatus.unhealthy
        config.last_health_check = datetime.utcnow()
        config.last_health_message = "Connected" if healthy else "Authentication failed"
        await db.commit()

        return TestConnectionResponse(
            healthy=healthy,
            message="Connected to Microsoft Graph API" if healthy else "Authentication failed — check credentials",
        )
    except HTTPException:
        raise
    except Exception as e:
        return TestConnectionResponse(healthy=False, message=str(e))


@router.delete("/config")
async def delete_sharepoint_config(
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = None,
):
    """Deactivate SharePoint configuration."""
    query = select(IntegrationConfig).where(
        IntegrationConfig.tenant_id == tenant_id,
        IntegrationConfig.system == IntegrationSystem.sharepoint,
    )
    result = await db.execute(query)
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="No SharePoint configuration found")

    config.is_active = False
    await db.commit()
    return {"status": "disconnected"}


# ── Browse Endpoints ───────────────────────────────────────────────────


@router.get("/sites", response_model=list[SiteResponse])
async def search_sites(
    q: str = Query(..., min_length=2, description="Search query"),
    tenant_id: RequiredTenantId = None,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = None,
):
    """Search for SharePoint sites by name."""
    sp = await _get_sharepoint_client(db, tenant_id)
    async with sp:
        sites = await sp.search_sites(q)

    return [
        SiteResponse(
            id=s.get("id", ""),
            name=s.get("name", ""),
            display_name=s.get("displayName"),
            web_url=s.get("webUrl"),
        )
        for s in sites
    ]


@router.get("/sites/{site_id}/drives", response_model=list[DriveResponse])
async def list_document_libraries(
    site_id: str,
    tenant_id: RequiredTenantId = None,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = None,
):
    """List document libraries (drives) in a SharePoint site."""
    sp = await _get_sharepoint_client(db, tenant_id)
    async with sp:
        drives = await sp.list_drives(site_id)

    return [
        DriveResponse(
            id=d.get("id", ""),
            name=d.get("name", ""),
            description=d.get("description"),
            web_url=d.get("webUrl"),
            item_count=d.get("quota", {}).get("used"),
        )
        for d in drives
    ]


@router.get("/drives/{drive_id}/browse", response_model=list[FolderItemResponse])
async def browse_folder(
    drive_id: str,
    path: str = Query(default="root", description="Folder path"),
    tenant_id: RequiredTenantId = None,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = None,
):
    """Browse files and folders in a document library."""
    sp = await _get_sharepoint_client(db, tenant_id)
    async with sp:
        items = await sp.list_folder(drive_id, path)

    return [
        FolderItemResponse(
            id=item.get("id", ""),
            name=item.get("name", ""),
            size=item.get("size"),
            is_folder="folder" in item,
            mime_type=item.get("file", {}).get("mimeType") if "file" in item else None,
            last_modified=item.get("lastModifiedDateTime"),
            web_url=item.get("webUrl"),
            child_count=item.get("folder", {}).get("childCount") if "folder" in item else None,
        )
        for item in items
    ]


# ── Import Endpoints ──────────────────────────────────────────────────


@router.post("/import", response_model=ImportStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def import_from_sharepoint(
    body: ImportRequest,
    background_tasks: BackgroundTasks,
    tenant_id: RequiredTenantId = None,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = None,
):
    """Import contracts from a SharePoint folder.

    Kicks off a background job that:
    1. Lists all matching files in the folder
    2. Downloads each file
    3. Creates contract records and enqueues for AI processing

    Returns a job ID to poll for status.
    """
    # Verify connection first
    sp = await _get_sharepoint_client(db, tenant_id)

    # Create job
    job_id = uuid4().hex[:16]
    _import_jobs[job_id] = {
        "status": "pending",
        "total_files": 0,
        "imported": 0,
        "skipped": 0,
        "failed": 0,
        "errors": [],
        "started_at": None,
        "completed_at": None,
    }

    # Store config ID and user info for background task
    config_id = sp.config.id

    background_tasks.add_task(
        _run_import,
        job_id=job_id,
        config_id=config_id,
        tenant_id=tenant_id,
        user_id=current_user.id,
        drive_id=body.drive_id,
        folder_path=body.folder_path,
        recursive=body.recursive,
        file_types=set(body.file_types),
        client_id=UUID(body.client_id) if body.client_id else None,
    )

    return ImportStatusResponse(job_id=job_id, **_import_jobs[job_id])


@router.get("/import/{job_id}", response_model=ImportStatusResponse)
async def get_import_status(
    job_id: str,
    tenant_id: RequiredTenantId = None,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = None,
):
    """Get the status of a SharePoint import job."""
    job = _import_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")
    return ImportStatusResponse(job_id=job_id, **job)


# ── Background Import Task ────────────────────────────────────────────


async def _run_import(
    job_id: str,
    config_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    drive_id: str,
    folder_path: str,
    recursive: bool,
    file_types: set[str],
    client_id: UUID | None,
):
    """Background task that downloads and imports files from SharePoint."""
    from app.integrations.sharepoint import SharePointClient
    from app.models.contract import Contract, ContractStatus
    from app.services.upload import compute_content_hash, sanitize_filename, ALLOWED_EXTENSIONS
    from app.services.processing_queue import ProcessingQueueService
    from app.config import settings

    job = _import_jobs[job_id]
    job["status"] = "running"
    job["started_at"] = datetime.utcnow().isoformat()

    try:
        async with async_session_maker() as db:
            # Load config
            config = await db.get(IntegrationConfig, config_id)
            if not config:
                job["status"] = "failed"
                job["errors"].append("Integration config not found")
                return

            sp = SharePointClient(config, db)
            async with sp:
                # 1. List files
                if recursive:
                    items = await sp.list_folder_recursive(
                        drive_id, folder_path, file_types
                    )
                else:
                    items = await sp.list_folder(drive_id, folder_path)
                    items = [
                        i for i in items
                        if "file" in i
                        and any(i.get("name", "").lower().endswith(ext) for ext in file_types)
                    ]

                job["total_files"] = len(items)
                logger.info(f"[SP Import {job_id}] Found {len(items)} files to import")

                # 2. Download and create contracts
                upload_dir = Path(settings.upload_dir)
                sp_folder = upload_dir / f"sharepoint_{job_id}"
                sp_folder.mkdir(parents=True, exist_ok=True)

                queue_items = []

                for item in items:
                    filename = item.get("name", "unknown")
                    item_id = item.get("id", "")

                    try:
                        # Check extension
                        ext = Path(filename).suffix.lower()
                        if ext not in ALLOWED_EXTENSIONS:
                            job["skipped"] += 1
                            continue

                        # Download
                        content = await sp.download_file(drive_id, item_id)
                        content_hash = compute_content_hash(content)

                        # Check duplicate by hash
                        existing = await db.execute(
                            select(Contract.id).where(
                                Contract.tenant_id == tenant_id,
                                Contract.content_hash == content_hash,
                            ).limit(1)
                        )
                        if existing.scalar_one_or_none():
                            job["skipped"] += 1
                            logger.debug(f"  Skipping duplicate: {filename}")
                            continue

                        # Save to disk
                        safe_name = sanitize_filename(filename)
                        file_path = sp_folder / safe_name
                        counter = 1
                        while file_path.exists():
                            stem = Path(safe_name).stem
                            file_path = sp_folder / f"{stem}_{counter}{ext}"
                            counter += 1

                        with open(file_path, "wb") as f:
                            f.write(content)

                        # Determine MIME type
                        mime_map = {
                            ".pdf": "application/pdf",
                            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            ".doc": "application/msword",
                            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        }
                        mime_type = item.get("file", {}).get("mimeType") or mime_map.get(ext, "application/octet-stream")

                        # Create contract record
                        contract = Contract(
                            filename=filename,
                            file_path=str(file_path),
                            file_size=len(content),
                            mime_type=mime_type,
                            content_hash=content_hash,
                            status=ContractStatus.PENDING,
                            uploaded_by=user_id,
                            tenant_id=tenant_id,
                            client_id=client_id,
                        )
                        db.add(contract)
                        await db.flush()

                        queue_items.append((str(contract.id), filename))
                        job["imported"] += 1
                        logger.info(f"  Imported: {filename} ({len(content)} bytes)")

                    except Exception as e:
                        job["failed"] += 1
                        job["errors"].append(f"{filename}: {str(e)[:200]}")
                        logger.warning(f"  Failed: {filename} — {e}")

                # 3. Enqueue for processing
                if queue_items:
                    queue_svc = ProcessingQueueService(db)
                    batch_items = [
                        {"contract_id": cid, "filename": fn}
                        for cid, fn in queue_items
                    ]
                    await queue_svc.enqueue_batch(
                        batch_items, f"sp_{job_id}", str(tenant_id)
                    )

                await db.commit()

        job["status"] = "completed"
        job["completed_at"] = datetime.utcnow().isoformat()
        logger.info(
            f"[SP Import {job_id}] Complete: "
            f"{job['imported']} imported, {job['skipped']} skipped, {job['failed']} failed"
        )

    except Exception as e:
        job["status"] = "failed"
        job["errors"].append(str(e)[:500])
        job["completed_at"] = datetime.utcnow().isoformat()
        logger.exception(f"[SP Import {job_id}] Failed: {e}")


# ── Super Admin Endpoints ─────────────────────────────────────────────


@router.get("/admin/overview")
async def admin_overview(
    db: AsyncSession = Depends(get_db),
    current_user: SuperAdminUser = None,
):
    """Super admin: list all tenant SharePoint configs."""
    query = select(IntegrationConfig).where(
        IntegrationConfig.system == IntegrationSystem.sharepoint,
    )
    result = await db.execute(query)
    configs = result.scalars().all()

    return [
        {
            "id": str(c.id),
            "tenant_id": str(c.tenant_id) if c.tenant_id else None,
            "name": c.name,
            "is_active": c.is_active,
            "health_status": c.health_status.value if hasattr(c.health_status, "value") else str(c.health_status),
            "last_health_check": c.last_health_check,
            "total_requests": c.total_requests,
            "failed_requests": c.failed_requests,
        }
        for c in configs
    ]


@router.get("/admin/logs")
async def admin_logs(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: SuperAdminUser = None,
):
    """Super admin: get recent SharePoint integration logs."""
    config_query = select(IntegrationConfig.id).where(
        IntegrationConfig.system == IntegrationSystem.sharepoint,
    )
    config_result = await db.execute(config_query)
    config_ids = [row[0] for row in config_result.all()]

    if not config_ids:
        return []

    log_query = (
        select(IntegrationLog)
        .where(IntegrationLog.integration_id.in_(config_ids))
        .order_by(desc(IntegrationLog.started_at))
        .limit(limit)
    )
    log_result = await db.execute(log_query)
    logs = log_result.scalars().all()

    return [
        {
            "id": str(log.id),
            "operation": log.operation,
            "method": log.method,
            "endpoint": log.endpoint,
            "status_code": log.status_code,
            "is_success": log.is_success,
            "error_message": log.error_message,
            "duration_ms": log.duration_ms,
            "started_at": log.started_at.isoformat() if log.started_at else None,
        }
        for log in logs
    ]
