"""Deterministic framework-set linking.

Outsourcing/framework agreements arrive as one master plus dozens of
"Exhibit N", "Attachment N-X", "Schedule N" documents. AI signals routinely
fail on these (counterparty extraction picks up the doc's own filename, type
classification is erratic), but the structure is deterministic from the
filenames — the same signal a human uses. Within an upload folder, if there
is exactly one master-type document and two or more exhibit/attachment-named
documents, link each child under the master with the link type its filename
declares.
"""

import logging
import os
import re
import uuid
from collections import defaultdict

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.contract_link import ContractLink, LinkType

logger = logging.getLogger(__name__)

_CHILD_RE = re.compile(
    r"^(exhibit|attachment|schedule|annex|appendix)\b[\s\-_]*([0-9]+(?:[\s.\-][0-9A-Za-z]+)?)?",
    re.IGNORECASE,
)
_MASTER_RE = re.compile(r"^(msa\b|master\b|framework\b)", re.IGNORECASE)

_PREFIX_TO_LINK_TYPE = {
    "exhibit": "exhibit",
    "attachment": "attachment",
    "schedule": "schedule",
    "annex": "appendix",
    "appendix": "appendix",
}


# "Algoleap_SOW 122_... - SOW0001894.pdf" → root="Algoleap_SOW 122_...",
# num="SOW0001894"; CSOW-numbered or "(CR n)"-marked documents are change
# orders of the root's base SOW.
_DOCNUM_RE = re.compile(
    r"^(?P<root>.+?)\s*-\s*(?P<num>C?SOW\s?0*(?P<digits>\d+))\s*(?P<cr>\(CR\s*\d+\))?\s*(?:\.[A-Za-z0-9]+)?$",
    re.IGNORECASE,
)


async def link_change_orders(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> int:
    """Nest change orders under their base SOW by document-number structure.

    Documents sharing a filename root form one work package: the lowest
    plain SOW number is the base; CSOW-numbered / CR-marked documents become
    its change orders, and later plain SOW numbers its modifications. A
    child currently parented at the family master (or unparented) is moved
    one level down under the base — curated deeper structure is preserved.
    Returns links created/moved; does not commit.
    """
    contracts = (
        (
            await db.execute(
                select(Contract).where(Contract.tenant_id == tenant_id)
            )
        )
        .scalars()
        .all()
    )

    groups: dict[str, list[tuple[Contract, int, bool]]] = defaultdict(list)
    for c in contracts:
        m = _DOCNUM_RE.match(c.filename or "")
        if not m:
            continue
        is_change = m.group("num").lower().startswith("csow") or bool(m.group("cr"))
        groups[m.group("root").strip().lower()].append(
            (c, int(m.group("digits")), is_change)
        )

    moved = 0
    for root, docs in groups.items():
        if len(docs) < 2:
            continue
        bases = [(n, c) for c, n, is_change in docs if not is_change]
        if not bases:
            continue
        base = min(bases, key=lambda t: t[0])[1]

        from app.services.link_authority import claim_parent

        for child, _num, is_change in docs:
            if child.id == base.id:
                continue
            if await claim_parent(
                db,
                child_id=child.id,
                parent_id=base.id,
                link_type="change_order" if is_change else "modification",
                rule="document_number",
                description=(
                    "Work package structure: document number marks this as "
                    + ("a change order of " if is_change else "a later revision of ")
                    + f"'{base.filename}'"
                ),
            ):
                moved += 1

    if moved:
        logger.info(
            f"Change-order nesting created/moved {moved} link(s) for tenant {tenant_id}"
        )
    await db.flush()
    return moved


async def _parent_link_of(db: AsyncSession, contract_id: uuid.UUID):
    return (
        await db.execute(
            select(ContractLink)
            .where(
                ContractLink.child_contract_id == contract_id,
                ContractLink.is_active == True,  # noqa: E712
                ContractLink.link_type.notin_(["related", "references"]),
            )
            .limit(1)
        )
    ).scalar_one_or_none()


# Subordinate types that naturally hang under a master agreement. These are
# canonical codes (see contract_types.canonical_contract_type) — the schedule
# family an outsourcing MSA spawns: work orders, service levels, pricing/rate
# cards, governance & operating-model docs, policies, amendments, etc.
_SUBORDINATE_TYPES = {
    "sow", "amendment", "addendum", "schedule", "exhibit", "attachment",
    "sla", "service_agreement", "pricing", "governance", "policy", "order", "mou",
}
# Master tiers, strongest first. A family is anchored by its single top-tier
# master: a lone MSA wins outright; with no MSA, a lone service/supply/vendor
# agreement (an outsourcing/framework deal) anchors the family instead. More
# than one candidate in a tier is genuinely ambiguous → that party gets no
# auto-master (never silently guess).
_MASTER_TYPE_TIERS: tuple[frozenset[str], ...] = (
    frozenset({"msa"}),
    frozenset({"service_agreement", "supply_agreement", "vendor_agreement"}),
)
_MASTER_TYPES = frozenset().union(*_MASTER_TYPE_TIERS)


def _resolve_tiered_master(
    by_tier: dict[int, list["Contract"]],
) -> "Contract | None":
    """Pick a party's master: the lone contract in the strongest occupied tier.
    Ambiguity (2+ in that tier) yields None rather than a wrong guess."""
    for tier_idx in range(len(_MASTER_TYPE_TIERS)):
        docs = by_tier.get(tier_idx, [])
        if len(docs) == 1:
            return docs[0]
        if len(docs) > 1:
            return None  # ambiguous at the strongest occupied tier
    return None

# Contract types are NOT link types. Reuse a contract type as the relationship
# label only when it's also a valid LinkType value (sow/amendment/schedule/…);
# everything else (service_agreement, sla, pricing, governance, policy, …)
# becomes a generic parent-child family link. 'child' — not 'related' — because
# 'related' is excluded from family grouping (see group_sync._FAMILY_LINK_TYPES_EXCLUDED).
_VALID_LINK_TYPES = {lt.value for lt in LinkType}


def _subordinate_link_type(contract_type: str) -> str:
    return contract_type if contract_type in _VALID_LINK_TYPES else "child"


def _norm_party(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


async def link_by_counterparty_master(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> int:
    """Link unparented subordinate contracts under their counterparty's master.

    Metadata-driven rule: when a tenant has exactly ONE master agreement for
    a counterparty, subordinate-type contracts (SOWs, amendments, schedules)
    with the same counterparty belong under it — the same reasoning a human
    applies. Ambiguity (multiple masters for the counterparty) creates
    nothing. Returns links created; does not commit.
    """
    from app.services.contract_types import canonical_contract_type

    contracts = (
        (
            await db.execute(
                select(Contract).where(
                    Contract.tenant_id == tenant_id,
                    Contract.counterparty.isnot(None),
                )
            )
        )
        .scalars()
        .all()
    )

    # Masters bucketed per party AND per tier, so a lone MSA outranks a lone
    # service/supply agreement for the same party.
    masters_by_party: dict[str, dict[int, list[Contract]]] = defaultdict(
        lambda: defaultdict(list)
    )
    subordinates: list[tuple[Contract, str]] = []
    for c in contracts:
        ntype = canonical_contract_type(c.contract_type) or (c.contract_type or "")
        party = _norm_party(c.counterparty)
        if not party:
            continue
        tier = next(
            (i for i, t in enumerate(_MASTER_TYPE_TIERS) if ntype in t), None
        )
        if tier is not None:
            masters_by_party[party][tier].append(c)
        if ntype in _SUBORDINATE_TYPES:
            subordinates.append((c, ntype))

    if not subordinates:
        return 0

    from app.services.link_authority import claim_parent

    created = 0
    for child, ntype in subordinates:
        master = _resolve_tiered_master(
            masters_by_party.get(_norm_party(child.counterparty), {})
        )
        if master is None or master.id == child.id:
            continue
        if await claim_parent(
            db,
            child_id=child.id,
            parent_id=master.id,
            link_type=_subordinate_link_type(ntype),
            rule="counterparty_master",
            description=(
                "Counterparty family: same counterparty as the tenant's "
                "only master agreement for this party"
            ),
        ):
            created += 1

    if created:
        logger.info(
            f"Counterparty-master linking created {created} link(s) for tenant {tenant_id}"
        )
    await db.flush()
    return created


# A document's number encodes its parent in these outsourcing-style families:
#   "Attachment N-X ..."     -> the "Exhibit N ..." head
#   "Exhibit N.M ..." (M>0)  -> the "Exhibit N.0 ..." head
# Bounded so numbers can't bleed: "Exhibit 5" is a head; "Exhibit 2.0" heads the
# 2.x sub-series; "Exhibit 20"/"Exhibit 20-2IM" are NOT heads for key "5"/"2".
_HEAD_BARE_RE = re.compile(r"^\s*exhibit\s+(\d+)(?![.\d-])", re.IGNORECASE)
_HEAD_DOTZERO_RE = re.compile(r"^\s*exhibit\s+(\d+)\.0(?![.\d])", re.IGNORECASE)
_CHILD_ATTACHMENT_RE = re.compile(r"^\s*attachment\s+(\d+)", re.IGNORECASE)
_CHILD_SUBEXHIBIT_RE = re.compile(r"^\s*exhibit\s+(\d+)\.([1-9]\d*)", re.IGNORECASE)


async def link_by_document_numbering(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> int:
    """Link structural documents to their parent by their filename numbering.

    Deterministic and independent of the (frequently broken) extracted
    parent-reference field — an "Attachment 5-E(4)" whose reference field wrongly
    names itself still resolves to "Exhibit 5" by its number. Fires only on a
    UNIQUE head match, so ambiguity links nothing. Goes through the link referee
    (rule='document_number'), so a stronger declared/human parent still wins.
    Returns links created; does not commit.
    """
    from app.services.link_authority import claim_parent

    contracts = (
        (await db.execute(select(Contract).where(Contract.tenant_id == tenant_id)))
        .scalars()
        .all()
    )

    heads: dict[str, list[Contract]] = defaultdict(list)
    for c in contracts:
        fn = c.filename or ""
        m = _HEAD_BARE_RE.match(fn) or _HEAD_DOTZERO_RE.match(fn)
        if m:
            heads[m.group(1)].append(c)

    created = 0
    for c in contracts:
        fn = c.filename or ""
        am = _CHILD_ATTACHMENT_RE.match(fn)
        em = _CHILD_SUBEXHIBIT_RE.match(fn) if not am else None
        if am:
            key, link_type = am.group(1), "attachment"
        elif em:
            key, link_type = em.group(1), "exhibit"
        else:
            continue
        candidates = heads.get(key, [])
        if len(candidates) != 1 or candidates[0].id == c.id:
            continue  # no head, or ambiguous, or self
        if await claim_parent(
            db,
            child_id=c.id,
            parent_id=candidates[0].id,
            link_type=link_type,
            rule="document_number",
            description=f"Document numbering: child of {(candidates[0].filename or '')[:120]}",
        ):
            created += 1

    if created:
        logger.info(
            f"Document-numbering linking created {created} link(s) for tenant {tenant_id}"
        )
    await db.flush()
    return created


async def link_framework_sets(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    folder: str | None = None,
) -> int:
    """Create child→master links for framework document sets.

    Scans upload folders (optionally one folder); in each folder with exactly
    one master-named document and >=2 exhibit/attachment-named documents,
    links children under the master. Skips children that already have any
    parent link. Returns the number of links created. Does not commit.
    """
    query = select(Contract).where(
        Contract.tenant_id == tenant_id, Contract.file_path.isnot(None)
    )
    contracts = (await db.execute(query)).scalars().all()

    by_folder: dict[str, list[Contract]] = defaultdict(list)
    for c in contracts:
        by_folder[os.path.dirname(c.file_path or "")].append(c)

    if folder is not None:
        by_folder = {k: v for k, v in by_folder.items() if k == folder}

    created = 0
    for folder_path, docs in by_folder.items():
        masters = [
            c for c in docs
            if _MASTER_RE.match(c.filename or "") and not _CHILD_RE.match(c.filename or "")
        ]
        children = [c for c in docs if _CHILD_RE.match(c.filename or "")]
        if len(masters) != 1 or len(children) < 2:
            continue
        master = masters[0]

        from app.services.link_authority import claim_parent

        for child in children:
            if child.id == master.id:
                continue
            match = _CHILD_RE.match(child.filename)
            prefix = match.group(1).lower()
            if await claim_parent(
                db,
                child_id=child.id,
                parent_id=master.id,
                link_type=_PREFIX_TO_LINK_TYPE.get(prefix, "attachment"),
                rule="framework_set",
                description=(
                    "Framework set: filename declares this document as "
                    f"{prefix} of the master agreement in the same upload folder"
                ),
            ):
                created += 1

        if created:
            logger.info(
                f"Framework linking: {created} children linked under "
                f"'{master.filename}' in {folder_path}"
            )

    await db.flush()
    return created
