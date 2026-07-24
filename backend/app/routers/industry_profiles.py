"""Industry profiles router — list and manage industry profiles."""

import logging
import re
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
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
    # Usage — profiles drive per-contract assignment and tenant fallback;
    # admins need to see impact before editing/retiring one
    tenant_default_count: int = 0
    contract_count: int = 0

    @classmethod
    def from_model(
        cls,
        profile: IndustryProfile,
        tenant_default_count: int = 0,
        contract_count: int = 0,
    ) -> "IndustryProfileSummary":
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
            tenant_default_count=tenant_default_count,
            contract_count=contract_count,
        )


class ContractTypeDef(BaseModel):
    code: str
    label: str
    description: str | None = None
    icon: str | None = None


class ClauseTypeDef(BaseModel):
    code: str
    label: str
    category: str | None = None
    risk_weight: int = Field(default=5, ge=0, le=15)
    description: str | None = None


class RiskCategoryDef(BaseModel):
    code: str
    label: str
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    weight: int = Field(default=10, ge=0, le=30)
    description: str | None = None


class SLAMetricDef(BaseModel):
    code: str
    label: str
    unit: str | None = None
    direction: Literal["lower_is_better", "higher_is_better"] = "lower_is_better"
    default_target: float | None = None
    description: str | None = None


EXTRACTION_HINT_KEYS = {"metadata", "clauses", "risks", "slas", "obligations"}


class IndustryProfileCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=100)
    description: str | None = None
    contract_types: list[ContractTypeDef] = []
    clause_types: list[ClauseTypeDef] = []
    risk_categories: list[RiskCategoryDef] = []
    sla_metrics: list[SLAMetricDef] = []
    field_definitions: dict[str, list[dict]] = {}
    extraction_hints: dict[str, str] = {}
    ui_config: dict = {}

    @field_validator("slug")
    @classmethod
    def slug_is_kebab(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", v):
            raise ValueError("slug must be lowercase kebab-case (a-z, 0-9, hyphens)")
        return v

    @field_validator("extraction_hints")
    @classmethod
    def hints_keys_known(cls, v: dict[str, str]) -> dict[str, str]:
        unknown = set(v.keys()) - EXTRACTION_HINT_KEYS
        if unknown:
            raise ValueError(
                f"Unknown extraction_hints keys: {unknown}. "
                f"Allowed: {EXTRACTION_HINT_KEYS}"
            )
        return v


class GenerateProfileRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=10, max_length=2000)
    sample_contract_text: str | None = None


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:100] or "industry"


def _profile_to_dict(profile: IndustryProfile) -> dict:
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


# =============================================================================
# Endpoints
# =============================================================================


@router.get("", response_model=list[IndustryProfileSummary])
async def list_industry_profiles(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[IndustryProfileSummary]:
    """List all active industry profiles with usage counts."""
    from sqlalchemy import func

    from app.models.contract import Contract
    from app.models.tenant import Tenant

    result = await db.execute(
        select(IndustryProfile)
        .where(IndustryProfile.is_active.is_(True))
        .order_by(IndustryProfile.name)
    )
    profiles = result.scalars().all()

    tenant_counts = dict(
        (
            await db.execute(
                select(Tenant.industry_profile_id, func.count(Tenant.id))
                .where(Tenant.industry_profile_id.isnot(None))
                .group_by(Tenant.industry_profile_id)
            )
        ).all()
    )
    contract_counts = dict(
        (
            await db.execute(
                select(Contract.industry_profile_id, func.count(Contract.id))
                .where(Contract.industry_profile_id.isnot(None))
                .group_by(Contract.industry_profile_id)
            )
        ).all()
    )

    return [
        IndustryProfileSummary.from_model(
            p,
            tenant_default_count=tenant_counts.get(p.id, 0),
            contract_count=contract_counts.get(p.id, 0),
        )
        for p in profiles
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_industry_profile(
    payload: IndustryProfileCreate,
    current_user: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Create a new industry profile (super-admin only)."""
    existing = await db.execute(
        select(IndustryProfile).where(IndustryProfile.slug == payload.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Profile with slug '{payload.slug}' already exists",
        )

    profile = IndustryProfile(
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        contract_types=[ct.model_dump() for ct in payload.contract_types],
        clause_types=[ct.model_dump() for ct in payload.clause_types],
        risk_categories=[rc.model_dump() for rc in payload.risk_categories],
        sla_metrics=[m.model_dump() for m in payload.sla_metrics],
        field_definitions=payload.field_definitions,
        extraction_hints=payload.extraction_hints,
        ui_config=payload.ui_config,
        is_active=True,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    logger.info(f"Industry profile created: {profile.name} ({profile.slug})")
    return _profile_to_dict(profile)


@router.post("/generate")
async def generate_industry_profile(
    payload: GenerateProfileRequest,
    current_user: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Generate a draft industry profile with AI (super-admin only).

    Returns a draft for review — nothing is saved. The draft is validated
    against the same schema as the create endpoint; sections that fail
    validation are returned as-is with warnings so the admin can fix them
    in the review UI.
    """
    from app.services.industry_profile_generator import generate_profile_draft

    try:
        draft = await generate_profile_draft(
            db,
            name=payload.name,
            description=payload.description,
            sample_contract_text=payload.sample_contract_text,
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))

    slug = _slugify(payload.name)
    candidate = {
        "name": payload.name,
        "slug": slug,
        "description": draft.get("description") or payload.description,
        "contract_types": draft.get("contract_types", []),
        "clause_types": draft.get("clause_types", []),
        "risk_categories": draft.get("risk_categories", []),
        "sla_metrics": draft.get("sla_metrics", []),
        "field_definitions": draft.get("field_definitions", {}),
        "extraction_hints": draft.get("extraction_hints", {}),
        "ui_config": draft.get("ui_config", {}),
    }

    warnings: list[str] = []
    try:
        validated = IndustryProfileCreate.model_validate(candidate)
        candidate = validated.model_dump()
    except Exception as e:
        warnings.append(f"Draft has validation issues to fix before saving: {e}")

    existing = await db.execute(
        select(IndustryProfile).where(IndustryProfile.slug == slug)
    )
    if existing.scalar_one_or_none():
        warnings.append(f"Slug '{slug}' is already taken — change it before saving")

    return {"draft": candidate, "warnings": warnings}


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
    current_user: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Update industry profile JSONB fields (super-admin only).

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
