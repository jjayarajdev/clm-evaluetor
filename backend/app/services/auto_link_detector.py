"""Auto-link detector service for suggesting contract relationships."""

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.contract import Contract, ContractType, ContractStatus
from app.models.contract_link import LinkType
from app.models.suggested_link import SuggestedContractLink, SuggestionStatus
from app.services.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)


@dataclass
class MatchCandidate:
    """A potential link candidate with scoring details."""

    contract: Contract
    link_type: LinkType
    direction: str  # "source_is_child" or "source_is_parent"
    signals: dict[str, float] = field(default_factory=dict)
    reasoning_parts: list[str] = field(default_factory=list)

    @property
    def confidence_score(self) -> float:
        """Calculate total confidence score from all signals."""
        return min(sum(self.signals.values()), 1.0)

    @property
    def reasoning(self) -> str:
        """Generate human-readable reasoning."""
        return "; ".join(self.reasoning_parts)


# Signal weights — scope-based embeddings carry more weight since they
# compare actual service descriptions, not boilerplate
SIGNAL_WEIGHTS = {
    "counterparty_match": 0.30,
    "counterparty_fuzzy": 0.20,
    "type_hierarchy": 0.15,           # Reduced — too broad without counterparty gate
    "semantic_similarity": 0.35,       # Increased — now scope-based, not boilerplate
    "filename_pattern": 0.15,
    "date_proximity": 0.10,
    "same_batch": 0.15,
    "content_reference": 0.25,        # Child text references a parent agreement
    "parent_references_child": 0.20,  # Parent text mentions this child by identifier
}

# Section types that carry meaningful content for linking.
# Excludes boilerplate: preamble, definitions, signatures, general, termination
LINKING_SECTION_TYPES = ["scope", "sla", "governance", "compliance", "ip", "exhibits"]

# Contract type hierarchies (parent → children)
TYPE_HIERARCHY = {
    ContractType.MSA: [ContractType.SOW, ContractType.AMENDMENT],
    ContractType.NDA: [ContractType.AMENDMENT],
    ContractType.SOW: [ContractType.AMENDMENT],
    ContractType.VENDOR_AGREEMENT: [ContractType.SOW, ContractType.AMENDMENT],
    ContractType.EMPLOYMENT_CONTRACT: [ContractType.AMENDMENT],
}

# Filename patterns that indicate relationship types
AMENDMENT_PATTERNS = [
    r"amend(?:ment)?[-_\s]*\d*",
    r"add(?:endum)?[-_\s]*\d*",
    r"change[-_\s]*order",
    r"modification[-_\s]*\d*",
    r"supplement[-_\s]*\d*",
    r"csow\d*",             # Change SOW (e.g., CSOW0004760)
    r"change[-_\s]*sow",
]

RENEWAL_PATTERNS = [
    r"renewal[-_\s]*\d*",
    r"extension[-_\s]*\d*",
    r"renewed",
]

SOW_PATTERNS = [
    r"sow[-_\s]*\d*",
    r"statement[-_\s]*of[-_\s]*work[-_\s]*\d*",
    r"work[-_\s]*order[-_\s]*\d*",
    r"service[-_\s]*order[-_\s]*\d*",
]

SCHEDULE_PATTERNS = [
    r"schedule[-_\s]*\d+",
    r"schedule[-_\s]*[a-z]\b",
    r"sch[-_\s]*\d+",
    r"annex[-_\s]*\d+",
    r"annex[-_\s]*[a-z]\b",
    r"appendix[-_\s]*\d+",
    r"appendix[-_\s]*[a-z]\b",
    r"exhibit[-_\s]*\d+",
    r"exhibit[-_\s]*[a-z]\b",
]


# Map AI-extracted agreement type strings to ContractType enum
REFERENCE_TYPE_MAP = {
    "MSA": ContractType.MSA,
    "MASTER SERVICES AGREEMENT": ContractType.MSA,
    "MASTER SERVICE AGREEMENT": ContractType.MSA,
    "MASTER AGREEMENT": ContractType.MSA,
    "NDA": ContractType.NDA,
    "NON-DISCLOSURE AGREEMENT": ContractType.NDA,
    "CONFIDENTIALITY AGREEMENT": ContractType.NDA,
    "SOW": ContractType.SOW,
    "STATEMENT OF WORK": ContractType.SOW,
    "VENDOR_AGREEMENT": ContractType.VENDOR_AGREEMENT,
    "VENDOR AGREEMENT": ContractType.VENDOR_AGREEMENT,
    "SERVICES AGREEMENT": ContractType.VENDOR_AGREEMENT,
    "SERVICE AGREEMENT": ContractType.VENDOR_AGREEMENT,
    "EMPLOYMENT_CONTRACT": ContractType.EMPLOYMENT_CONTRACT,
    "EMPLOYMENT CONTRACT": ContractType.EMPLOYMENT_CONTRACT,
    "EMPLOYMENT AGREEMENT": ContractType.EMPLOYMENT_CONTRACT,
    "AMENDMENT": ContractType.AMENDMENT,
}


class AutoLinkDetector:
    """Detects potential parent/related contracts using multi-signal scoring."""

    def __init__(
        self,
        db: AsyncSession,
        tenant_id: uuid.UUID | None = None,
        vector_store: VectorStore | None = None,
    ):
        self.db = db
        self.tenant_id = tenant_id
        self.vector_store = vector_store or get_vector_store()

    async def detect_links(
        self,
        contract: Contract,
        batch_contract_ids: list[str] | None = None,
        min_confidence: float = 0.3,
        max_suggestions: int = 5,
    ) -> list[SuggestedContractLink]:
        """Detect potential links for a newly uploaded contract.

        Args:
            contract: The newly uploaded contract to find links for.
            batch_contract_ids: IDs of other contracts uploaded in the same batch.
            min_confidence: Minimum confidence score to include in suggestions.
            max_suggestions: Maximum number of suggestions to return.

        Returns:
            List of SuggestedContractLink objects ready to be persisted.
        """
        logger.info(f"Detecting potential links for contract {contract.id} ({contract.filename})")

        candidates: dict[str, MatchCandidate] = {}

        # Reset schedule parent search flag
        self._schedule_needs_parent = False
        self._schedule_link_type = LinkType.SCHEDULE

        # Run all detection methods
        await self._find_by_counterparty(contract, candidates)
        await self._find_by_type_hierarchy(contract, candidates)
        await self._find_by_semantic_similarity(contract, candidates)
        self._find_by_filename_patterns(contract, candidates)
        await self._find_by_filename_root(contract, candidates)
        await self._find_by_date_proximity(contract, candidates)
        await self._find_by_content_references(contract, candidates)

        if batch_contract_ids:
            await self._find_by_batch(contract, batch_contract_ids, candidates)

        # If filename indicates a schedule but no MSA parent was found yet, search for one
        if self._schedule_needs_parent:
            await self._find_msa_parent_for_schedule(contract, candidates)

        # Use embedding distance as a gatekeeper: if a candidate was found
        # only via counterparty/date but has NO meaningful content signal,
        # the contracts are from the same vendor but different projects.
        # Strip weak signals that don't prove content relatedness.
        # A content_reference signal below 0.10 means it came from an ambiguous
        # Strategy 2 match (multiple same-party same-type contracts) — don't count it.
        for candidate in candidates.values():
            content_ref_score = candidate.signals.get("content_reference", 0)
            has_content_signal = (
                "semantic_similarity" in candidate.signals
                or (content_ref_score >= 0.10)  # Only count meaningful content references
                or "parent_references_child" in candidate.signals
                or "filename_root" in candidate.signals
                or "type_hierarchy" in candidate.signals
            )
            if not has_content_signal:
                # Only counterparty/date/batch — not enough to prove relatedness
                candidate.signals.pop("counterparty_match", None)
                candidate.signals.pop("counterparty_fuzzy", None)
                candidate.signals.pop("date_proximity", None)
                candidate.signals.pop("content_reference", None)  # Remove ambiguous tiny signal too

        # Filter by minimum confidence and sort
        valid_candidates = [
            c for c in candidates.values()
            if c.confidence_score >= min_confidence
        ]
        valid_candidates.sort(key=lambda x: x.confidence_score, reverse=True)

        # Take top N suggestions
        top_candidates = valid_candidates[:max_suggestions]

        # Filter out candidates where a link already exists in either direction
        from app.models.contract_link import ContractLink
        deduplicated = []
        for candidate in top_candidates:
            existing = await self.db.execute(
                select(ContractLink).where(
                    or_(
                        and_(
                            ContractLink.parent_contract_id == contract.id,
                            ContractLink.child_contract_id == candidate.contract.id,
                        ),
                        and_(
                            ContractLink.parent_contract_id == candidate.contract.id,
                            ContractLink.child_contract_id == contract.id,
                        ),
                    )
                )
            )
            if not existing.scalar_one_or_none():
                deduplicated.append(candidate)

        # Also check existing pending suggestions in either direction
        final_candidates = []
        for candidate in deduplicated:
            existing_suggestion = await self.db.execute(
                select(SuggestedContractLink).where(
                    or_(
                        and_(
                            SuggestedContractLink.source_contract_id == contract.id,
                            SuggestedContractLink.target_contract_id == candidate.contract.id,
                        ),
                        and_(
                            SuggestedContractLink.source_contract_id == candidate.contract.id,
                            SuggestedContractLink.target_contract_id == contract.id,
                        ),
                    )
                )
            )
            if not existing_suggestion.scalar_one_or_none():
                final_candidates.append(candidate)

        # Convert to SuggestedContractLink objects
        suggestions = []
        for candidate in final_candidates:
            suggestion = SuggestedContractLink(
                tenant_id=contract.tenant_id,
                source_contract_id=contract.id,
                target_contract_id=candidate.contract.id,
                suggested_link_type=candidate.link_type.value,  # Use string value
                suggested_direction=candidate.direction,
                confidence_score=candidate.confidence_score,
                reasoning=candidate.reasoning,
                matching_signals=candidate.signals,
                status="pending",  # Use lowercase string for PostgreSQL enum
            )
            suggestions.append(suggestion)

        logger.info(
            f"Found {len(suggestions)} link suggestions for contract {contract.id} "
            f"(filtered from {len(candidates)} candidates)"
        )

        return suggestions

    async def _find_by_counterparty(
        self,
        contract: Contract,
        candidates: dict[str, MatchCandidate],
    ) -> None:
        """Find contracts with matching counterparty.

        When many contracts (10+) share the same counterparty in a tenant
        (e.g., an enterprise outsourcing deal with 96 files), counterparty match
        becomes meaningless — it fires for every pair. In that case, zero out the
        signal so it doesn't produce noise. Content signals (scope embeddings,
        reference extraction) are what actually differentiate documents.
        """
        if not contract.counterparty:
            return

        counterparty = contract.counterparty.strip().lower()

        # Build query for contracts with same/similar counterparty
        query = select(Contract).where(
            Contract.id != contract.id,
            Contract.status == ContractStatus.COMPLETED,
            Contract.counterparty.isnot(None),
        )

        if self.tenant_id:
            query = query.where(Contract.tenant_id == self.tenant_id)

        result = await self.db.execute(query)
        other_contracts = result.scalars().all()

        # Count how many contracts share this counterparty (exact or fuzzy)
        same_cp_count = sum(
            1 for o in other_contracts
            if o.counterparty and (
                counterparty == o.counterparty.strip().lower()
                or counterparty in o.counterparty.strip().lower()
                or o.counterparty.strip().lower() in counterparty
            )
        )

        # Counterparty saturation: when 10+ contracts share the same counterparty,
        # the signal is noise — it matches everything in the deal
        saturated = same_cp_count >= 10
        if saturated:
            logger.info(
                f"Counterparty saturated: {same_cp_count} contracts match '{contract.counterparty}' — zeroing signal"
            )

        for other in other_contracts:
            if not other.counterparty:
                continue

            other_counterparty = other.counterparty.strip().lower()

            # Exact match
            if counterparty == other_counterparty:
                key = str(other.id)
                if key not in candidates:
                    candidates[key] = MatchCandidate(
                        contract=other,
                        link_type=LinkType.RELATED,
                        direction="source_is_child",
                    )
                weight = 0.0 if saturated else SIGNAL_WEIGHTS["counterparty_match"]
                if weight > 0:
                    candidates[key].signals["counterparty_match"] = weight
                    candidates[key].reasoning_parts.append(
                        f"Same counterparty: {other.counterparty}"
                    )

            # Fuzzy match (one contains the other)
            elif (counterparty in other_counterparty or
                  other_counterparty in counterparty):
                key = str(other.id)
                if key not in candidates:
                    candidates[key] = MatchCandidate(
                        contract=other,
                        link_type=LinkType.RELATED,
                        direction="source_is_child",
                    )
                weight = 0.0 if saturated else SIGNAL_WEIGHTS["counterparty_fuzzy"]
                if weight > 0:
                    candidates[key].signals["counterparty_fuzzy"] = weight
                candidates[key].reasoning_parts.append(
                    f"Similar counterparty: {other.counterparty}"
                )

    async def _find_by_type_hierarchy(
        self,
        contract: Contract,
        candidates: dict[str, MatchCandidate],
    ) -> None:
        """Find contracts based on type hierarchy (MSA→SOW, etc.).

        Type hierarchy alone is weak — "this is an amendment, that's an MSA" matches
        every MSA in the tenant. Require counterparty overlap for full weight;
        without it, apply a steep discount so type_hierarchy alone can't produce
        a high-confidence suggestion.
        """
        if not contract.contract_type:
            return

        source_cp = (contract.counterparty or "").strip().lower()

        def _counterparty_overlaps(other: Contract) -> bool:
            other_cp = (other.counterparty or "").strip().lower()
            if source_cp and other_cp:
                return (source_cp in other_cp or other_cp in source_cp
                        or source_cp == other_cp)
            # If either is unknown, can't confirm overlap
            return False

        full_weight = SIGNAL_WEIGHTS["type_hierarchy"]
        no_cp_weight = full_weight * 0.25  # Steep discount without counterparty

        # Check if source could be a child of existing contracts
        for parent_type, child_types in TYPE_HIERARCHY.items():
            if contract.contract_type in child_types:
                query = select(Contract).where(
                    Contract.id != contract.id,
                    Contract.status == ContractStatus.COMPLETED,
                    Contract.contract_type == parent_type,
                )
                if self.tenant_id:
                    query = query.where(Contract.tenant_id == self.tenant_id)

                result = await self.db.execute(query)
                parent_contracts = result.scalars().all()

                for parent in parent_contracts:
                    key = str(parent.id)
                    if key not in candidates:
                        candidates[key] = MatchCandidate(
                            contract=parent,
                            link_type=self._infer_link_type(contract.contract_type),
                            direction="source_is_child",
                        )
                    has_cp = _counterparty_overlaps(parent)
                    weight = full_weight if has_cp else no_cp_weight
                    candidates[key].signals["type_hierarchy"] = weight
                    cp_note = "" if has_cp else " (no counterparty overlap)"
                    candidates[key].reasoning_parts.append(
                        f"Type hierarchy: {contract.contract_type.value} typically falls under {parent_type.value}{cp_note}"
                    )

        # Check if source could be a parent of existing contracts
        if contract.contract_type in TYPE_HIERARCHY:
            child_types = TYPE_HIERARCHY[contract.contract_type]
            query = select(Contract).where(
                Contract.id != contract.id,
                Contract.status == ContractStatus.COMPLETED,
                Contract.contract_type.in_(child_types),
            )
            if self.tenant_id:
                query = query.where(Contract.tenant_id == self.tenant_id)

            result = await self.db.execute(query)
            child_contracts = result.scalars().all()

            for child in child_contracts:
                key = str(child.id)
                if key not in candidates:
                    candidates[key] = MatchCandidate(
                        contract=child,
                        link_type=self._infer_link_type(child.contract_type),
                        direction="source_is_parent",
                    )
                has_cp = _counterparty_overlaps(child)
                weight = full_weight if has_cp else no_cp_weight
                candidates[key].signals["type_hierarchy"] = weight
                cp_note = "" if has_cp else " (no counterparty overlap)"
                candidates[key].reasoning_parts.append(
                    f"Type hierarchy: {child.contract_type.value} typically falls under {contract.contract_type.value}{cp_note}"
                )

    async def _find_by_semantic_similarity(
        self,
        contract: Contract,
        candidates: dict[str, MatchCandidate],
    ) -> None:
        """Find contracts with semantically similar SCOPE content.

        Instead of embedding the first 2000 chars (which is mostly preamble/boilerplate),
        we query this contract's own scope/service-description chunks from ChromaDB,
        then use those as the query text against other contracts' scope chunks.

        This means two unrelated NDAs won't match (their boilerplate is excluded),
        but SOW 124 (GCPS-GCM-ShareTax) will match its CSOW because their scope
        descriptions are about the same project.
        """
        if not contract.extracted_text:
            return

        try:
            tenant_filter = str(self.tenant_id) if self.tenant_id else None
            contract_id_str = str(contract.id)

            # Step 1: Get this contract's scope/service chunks from ChromaDB.
            # These are already classified by section_classifier during indexing.
            scope_chunks = self.vector_store.query_similar(
                query_text="scope of work services deliverables description",
                top_k=5,
                contract_id=contract_id_str,
                section_types=LINKING_SECTION_TYPES,
                user_id=None,
                user_role="admin",
                tenant_id=tenant_filter,
            )

            # Build composite query from scope chunks (the actual service description)
            if scope_chunks:
                # Take the best scope chunks, cap at ~3000 chars total
                composite_parts = []
                total_chars = 0
                for chunk in scope_chunks:
                    text = chunk.text.strip()
                    if text and total_chars < 3000:
                        composite_parts.append(text[:1500])
                        total_chars += min(len(text), 1500)
                query_text = "\n".join(composite_parts)
            else:
                # Fallback: no classified scope chunks yet — use extracted text
                # but skip the first 500 chars (usually preamble/parties)
                query_text = contract.extracted_text[500:2500]

            if not query_text or len(query_text.strip()) < 50:
                # Not enough text to compare meaningfully
                return

            # Step 2: Query OTHER contracts' scope chunks (not boilerplate)
            results = self.vector_store.query_similar(
                query_text=query_text,
                top_k=30,
                section_types=LINKING_SECTION_TYPES,
                user_id=None,
                user_role="admin",
                tenant_id=tenant_filter,
            )

            # Group by contract and find highest similarity per contract
            contract_similarities: dict[str, float] = {}
            for result in results:
                cid = result.metadata.get("contract_id")
                if cid and cid != contract_id_str:
                    similarity = max(0, 1 - result.distance)
                    if similarity > 0.65:  # Slightly lower threshold — scope is more specific
                        if cid not in contract_similarities:
                            contract_similarities[cid] = similarity
                        else:
                            contract_similarities[cid] = max(
                                contract_similarities[cid], similarity
                            )

            # Add to candidates — discount when counterparties differ (boilerplate similarity)
            source_counterparty = (contract.counterparty or "").strip().lower()
            for cid, similarity in contract_similarities.items():
                key = cid
                if key not in candidates:
                    other = await self.db.get(Contract, uuid.UUID(cid))
                    if other and other.status == ContractStatus.COMPLETED:
                        candidates[key] = MatchCandidate(
                            contract=other,
                            link_type=LinkType.RELATED,
                            direction="source_is_child",
                        )
                if key in candidates:
                    other_counterparty = (candidates[key].contract.counterparty or "").strip().lower()
                    counterparty_overlap = False
                    if source_counterparty and other_counterparty:
                        counterparty_overlap = (
                            source_counterparty in other_counterparty
                            or other_counterparty in source_counterparty
                            or source_counterparty == other_counterparty
                        )
                    elif not source_counterparty and not other_counterparty:
                        counterparty_overlap = True

                    if counterparty_overlap:
                        weight = SIGNAL_WEIGHTS["semantic_similarity"] * similarity
                        candidates[key].signals["semantic_similarity"] = weight
                        candidates[key].reasoning_parts.append(
                            f"Scope similarity: {similarity:.0%} (same counterparty)"
                        )
                    else:
                        discounted_weight = SIGNAL_WEIGHTS["semantic_similarity"] * similarity * 0.3
                        candidates[key].signals["semantic_similarity"] = discounted_weight
                        candidates[key].reasoning_parts.append(
                            f"Scope similarity: {similarity:.0%} (discounted — different counterparties)"
                        )

        except Exception as e:
            logger.warning(f"Semantic similarity search failed: {e}")

    def _find_by_filename_patterns(
        self,
        contract: Contract,
        candidates: dict[str, MatchCandidate],
    ) -> None:
        """Detect link type from filename patterns."""
        filename = contract.filename.lower()

        # Check for amendment patterns
        for pattern in AMENDMENT_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                # This contract looks like an amendment
                for key, candidate in candidates.items():
                    candidate.signals["filename_pattern"] = SIGNAL_WEIGHTS["filename_pattern"]
                    candidate.link_type = LinkType.AMENDMENT
                    candidate.direction = "source_is_child"
                    candidate.reasoning_parts.append(
                        f"Filename suggests amendment: {contract.filename}"
                    )
                return

        # Check for renewal patterns
        for pattern in RENEWAL_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                for key, candidate in candidates.items():
                    candidate.signals["filename_pattern"] = SIGNAL_WEIGHTS["filename_pattern"]
                    candidate.link_type = LinkType.RENEWAL
                    candidate.direction = "source_is_child"
                    candidate.reasoning_parts.append(
                        f"Filename suggests renewal: {contract.filename}"
                    )
                return

        # Check for SOW patterns
        for pattern in SOW_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                for key, candidate in candidates.items():
                    if candidate.contract.contract_type == ContractType.MSA:
                        candidate.signals["filename_pattern"] = SIGNAL_WEIGHTS["filename_pattern"]
                        candidate.link_type = LinkType.SOW
                        candidate.direction = "source_is_child"
                        candidate.reasoning_parts.append(
                            f"Filename suggests SOW: {contract.filename}"
                        )
                return

        # Check for schedule/exhibit/appendix patterns
        for pattern in SCHEDULE_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                # Determine link type from filename
                if re.search(r"exhibit", filename, re.IGNORECASE):
                    link_type = LinkType.EXHIBIT
                elif re.search(r"appendix|annex", filename, re.IGNORECASE):
                    link_type = LinkType.APPENDIX
                else:
                    link_type = LinkType.SCHEDULE

                # Update existing candidates (prefer MSA parents)
                for key, candidate in candidates.items():
                    if candidate.contract.contract_type == ContractType.MSA:
                        candidate.signals["filename_pattern"] = SIGNAL_WEIGHTS["filename_pattern"]
                        candidate.link_type = link_type
                        candidate.direction = "source_is_child"
                        candidate.reasoning_parts.append(
                            f"Filename suggests {link_type.value}: {contract.filename}"
                        )

                # Also search for MSA parents in same tenant if none found yet
                if not any(
                    c.contract.contract_type == ContractType.MSA
                    for c in candidates.values()
                ):
                    self._schedule_needs_parent = True
                    self._schedule_link_type = link_type
                return

    async def _find_by_filename_root(
        self,
        contract: Contract,
        candidates: dict[str, MatchCandidate],
    ) -> None:
        """Find contracts with shared filename root.

        If two files share a long common prefix (e.g. 'Algoleap_SOW 124_GCPS-GCM-ShareTax'),
        they almost certainly belong together (SOW + Change SOW, MSA + Amendment, etc.).
        """
        if not contract.filename:
            return

        # Extract meaningful root: strip extension, then strip trailing identifiers
        # e.g. "Algoleap_SOW 124_GCPS-GCM-ShareTax_FY 2026 - CSOW0004760.pdf"
        #  → root candidates by splitting on common separators before IDs
        import os
        basename = os.path.splitext(contract.filename)[0]

        # Split on " - " which typically separates the common part from the identifier
        parts = basename.split(" - ")
        if len(parts) >= 2:
            # Use everything before the last separator as the root
            root = " - ".join(parts[:-1]).strip()
        else:
            # Fall back: use first 60% of the filename (skip trailing IDs)
            root = basename[:max(20, int(len(basename) * 0.6))].strip()

        if len(root) < 15:
            return  # Too short to be meaningful

        # Search for contracts whose filename starts with the same root
        query = select(Contract).where(
            Contract.id != contract.id,
            Contract.status == ContractStatus.COMPLETED,
            Contract.filename.ilike(f"{root}%"),
        )
        if self.tenant_id:
            query = query.where(Contract.tenant_id == self.tenant_id)

        result = await self.db.execute(query)
        matches = result.scalars().all()

        for match in matches:
            key = str(match.id)

            # Determine link type and direction from filename identifiers
            # e.g., CSOW0004760 is a change order (child) of SOW0001936
            import os as _os
            source_id_part = basename.split(" - ")[-1] if " - " in basename else ""
            target_basename = _os.path.splitext(match.filename)[0]
            target_id_part = target_basename.split(" - ")[-1] if " - " in target_basename else ""

            is_source_csow = bool(re.search(r"(?i)csow", source_id_part))
            is_target_csow = bool(re.search(r"(?i)csow", target_id_part))
            is_source_sow = bool(re.search(r"(?i)^sow\d", source_id_part))
            is_target_sow = bool(re.search(r"(?i)^sow\d", target_id_part))

            if is_source_csow and is_target_sow:
                # This contract (CSOW) is a change order of the target (SOW)
                link_type = LinkType.AMENDMENT
                direction = "source_is_child"
            elif is_source_sow and is_target_csow:
                # This contract (SOW) is the parent of the target (CSOW)
                link_type = LinkType.AMENDMENT
                direction = "source_is_parent"
            else:
                link_type = LinkType.RELATED
                direction = "source_is_child"

            if key not in candidates:
                candidates[key] = MatchCandidate(
                    contract=match,
                    link_type=link_type,
                    direction=direction,
                )
            else:
                # Upgrade link type if we have more specific info
                if link_type != LinkType.RELATED:
                    candidates[key].link_type = link_type
                    candidates[key].direction = direction

            candidates[key].signals["filename_root"] = 0.35
            candidates[key].reasoning_parts.append(
                f"Shared filename root: '{root}'"
            )

    async def _find_by_date_proximity(
        self,
        contract: Contract,
        candidates: dict[str, MatchCandidate],
    ) -> None:
        """Add weight for contracts with dates in proximity."""
        if not contract.effective_date and not contract.created_at:
            return

        reference_date = contract.effective_date or contract.created_at.date()

        for key, candidate in candidates.items():
            other = candidate.contract
            if not other.effective_date and not other.expiration_date:
                continue

            # Check if source effective date is close to target expiration
            # (indicating renewal/succession)
            if other.expiration_date and contract.effective_date:
                days_diff = abs((contract.effective_date - other.expiration_date).days)
                if days_diff <= 30:
                    candidate.signals["date_proximity"] = SIGNAL_WEIGHTS["date_proximity"]
                    candidate.reasoning_parts.append(
                        f"Date proximity: source starts within 30 days of target expiration"
                    )
                    if candidate.link_type == LinkType.RELATED:
                        candidate.link_type = LinkType.RENEWAL
                    continue

            # Check for contracts in same time period
            other_date = other.effective_date or (
                other.created_at.date() if other.created_at else None
            )
            if other_date:
                days_diff = abs((reference_date - other_date).days)
                if days_diff <= 60:
                    # Partial weight for general date proximity
                    weight = SIGNAL_WEIGHTS["date_proximity"] * 0.5
                    candidate.signals["date_proximity"] = weight
                    candidate.reasoning_parts.append(
                        f"Date proximity: contracts created within {days_diff} days"
                    )

    async def _find_by_batch(
        self,
        contract: Contract,
        batch_contract_ids: list[str],
        candidates: dict[str, MatchCandidate],
    ) -> None:
        """Add weight for contracts uploaded in the same batch."""
        # Check if current contract looks like a schedule/exhibit
        filename_lower = contract.filename.lower() if contract.filename else ""
        is_schedule = any(
            re.search(p, filename_lower, re.IGNORECASE) for p in SCHEDULE_PATTERNS
        )

        for cid in batch_contract_ids:
            if cid == str(contract.id):
                continue

            key = cid
            if key in candidates:
                candidates[key].signals["same_batch"] = SIGNAL_WEIGHTS["same_batch"]
                candidates[key].reasoning_parts.append("Uploaded in same batch")
            else:
                # Fetch the contract and add as candidate
                other = await self.db.get(Contract, uuid.UUID(cid))
                if other and other.status == ContractStatus.COMPLETED:
                    # If current doc is a schedule and batch mate is an MSA, boost heavily
                    # But skip batch mates that look like schedules themselves (misclassified)
                    other_is_schedule = any(
                        re.search(p, (other.filename or "").lower(), re.IGNORECASE)
                        for p in SCHEDULE_PATTERNS
                    )
                    other_is_msa = (
                        other.contract_type == ContractType.MSA
                        or bool(re.search(r'\bMSA\b', other.filename or "", re.IGNORECASE))
                    ) and not other_is_schedule

                    if is_schedule and other_is_msa:
                        link_type = getattr(self, '_schedule_link_type', LinkType.SCHEDULE)
                        candidates[key] = MatchCandidate(
                            contract=other,
                            link_type=link_type,
                            direction="source_is_child",
                            signals={
                                "same_batch": SIGNAL_WEIGHTS["same_batch"],
                                "type_hierarchy": SIGNAL_WEIGHTS["type_hierarchy"],
                            },
                            reasoning_parts=[
                                "Uploaded in same batch",
                                f"Schedule uploaded with MSA: {other.filename}",
                            ],
                        )
                    else:
                        candidates[key] = MatchCandidate(
                            contract=other,
                            link_type=LinkType.RELATED,
                            direction="source_is_child",
                            signals={"same_batch": SIGNAL_WEIGHTS["same_batch"]},
                            reasoning_parts=["Uploaded in same batch"],
                        )

    async def _find_msa_parent_for_schedule(
        self,
        contract: Contract,
        candidates: dict[str, MatchCandidate],
    ) -> None:
        """Find MSA parent contracts for a schedule/exhibit/appendix.

        Prefers contracts whose filename contains 'MSA' and skips
        contracts that look like schedules themselves (misclassified).
        """
        # Search for both contract_type=MSA and filename containing "MSA"
        query = select(Contract).where(
            Contract.id != contract.id,
            Contract.status == ContractStatus.COMPLETED,
            or_(
                Contract.contract_type == ContractType.MSA,
                Contract.filename.ilike("%MSA%"),
            ),
        )
        if self.tenant_id:
            query = query.where(Contract.tenant_id == self.tenant_id)

        result = await self.db.execute(query)
        msa_contracts = result.scalars().all()

        link_type = getattr(self, '_schedule_link_type', LinkType.SCHEDULE)

        # Sort: prefer filename-confirmed MSA, skip misclassified schedules
        def _msa_sort_key(c: Contract) -> tuple:
            filename_has_msa = bool(re.search(r'\bMSA\b', c.filename, re.IGNORECASE))
            filename_is_schedule = any(
                re.search(p, c.filename.lower(), re.IGNORECASE)
                for p in SCHEDULE_PATTERNS
            )
            return (
                0 if filename_is_schedule else 1,  # Non-schedules first
                1 if filename_has_msa else 0,       # MSA in filename preferred
            )

        msa_contracts_sorted = sorted(msa_contracts, key=_msa_sort_key, reverse=True)

        for msa in msa_contracts_sorted:
            # Skip contracts whose filename looks like a schedule (misclassified as MSA)
            if any(
                re.search(p, msa.filename.lower(), re.IGNORECASE)
                for p in SCHEDULE_PATTERNS
            ):
                continue

            key = str(msa.id)
            filename_has_msa = bool(re.search(r'\bMSA\b', msa.filename, re.IGNORECASE))

            if key not in candidates:
                candidates[key] = MatchCandidate(
                    contract=msa,
                    link_type=link_type,
                    direction="source_is_child",
                )

            # Higher confidence for filename-confirmed MSA
            if filename_has_msa:
                candidates[key].signals["filename_pattern"] = SIGNAL_WEIGHTS["filename_pattern"]
                candidates[key].signals["type_hierarchy"] = SIGNAL_WEIGHTS["type_hierarchy"]
            else:
                candidates[key].signals["type_hierarchy"] = SIGNAL_WEIGHTS["type_hierarchy"] * 0.7

            candidates[key].link_type = link_type
            candidates[key].direction = "source_is_child"
            candidates[key].reasoning_parts.append(
                f"Schedule/exhibit filename linked to MSA: {msa.filename}"
            )

    async def _find_by_content_references(
        self,
        contract: Contract,
        candidates: dict[str, MatchCandidate],
    ) -> None:
        """Find links using AI-extracted contract reference data.

        Uses structured data stored in schema_data['_contract_references']
        (populated during indexing by the contract_reference_extraction agent).
        The LLM reads the document and extracts reference_text, reference_identifier,
        party_names, and referenced_type — then we match against other contracts.

        Three matching strategies:
        1. reference_text / reference_identifier against filenames (strongest signal)
        2. Type + party matching against contract metadata
        3. Reverse: parent's AI data lists this contract as a child
        """
        ai_refs = (contract.schema_data or {}).get("_contract_references", {})
        parent_refs = ai_refs.get("parent_references", [])

        if not parent_refs and not ai_refs.get("child_references"):
            return

        # Extract AI-detected reference details
        referenced_types: set[ContractType] = set()
        mentioned_parties: list[str] = []
        reference_texts: list[str] = []
        reference_ids: list[str] = []

        for ref in parent_refs:
            ref_type = (ref.get("referenced_type") or "").upper()
            if ref_type in REFERENCE_TYPE_MAP:
                referenced_types.add(REFERENCE_TYPE_MAP[ref_type])
            for party in ref.get("party_names", []):
                if party and len(party.strip()) >= 3:
                    mentioned_parties.append(party.strip())
            # Collect reference text and identifiers for filename matching
            ref_text = ref.get("reference_text", "")
            ref_id = ref.get("reference_identifier", "")
            if ref_text and len(ref_text) >= 5:
                reference_texts.append(ref_text)
            if ref_id and len(ref_id) >= 3:
                reference_ids.append(ref_id)

        logger.info(
            f"AI refs for {contract.id}: "
            f"types={[t.value for t in referenced_types]}, "
            f"parties={mentioned_parties[:3]}, "
            f"ref_ids={reference_ids[:3]}"
        )

        # --- Strategy 1: Match reference_text/identifier against filenames ---
        # This is the strongest signal: the AI read "pursuant to SOW0001936" and
        # we find a file named "...SOW0001936.pdf" in the same tenant.
        all_tenant_contracts: list[Contract] = []
        base_conditions = [
            Contract.id != contract.id,
            Contract.status == ContractStatus.COMPLETED,
        ]
        if self.tenant_id:
            base_conditions.append(Contract.tenant_id == self.tenant_id)

        result = await self.db.execute(select(Contract).where(*base_conditions))
        all_tenant_contracts = list(result.scalars().all())

        for other in all_tenant_contracts:
            if not other.filename:
                continue
            other_filename_lower = other.filename.lower()
            key = str(other.id)
            matched = False

            # Check if any reference_identifier appears in the other contract's filename
            # Use word-boundary matching to prevent "Exhibit 3" matching "Exhibit 30"
            for ref_id in reference_ids:
                ref_id_lower = ref_id.lower().strip()
                if self._identifier_matches_filename(ref_id_lower, other_filename_lower):
                    if key not in candidates:
                        candidates[key] = MatchCandidate(
                            contract=other,
                            link_type=self._infer_child_link_type(contract),
                            direction="source_is_child",
                        )
                    candidates[key].signals["content_reference"] = SIGNAL_WEIGHTS["content_reference"]
                    candidates[key].reasoning_parts.append(
                        f"AI: document references '{ref_id}' found in filename '{other.filename}'"
                    )
                    matched = True
                    break

            # Check if reference_text contains enough of the filename to match
            if not matched:
                for ref_text in reference_texts:
                    ref_text_lower = ref_text.lower()
                    # Check both directions: filename in reference_text or meaningful part of reference in filename
                    other_base = other.filename.rsplit(".", 1)[0].lower()
                    if (other_base in ref_text_lower or
                            (len(other_base) > 20 and ref_text_lower[:30] in other_base)):
                        if key not in candidates:
                            candidates[key] = MatchCandidate(
                                contract=other,
                                link_type=self._infer_child_link_type(contract),
                                direction="source_is_child",
                            )
                        candidates[key].signals["content_reference"] = SIGNAL_WEIGHTS["content_reference"]
                        candidates[key].reasoning_parts.append(
                            f"AI: reference text matches filename '{other.filename}'"
                        )
                        matched = True
                        break

        # --- Strategy 2: Type + party matching ---
        # Type match alone is too broad ("references MSA" matches every MSA).
        # Require party match to anchor the reference to a specific contract.
        # EXCEPTION: When there are very few contracts of the referenced type
        # (e.g., 1-2 MSAs in the tenant), the type alone is a strong signal —
        # party match not required. This handles enterprise deals where the
        # MSA counterparty ("ServicePro") differs from the parties cited in
        # exhibits ("GlobalPharma").

        # Pre-compute how many contracts of each referenced type exist
        type_counts: dict[ContractType, int] = {}
        for ref_type in referenced_types:
            type_counts[ref_type] = sum(
                1 for c in all_tenant_contracts
                if c.contract_type == ref_type
            )

        # First pass: collect all party+type matches to detect ambiguity
        strategy2_matches: list[tuple[str, float, list[str]]] = []  # (key, score, reasons)
        for other in all_tenant_contracts:
            key = str(other.id)
            ref_score = 0.0
            reasons = []
            has_party_match = False

            # Party match (strong anchor)
            if mentioned_parties and other.counterparty:
                other_cp = other.counterparty.strip().lower()
                for party in mentioned_parties:
                    party_lower = party.strip().lower()
                    if (len(party_lower) >= 3 and len(other_cp) >= 3 and
                            (party_lower in other_cp or other_cp in party_lower)):
                        ref_score += 0.15
                        reasons.append(
                            f"AI: referenced party matches '{other.counterparty}'"
                        )
                        has_party_match = True
                        break

            # Type match
            if other.contract_type and other.contract_type in referenced_types:
                type_count = type_counts.get(other.contract_type, 0)

                if has_party_match:
                    # Party + type = strong signal
                    ref_score += 0.10
                    reasons.append(
                        f"AI: references {other.contract_type.value} agreement"
                    )
                elif type_count <= 3:
                    # Few contracts of this type in tenant — type alone is meaningful
                    # (e.g., "references MSA" and there's only 1 MSA)
                    ref_score += 0.20
                    reasons.append(
                        f"AI: references {other.contract_type.value} (only {type_count} in tenant)"
                    )

            # Boost if AI extraction was high confidence
            if ref_score > 0 and parent_refs:
                best_conf = max(
                    (r.get("confidence", 0) for r in parent_refs), default=0
                )
                if best_conf >= 0.8:
                    ref_score += 0.05
                    reasons.append(f"AI confidence: {best_conf:.0%}")

            if ref_score > 0:
                strategy2_matches.append((key, ref_score, reasons))

        # If multiple contracts match the same party+type, the signal is ambiguous
        # (e.g., "references a SOW from Algoleap" but there are 3 Algoleap SOWs).
        # Apply steep discount so Strategy 2 alone can't produce a high-confidence link.
        is_ambiguous = len(strategy2_matches) > 1
        for key, ref_score, reasons in strategy2_matches:
            if is_ambiguous:
                ref_score *= 0.3  # Steep discount: can't tell which contract is the real parent
                reasons.append(f"(ambiguous: {len(strategy2_matches)} candidates match party+type)")

            if key not in candidates:
                candidates[key] = MatchCandidate(
                    contract=[c for c in all_tenant_contracts if str(c.id) == key][0],
                    link_type=self._infer_child_link_type(contract),
                    direction="source_is_child",
                )
            # Don't overwrite a stronger content_reference signal from Strategy 1
            existing = candidates[key].signals.get("content_reference", 0)
            if ref_score > existing:
                candidates[key].signals["content_reference"] = min(
                    ref_score, SIGNAL_WEIGHTS["content_reference"]
                )
            candidates[key].reasoning_parts.extend(reasons)

        # --- Strategy 3: Reverse matching — parent's AI data lists this contract ---
        child_ref_id = parent_refs[0].get("reference_identifier") if parent_refs else None

        for other in all_tenant_contracts:
            key = str(other.id)
            parent_ai = (other.schema_data or {}).get("_contract_references", {})
            parent_child_list = parent_ai.get("child_references", [])

            if not parent_child_list or not child_ref_id:
                continue

            child_ref_lower = child_ref_id.lower()
            child_ref_normalised = re.sub(r"0+(\d)", r"\1", child_ref_lower)

            for listed_child in parent_child_list:
                listed_lower = listed_child.lower()
                listed_normalised = re.sub(r"0+(\d)", r"\1", listed_lower)
                if (child_ref_lower in listed_lower
                        or listed_lower in child_ref_lower
                        or child_ref_normalised == listed_normalised):
                    if key not in candidates:
                        candidates[key] = MatchCandidate(
                            contract=other,
                            link_type=self._infer_child_link_type(contract),
                            direction="source_is_child",
                        )
                    candidates[key].signals["parent_references_child"] = SIGNAL_WEIGHTS["parent_references_child"]
                    candidates[key].reasoning_parts.append(
                        f"AI: parent lists child '{listed_child}'"
                    )
                    break

    @staticmethod
    def _identifier_matches_filename(ref_id: str, filename: str) -> bool:
        """Check if a reference identifier matches a filename using word boundaries.

        Prevents "Exhibit 3" from matching "Exhibit 30" or "Exhibit 34".
        The identifier must appear as a complete unit — the character after it
        (if any) must NOT be a digit, so "Exhibit 3" matches "Exhibit 3 (Service Levels)"
        but not "Exhibit 30 (T & T)".

        Also handles identifiers like "SOW0001936" or "CSOW0004760" which are
        unique enough for plain substring matching.
        """
        if not ref_id or not filename:
            return False

        # For long identifiers (8+ chars like "SOW0001936"), plain substring is fine
        # — they're unique enough that collisions are extremely unlikely
        if len(ref_id) >= 8 and ref_id in filename:
            return True

        # For short identifiers ("Exhibit 3", "Attachment 3-A", "Schedule 02"),
        # require the match to be followed by a non-digit character (or end of string)
        # to prevent "Exhibit 3" matching "Exhibit 30"
        pattern = re.escape(ref_id) + r"(?!\d)"
        return bool(re.search(pattern, filename, re.IGNORECASE))

    def _infer_child_link_type(self, contract: Contract) -> LinkType:
        """Infer link type for a child contract based on its filename and type."""
        if contract.contract_type == ContractType.SOW:
            return LinkType.SOW
        if contract.contract_type == ContractType.AMENDMENT:
            return LinkType.AMENDMENT

        fname = (contract.filename or "").lower()
        if any(re.search(p, fname, re.IGNORECASE) for p in SCHEDULE_PATTERNS):
            if re.search(r"exhibit", fname, re.IGNORECASE):
                return LinkType.EXHIBIT
            if re.search(r"appendix|annex", fname, re.IGNORECASE):
                return LinkType.APPENDIX
            return LinkType.SCHEDULE
        if any(re.search(p, fname, re.IGNORECASE) for p in AMENDMENT_PATTERNS):
            return LinkType.AMENDMENT
        if any(re.search(p, fname, re.IGNORECASE) for p in SOW_PATTERNS):
            return LinkType.SOW
        return LinkType.RELATED

    def _infer_link_type(self, contract_type: ContractType | None) -> LinkType:
        """Infer the appropriate link type based on contract type."""
        if contract_type == ContractType.SOW:
            return LinkType.SOW
        elif contract_type == ContractType.AMENDMENT:
            return LinkType.AMENDMENT
        else:
            return LinkType.RELATED


# Module-level instance getter
_detector_instance: AutoLinkDetector | None = None


def get_auto_link_detector(
    db: AsyncSession,
    tenant_id: uuid.UUID | None = None,
) -> AutoLinkDetector:
    """Get an AutoLinkDetector instance."""
    return AutoLinkDetector(db, tenant_id)


async def auto_approve_batch_links(
    db: AsyncSession,
    batch_contract_ids: list[str],
    confidence_threshold: float = 0.35,
) -> list:
    """Auto-approve suggested links above threshold for same-batch contracts.

    When all contracts in a batch have been processed, promote high-confidence
    suggested links to actual contract_links.

    Args:
        db: Database session.
        batch_contract_ids: Contract IDs from the completed batch.
        confidence_threshold: Minimum confidence to auto-approve.

    Returns:
        List of created ContractLink objects.
    """
    from app.models.contract_link import ContractLink

    batch_uuids = [uuid.UUID(cid) for cid in batch_contract_ids]

    # Find pending suggestions where both source and target are in the batch
    # OR where the target is an MSA outside the batch (schedule→MSA links)
    query = select(SuggestedContractLink).where(
        SuggestedContractLink.source_contract_id.in_(batch_uuids),
        SuggestedContractLink.status == "pending",
        SuggestedContractLink.confidence_score >= confidence_threshold,
    )
    result = await db.execute(query)
    suggestions = result.scalars().all()

    if not suggestions:
        return []

    created_links = []
    now = datetime.now(timezone.utc) if hasattr(datetime, 'now') else datetime.utcnow()

    for suggestion in suggestions:
        # Determine parent/child based on direction
        if suggestion.suggested_direction == "source_is_child":
            parent_id = suggestion.target_contract_id
            child_id = suggestion.source_contract_id
        else:
            parent_id = suggestion.source_contract_id
            child_id = suggestion.target_contract_id

        # Check for existing link in either direction (avoid duplicates)
        existing = await db.execute(
            select(ContractLink).where(
                or_(
                    and_(
                        ContractLink.parent_contract_id == parent_id,
                        ContractLink.child_contract_id == child_id,
                    ),
                    and_(
                        ContractLink.parent_contract_id == child_id,
                        ContractLink.child_contract_id == parent_id,
                    ),
                )
            )
        )
        if existing.scalar_one_or_none():
            suggestion.status = "approved"
            continue

        # Create the actual link
        link = ContractLink(
            id=uuid.uuid4(),
            parent_contract_id=parent_id,
            child_contract_id=child_id,
            link_type=suggestion.suggested_link_type,
            link_description=f"Auto-approved: {suggestion.reasoning[:200]}" if suggestion.reasoning else "Auto-approved from batch upload",
            is_active=True,
        )
        db.add(link)
        await db.flush()

        # Update suggestion status
        suggestion.status = "approved"
        suggestion.reviewed_at = now
        suggestion.created_link_id = link.id

        created_links.append(link)

    await db.flush()
    logger.info(
        f"Auto-approved {len(created_links)} links from {len(suggestions)} suggestions"
    )
    return created_links
