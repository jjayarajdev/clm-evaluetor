"""The link referee: evidence-ranked parent arbitration.

Several rules can claim a contract's parent. Without arbitration the first
writer wins forever — circumstantial evidence can block the document's own
declared parent. Every machine link records the rule that made it; a claim
succeeds only when its evidence outranks the existing link's. Human links
(created_by_rule = NULL) are never replaced by machines.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract_link import ContractLink

logger = logging.getLogger(__name__)

# Higher wins. Humans are unrankable-above-everything.
RULE_RANK = {
    None: 100,                 # human
    "declared_reference": 90,  # the document names its parent
    "document_number": 80,     # CSOW/CR numbering structure
    "framework_set": 70,       # exhibit/attachment filename structure
    "counterparty_master": 60, # same party, single master
    "llm_detection": 50,       # pairwise AI matching
}

_WEAK_TYPES = ("related", "references")


def rank_of(rule: str | None) -> int:
    return RULE_RANK.get(rule, 50)


async def claim_parent(
    db: AsyncSession,
    child_id: uuid.UUID,
    parent_id: uuid.UUID,
    link_type: str,
    rule: str | None,
    description: str,
) -> bool:
    """Create or replace the child's parent link if `rule` outranks it.

    Returns True when a link was created or replaced. Does not commit.
    """
    if child_id == parent_id:
        return False

    existing = (
        await db.execute(
            select(ContractLink)
            .where(
                ContractLink.child_contract_id == child_id,
                ContractLink.is_active == True,  # noqa: E712
                ContractLink.link_type.notin_(_WEAK_TYPES),
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    if existing is not None:
        same = (
            existing.parent_contract_id == parent_id
            and existing.link_type == link_type
        )
        if same or rank_of(rule) <= rank_of(existing.created_by_rule):
            return False
        logger.info(
            f"Link referee: '{rule}' (rank {rank_of(rule)}) replaces "
            f"'{existing.created_by_rule}' (rank {rank_of(existing.created_by_rule)}) "
            f"as parent of {child_id}"
        )
        await db.delete(existing)
        await db.flush()

    db.add(
        ContractLink(
            parent_contract_id=parent_id,
            child_contract_id=child_id,
            link_type=link_type,
            link_description=description[:500],
            created_by_rule=rule,
            is_active=True,
        )
    )
    await db.flush()
    return True
