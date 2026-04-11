"""Build contract hierarchy from classified pairs.

Assembles a tree structure from pairwise classification results
and generates SuggestedContractLink records for the database.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract_link import LinkType
from app.models.suggested_link import SuggestedContractLink

from .models import ClassifiedPair, DocumentCard, RelationshipType

logger = logging.getLogger(__name__)

# Map from classifier link_type strings to LinkType enum values
LINK_TYPE_MAP: dict[str, str] = {
    "sow": "sow",
    "exhibit": "exhibit",
    "schedule": "schedule",
    "attachment": "attachment",
    "appendix": "appendix",
    "amendment": "amendment",
    "addendum": "addendum",
    "renewal": "renewal",
    "references": "references",
    "related": "related",
}

# Minimum confidence thresholds
MIN_CONFIDENCE_FAMILY = 0.50  # For SAME_DOCUMENT_FAMILY
MIN_CONFIDENCE_FRAMEWORK = 0.40  # For SAME_MASTER_FRAMEWORK
MIN_CONFIDENCE_INDIRECT = 0.30  # For RELATED_BUT_INDIRECT


class HierarchyBuilder:
    """Build hierarchy and generate SuggestedContractLink records."""

    async def build_and_persist(
        self,
        db: AsyncSession,
        classified_pairs: list[ClassifiedPair],
        cards: dict[uuid.UUID, DocumentCard],
        tenant_id: uuid.UUID,
        batch_id: str | None = None,
    ) -> list[SuggestedContractLink]:
        """Build hierarchy from classified pairs and create suggestions.

        Returns the list of created SuggestedContractLink records.
        """
        # Filter to meaningful relationships above confidence threshold
        actionable = self._filter_actionable(classified_pairs)

        if not actionable:
            logger.info("No actionable relationships found")
            return []

        # Resolve conflicts (same pair classified differently)
        resolved = self._resolve_conflicts(actionable)

        # Generate SuggestedContractLink records
        suggestions = self._generate_suggestions(
            resolved, cards, tenant_id, batch_id
        )

        # Persist
        for suggestion in suggestions:
            db.add(suggestion)

        logger.info(
            f"Created {len(suggestions)} hierarchy suggestions "
            f"(batch={batch_id})"
        )
        return suggestions

    def _filter_actionable(
        self, pairs: list[ClassifiedPair]
    ) -> list[ClassifiedPair]:
        """Filter to pairs that represent meaningful relationships."""
        actionable = []
        for pair in pairs:
            if pair.relationship == RelationshipType.UNRELATED:
                continue
            if pair.relationship == RelationshipType.SAME_DOCUMENT:
                # Duplicates — include with high bar
                if pair.confidence >= 0.70:
                    actionable.append(pair)
            elif pair.relationship == RelationshipType.SAME_DOCUMENT_FAMILY:
                if pair.confidence >= MIN_CONFIDENCE_FAMILY:
                    actionable.append(pair)
            elif pair.relationship == RelationshipType.SAME_MASTER_FRAMEWORK:
                if pair.confidence >= MIN_CONFIDENCE_FRAMEWORK:
                    actionable.append(pair)
            elif pair.relationship == RelationshipType.RELATED_BUT_INDIRECT:
                if pair.confidence >= MIN_CONFIDENCE_INDIRECT:
                    actionable.append(pair)
        return actionable

    def _resolve_conflicts(
        self, pairs: list[ClassifiedPair]
    ) -> list[ClassifiedPair]:
        """Resolve conflicts when the same pair appears multiple times.

        Keeps the classification with highest confidence.
        """
        best: dict[tuple[uuid.UUID, uuid.UUID], ClassifiedPair] = {}
        for pair in pairs:
            key = (min(pair.contract_a_id, pair.contract_b_id),
                   max(pair.contract_a_id, pair.contract_b_id))
            existing = best.get(key)
            if not existing or pair.confidence > existing.confidence:
                best[key] = pair
        return list(best.values())

    def _generate_suggestions(
        self,
        pairs: list[ClassifiedPair],
        cards: dict[uuid.UUID, DocumentCard],
        tenant_id: uuid.UUID,
        batch_id: str | None,
    ) -> list[SuggestedContractLink]:
        """Generate SuggestedContractLink records from classified pairs."""
        suggestions: list[SuggestedContractLink] = []

        for pair in pairs:
            parent_id, child_id, direction = self._determine_direction(
                pair, cards
            )
            link_type = self._map_link_type(pair, cards)

            # Build matching signals for JSONB column
            matching_signals = {
                "detection_method": "hierarchy_v2",
                "relationship_type": pair.relationship.value,
                "classifier_link_type": pair.link_type,
                "classifier_confidence": pair.confidence,
                "reasoning": pair.reasoning,
            }

            suggestion = SuggestedContractLink(
                source_contract_id=child_id,
                target_contract_id=parent_id,
                suggested_link_type=link_type,
                suggested_direction="source_is_child" if direction == "child" else "source_is_parent",
                confidence_score=pair.confidence,
                reasoning=pair.reasoning[:500] if pair.reasoning else None,
                matching_signals=matching_signals,
                status="pending",
                batch_id=batch_id,
                tenant_id=tenant_id,
            )
            suggestions.append(suggestion)

        return suggestions

    def _determine_direction(
        self,
        pair: ClassifiedPair,
        cards: dict[uuid.UUID, DocumentCard],
    ) -> tuple[uuid.UUID, uuid.UUID, str]:
        """Determine parent/child direction for a classified pair.

        Returns (parent_id, child_id, direction_label).
        """
        # If classifier explicitly set parent/child, use that
        if pair.parent_id and pair.child_id:
            return pair.parent_id, pair.child_id, "child"

        # Fallback: use document type hierarchy
        card_a = cards.get(pair.contract_a_id)
        card_b = cards.get(pair.contract_b_id)

        type_rank = self._type_rank(card_a) if card_a else 99
        type_rank_b = self._type_rank(card_b) if card_b else 99

        if type_rank <= type_rank_b:
            return pair.contract_a_id, pair.contract_b_id, "child"
        else:
            return pair.contract_b_id, pair.contract_a_id, "child"

    def _type_rank(self, card: DocumentCard) -> int:
        """Rank document types by hierarchy level (lower = more senior)."""
        ranks = {
            "MSA": 0, "MATA": 0,
            "LSA": 1, "LATA": 1, "ETA": 1,
            "SOW": 2, "SLA": 2,
            "EXHIBIT": 3, "SCHEDULE": 3, "APPENDIX": 3,
            "ATTACHMENT": 4,
            "AMENDMENT": 5,
            "NDA": 6, "VENDOR_AGREEMENT": 6, "EMPLOYMENT_CONTRACT": 6,
            "GUARANTEE": 7, "ESCROW": 7,
        }
        dt = (card.doc_type or "").upper()
        return ranks.get(dt, 10)

    def _map_link_type(
        self,
        pair: ClassifiedPair,
        cards: dict[uuid.UUID, DocumentCard],
    ) -> str:
        """Map the classified link_type to a LinkType enum value."""
        # Use classifier's link_type if it maps cleanly
        if pair.link_type and pair.link_type in LINK_TYPE_MAP:
            return LINK_TYPE_MAP[pair.link_type]

        # Fallback: infer from document types
        child_card = cards.get(pair.child_id) if pair.child_id else None
        if child_card:
            dt = (child_card.doc_type or "").upper()
            type_to_link = {
                "SOW": "sow",
                "EXHIBIT": "exhibit",
                "SCHEDULE": "schedule",
                "ATTACHMENT": "attachment",
                "APPENDIX": "appendix",
                "AMENDMENT": "amendment",
                "SLA": "related",
            }
            if dt in type_to_link:
                return type_to_link[dt]

        # For same-document or framework relationships
        if pair.relationship == RelationshipType.SAME_DOCUMENT:
            return "related"
        if pair.relationship == RelationshipType.SAME_MASTER_FRAMEWORK:
            return "references"

        return "related"
