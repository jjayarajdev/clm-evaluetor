"""Post-Signing Dashboard API endpoints.

Thin HTTP handlers delegating to PostSigningService.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, CurrentTenantId
from app.database import get_db
from app.schemas.postsigning import PostSigningDashboard
from app.services.postsigning_service import PostSigningService

router = APIRouter(prefix="/api/dashboard/postsigning", tags=["postsigning-dashboard"])


def _service(current_user: CurrentUser, tenant_id: CurrentTenantId, db: AsyncSession) -> PostSigningService:
    return PostSigningService(
        db=db,
        tenant_id=tenant_id,
        business_unit_id=current_user.business_unit_id,
        user_role=current_user.role.value if current_user.role else None,
    )


@router.get("", response_model=PostSigningDashboard)
async def get_postsigning_dashboard(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get complete post-signing dashboard data."""
    svc = _service(current_user, tenant_id, db)
    return await svc.get_dashboard()


@router.get("/obligations")
async def get_obligation_details(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    status: str = None,
    rag: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed obligation list with optional filters."""
    svc = _service(current_user, tenant_id, db)
    return await svc.get_obligation_details(status_filter=status, rag_filter=rag)


@router.get("/slas")
async def get_sla_details(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    breached_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed SLA list with optional filters."""
    svc = _service(current_user, tenant_id, db)
    return await svc.get_sla_details(breached_only=breached_only)


@router.get("/milestones")
async def get_milestone_details(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: AsyncSession = Depends(get_db),
):
    """Get all obligations with deadlines (milestones)."""
    svc = _service(current_user, tenant_id, db)
    return await svc.get_milestone_details()
