"""Materialize auto_family contract groups from the ContractLink graph.

Every connected component of the (undirected) link graph with two or more
contracts gets exactly one `auto_family` group, anchored at its root contract
and keyed by the partial unique index (tenant_id, root_contract_id) WHERE
group_type='auto_family'. Sync is a scoped recompute-and-reconcile: it only
touches components containing the given contract ids, and only reconciles
membership rows with source='auto_family' so manual pins survive.
"""

import logging
import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.contract_group import ContractGroup, ContractGroupMember
from app.models.contract_link import ContractLink

logger = logging.getLogger(__name__)


async def _load_link_graph(
    db: AsyncSession, tenant_id: uuid.UUID
) -> tuple[dict[uuid.UUID, set[uuid.UUID]], set[uuid.UUID]]:
    """Adjacency (undirected) and the set of contracts that are children."""
    rows = (
        await db.execute(
            select(ContractLink.parent_contract_id, ContractLink.child_contract_id)
            .join(Contract, ContractLink.parent_contract_id == Contract.id)
            .where(ContractLink.is_active == True, Contract.tenant_id == tenant_id)  # noqa: E712
        )
    ).all()

    adjacency: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    children: set[uuid.UUID] = set()
    for parent_id, child_id in rows:
        adjacency[parent_id].add(child_id)
        adjacency[child_id].add(parent_id)
        children.add(child_id)
    return adjacency, children


def _component_of(
    start: uuid.UUID, adjacency: dict[uuid.UUID, set[uuid.UUID]]
) -> set[uuid.UUID]:
    seen = {start}
    stack = [start]
    while stack:
        node = stack.pop()
        for neighbor in adjacency.get(node, ()):
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return seen


async def _pick_root(
    db: AsyncSession,
    component: set[uuid.UUID],
    children: set[uuid.UUID],
    adjacency: dict[uuid.UUID, set[uuid.UUID]],
) -> uuid.UUID:
    """Root = a contract that is nobody's child; ties broken by degree then age."""
    candidates = [c for c in component if c not in children]
    if not candidates:
        # Pure cycle — fall back to the whole component
        candidates = list(component)
    if len(candidates) == 1:
        return candidates[0]

    rows = (
        await db.execute(
            select(Contract.id, Contract.created_at).where(Contract.id.in_(candidates))
        )
    ).all()
    created = {r[0]: r[1] for r in rows}
    return sorted(
        candidates,
        key=lambda c: (-len(adjacency.get(c, ())), created.get(c) or 0, str(c)),
    )[0]


async def sync_auto_family_groups(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    contract_ids: list[uuid.UUID] | None = None,
) -> int:
    """Reconcile auto_family groups for the components touching contract_ids.

    With contract_ids=None, reconciles the whole tenant (nightly job).
    Returns the number of groups created or updated. Does not commit —
    caller owns the transaction.
    """
    adjacency, children = await _load_link_graph(db, tenant_id)

    # Which components to process
    seeds = contract_ids if contract_ids is not None else list(adjacency.keys())
    processed: set[uuid.UUID] = set()
    components: list[set[uuid.UUID]] = []
    for seed in seeds:
        if seed in processed:
            continue
        component = _component_of(seed, adjacency)
        processed |= component
        if len(component) >= 2:
            components.append(component)

    # Existing auto_family groups for this tenant
    existing_groups = (
        (
            await db.execute(
                select(ContractGroup).where(
                    ContractGroup.tenant_id == tenant_id,
                    ContractGroup.group_type == "auto_family",
                )
            )
        )
        .scalars()
        .all()
    )
    group_by_root = {g.root_contract_id: g for g in existing_groups}

    touched = 0
    for component in components:
        root = await _pick_root(db, component, children, adjacency)

        # Reuse a group anchored anywhere inside this component (root may have
        # moved when a new parent appeared above the old root)
        group = group_by_root.get(root)
        if not group:
            anchored_inside = [
                g for r, g in group_by_root.items() if r in component
            ]
            if anchored_inside:
                group = anchored_inside[0]
                group.root_contract_id = root

        if not group:
            root_contract = (
                await db.execute(select(Contract).where(Contract.id == root))
            ).scalar_one_or_none()
            stem = (root_contract.counterparty or root_contract.filename.rsplit(".", 1)[0]) if root_contract else "Contract"
            group = ContractGroup(
                tenant_id=tenant_id,
                name=f"{stem} family",
                group_type="auto_family",
                root_contract_id=root,
            )
            db.add(group)
            await db.flush()
            group_by_root[root] = group

        # Reconcile auto_family members only
        current = {
            m.contract_id: m
            for m in (
                await db.execute(
                    select(ContractGroupMember).where(
                        ContractGroupMember.group_id == group.id
                    )
                )
            )
            .scalars()
            .all()
        }
        for cid in component:
            if cid not in current:
                db.add(
                    ContractGroupMember(
                        tenant_id=tenant_id,
                        group_id=group.id,
                        contract_id=cid,
                        source="auto_family",
                    )
                )
        for cid, member in current.items():
            if member.source == "auto_family" and cid not in component:
                await db.delete(member)
        touched += 1

    # Cleanup: auto groups whose component dissolved (root no longer linked)
    scope = set(contract_ids) if contract_ids is not None else None
    for root, group in list(group_by_root.items()):
        if root is None:
            continue
        component = _component_of(root, adjacency)
        if len(component) >= 2:
            continue
        if scope is not None and root not in scope:
            continue
        members = (
            (
                await db.execute(
                    select(ContractGroupMember).where(
                        ContractGroupMember.group_id == group.id
                    )
                )
            )
            .scalars()
            .all()
        )
        non_auto = [m for m in members if m.source != "auto_family"]
        for m in members:
            if m.source == "auto_family":
                await db.delete(m)
        if not non_auto:
            await db.delete(group)
            group_by_root.pop(root, None)
        touched += 1

    if touched:
        logger.info(
            f"Auto-family sync touched {touched} group(s) for tenant {tenant_id}"
        )
    return touched
