"""Hierarchy detection pipeline for contract document relationships.

Orchestrates the 4-stage pipeline:
1. Smart extraction — section-targeted metadata extraction via LLM
2. Candidate generation — heuristic pre-filtering of N² pairs
3. Relationship classification — LLM-powered pairwise classification
4. Hierarchy building — tree assembly + SuggestedContractLink creation
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .candidate_generator import CandidatePairGenerator
from .hierarchy_builder import HierarchyBuilder
from .relationship_classifier import RelationshipClassifier
from .smart_extractor import SmartDocumentExtractor

logger = logging.getLogger(__name__)

# Suggestion statuses that block re-detection; rejected/expired must not
# block forever.
LIVE_SUGGESTION_STATUSES = ("pending", "approved")

# How many recent portfolio contracts a detection run compares against.
PORTFOLIO_SCAN_LIMIT = 50


async def should_detect(db: AsyncSession, contract_id: uuid.UUID) -> bool:
    """Whether hierarchy detection is worth running for this contract.

    False when the contract already has a link or a live suggestion —
    re-analysis would just re-derive them with expensive LLM pairwise
    comparisons and flood the suggestion queue.
    """
    from app.models.contract_link import ContractLink
    from app.models.suggested_link import SuggestedContractLink

    has_links = (
        await db.execute(
            select(ContractLink.id)
            .where(
                or_(
                    ContractLink.parent_contract_id == contract_id,
                    ContractLink.child_contract_id == contract_id,
                )
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if has_links:
        return False

    has_suggestions = (
        await db.execute(
            select(SuggestedContractLink.id)
            .where(
                or_(
                    SuggestedContractLink.source_contract_id == contract_id,
                    SuggestedContractLink.target_contract_id == contract_id,
                ),
                SuggestedContractLink.status.in_(LIVE_SUGGESTION_STATUSES),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return not has_suggestions


async def get_hierarchy_scope(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    seed_ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    """Contracts a detection run should compare: seeds ∪ recent portfolio.

    Seeds (the newly processed contracts) come first, then the tenant's most
    recently created COMPLETED contracts up to PORTFOLIO_SCAN_LIMIT, deduped.
    """
    from app.models.contract import Contract, ContractStatus

    recent = await db.execute(
        select(Contract.id)
        .where(
            Contract.tenant_id == tenant_id,
            Contract.status == ContractStatus.COMPLETED,
        )
        .order_by(Contract.created_at.desc())
        .limit(PORTFOLIO_SCAN_LIMIT)
    )
    scope: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for cid in [*seed_ids, *recent.scalars().all()]:
        if cid not in seen:
            seen.add(cid)
            scope.append(cid)
    return scope


async def _load_existing_pairs(
    db: AsyncSession, contract_ids: list[uuid.UUID]
) -> set[tuple[uuid.UUID, uuid.UUID]]:
    """Normalized (min, max) pairs that already have a link or live suggestion."""
    from app.models.contract_link import ContractLink
    from app.models.suggested_link import SuggestedContractLink

    links = await db.execute(
        select(ContractLink.parent_contract_id, ContractLink.child_contract_id).where(
            ContractLink.parent_contract_id.in_(contract_ids),
            ContractLink.child_contract_id.in_(contract_ids),
        )
    )
    suggestions = await db.execute(
        select(
            SuggestedContractLink.source_contract_id,
            SuggestedContractLink.target_contract_id,
        ).where(
            SuggestedContractLink.source_contract_id.in_(contract_ids),
            SuggestedContractLink.target_contract_id.in_(contract_ids),
            SuggestedContractLink.status.in_(LIVE_SUGGESTION_STATUSES),
        )
    )
    return {
        (min(a, b), max(a, b))
        for a, b in [*links.all(), *suggestions.all()]
    }


async def detect_hierarchy(
    db: AsyncSession,
    contract_ids: list[uuid.UUID],
    tenant_id: uuid.UUID,
    batch_id: str | None = None,
) -> int:
    """Run the full hierarchy detection pipeline on a set of contracts.

    Args:
        db: Database session
        contract_ids: List of contract IDs to analyse
        tenant_id: Tenant ID for created suggestions
        batch_id: Optional batch ID for grouping suggestions

    Returns:
        Number of suggested links created.
    """
    if len(contract_ids) < 2:
        logger.info("Need at least 2 contracts for hierarchy detection")
        return 0

    logger.info(
        f"Starting hierarchy detection for {len(contract_ids)} contracts "
        f"(tenant={tenant_id}, batch={batch_id})"
    )

    # Stage 1: Extract rich metadata from each contract
    extractor = SmartDocumentExtractor()
    cards = await extractor.extract_batch(db, contract_ids)

    if len(cards) < 2:
        logger.warning("Fewer than 2 cards extracted, skipping")
        return 0

    # Stage 2: Generate candidate pairs (heuristic pre-filter)
    generator = CandidatePairGenerator()
    pairs = generator.generate(cards)

    if not pairs:
        logger.info("No candidate pairs generated")
        return 0

    # Stage 2.5: Drop pairs that already have a link or live suggestion —
    # BEFORE classification, so we don't pay LLM calls to re-derive them.
    existing_pairs = await _load_existing_pairs(db, list(cards.keys()))
    if existing_pairs:
        before = len(pairs)
        pairs = [
            p
            for p in pairs
            if (min(p.contract_a_id, p.contract_b_id),
                max(p.contract_a_id, p.contract_b_id)) not in existing_pairs
        ]
        if len(pairs) < before:
            logger.info(
                f"Filtered {before - len(pairs)} pairs with existing links/suggestions"
            )
    if not pairs:
        logger.info("All candidate pairs already linked or suggested")
        return 0

    # Stage 3: Classify each candidate pair via LLM
    classifier = RelationshipClassifier()
    classified = await classifier.classify_batch(pairs, cards)

    if not classified:
        logger.info("No pairs classified")
        return 0

    # Stage 4: Build hierarchy and persist suggestions
    builder = HierarchyBuilder()
    suggestions = await builder.build_and_persist(
        db, classified, cards, tenant_id, batch_id, existing_pairs=existing_pairs
    )

    logger.info(
        f"Hierarchy detection complete: {len(suggestions)} suggestions created"
    )
    return len(suggestions)
