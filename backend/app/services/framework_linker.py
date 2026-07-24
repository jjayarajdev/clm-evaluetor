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
