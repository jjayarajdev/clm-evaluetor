"""Pairwise relationship classifier using LLM.

Classifies candidate pairs into relationship types using batched
OpenAI calls with the document card metadata.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from app.agents.base import openai_client, extract_json_from_response
from app.config import settings

from .models import (
    ClassifiedPair,
    DocumentCard,
    PairCandidate,
    RelationshipType,
)
from .prompts import (
    CLASSIFICATION_SYSTEM_PROMPT,
    CLASSIFICATION_USER_PROMPT,
    BATCH_CLASSIFICATION_USER_PROMPT,
)

logger = logging.getLogger(__name__)

CLASSIFICATION_MODEL = "gpt-4o"  # Full model for relationship judgement
BATCH_SIZE = 8  # Pairs per batch call
MAX_CONCURRENT = 3  # Concurrent LLM calls


class RelationshipClassifier:
    """Classify document pairs into relationship types."""

    async def classify_batch(
        self,
        pairs: list[PairCandidate],
        cards: dict[uuid.UUID, DocumentCard],
    ) -> list[ClassifiedPair]:
        """Classify a list of candidate pairs.

        Groups pairs into batches for efficient LLM usage.
        """
        if not pairs:
            return []

        # Split into batches
        batches: list[list[PairCandidate]] = []
        for i in range(0, len(pairs), BATCH_SIZE):
            batches.append(pairs[i : i + BATCH_SIZE])

        # Process batches with concurrency limit
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        all_results: list[ClassifiedPair] = []

        async def _classify_one_batch(batch: list[PairCandidate]) -> list[ClassifiedPair]:
            async with semaphore:
                try:
                    if len(batch) == 1:
                        return await self._classify_single(batch[0], cards)
                    return await self._classify_multi(batch, cards)
                except Exception as e:
                    logger.warning(f"Batch classification failed: {e}")
                    return []

        results = await asyncio.gather(
            *[_classify_one_batch(b) for b in batches]
        )
        for batch_results in results:
            all_results.extend(batch_results)

        logger.info(
            f"Classified {len(all_results)} pairs "
            f"({sum(1 for r in all_results if r.relationship != RelationshipType.UNRELATED)} related)"
        )
        return all_results

    async def _classify_single(
        self,
        pair: PairCandidate,
        cards: dict[uuid.UUID, DocumentCard],
    ) -> list[ClassifiedPair]:
        """Classify a single pair using the single-pair prompt."""
        card_a = cards.get(pair.contract_a_id)
        card_b = cards.get(pair.contract_b_id)
        if not card_a or not card_b:
            return []

        prompt = CLASSIFICATION_USER_PROMPT.format(
            a_filename=card_a.filename,
            a_doc_type=card_a.doc_type or "UNKNOWN",
            a_doc_identifier=card_a.doc_identifier or "N/A",
            a_title=card_a.title or "N/A",
            a_parties=self._format_parties(card_a),
            a_parent_refs=self._format_parent_refs(card_a),
            a_child_refs=", ".join(card_a.child_references) if card_a.child_references else "None",
            a_subject=card_a.subject_summary or "N/A",
            a_date=card_a.effective_date or "N/A",
            b_filename=card_b.filename,
            b_doc_type=card_b.doc_type or "UNKNOWN",
            b_doc_identifier=card_b.doc_identifier or "N/A",
            b_title=card_b.title or "N/A",
            b_parties=self._format_parties(card_b),
            b_parent_refs=self._format_parent_refs(card_b),
            b_child_refs=", ".join(card_b.child_references) if card_b.child_references else "None",
            b_subject=card_b.subject_summary or "N/A",
            b_date=card_b.effective_date or "N/A",
        )

        response = await openai_client.chat.completions.create(
            model=CLASSIFICATION_MODEL,
            messages=[
                {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=500,
        )

        raw = response.choices[0].message.content or ""
        data = extract_json_from_response(raw)
        if not data:
            return []

        return [self._parse_classification(pair, data, cards)]

    async def _classify_multi(
        self,
        batch: list[PairCandidate],
        cards: dict[uuid.UUID, DocumentCard],
    ) -> list[ClassifiedPair]:
        """Classify multiple pairs in a single LLM call."""
        # Build documents section (deduplicated)
        seen_ids: set[uuid.UUID] = set()
        doc_lines: list[str] = []
        doc_label_map: dict[uuid.UUID, str] = {}
        label_counter = 0

        for pair in batch:
            for cid in [pair.contract_a_id, pair.contract_b_id]:
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    card = cards.get(cid)
                    if not card:
                        continue
                    label = chr(65 + label_counter)  # A, B, C, ...
                    if label_counter >= 26:
                        label = f"D{label_counter - 25}"
                    doc_label_map[cid] = label
                    label_counter += 1
                    doc_lines.append(self._format_doc_block(label, card))

        documents_section = "\n".join(doc_lines)

        # Build pairs section
        pair_lines: list[str] = []
        for idx, pair in enumerate(batch):
            label_a = doc_label_map.get(pair.contract_a_id, "?")
            label_b = doc_label_map.get(pair.contract_b_id, "?")
            pair_lines.append(
                f"Pair {idx}: Document {label_a} vs Document {label_b}"
            )

        pairs_section = "\n".join(pair_lines)

        prompt = BATCH_CLASSIFICATION_USER_PROMPT.format(
            documents_section=documents_section,
            pairs_section=pairs_section,
        )

        response = await openai_client.chat.completions.create(
            model=CLASSIFICATION_MODEL,
            messages=[
                {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=300 * len(batch),
        )

        raw = response.choices[0].message.content or ""
        data = extract_json_from_response(raw)
        if not data:
            return []

        # Handle both list and single-object responses
        if isinstance(data, dict):
            data = [data]

        results: list[ClassifiedPair] = []
        for item in data:
            idx = item.get("pair_index", 0)
            if 0 <= idx < len(batch):
                results.append(
                    self._parse_classification(batch[idx], item, cards)
                )

        return results

    def _parse_classification(
        self,
        pair: PairCandidate,
        data: dict,
        cards: dict[uuid.UUID, DocumentCard],
    ) -> ClassifiedPair:
        """Parse a classification response into a ClassifiedPair."""
        # Parse relationship type
        rel_str = (data.get("relationship") or "UNRELATED").upper()
        try:
            relationship = RelationshipType(rel_str.lower())
        except ValueError:
            # Try mapping common variations
            rel_map = {
                "SAME_DOCUMENT": RelationshipType.SAME_DOCUMENT,
                "SAME_DOCUMENT_FAMILY": RelationshipType.SAME_DOCUMENT_FAMILY,
                "SAME_MASTER_FRAMEWORK": RelationshipType.SAME_MASTER_FRAMEWORK,
                "RELATED_BUT_INDIRECT": RelationshipType.RELATED_BUT_INDIRECT,
                "UNRELATED": RelationshipType.UNRELATED,
            }
            relationship = rel_map.get(rel_str, RelationshipType.UNRELATED)

        # Determine parent/child
        parent_id = None
        child_id = None
        parent_doc = data.get("parent_doc")
        if parent_doc == "A":
            parent_id = pair.contract_a_id
            child_id = pair.contract_b_id
        elif parent_doc == "B":
            parent_id = pair.contract_b_id
            child_id = pair.contract_a_id

        # Map link_type
        link_type = data.get("link_type")
        if link_type:
            link_type = link_type.lower()

        confidence = float(data.get("confidence", 50)) / 100.0
        reasoning = data.get("rationale") or data.get("reasoning") or ""

        return ClassifiedPair(
            contract_a_id=pair.contract_a_id,
            contract_b_id=pair.contract_b_id,
            relationship=relationship,
            parent_id=parent_id,
            child_id=child_id,
            link_type=link_type,
            confidence=confidence,
            reasoning=reasoning,
        )

    # -- Formatting helpers --

    def _format_parties(self, card: DocumentCard) -> str:
        if not card.parties:
            return "N/A"
        return "; ".join(
            f"{p.name} ({p.role})" if p.role else p.name
            for p in card.parties
        )

    def _format_parent_refs(self, card: DocumentCard) -> str:
        if not card.parent_references:
            return "None"
        parts = []
        for pr in card.parent_references:
            desc = pr.referenced_type or "unknown"
            if pr.referenced_title:
                desc += f" ({pr.referenced_title})"
            if pr.relationship:
                desc += f" [{pr.relationship}]"
            parts.append(desc)
        return "; ".join(parts)

    def _format_doc_block(self, label: str, card: DocumentCard) -> str:
        return (
            f"Document {label}:\n"
            f"  File: {card.filename}\n"
            f"  Type: {card.doc_type or 'UNKNOWN'}\n"
            f"  Identifier: {card.doc_identifier or 'N/A'}\n"
            f"  Title: {card.title or 'N/A'}\n"
            f"  Parties: {self._format_parties(card)}\n"
            f"  Parent refs: {self._format_parent_refs(card)}\n"
            f"  Child refs: {', '.join(card.child_references) if card.child_references else 'None'}\n"
            f"  Subject: {card.subject_summary or 'N/A'}\n"
            f"  Date: {card.effective_date or 'N/A'}\n"
        )
