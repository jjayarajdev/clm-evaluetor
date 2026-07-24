"""Resolve declared in-document references into contract links.

Legal documents state their lineage in their own text ("This SOW is entered
into pursuant to the Master Services Agreement dated ... between ..."). The
reference-extraction agent captures these as
schema_data._contract_references.parent_references. This resolver matches
each declaration against the tenant corpus — the most reliable relationship
signal there is, and the one that survives bad filenames and bad metadata.

Resolution scoring per candidate parent:
- reference identifier appears in candidate filename          -> +3 (near-certain)
- declared type matches candidate type (normalized)           -> +2
- a declared party matches candidate counterparty/filename    -> +2
- declared date matches candidate effective date              -> +2

A unique candidate scoring >= 4 becomes a link; a unique candidate scoring
>= 2 (or ties) becomes a pending suggestion for human review.
"""

import logging
import re
import uuid
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.contract_link import ContractLink
from app.models.suggested_link import SuggestedContractLink
from app.services.contract_types import normalize_contract_type

logger = logging.getLogger(__name__)

_RELATIONSHIP_TO_LINK_TYPE = {
    "amends": "amendment",
    "renews": "renewal",
}
_ROLE_TO_LINK_TYPE = {
    "schedule": "schedule",
    "exhibit": "exhibit",
    "amendment": "amendment",
    "sow": "sow",
    "appendix": "appendix",
    "attachment": "attachment",
}


def _norm(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _link_type_for(reference: dict, document_role: str | None) -> str:
    lt = _RELATIONSHIP_TO_LINK_TYPE.get((reference.get("relationship") or "").lower())
    if lt:
        return lt
    role = (document_role or "").lower()
    return _ROLE_TO_LINK_TYPE.get(role, "sow" if role == "sow" else "attachment")


async def resolve_declared_references(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    contract_ids: list[uuid.UUID] | None = None,
) -> tuple[int, int]:
    """Resolve parent declarations for the given contracts (or whole tenant).

    Returns (links_created, suggestions_created). Does not commit.
    """
    query = select(Contract).where(
        Contract.tenant_id == tenant_id, Contract.schema_data.isnot(None)
    )
    if contract_ids is not None:
        query = query.where(Contract.id.in_(contract_ids))
    candidates_query = select(Contract).where(Contract.tenant_id == tenant_id)

    children = [
        c
        for c in (await db.execute(query)).scalars().all()
        if (c.schema_data or {}).get("_contract_references", {}).get("parent_references")
    ]
    if not children:
        return (0, 0)

    corpus = (await db.execute(candidates_query)).scalars().all()

    # Weak-rule parents may be replaced by a declaration (the referee
    # decides); suggestion-strength matches still skip parented children.
    parented = set(
        (
            await db.execute(
                select(ContractLink.child_contract_id).where(
                    ContractLink.child_contract_id.in_([c.id for c in children]),
                    ContractLink.is_active == True,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )

    links_created = 0
    suggestions_created = 0

    for child in children:
        refs = (child.schema_data or {}).get("_contract_references", {})
        document_role = refs.get("document_role")

        for ref in refs.get("parent_references", []):
            if not isinstance(ref, dict) or (ref.get("confidence") or 0) < 0.5:
                continue

            ref_type = normalize_contract_type(ref.get("referenced_type"))
            ref_parties = [_norm(p) for p in (ref.get("party_names") or []) if p]
            ref_ident = _norm(ref.get("reference_identifier"))
            ref_date = ref.get("referenced_date")

            scored: list[tuple[int, Contract]] = []
            for cand in corpus:
                if cand.id == child.id:
                    continue
                score = 0
                cand_fn = _norm(cand.filename)
                cand_cp = _norm(cand.counterparty)

                if ref_ident and len(ref_ident) >= 4 and ref_ident in cand_fn:
                    score += 3
                if ref_type and normalize_contract_type(cand.contract_type) == ref_type:
                    score += 2
                if ref_parties and any(
                    p and (p in cand_cp or p in cand_fn) for p in ref_parties
                ):
                    score += 2
                if ref_date and cand.effective_date:
                    try:
                        if str(cand.effective_date) == str(date.fromisoformat(ref_date)):
                            score += 2
                    except (ValueError, TypeError):
                        pass
                if score > 0:
                    scored.append((score, cand))

            if not scored:
                continue
            scored.sort(key=lambda s: s[0], reverse=True)
            best_score, best = scored[0]
            unique = len(scored) == 1 or scored[1][0] < best_score

            link_type = _link_type_for(ref, document_role)

            if best_score >= 4 and unique:
                # Certain enough to claim — the referee replaces any
                # lower-evidence parent, never a human's
                from app.services.link_authority import claim_parent

                if await claim_parent(
                    db,
                    child_id=child.id,
                    parent_id=best.id,
                    link_type=link_type,
                    rule="declared_reference",
                    description=(
                        "Declared reference: "
                        + (ref.get("reference_text") or "")[:400]
                    ),
                ):
                    links_created += 1
                    parented.add(child.id)
                break
            elif best_score >= 2 and child.id not in parented:
                exists = (
                    await db.execute(
                        select(SuggestedContractLink.id).where(
                            or_(
                                (SuggestedContractLink.source_contract_id == child.id)
                                & (SuggestedContractLink.target_contract_id == best.id),
                                (SuggestedContractLink.source_contract_id == best.id)
                                & (SuggestedContractLink.target_contract_id == child.id),
                            ),
                            SuggestedContractLink.status.in_(["pending", "approved"]),
                        ).limit(1)
                    )
                ).scalar_one_or_none()
                if not exists:
                    db.add(
                        SuggestedContractLink(
                            tenant_id=tenant_id,
                            source_contract_id=child.id,
                            target_contract_id=best.id,
                            suggested_link_type=link_type,
                            suggested_direction="source_is_child",
                            confidence_score=0.7,
                            matching_signals={"declared_reference": best_score},
                            status="pending",
                            reasoning=(
                                "Document declares its parent: "
                                + (ref.get("reference_text") or "")[:300]
                            ),
                        )
                    )
                    suggestions_created += 1
                break

    if links_created or suggestions_created:
        logger.info(
            f"Declared-reference resolution: {links_created} links, "
            f"{suggestions_created} suggestions for tenant {tenant_id}"
        )
    await db.flush()
    return (links_created, suggestions_created)
