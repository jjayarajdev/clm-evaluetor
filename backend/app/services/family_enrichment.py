"""Inherit and correct context from a contract's family.

Structural documents (exhibits, attachments, schedules) often carry no
extractable counterparty, or worse an unreliable one — their own filename, a
document title, or a generic role word. Their true identity comes from the
master agreement they hang under. Once links exist, this service flows that
context down the family tree:

- EMPTY counterparty/profile is filled from the nearest ancestor (as before).
- An UNRELIABLE or uncorroborated counterparty on a child is OVERRIDDEN by the
  family root's — but a child whose counterparty is itself a real party (it
  heads its own master agreement somewhere in the tenant) is left untouched,
  so genuine multi-party structures survive.

When a child moves off a junk organization that this creates, the vacated org
is pruned. All changes record provenance and never commit.
"""

import logging
import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.metadata_extraction import clean_counterparty, is_unreliable_counterparty
from app.models.contract import Contract
from app.models.contract_link import ContractLink
from app.services.org_cleanup import prune_org_if_empty
from app.services.org_resolver import canonical_org_key

logger = logging.getLogger(__name__)

_MAX_ANCESTOR_DEPTH = 5

# Weak links don't define family context either (consistent with grouping)
_EXCLUDED_LINK_TYPES = ("related", "references")

# Contract types whose extracted counterparty is authoritative — a party that
# heads one of these is a real party, never overridden by family inheritance.
_MASTER_TYPES = {"msa", "master", "framework", "master_services_agreement"}


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


async def _reliable_ancestor(db: AsyncSession, contract: Contract):
    """Walk up to the nearest ancestor with a reliable (clean) counterparty."""
    ancestor_id = await _parent_of(db, contract.id)
    depth = 0
    while ancestor_id and depth < _MAX_ANCESTOR_DEPTH:
        ancestor = await db.get(Contract, ancestor_id)
        if not ancestor:
            break
        if ancestor.counterparty and not is_unreliable_counterparty(
            ancestor.counterparty, ancestor.filename
        ):
            return ancestor
        ancestor_id = await _parent_of(db, ancestor.id)
        depth += 1
    return None


async def enrich_from_family(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    contract_ids: list[uuid.UUID] | None = None,
) -> int:
    """Fill/correct counterparty, org and profile on linked children.

    Scoped to contract_ids when given, else all tenant contracts. Returns the
    number of contracts changed. Does not commit.
    """
    from app.services.contract_types import normalize_contract_type

    all_tenant = (
        await db.execute(select(Contract).where(Contract.tenant_id == tenant_id))
    ).scalars().all()

    # Canonical keys of parties that head a master agreement — authoritative,
    # never overridden even when they appear as a differing child.
    master_party_keys: set[str] = set()
    for c in all_tenant:
        ntype = normalize_contract_type(c.contract_type) or (c.contract_type or "")
        if ntype in _MASTER_TYPES and c.counterparty and not is_unreliable_counterparty(
            c.counterparty, c.filename
        ):
            key = canonical_org_key(c.counterparty)
            if key:
                master_party_keys.add(key)

    targets = all_tenant
    if contract_ids is not None:
        wanted = set(contract_ids)
        targets = [c for c in all_tenant if c.id in wanted]

    changed = 0
    vacated_orgs: set[uuid.UUID] = set()

    for contract in targets:
        cp_unreliable = is_unreliable_counterparty(contract.counterparty, contract.filename)
        cp_key = canonical_org_key(contract.counterparty or "")
        needs_profile = contract.industry_profile_id is None

        # A child keeps its own counterparty when it is reliable AND either
        # matches nothing to override against or is itself a real master party.
        root = await _reliable_ancestor(db, contract)
        inherited: dict[str, str] = {}

        if root is not None:
            root_key = canonical_org_key(root.counterparty or "")
            differs = bool(cp_key) and bool(root_key) and cp_key != root_key
            corroborated = cp_key in master_party_keys
            should_override_cp = cp_unreliable or (differs and not corroborated)

            if should_override_cp and root_key != cp_key:
                if contract.organization_id and contract.organization_id != root.organization_id:
                    vacated_orgs.add(contract.organization_id)
                contract.counterparty = root.counterparty
                if root.organization_id is not None:
                    contract.organization_id = root.organization_id
                inherited["counterparty"] = str(root.id)
            if needs_profile and root.industry_profile_id is not None:
                contract.industry_profile_id = root.industry_profile_id
                inherited["industry_profile_id"] = str(root.id)

        if inherited:
            provenance = dict(contract.metadata_provenance or {})
            for field, source in inherited.items():
                provenance[field] = {
                    "raw_text": "inherited from family",
                    "source": "family_inheritance",
                    "from_contract_id": source,
                }
            contract.metadata_provenance = provenance
            changed += 1

    await db.flush()

    # Prune orgs that this inheritance emptied (junk orgs the child's own
    # extraction had created before it was corrected).
    pruned = 0
    for oid in vacated_orgs:
        if await prune_org_if_empty(db, oid):
            pruned += 1

    if changed or pruned:
        logger.info(
            f"Family enrichment corrected {changed} contract(s), pruned "
            f"{pruned} emptied org(s) for tenant {tenant_id}"
        )
    await db.flush()
    return changed
