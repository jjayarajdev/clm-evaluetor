"""Admin API endpoints for extraction quality golden set management.

Provides:
- Golden set overview (aggregate quality metrics)
- Golden set CRUD (add/remove contracts)
- Extraction detail view (metadata, clauses, obligations, SLAs)
- Verification workflow (mark items correct/incorrect/partial)

Supports global (platform-wide) and tenant-specific golden sets.
Super admin can add contracts to the global golden set (is_global=True).
Tenant admins see both global and their own tenant entries.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, AdminUser, CurrentTenantId
from app.services.extraction_quality_service import (
    get_golden_set_overview,
    list_golden_set,
    get_extraction_detail,
    add_to_golden_set,
    remove_from_golden_set,
    verify_extraction,
)

router = APIRouter(prefix="/api/admin/extraction-quality", tags=["extraction-quality"])


# ============== Pydantic Models ==============

class AddToGoldenSetRequest(BaseModel):
    notes: Optional[str] = None
    is_global: bool = False


class VerifyExtractionRequest(BaseModel):
    golden_set_id: str
    entity_type: str  # "metadata_field", "clause", "obligation", "sla"
    entity_id: str
    status: str  # "correct", "incorrect", "partial"
    corrected_value: Optional[dict] = None
    notes: Optional[str] = None


class BulkVerifyRequest(BaseModel):
    golden_set_id: str
    verifications: list[dict]


# ============== Endpoints ==============

@router.get("/overview")
async def golden_set_overview(
    tenant_id: CurrentTenantId,
    current_user: AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Get aggregate extraction quality metrics for the golden set.

    Tenant admins see metrics for global + their own entries.
    Super admins see metrics for all entries.
    """
    return await get_golden_set_overview(db, tenant_id)


@router.get("/golden-set")
async def list_golden_set_contracts(
    tenant_id: CurrentTenantId,
    current_user: AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """List all contracts in the visible golden set.

    Tenant admins see global entries + their own tenant entries.
    Super admins see all entries across all tenants.
    """
    return await list_golden_set(db, tenant_id)


@router.post("/golden-set/{contract_id}")
async def add_contract_to_golden_set(
    contract_id: UUID,
    body: AddToGoldenSetRequest,
    tenant_id: CurrentTenantId,
    current_user: AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Add a contract to the golden set.

    If is_global=True (super admin only), creates a platform-wide entry.
    Otherwise creates a tenant-specific entry.
    """
    if body.is_global and tenant_id is not None:
        raise HTTPException(
            status_code=403,
            detail="Only super admin can add to global golden set"
        )
    if not body.is_global and tenant_id is None:
        raise HTTPException(
            status_code=400,
            detail="Super admin must use is_global=True or specify X-Tenant-ID"
        )
    try:
        golden = await add_to_golden_set(
            db, contract_id, tenant_id, current_user.id,
            notes=body.notes, is_global=body.is_global,
        )
        await db.commit()
        return {
            "id": str(golden.id),
            "contract_id": str(contract_id),
            "is_global": golden.is_global,
            "status": "added",
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/golden-set/{contract_id}")
async def remove_contract_from_golden_set(
    contract_id: UUID,
    tenant_id: CurrentTenantId,
    current_user: AdminUser,
    is_global: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Remove a contract from the golden set.

    Super admin can remove global entries (is_global=True query param).
    Tenant admins can only remove their own entries.
    """
    try:
        removed = await remove_from_golden_set(
            db, contract_id, tenant_id, is_global=is_global,
        )
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not removed:
        raise HTTPException(status_code=404, detail="Contract not in golden set")
    await db.commit()
    return {"contract_id": str(contract_id), "status": "removed"}


@router.get("/contracts/{contract_id}")
async def extraction_detail(
    contract_id: UUID,
    tenant_id: CurrentTenantId,
    current_user: AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Get full extraction detail for a contract — metadata, clauses, obligations, SLAs."""
    detail = await get_extraction_detail(db, contract_id, tenant_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Contract not found")
    return detail


@router.post("/verify")
async def verify_extraction_item(
    body: VerifyExtractionRequest,
    tenant_id: CurrentTenantId,
    current_user: AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Verify (correct/incorrect/partial) an extracted item."""
    if body.status not in ("correct", "incorrect", "partial"):
        raise HTTPException(status_code=400, detail="Invalid status")
    try:
        verification = await verify_extraction(
            db,
            golden_set_id=UUID(body.golden_set_id),
            entity_type=body.entity_type,
            entity_id=body.entity_id,
            status=body.status,
            user_id=current_user.id,
            corrected_value=body.corrected_value,
            notes=body.notes,
            tenant_id=tenant_id,
        )
        await db.commit()
        return {
            "id": str(verification.id),
            "status": verification.status,
            "entity_type": verification.entity_type,
            "entity_id": verification.entity_id,
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/compile")
async def compile_dspy_programs(
    tenant_id: CurrentTenantId,
    current_user: AdminUser,
    agent_types: Optional[list[str]] = None,
    db: AsyncSession = Depends(get_db),
):
    """Compile DSPy extraction programs from golden set verifications.

    Uses verified golden set data to optimize extraction prompts via
    DSPy's BootstrapFewShot optimizer. Requires at least 3 verified
    examples per agent type.

    Super admin compiles global programs; tenant admin compiles tenant-specific.
    """
    from app.services.dspy_compiler import compile_for_tenant
    try:
        results = await compile_for_tenant(db, tenant_id, agent_types)
        return {"tenant_id": str(tenant_id) if tenant_id else "global", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compilation failed: {e}")


@router.get("/compile/status")
async def compilation_status(
    tenant_id: CurrentTenantId,
    current_user: AdminUser,
):
    """Check which DSPy compiled programs exist for the current tenant."""
    from app.services.dspy_compiler import get_compilation_status
    status = await get_compilation_status(tenant_id)
    return {"tenant_id": str(tenant_id) if tenant_id else "global", "programs": status}


@router.post("/verify/bulk")
async def bulk_verify(
    body: BulkVerifyRequest,
    tenant_id: CurrentTenantId,
    current_user: AdminUser,
    db: AsyncSession = Depends(get_db),
):
    """Bulk verify multiple extraction items at once."""
    results = []
    try:
        for item in body.verifications:
            verification = await verify_extraction(
                db,
                golden_set_id=UUID(body.golden_set_id),
                entity_type=item["entity_type"],
                entity_id=item["entity_id"],
                status=item["status"],
                user_id=current_user.id,
                corrected_value=item.get("corrected_value"),
                notes=item.get("notes"),
                tenant_id=tenant_id,
            )
            results.append({
                "entity_type": verification.entity_type,
                "entity_id": verification.entity_id,
                "status": verification.status,
            })
        await db.commit()
        return {"verified": len(results), "results": results}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
