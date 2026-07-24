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
from app.models.contract_link import ContractLink

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


# Subordinate types that naturally hang under a master agreement
_SUBORDINATE_TYPES = {"sow", "amendment", "addendum", "schedule", "exhibit", "attachment"}
_MASTER_TYPES = {"msa"}


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
    from app.services.contract_types import normalize_contract_type

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

    masters_by_party: dict[str, list[Contract]] = defaultdict(list)
    subordinates: list[tuple[Contract, str]] = []
    for c in contracts:
        ntype = normalize_contract_type(c.contract_type) or (c.contract_type or "")
        party = _norm_party(c.counterparty)
        if not party:
            continue
        if ntype in _MASTER_TYPES:
            masters_by_party[party].append(c)
        elif ntype in _SUBORDINATE_TYPES:
            subordinates.append((c, ntype))

    if not subordinates:
        return 0

    from app.services.link_authority import claim_parent

    created = 0
    for child, ntype in subordinates:
        masters = masters_by_party.get(_norm_party(child.counterparty), [])
        if len(masters) != 1 or masters[0].id == child.id:
            continue
        if await claim_parent(
            db,
            child_id=child.id,
            parent_id=masters[0].id,
            link_type=ntype if ntype in _SUBORDINATE_TYPES else "sow",
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
