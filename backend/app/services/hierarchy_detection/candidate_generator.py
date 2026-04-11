"""Generate candidate pairs for relationship classification.

Reduces N² pairwise comparisons to a manageable set of ~100-200 pairs
using heuristic pre-filtering. No LLM calls — pure logic.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections import defaultdict
from itertools import combinations

from .models import DocumentCard, PairCandidate

logger = logging.getLogger(__name__)

MAX_PAIRS = 250  # Hard cap on generated pairs


class CandidatePairGenerator:
    """Generate high-quality candidate pairs from document cards."""

    def generate(
        self, cards: dict[uuid.UUID, DocumentCard]
    ) -> list[PairCandidate]:
        """Generate candidate pairs from a set of document cards.

        Applies multiple strategies and deduplicates.
        """
        pair_map: dict[tuple[uuid.UUID, uuid.UUID], PairCandidate] = {}
        card_list = list(cards.values())

        # Strategy 1: Cross-reference matching (highest signal)
        self._match_cross_references(card_list, pair_map)

        # Strategy 2: Filename number grouping
        self._match_filename_numbers(card_list, pair_map)

        # Strategy 3: Master-to-child type matching
        self._match_master_to_children(card_list, pair_map)

        # Strategy 4: Party overlap
        self._match_party_overlap(card_list, pair_map)

        # Strategy 5: Same-type duplicate detection
        self._match_same_type_duplicates(card_list, pair_map)

        # Strategy 6: Sibling grouping (same parent type)
        self._match_siblings(card_list, pair_map)

        # Cap and sort by priority
        pairs = sorted(pair_map.values(), key=lambda p: p.priority, reverse=True)
        if len(pairs) > MAX_PAIRS:
            pairs = pairs[:MAX_PAIRS]

        logger.info(
            f"Generated {len(pairs)} candidate pairs from {len(cards)} documents"
        )
        return pairs

    def _key(self, a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
        """Canonical pair key (smaller UUID first)."""
        return (min(a, b), max(a, b))

    def _add_pair(
        self,
        pair_map: dict[tuple[uuid.UUID, uuid.UUID], PairCandidate],
        a: uuid.UUID,
        b: uuid.UUID,
        reason: str,
        priority_bump: int = 1,
    ) -> None:
        """Add or update a candidate pair."""
        if a == b:
            return
        k = self._key(a, b)
        if k not in pair_map:
            pair_map[k] = PairCandidate(
                contract_a_id=k[0],
                contract_b_id=k[1],
            )
        pair_map[k].generation_reasons.append(reason)
        pair_map[k].priority += priority_bump

    def _match_cross_references(
        self,
        cards: list[DocumentCard],
        pair_map: dict[tuple[uuid.UUID, uuid.UUID], PairCandidate],
    ) -> None:
        """Match documents via explicit cross-references.

        If card A's child_references mentions "Exhibit 3" and card B's
        doc_identifier is "Exhibit 3", pair them.
        """
        # Build lookup: normalised identifier -> card
        id_lookup: dict[str, list[DocumentCard]] = defaultdict(list)
        for card in cards:
            if card.doc_identifier:
                norm = self._normalise_identifier(card.doc_identifier)
                id_lookup[norm].append(card)

        for card in cards:
            # Check child references
            for child_ref in card.child_references:
                norm = self._normalise_identifier(child_ref)
                for target in id_lookup.get(norm, []):
                    if target.contract_id != card.contract_id:
                        self._add_pair(
                            pair_map,
                            card.contract_id,
                            target.contract_id,
                            f"child_ref:{child_ref}",
                            priority_bump=5,
                        )

            # Check parent references
            for pref in card.parent_references:
                if pref.referenced_type:
                    norm = self._normalise_identifier(pref.referenced_type)
                    for target in id_lookup.get(norm, []):
                        if target.contract_id != card.contract_id:
                            self._add_pair(
                                pair_map,
                                card.contract_id,
                                target.contract_id,
                                f"parent_ref:{pref.referenced_type}",
                                priority_bump=5,
                            )

                    # Also match against doc_type (e.g. parent_ref="MSA" matches doc_type="MSA")
                    for other in cards:
                        if other.contract_id == card.contract_id:
                            continue
                        if other.doc_type and self._normalise_identifier(other.doc_type) == norm:
                            self._add_pair(
                                pair_map,
                                card.contract_id,
                                other.contract_id,
                                f"parent_ref_type:{pref.referenced_type}",
                                priority_bump=4,
                            )

    def _match_filename_numbers(
        self,
        cards: list[DocumentCard],
        pair_map: dict[tuple[uuid.UUID, uuid.UUID], PairCandidate],
    ) -> None:
        """Group by the primary number in the filename.

        "Exhibit 3 - Service Levels" and "Attachment 3-A SL Matrix"
        share the root number "3".
        """
        number_groups: dict[str, list[DocumentCard]] = defaultdict(list)
        for card in cards:
            root = self._extract_root_number(card.doc_number or card.doc_identifier or "")
            if root:
                number_groups[root].append(card)

        for root, group in number_groups.items():
            if len(group) < 2:
                continue
            for a, b in combinations(group, 2):
                self._add_pair(
                    pair_map,
                    a.contract_id,
                    b.contract_id,
                    f"number_group:{root}",
                    priority_bump=3,
                )

    def _match_master_to_children(
        self,
        cards: list[DocumentCard],
        pair_map: dict[tuple[uuid.UUID, uuid.UUID], PairCandidate],
    ) -> None:
        """Pair every MSA/LSA with every EXHIBIT/ATTACHMENT/SCHEDULE/AMENDMENT."""
        master_types = {"MSA", "LSA", "MATA", "ETA", "LATA"}
        child_types = {
            "EXHIBIT", "ATTACHMENT", "SCHEDULE", "APPENDIX",
            "SOW", "AMENDMENT", "SLA",
        }

        masters = [c for c in cards if (c.doc_type or "").upper() in master_types]
        children = [c for c in cards if (c.doc_type or "").upper() in child_types]

        for m in masters:
            for ch in children:
                self._add_pair(
                    pair_map,
                    m.contract_id,
                    ch.contract_id,
                    f"master_child:{m.doc_type}->{ch.doc_type}",
                    priority_bump=2,
                )

    def _match_party_overlap(
        self,
        cards: list[DocumentCard],
        pair_map: dict[tuple[uuid.UUID, uuid.UUID], PairCandidate],
    ) -> None:
        """Pair documents that share party names."""
        # Build party name sets per card
        card_parties: dict[uuid.UUID, set[str]] = {}
        for card in cards:
            names = set()
            for p in card.parties:
                norm = self._normalise_party(p.name)
                if norm and len(norm) > 3:
                    names.add(norm)
            if names:
                card_parties[card.contract_id] = names

        # Only pair if not already paired and parties overlap
        card_ids = list(card_parties.keys())
        for i in range(len(card_ids)):
            for j in range(i + 1, len(card_ids)):
                a_id, b_id = card_ids[i], card_ids[j]
                if card_parties[a_id] & card_parties[b_id]:
                    k = self._key(a_id, b_id)
                    if k not in pair_map:
                        self._add_pair(
                            pair_map, a_id, b_id,
                            "party_overlap",
                            priority_bump=1,
                        )

    def _match_same_type_duplicates(
        self,
        cards: list[DocumentCard],
        pair_map: dict[tuple[uuid.UUID, uuid.UUID], PairCandidate],
    ) -> None:
        """Detect potential duplicates (same type, similar filenames)."""
        for a, b in combinations(cards, 2):
            if a.content_hash and a.content_hash == b.content_hash:
                self._add_pair(
                    pair_map,
                    a.contract_id,
                    b.contract_id,
                    "content_hash_match",
                    priority_bump=10,
                )

    def _match_siblings(
        self,
        cards: list[DocumentCard],
        pair_map: dict[tuple[uuid.UUID, uuid.UUID], PairCandidate],
    ) -> None:
        """Group exhibits together, attachments together (siblings under same parent)."""
        type_groups: dict[str, list[DocumentCard]] = defaultdict(list)
        for card in cards:
            dt = (card.doc_type or "").upper()
            if dt in ("EXHIBIT", "ATTACHMENT", "SCHEDULE"):
                type_groups[dt].append(card)

        for dtype, group in type_groups.items():
            # Only pair if reasonable count (avoid N² explosion for 30 exhibits)
            if len(group) > 20:
                continue
            for a, b in combinations(group, 2):
                k = self._key(a.contract_id, b.contract_id)
                if k not in pair_map:
                    self._add_pair(
                        pair_map,
                        a.contract_id,
                        b.contract_id,
                        f"sibling:{dtype}",
                        priority_bump=1,
                    )

    # -- Normalisation helpers --

    def _normalise_identifier(self, identifier: str) -> str:
        """Normalise a document identifier for matching.

        "Exhibit 3", "exhibit 3", "EXHIBIT 3" -> "exhibit 3"
        "Attachment 4-A", "attachment 4a" -> "attachment 4-a"
        """
        s = identifier.strip().lower()
        s = re.sub(r"\s+", " ", s)
        return s

    def _extract_root_number(self, identifier: str) -> str | None:
        """Extract the root number from an identifier.

        "3" -> "3", "4-A" -> "4", "2.1" -> "2", "17-B" -> "17"
        """
        if not identifier:
            return None
        m = re.match(r"(\d+)", identifier.strip())
        if m:
            return m.group(1)
        return None

    def _normalise_party(self, name: str) -> str:
        """Normalise a party name for comparison."""
        s = name.strip().lower()
        # Remove common suffixes
        for suffix in [
            " ltd.", " ltd", " llc", " inc.", " inc", " corp.", " corp",
            " n.v.", " nv", " ag", " a.g.", " sarl", " sàrl", " b.v.", " bv",
            " gmbh", " plc",
        ]:
            if s.endswith(suffix):
                s = s[: -len(suffix)]
        return s.strip()
