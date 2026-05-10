"""Industry profiles router — list and manage industry profiles."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import AdminUser, CurrentUser, SuperAdminUser
from app.database import get_db
from app.models.industry_profile import IndustryProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/industry-profiles", tags=["Industry Profiles"])


# =============================================================================
# Schemas
# =============================================================================


class IndustryProfileSummary(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    contract_type_count: int
    clause_type_count: int
    risk_category_count: int
    sla_metric_count: int
    is_active: bool

    @classmethod
    def from_model(cls, profile: IndustryProfile) -> "IndustryProfileSummary":
        return cls(
            id=str(profile.id),
            name=profile.name,
            slug=profile.slug,
            description=profile.description,
            contract_type_count=len(profile.contract_types or []),
            clause_type_count=len(profile.clause_types or []),
            risk_category_count=len(profile.risk_categories or []),
            sla_metric_count=len(profile.sla_metrics or []),
            is_active=profile.is_active,
        )


# =============================================================================
# Endpoints
# =============================================================================


@router.get("", response_model=list[IndustryProfileSummary])
async def list_industry_profiles(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[IndustryProfileSummary]:
    """List all active industry profiles."""
    result = await db.execute(
        select(IndustryProfile)
        .where(IndustryProfile.is_active.is_(True))
        .order_by(IndustryProfile.name)
    )
    profiles = result.scalars().all()
    return [IndustryProfileSummary.from_model(p) for p in profiles]


@router.get("/{profile_id}")
async def get_industry_profile(
    profile_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get full industry profile details including all JSONB config."""
    result = await db.execute(
        select(IndustryProfile).where(IndustryProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Industry profile not found")

    return {
        "id": str(profile.id),
        "name": profile.name,
        "slug": profile.slug,
        "description": profile.description,
        "contract_types": profile.contract_types,
        "clause_types": profile.clause_types,
        "risk_categories": profile.risk_categories,
        "sla_metrics": profile.sla_metrics,
        "field_definitions": profile.field_definitions,
        "extraction_hints": profile.extraction_hints,
        "ui_config": profile.ui_config,
        "is_active": profile.is_active,
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


@router.patch("/my-profile", status_code=status.HTTP_200_OK)
async def set_my_tenant_profile(
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    profile_slug: str | None = None,
) -> dict:
    """Set the industry profile for the current user's tenant (admin only)."""
    from app.models.tenant import Tenant

    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="No tenant context")

    result = await db.execute(
        select(Tenant).where(Tenant.id == current_user.tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if profile_slug:
        result = await db.execute(
            select(IndustryProfile).where(
                IndustryProfile.slug == profile_slug,
                IndustryProfile.is_active.is_(True),
            )
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(
                status_code=404, detail=f"Profile '{profile_slug}' not found"
            )
        tenant.industry_profile_id = profile.id
        await db.commit()
        logger.info(
            f"Tenant {tenant.name} assigned industry profile: {profile.name}"
        )
        return {
            "tenant": tenant.name,
            "profile": profile.name,
            "slug": profile.slug,
            "profile_id": str(profile.id),
        }
    else:
        tenant.industry_profile_id = None
        await db.commit()
        logger.info(f"Tenant {tenant.name} cleared industry profile")
        return {"tenant": tenant.name, "profile": None, "slug": None, "profile_id": None}


@router.patch("/{profile_id}/update", status_code=status.HTTP_200_OK)
async def update_industry_profile(
    profile_id: uuid.UUID,
    updates: dict,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Update industry profile JSONB fields (admin only).

    Accepts partial updates to any JSONB column:
    contract_types, clause_types, risk_categories, sla_metrics,
    extraction_hints, ui_config, field_definitions.
    Also accepts name and description.
    """
    result = await db.execute(
        select(IndustryProfile).where(IndustryProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Industry profile not found")

    allowed_keys = {
        "name", "description",
        "contract_types", "clause_types", "risk_categories",
        "sla_metrics", "extraction_hints", "ui_config", "field_definitions",
    }
    invalid_keys = set(updates.keys()) - allowed_keys
    if invalid_keys:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid keys: {invalid_keys}. Allowed: {allowed_keys}",
        )

    for key, value in updates.items():
        setattr(profile, key, value)

    await db.commit()
    await db.refresh(profile)

    logger.info(f"Industry profile '{profile.name}' updated: {list(updates.keys())}")

    return {
        "id": str(profile.id),
        "name": profile.name,
        "slug": profile.slug,
        "description": profile.description,
        "contract_types": profile.contract_types,
        "clause_types": profile.clause_types,
        "risk_categories": profile.risk_categories,
        "sla_metrics": profile.sla_metrics,
        "field_definitions": profile.field_definitions,
        "extraction_hints": profile.extraction_hints,
        "ui_config": profile.ui_config,
        "is_active": profile.is_active,
    }


@router.patch("/{tenant_id}/assign", status_code=status.HTTP_200_OK)
async def assign_profile_to_tenant(
    tenant_id: uuid.UUID,
    current_user: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    profile_slug: str | None = None,
) -> dict:
    """Assign an industry profile to a tenant (super-admin only).

    Pass profile_slug to assign, or null to clear.
    """
    from app.models.tenant import Tenant

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if profile_slug:
        result = await db.execute(
            select(IndustryProfile).where(IndustryProfile.slug == profile_slug)
        )
        profile = result.scalar_one_or_none()
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile '{profile_slug}' not found")
        tenant.industry_profile_id = profile.id
        await db.commit()
        return {"tenant": tenant.name, "profile": profile.name, "slug": profile.slug}
    else:
        tenant.industry_profile_id = None
        await db.commit()
        return {"tenant": tenant.name, "profile": None, "slug": None}
