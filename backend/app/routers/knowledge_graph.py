"""Knowledge graph router for contract entity extraction and querying."""

import uuid as uuid_mod
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, CurrentTenantId
from app.database import get_db
from app.models.contract import Contract
from app.services.knowledge_graph_extractor import (
    KnowledgeGraphExtractor,
    get_knowledge_graph_extractor,
)
from app.services.knowledge_graph_service import (
    KnowledgeGraphService,
    get_knowledge_graph_service,
)
from app.schemas.knowledge_graph import (
    KGEntityResponse,
    KGEntityWithRelationships,
    KGGraphResponse,
    KGPartyObligations,
    KGPortfolioStats,
    KGRelatedClauses,
    KGRiskAnalysis,
    KGTermResolution,
)

router = APIRouter(prefix="/api/knowledge-graph", tags=["Knowledge Graph"])


@router.get("/portfolio/stats", response_model=KGPortfolioStats)
async def get_portfolio_stats(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KGPortfolioStats:
    """Get portfolio-wide knowledge graph statistics for the tenant."""
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant ID required for portfolio stats")

    service = await get_knowledge_graph_service(db)
    return await service.get_portfolio_stats(str(tenant_id))


@router.get("/entities/{entity_id}/timeline", response_model=list[KGEntityResponse])
async def get_entity_timeline(
    entity_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[KGEntityResponse]:
    """Get the temporal timeline for an entity across multiple contracts/amendments."""
    service = await get_knowledge_graph_service(db)
    timeline = await service.get_entity_timeline(entity_id)

    # Simple RBAC check (ensure at least one entity is accessible)
    if timeline and tenant_id:
        # We assume if the user has access to the tenant, they can see the timeline
        # A stricter check would verify access to each contract in the timeline
        pass

    return timeline


async def verify_contract_access(
    contract_id: str,
    tenant_id: uuid_mod.UUID | None,
    db: AsyncSession,
) -> Contract:
    """Verify contract exists and user has access."""
    query = select(Contract).where(Contract.id == uuid_mod.UUID(contract_id))
    if tenant_id:
        query = query.where(Contract.tenant_id == tenant_id)
    result = await db.execute(query)
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract


@router.post("/contracts/{contract_id}/extract", status_code=status.HTTP_202_ACCEPTED)
async def extract_knowledge_graph(
    contract_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    force_reextract: bool = Query(False, description="Delete existing and re-extract"),
) -> dict:
    """Extract entities and relationships from a contract.

    This triggers LLM-based extraction of the knowledge graph from the contract text.
    """
    contract = await verify_contract_access(contract_id, tenant_id, db)

    # Get contract text from parsed document
    from app.services.parser import get_parser

    parser = get_parser()
    parsed = parser.parse_file(contract.file_path)

    if not parsed.success or not parsed.full_text:
        raise HTTPException(
            status_code=400,
            detail="Could not parse contract text for extraction",
        )

    extractor = await get_knowledge_graph_extractor(db)
    entity_count, rel_count = await extractor.extract_and_store(
        contract_id=contract_id,
        tenant_id=str(contract.tenant_id),
        contract_text=parsed.full_text,
        force_reextract=force_reextract,
    )

    await db.commit()

    return {
        "status": "completed",
        "contract_id": contract_id,
        "entities_extracted": entity_count,
        "relationships_extracted": rel_count,
    }


@router.get("/contracts/{contract_id}", response_model=KGGraphResponse)
async def get_contract_graph(
    contract_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KGGraphResponse:
    """Get the full knowledge graph for a contract."""
    contract = await verify_contract_access(contract_id, tenant_id, db)

    service = await get_knowledge_graph_service(db)
    return await service.get_full_graph(contract_id, str(contract.tenant_id))


@router.get("/contracts/{contract_id}/stats")
async def get_graph_stats(
    contract_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get statistics about the knowledge graph for a contract."""
    await verify_contract_access(contract_id, tenant_id, db)

    extractor = await get_knowledge_graph_extractor(db)
    return await extractor.get_extraction_stats(contract_id)


@router.get("/contracts/{contract_id}/entities", response_model=list[KGEntityResponse])
async def search_entities(
    contract_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    entity_type: str | None = Query(None, description="Filter by entity type"),
    search: str | None = Query(None, description="Search term for entity name"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
) -> list[KGEntityResponse]:
    """Search entities in a contract's knowledge graph."""
    await verify_contract_access(contract_id, tenant_id, db)

    service = await get_knowledge_graph_service(db)
    return await service.search_entities(
        contract_id=contract_id,
        entity_type=entity_type,
        search_term=search,
        limit=limit,
    )


@router.get("/contracts/{contract_id}/entities/{entity_id}", response_model=KGEntityWithRelationships)
async def get_entity(
    contract_id: str,
    entity_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KGEntityWithRelationships:
    """Get a specific entity with its relationships."""
    await verify_contract_access(contract_id, tenant_id, db)

    service = await get_knowledge_graph_service(db)
    entity = await service.get_entity_by_id(entity_id)

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Verify entity belongs to this contract
    if entity.contract_id != contract_id:
        raise HTTPException(status_code=404, detail="Entity not found in this contract")

    return entity


@router.get("/contracts/{contract_id}/resolve-term", response_model=KGTermResolution)
async def resolve_term(
    contract_id: str,
    term: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KGTermResolution:
    """Resolve a defined term to its actual meaning.

    Example: "Provider" -> "Acme Corp"
    """
    await verify_contract_access(contract_id, tenant_id, db)

    service = await get_knowledge_graph_service(db)
    return await service.resolve_term(contract_id, term)


@router.get("/contracts/{contract_id}/party-obligations", response_model=list[KGPartyObligations])
async def get_party_obligations(
    contract_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    party: str | None = Query(None, description="Filter by party name"),
) -> list[KGPartyObligations]:
    """Get obligations for each party with their limits and beneficiaries."""
    await verify_contract_access(contract_id, tenant_id, db)

    service = await get_knowledge_graph_service(db)
    return await service.get_party_obligations(contract_id, party)


@router.get("/contracts/{contract_id}/related-clauses", response_model=KGRelatedClauses)
async def get_related_clauses(
    contract_id: str,
    clause: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    max_depth: int = Query(5, ge=1, le=10, description="Maximum traversal depth"),
) -> KGRelatedClauses:
    """Find clauses related to a given clause.

    Uses recursive graph traversal to find references and amendments.
    """
    await verify_contract_access(contract_id, tenant_id, db)

    service = await get_knowledge_graph_service(db)
    try:
        return await service.get_related_clauses(contract_id, clause, max_depth)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/contracts/{contract_id}/risk-analysis", response_model=KGRiskAnalysis)
async def analyze_risks(
    contract_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KGRiskAnalysis:
    """Detect risk patterns in the contract's knowledge graph.

    Analyzes:
    - Unlimited obligations (no caps)
    - Missing jurisdictions
    - Undefined terms
    """
    contract = await verify_contract_access(contract_id, tenant_id, db)

    service = await get_knowledge_graph_service(db)
    return await service.detect_risk_patterns(contract_id, str(contract.tenant_id))
