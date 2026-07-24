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

    sub_ids = [c.id for c, _ in subordinates]
    already_parented = set(
        (
            await db.execute(
                select(ContractLink.child_contract_id).where(
                    ContractLink.child_contract_id.in_(sub_ids),
                    ContractLink.is_active == True,  # noqa: E712
                    ContractLink.link_type.notin_(["related", "references"]),
                )
            )
        )
        .scalars()
        .all()
    )

    created = 0
    for child, ntype in subordinates:
        if child.id in already_parented:
            continue
        masters = masters_by_party.get(_norm_party(child.counterparty), [])
        if len(masters) != 1 or masters[0].id == child.id:
            continue
        master = masters[0]
        db.add(
            ContractLink(
                parent_contract_id=master.id,
                child_contract_id=child.id,
                link_type=ntype if ntype in _SUBORDINATE_TYPES else "sow",
                link_description=(
                    "Counterparty family: same counterparty as the tenant's "
                    "only master agreement for this party"
                ),
                is_active=True,
            )
        )
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

        # Children that already have a parent link keep their structure
        child_ids = [c.id for c in children]
        already_parented = set(
            (
                await db.execute(
                    select(ContractLink.child_contract_id).where(
                        ContractLink.child_contract_id.in_(child_ids),
                        ContractLink.is_active == True,  # noqa: E712
                    )
                )
            )
            .scalars()
            .all()
        )

        for child in children:
            if child.id in already_parented or child.id == master.id:
                continue
            match = _CHILD_RE.match(child.filename)
            prefix = match.group(1).lower()
            number = (match.group(2) or "").strip()
            db.add(
                ContractLink(
                    parent_contract_id=master.id,
                    child_contract_id=child.id,
                    link_type=_PREFIX_TO_LINK_TYPE.get(prefix, "attachment"),
                    reference_number=f"{prefix.title()} {number}".strip(),
                    link_description=(
                        "Framework set: filename declares this document as "
                        f"{prefix} of the master agreement in the same upload folder"
                    ),
                    is_active=True,
                )
            )
            created += 1

        if created:
            logger.info(
                f"Framework linking: {created} children linked under "
                f"'{master.filename}' in {folder_path}"
            )

    await db.flush()
    return created
