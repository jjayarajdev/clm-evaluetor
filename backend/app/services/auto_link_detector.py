"""Auto-link detector service for suggesting contract relationships."""

import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
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


# Signal weights
SIGNAL_WEIGHTS = {
    "counterparty_match": 0.30,
    "counterparty_fuzzy": 0.20,
    "type_hierarchy": 0.25,
    "semantic_similarity": 0.20,
    "filename_pattern": 0.15,
    "date_proximity": 0.10,
    "same_batch": 0.15,
}

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

        # Run all detection methods
        await self._find_by_counterparty(contract, candidates)
        await self._find_by_type_hierarchy(contract, candidates)
        await self._find_by_semantic_similarity(contract, candidates)
        self._find_by_filename_patterns(contract, candidates)
        await self._find_by_date_proximity(contract, candidates)

        if batch_contract_ids:
            await self._find_by_batch(contract, batch_contract_ids, candidates)

        # Filter by minimum confidence and sort
        valid_candidates = [
            c for c in candidates.values()
            if c.confidence_score >= min_confidence
        ]
        valid_candidates.sort(key=lambda x: x.confidence_score, reverse=True)

        # Take top N suggestions
        top_candidates = valid_candidates[:max_suggestions]

        # Convert to SuggestedContractLink objects
        suggestions = []
        for candidate in top_candidates:
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
        """Find contracts with matching counterparty."""
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
                candidates[key].signals["counterparty_match"] = SIGNAL_WEIGHTS["counterparty_match"]
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
                candidates[key].signals["counterparty_fuzzy"] = SIGNAL_WEIGHTS["counterparty_fuzzy"]
                candidates[key].reasoning_parts.append(
                    f"Similar counterparty: {other.counterparty}"
                )

    async def _find_by_type_hierarchy(
        self,
        contract: Contract,
        candidates: dict[str, MatchCandidate],
    ) -> None:
        """Find contracts based on type hierarchy (MSA→SOW, etc.)."""
        if not contract.contract_type:
            return

        # Check if source could be a child of existing contracts
        for parent_type, child_types in TYPE_HIERARCHY.items():
            if contract.contract_type in child_types:
                # Find potential parent contracts
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
                    candidates[key].signals["type_hierarchy"] = SIGNAL_WEIGHTS["type_hierarchy"]
                    candidates[key].reasoning_parts.append(
                        f"Type hierarchy: {contract.contract_type.value} typically falls under {parent_type.value}"
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
                candidates[key].signals["type_hierarchy"] = SIGNAL_WEIGHTS["type_hierarchy"]
                candidates[key].reasoning_parts.append(
                    f"Type hierarchy: {child.contract_type.value} typically falls under {contract.contract_type.value}"
                )

    async def _find_by_semantic_similarity(
        self,
        contract: Contract,
        candidates: dict[str, MatchCandidate],
    ) -> None:
        """Find contracts with semantically similar content."""
        if not contract.extracted_text:
            return

        try:
            # Get first 2000 chars as representative sample
            sample_text = contract.extracted_text[:2000]

            # Query for similar chunks
            results = self.vector_store.query_similar(
                query_text=sample_text,
                top_k=20,  # Get more results to find unique contracts
                user_id=None,  # Skip RBAC for internal detection
                user_role="admin",  # Full access
            )

            # Group by contract and find highest similarity per contract
            contract_similarities: dict[str, float] = {}
            for result in results:
                cid = result.metadata.get("contract_id")
                if cid and cid != str(contract.id):
                    # Convert cosine distance to similarity (0-1 scale)
                    # ChromaDB returns cosine distance, so similarity = 1 - distance
                    similarity = max(0, 1 - result.distance)
                    if similarity > 0.7:  # Only consider high similarity
                        if cid not in contract_similarities:
                            contract_similarities[cid] = similarity
                        else:
                            contract_similarities[cid] = max(
                                contract_similarities[cid], similarity
                            )

            # Add to candidates
            for cid, similarity in contract_similarities.items():
                key = cid
                if key not in candidates:
                    # Fetch the contract
                    other = await self.db.get(Contract, uuid.UUID(cid))
                    if other and other.status == ContractStatus.COMPLETED:
                        candidates[key] = MatchCandidate(
                            contract=other,
                            link_type=LinkType.RELATED,
                            direction="source_is_child",
                        )
                if key in candidates:
                    # Scale semantic weight by actual similarity
                    weight = SIGNAL_WEIGHTS["semantic_similarity"] * similarity
                    candidates[key].signals["semantic_similarity"] = weight
                    candidates[key].reasoning_parts.append(
                        f"Content similarity: {similarity:.0%}"
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
                    candidates[key] = MatchCandidate(
                        contract=other,
                        link_type=LinkType.RELATED,
                        direction="source_is_child",
                        signals={"same_batch": SIGNAL_WEIGHTS["same_batch"]},
                        reasoning_parts=["Uploaded in same batch"],
                    )

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
