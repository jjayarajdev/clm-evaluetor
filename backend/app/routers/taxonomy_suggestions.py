"""Taxonomy Suggestions router.

Allows tenant admins to review, approve, modify, or reject
AI-discovered taxonomy items from contract processing.
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import AdminUser
from app.database import get_db
from app.models.taxonomy_suggestion import SuggestionStatus, TaxonomySuggestion
from app.models.tenant import Tenant
from app.services import tenant_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/taxonomy-suggestions", tags=["Taxonomy Suggestions"])


# =============================================================================
# Schemas
# =============================================================================


class SuggestionResponse(BaseModel):
    id: str
    contract_id: str
    business_unit_id: str | None
    category: str
    code: str
    label: str
    details: dict
    source_agent: str
    confidence: float
    source_text: str | None
    status: str
    created_at: str


class ApproveRequest(BaseModel):
    """Optionally modify code/label/details before approving."""
    code: str | None = None
    label: str | None = None
    details: dict | None = None


class SuggestionStats(BaseModel):
    pending: int
    approved: int
    rejected: int
    by_category: dict[str, int]


# =============================================================================
# Endpoints
# =============================================================================


@router.get("", response_model=list[SuggestionResponse])
async def list_suggestions(
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = "pending",
    category: str | None = None,
    contract_id: str | None = None,
) -> list[SuggestionResponse]:
    """List taxonomy suggestions for the current tenant."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="No tenant context")

    query = (
        select(TaxonomySuggestion)
        .where(TaxonomySuggestion.tenant_id == current_user.tenant_id)
        .order_by(TaxonomySuggestion.created_at.desc())
    )
    if status_filter:
        query = query.where(TaxonomySuggestion.status == status_filter)
    if category:
        query = query.where(TaxonomySuggestion.category == category)
    if contract_id:
        query = query.where(
            TaxonomySuggestion.contract_id == uuid.UUID(contract_id)
        )

    result = await db.execute(query)
    suggestions = result.scalars().all()

    return [
        SuggestionResponse(
            id=str(s.id),
            contract_id=str(s.contract_id),
            business_unit_id=str(s.business_unit_id) if s.business_unit_id else None,
            category=s.category,
            code=s.code,
            label=s.label,
            details=s.details or {},
            source_agent=s.source_agent,
            confidence=s.confidence,
            source_text=s.source_text,
            status=s.status,
            created_at=s.created_at.isoformat(),
        )
        for s in suggestions
    ]


@router.get("/stats", response_model=SuggestionStats)
async def get_suggestion_stats(
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuggestionStats:
    """Get suggestion counts by status and category."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="No tenant context")

    # Status counts
    status_result = await db.execute(
        select(TaxonomySuggestion.status, func.count())
        .where(TaxonomySuggestion.tenant_id == current_user.tenant_id)
        .group_by(TaxonomySuggestion.status)
    )
    status_counts = dict(status_result.fetchall())

    # Category counts (pending only)
    cat_result = await db.execute(
        select(TaxonomySuggestion.category, func.count())
        .where(
            TaxonomySuggestion.tenant_id == current_user.tenant_id,
            TaxonomySuggestion.status == SuggestionStatus.PENDING.value,
        )
        .group_by(TaxonomySuggestion.category)
    )
    category_counts = dict(cat_result.fetchall())

    return SuggestionStats(
        pending=status_counts.get(SuggestionStatus.PENDING.value, 0),
        approved=status_counts.get(SuggestionStatus.APPROVED.value, 0)
        + status_counts.get(SuggestionStatus.MODIFIED.value, 0),
        rejected=status_counts.get(SuggestionStatus.REJECTED.value, 0),
        by_category=category_counts,
    )


@router.post("/{suggestion_id}/approve")
async def approve_suggestion(
    suggestion_id: uuid.UUID,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    body: ApproveRequest | None = None,
) -> dict:
    """Approve a suggestion, adding it to the tenant's custom taxonomy.

    Optionally modify the code, label, or details before approving.
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="No tenant context")

    result = await db.execute(
        select(TaxonomySuggestion).where(
            TaxonomySuggestion.id == suggestion_id,
            TaxonomySuggestion.tenant_id == current_user.tenant_id,
        )
    )
    suggestion = result.scalar_one_or_none()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    if suggestion.status != SuggestionStatus.PENDING.value:
        raise HTTPException(status_code=400, detail=f"Suggestion already {suggestion.status}")

    # Apply optional modifications
    modified = False
    if body:
        if body.code and body.code != suggestion.code:
            suggestion.code = body.code
            modified = True
        if body.label and body.label != suggestion.label:
            suggestion.label = body.label
            modified = True
        if body.details:
            suggestion.details = {**(suggestion.details or {}), **body.details}
            modified = True

    suggestion.status = (
        SuggestionStatus.MODIFIED.value if modified
        else SuggestionStatus.APPROVED.value
    )

    # Determine where to write: BU config_overrides or tenant config_overrides
    target_name = None
    if suggestion.business_unit_id:
        from app.models.business_unit import BusinessUnit
        bu_result = await db.execute(
            select(BusinessUnit).where(BusinessUnit.id == suggestion.business_unit_id)
        )
        target = bu_result.scalar_one_or_none()
        if target:
            target_name = f"BU:{target.name}"
        else:
            target = None
    else:
        target = None

    if not target:
        # Fall back to tenant
        target = await tenant_service.get_tenant_by_id(db, current_user.tenant_id)
        if not target:
            raise HTTPException(status_code=404, detail="Tenant not found")
        target_name = f"Tenant:{target.name}"

    overrides = dict(target.config_overrides or {})
    category_list = list(overrides.get(suggestion.category, []))

    # Build the taxonomy item
    item = {"code": suggestion.code, "label": suggestion.label}
    if suggestion.details:
        for k, v in suggestion.details.items():
            if v is not None:
                item[k] = v

    # Deduplicate: check both override codes AND base profile codes
    existing_codes = {i.get("code") for i in category_list}

    # Also check base profile to avoid duplicating items already in the profile
    base_profile_codes: set[str] = set()
    if hasattr(target, "industry_profile") and target.industry_profile:
        profile = target.industry_profile
        base_items = getattr(profile, suggestion.category, None)
        if base_items and isinstance(base_items, list):
            base_profile_codes = {i.get("code", "") for i in base_items}
    elif hasattr(target, "industry_profile_id") and target.industry_profile_id:
        from app.models.industry_profile import IndustryProfile
        profile_result = await db.get(IndustryProfile, target.industry_profile_id)
        if profile_result:
            base_items = getattr(profile_result, suggestion.category, None)
            if base_items and isinstance(base_items, list):
                base_profile_codes = {i.get("code", "") for i in base_items}

    if suggestion.code not in existing_codes and suggestion.code not in base_profile_codes:
        category_list.append(item)
        overrides[suggestion.category] = category_list
        target.config_overrides = overrides

    await db.commit()

    logger.info(
        f"Suggestion {suggestion.code} ({suggestion.category}) "
        f"{'modified and ' if modified else ''}approved for {target_name}"
    )

    return {
        "status": "approved",
        "category": suggestion.category,
        "code": suggestion.code,
        "label": suggestion.label,
        "applied_to": target_name,
    }


@router.post("/{suggestion_id}/reject")
async def reject_suggestion(
    suggestion_id: uuid.UUID,
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Reject a suggestion."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="No tenant context")

    result = await db.execute(
        select(TaxonomySuggestion).where(
            TaxonomySuggestion.id == suggestion_id,
            TaxonomySuggestion.tenant_id == current_user.tenant_id,
        )
    )
    suggestion = result.scalar_one_or_none()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    if suggestion.status != SuggestionStatus.PENDING.value:
        raise HTTPException(status_code=400, detail=f"Suggestion already {suggestion.status}")

    suggestion.status = SuggestionStatus.REJECTED.value
    await db.commit()

    return {"status": "rejected", "code": suggestion.code}


@router.post("/approve-all")
async def approve_all_pending(
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = None,
) -> dict:
    """Approve all pending suggestions (optionally filtered by category)."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="No tenant context")

    # Load all pending suggestions
    query = select(TaxonomySuggestion).where(
        TaxonomySuggestion.tenant_id == current_user.tenant_id,
        TaxonomySuggestion.status == SuggestionStatus.PENDING.value,
    )
    if category:
        query = query.where(TaxonomySuggestion.category == category)

    result = await db.execute(query)
    suggestions = result.scalars().all()
    if not suggestions:
        return {"approved": 0}

    # Group suggestions by target (BU or tenant)
    from app.models.business_unit import BusinessUnit

    tenant = await tenant_service.get_tenant_by_id(db, current_user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Cache of targets: None -> tenant, bu_id -> BU object
    targets: dict[uuid.UUID | None, object] = {None: tenant}
    approved_count = 0

    for suggestion in suggestions:
        suggestion.status = SuggestionStatus.APPROVED.value

        # Determine target
        target_key = suggestion.business_unit_id
        if target_key and target_key not in targets:
            bu_result = await db.execute(
                select(BusinessUnit).where(BusinessUnit.id == target_key)
            )
            bu = bu_result.scalar_one_or_none()
            targets[target_key] = bu if bu else tenant
            if not bu:
                target_key = None

        target = targets.get(target_key, tenant)
        overrides = dict(target.config_overrides or {})
        category_list = list(overrides.get(suggestion.category, []))
        existing_codes = {i.get("code") for i in category_list}

        if suggestion.code not in existing_codes:
            item = {"code": suggestion.code, "label": suggestion.label}
            if suggestion.details:
                for k, v in suggestion.details.items():
                    if v is not None:
                        item[k] = v
            category_list.append(item)
            overrides[suggestion.category] = category_list
            target.config_overrides = overrides

        approved_count += 1

    await db.commit()

    logger.info(f"Bulk approved {approved_count} suggestions for tenant {tenant.name}")
    return {"approved": approved_count}
