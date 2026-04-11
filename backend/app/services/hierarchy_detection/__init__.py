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

from sqlalchemy.ext.asyncio import AsyncSession

from .candidate_generator import CandidatePairGenerator
from .hierarchy_builder import HierarchyBuilder
from .relationship_classifier import RelationshipClassifier
from .smart_extractor import SmartDocumentExtractor

logger = logging.getLogger(__name__)


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

    # Stage 3: Classify each candidate pair via LLM
    classifier = RelationshipClassifier()
    classified = await classifier.classify_batch(pairs, cards)

    if not classified:
        logger.info("No pairs classified")
        return 0

    # Stage 4: Build hierarchy and persist suggestions
    builder = HierarchyBuilder()
    suggestions = await builder.build_and_persist(
        db, classified, cards, tenant_id, batch_id
    )

    logger.info(
        f"Hierarchy detection complete: {len(suggestions)} suggestions created"
    )
    return len(suggestions)
