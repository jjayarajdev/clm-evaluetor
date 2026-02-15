"""Master Data Admin router for SLA and Milestone configurations."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import AdminUser
from app.database import get_db
from app.models.master_data import MilestoneMasterData, SLAMasterData
from app.schemas.master_data import (
    MilestoneMasterDataCreate,
    MilestoneMasterDataListResponse,
    MilestoneMasterDataResponse,
    MilestoneMasterDataUpdate,
    SeedResultResponse,
    SLAMasterDataCreate,
    SLAMasterDataListResponse,
    SLAMasterDataResponse,
    SLAMasterDataUpdate,
)
from app.services.master_data_repository import MasterDataRepository

router = APIRouter(prefix="/api/admin/master-data", tags=["Master Data Admin"])


# ============================================================================
# Helper Functions
# ============================================================================


def sla_to_response(sla: SLAMasterData) -> SLAMasterDataResponse:
    """Convert SLAMasterData model to response schema."""
    return SLAMasterDataResponse(
        id=str(sla.id),
        reference_code=sla.reference_code,
        name=sla.name,
        description=sla.description,
        target_value=float(sla.target_value) if sla.target_value else 0,
        minimum_value=float(sla.minimum_value) if sla.minimum_value else None,
        typical_performance=float(sla.typical_performance) if sla.typical_performance else None,
        volatility=float(sla.volatility) if sla.volatility else None,
        category=sla.category,
        service_tower=sla.service_tower,
        is_active=sla.is_active,
        created_at=sla.created_at,
        updated_at=sla.updated_at,
    )


def milestone_to_response(ms: MilestoneMasterData) -> MilestoneMasterDataResponse:
    """Convert MilestoneMasterData model to response schema."""
    return MilestoneMasterDataResponse(
        id=str(ms.id),
        milestone_code=ms.milestone_code,
        name=ms.name,
        description=ms.description,
        baseline_days_from_start=ms.baseline_days_from_start,
        dependencies=ms.dependencies or [],
        credit_at_risk=float(ms.credit_at_risk) if ms.credit_at_risk else None,
        is_active=ms.is_active,
        created_at=ms.created_at,
        updated_at=ms.updated_at,
    )


# ============================================================================
# SLA Master Data Endpoints
# ============================================================================


@router.get("/slas", response_model=SLAMasterDataListResponse)
async def list_sla_master_data(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: bool = False,
    category: str | None = None,
    service_tower: str | None = None,
):
    """List all SLA master data configurations.

    Requires admin role.
    """
    repo = MasterDataRepository(db)
    slas = await repo.get_all_sla_master_data(
        active_only=active_only,
        category=category,
        service_tower=service_tower,
    )
    return SLAMasterDataListResponse(
        items=[sla_to_response(s) for s in slas],
        total=len(slas),
    )


@router.post("/slas", response_model=SLAMasterDataResponse, status_code=201)
async def create_sla_master_data(
    data: SLAMasterDataCreate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new SLA master data entry.

    Requires admin role.
    """
    repo = MasterDataRepository(db)

    # Check if reference code already exists
    existing = await repo.get_sla_config_by_code(data.reference_code)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"SLA with reference code '{data.reference_code}' already exists",
        )

    sla = await repo.create_sla(data.model_dump())
    await db.commit()
    return sla_to_response(sla)


@router.get("/slas/{sla_id}", response_model=SLAMasterDataResponse)
async def get_sla_master_data(
    sla_id: str,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get a specific SLA master data entry by ID.

    Requires admin role.
    """
    repo = MasterDataRepository(db)
    sla = await repo.get_sla_by_id(sla_id)
    if not sla:
        raise HTTPException(status_code=404, detail="SLA master data not found")
    return sla_to_response(sla)


@router.put("/slas/{sla_id}", response_model=SLAMasterDataResponse)
async def update_sla_master_data(
    sla_id: str,
    data: SLAMasterDataUpdate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update an SLA master data entry.

    Requires admin role.
    """
    repo = MasterDataRepository(db)
    sla = await repo.update_sla(sla_id, data.model_dump(exclude_unset=True))
    if not sla:
        raise HTTPException(status_code=404, detail="SLA master data not found")
    await db.commit()
    return sla_to_response(sla)


@router.delete("/slas/{sla_id}", status_code=204)
async def delete_sla_master_data(
    sla_id: str,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete an SLA master data entry.

    Requires admin role.
    """
    repo = MasterDataRepository(db)
    deleted = await repo.delete_sla(sla_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="SLA master data not found")
    await db.commit()


@router.post("/slas/seed", response_model=SeedResultResponse)
async def seed_sla_master_data(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Seed SLA master data from stub configurations.

    Requires admin role. Skips entries that already exist.
    """
    repo = MasterDataRepository(db)
    seeded, skipped = await repo.seed_sla_from_stubs()
    await db.commit()
    return SeedResultResponse(
        seeded=seeded,
        skipped=skipped,
        message=f"Successfully seeded {seeded} SLA configurations ({skipped} already existed)",
    )


# ============================================================================
# Milestone Master Data Endpoints
# ============================================================================


@router.get("/milestones", response_model=MilestoneMasterDataListResponse)
async def list_milestone_master_data(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: bool = False,
):
    """List all Milestone master data configurations.

    Requires admin role.
    """
    repo = MasterDataRepository(db)
    milestones = await repo.get_all_milestone_master_data(active_only=active_only)
    return MilestoneMasterDataListResponse(
        items=[milestone_to_response(m) for m in milestones],
        total=len(milestones),
    )


@router.post("/milestones", response_model=MilestoneMasterDataResponse, status_code=201)
async def create_milestone_master_data(
    data: MilestoneMasterDataCreate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a new Milestone master data entry.

    Requires admin role.
    """
    repo = MasterDataRepository(db)

    # Check if milestone code already exists
    existing = await repo.get_milestone_config_by_code(data.milestone_code)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Milestone with code '{data.milestone_code}' already exists",
        )

    milestone = await repo.create_milestone(data.model_dump())
    await db.commit()
    return milestone_to_response(milestone)


@router.get("/milestones/{milestone_id}", response_model=MilestoneMasterDataResponse)
async def get_milestone_master_data(
    milestone_id: str,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get a specific Milestone master data entry by ID.

    Requires admin role.
    """
    repo = MasterDataRepository(db)
    milestone = await repo.get_milestone_by_id(milestone_id)
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone master data not found")
    return milestone_to_response(milestone)


@router.put("/milestones/{milestone_id}", response_model=MilestoneMasterDataResponse)
async def update_milestone_master_data(
    milestone_id: str,
    data: MilestoneMasterDataUpdate,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a Milestone master data entry.

    Requires admin role.
    """
    repo = MasterDataRepository(db)
    milestone = await repo.update_milestone(milestone_id, data.model_dump(exclude_unset=True))
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone master data not found")
    await db.commit()
    return milestone_to_response(milestone)


@router.delete("/milestones/{milestone_id}", status_code=204)
async def delete_milestone_master_data(
    milestone_id: str,
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a Milestone master data entry.

    Requires admin role.
    """
    repo = MasterDataRepository(db)
    deleted = await repo.delete_milestone(milestone_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Milestone master data not found")
    await db.commit()


@router.post("/milestones/seed", response_model=SeedResultResponse)
async def seed_milestone_master_data(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Seed Milestone master data from stub configurations.

    Requires admin role. Skips entries that already exist.
    """
    repo = MasterDataRepository(db)
    seeded, skipped = await repo.seed_milestones_from_stubs()
    await db.commit()
    return SeedResultResponse(
        seeded=seeded,
        skipped=skipped,
        message=f"Successfully seeded {seeded} milestone configurations ({skipped} already existed)",
    )


# ============================================================================
# Combined Seed Endpoint
# ============================================================================


@router.post("/seed-all", response_model=dict)
async def seed_all_master_data(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Seed all master data (SLAs and Milestones) from stub configurations.

    Requires admin role. Skips entries that already exist.
    """
    repo = MasterDataRepository(db)
    result = await repo.seed_all_from_stubs()
    await db.commit()
    return {
        "sla": {
            "seeded": result["sla"]["seeded"],
            "skipped": result["sla"]["skipped"],
        },
        "milestones": {
            "seeded": result["milestones"]["seeded"],
            "skipped": result["milestones"]["skipped"],
        },
        "message": "Seed operation completed successfully",
    }


# ============================================================================
# Maintenance Endpoints
# ============================================================================


@router.post("/cleanup-vectors", response_model=dict)
async def cleanup_orphaned_vectors(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Clean up orphaned vectors from ChromaDB.

    Removes vectors that belong to contracts that no longer exist in PostgreSQL.
    Useful after failed deletions or database inconsistencies.

    Requires admin role.
    """
    from sqlalchemy import select
    from app.models.contract import Contract
    from app.services.vector_store import get_vector_store

    vector_store = get_vector_store()

    # Get all valid contract IDs from PostgreSQL
    result = await db.execute(select(Contract.id))
    valid_contract_ids = {str(row[0]) for row in result.fetchall()}

    # Get all contract IDs in ChromaDB
    chromadb_contract_ids = vector_store.get_all_contract_ids()

    # Find orphaned contracts
    orphaned_contracts = chromadb_contract_ids - valid_contract_ids

    if not orphaned_contracts:
        return {
            "status": "ok",
            "message": "No orphaned vectors found",
            "valid_contracts": len(valid_contract_ids),
            "chromadb_contracts": len(chromadb_contract_ids),
            "deleted_vectors": 0,
        }

    # Clean up orphaned vectors
    deleted_count = vector_store.cleanup_orphaned_documents(valid_contract_ids)

    return {
        "status": "cleaned",
        "message": f"Cleaned up vectors for {len(orphaned_contracts)} orphaned contracts",
        "valid_contracts": len(valid_contract_ids),
        "orphaned_contracts": list(orphaned_contracts),
        "deleted_vectors": deleted_count,
    }


@router.get("/vector-stats", response_model=dict)
async def get_vector_stats(
    admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get statistics about the vector store and detect orphaned data.

    Requires admin role.
    """
    from sqlalchemy import select, func
    from app.models.contract import Contract
    from app.services.vector_store import get_vector_store

    vector_store = get_vector_store()

    # Get ChromaDB stats
    chroma_stats = vector_store.get_collection_stats()

    # Get all contract IDs from both systems
    result = await db.execute(select(Contract.id))
    valid_contract_ids = {str(row[0]) for row in result.fetchall()}

    chromadb_contract_ids = vector_store.get_all_contract_ids()

    # Calculate orphans
    orphaned_in_chromadb = chromadb_contract_ids - valid_contract_ids
    missing_in_chromadb = valid_contract_ids - chromadb_contract_ids

    # Get contract count from PostgreSQL
    total_result = await db.execute(select(func.count(Contract.id)))
    pg_contract_count = total_result.scalar() or 0

    return {
        "chromadb": {
            "collection_name": chroma_stats["name"],
            "total_documents": chroma_stats["count"],
            "unique_contracts": len(chromadb_contract_ids),
        },
        "postgresql": {
            "total_contracts": pg_contract_count,
        },
        "consistency": {
            "orphaned_in_chromadb": len(orphaned_in_chromadb),
            "missing_in_chromadb": len(missing_in_chromadb),
            "orphaned_contract_ids": list(orphaned_in_chromadb)[:10],  # Limit to first 10
            "is_consistent": len(orphaned_in_chromadb) == 0,
        },
    }
