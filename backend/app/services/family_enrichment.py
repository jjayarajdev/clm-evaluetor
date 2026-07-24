"""Inherit missing context from a contract's family.

Structural documents (exhibits, attachments, schedules) often carry no
extractable counterparty or classifiable type of their own — their identity
comes from the master agreement they hang under. Once links exist, this
service flows that context down: EMPTY fields only, never overwriting
extracted values, with provenance recorded.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.contract_link import ContractLink

logger = logging.getLogger(__name__)

_MAX_ANCESTOR_DEPTH = 5

# Weak links don't define family context either (consistent with grouping)
_EXCLUDED_LINK_TYPES = ("related", "references")


async def _parent_of(db: AsyncSession, contract_id: uuid.UUID) -> uuid.UUID | None:
    return (
        await db.execute(
            select(ContractLink.parent_contract_id)
            .where(
                ContractLink.child_contract_id == contract_id,
                ContractLink.is_active == True,  # noqa: E712
                ContractLink.link_type.notin_(_EXCLUDED_LINK_TYPES),
            )
            .limit(1)
        )
    ).scalar_one_or_none()


async def enrich_from_family(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    contract_ids: list[uuid.UUID] | None = None,
) -> int:
    """Fill empty counterparty/profile on linked children from ancestors.

    Scoped to contract_ids when given, else all tenant contracts with a
    parent link. Returns the number of contracts enriched. Does not commit.
    """
    query = select(Contract).where(Contract.tenant_id == tenant_id)
    if contract_ids is not None:
        query = query.where(Contract.id.in_(contract_ids))
    contracts = (await db.execute(query)).scalars().all()

    enriched = 0
    for contract in contracts:
        needs_counterparty = not contract.counterparty
        needs_profile = contract.industry_profile_id is None
        if not needs_counterparty and not needs_profile:
            continue

        # Walk up the ancestor chain until both gaps are filled
        ancestor_id = await _parent_of(db, contract.id)
        depth = 0
        inherited: dict[str, str] = {}
        while ancestor_id and depth < _MAX_ANCESTOR_DEPTH and (
            needs_counterparty or needs_profile
        ):
            ancestor = await db.get(Contract, ancestor_id)
            if not ancestor:
                break
            if needs_counterparty and ancestor.counterparty:
                contract.counterparty = ancestor.counterparty
                inherited["counterparty"] = str(ancestor.id)
                needs_counterparty = False
            if needs_profile and ancestor.industry_profile_id is not None:
                contract.industry_profile_id = ancestor.industry_profile_id
                inherited["industry_profile_id"] = str(ancestor.id)
                needs_profile = False
            ancestor_id = await _parent_of(db, ancestor.id)
            depth += 1

        if inherited:
            provenance = dict(contract.metadata_provenance or {})
            for field, source in inherited.items():
                provenance[field] = {
                    "raw_text": "inherited from family",
                    "source": "family_inheritance",
                    "from_contract_id": source,
                }
            contract.metadata_provenance = provenance
            enriched += 1

    if enriched:
        logger.info(
            f"Family enrichment filled context on {enriched} contract(s) "
            f"for tenant {tenant_id}"
        )
    await db.flush()
    return enriched
