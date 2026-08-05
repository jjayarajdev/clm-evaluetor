"""Materialize auto_family contract groups from the ContractLink graph,
and detect missing referenced documents (Schedule A mentioned, not found).

Every connected component of the (undirected) link graph with two or more
contracts gets exactly one `auto_family` group, anchored at its root contract
and keyed by the partial unique index (tenant_id, root_contract_id) WHERE
group_type='auto_family'. Sync is a scoped recompute-and-reconcile: it only
touches components containing the given contract ids, and only reconciles
membership rows with source='auto_family' so manual pins survive.
"""

import logging
import re
import uuid
from collections import defaultdict

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.metadata_extraction import is_unreliable_counterparty
from app.models.contract import Contract
from app.models.contract_group import (
    ContractGroup,
    ContractGroupFinding,
    ContractGroupMember,
)
from app.models.contract_link import ContractLink

logger = logging.getLogger(__name__)


# Weak association types don't define family membership — one loose
# "related" link would otherwise merge unrelated contract families.
_FAMILY_LINK_TYPES_EXCLUDED = ("related", "references")


async def _load_link_graph(
    db: AsyncSession, tenant_id: uuid.UUID
) -> tuple[dict[uuid.UUID, set[uuid.UUID]], set[uuid.UUID]]:
    """Adjacency (undirected) and the set of contracts that are children."""
    rows = (
        await db.execute(
            select(ContractLink.parent_contract_id, ContractLink.child_contract_id)
            .join(Contract, ContractLink.parent_contract_id == Contract.id)
            .where(
                ContractLink.is_active == True,  # noqa: E712
                Contract.tenant_id == tenant_id,
                ContractLink.link_type.notin_(_FAMILY_LINK_TYPES_EXCLUDED),
            )
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


# Root preference by contract type. A real master agreement should anchor the
# family even when noisy links make it look like someone's child; a structural
# doc (schedule/exhibit/lease/amendment/TOC) is the worst possible root. Higher
# wins. Contract types are normalised through canonical_contract_type first.
_MASTER_ROOT_TYPES = {"msa"}
_STRONG_ROOT_TYPES = {
    "service_agreement", "supply_agreement", "vendor_agreement", "csa",
}
_SUBORDINATE_ROOT_TYPES = {
    "sow", "schedule", "amendment", "lease", "order", "pricing", "governance",
    "policy", "sla", "mou", "nda", "license",
}


def _root_type_rank(contract_type: str | None) -> int:
    from app.services.contract_types import canonical_contract_type

    canon = canonical_contract_type(contract_type) or (contract_type or "").lower()
    if canon in _MASTER_ROOT_TYPES:
        return 3
    if canon in _STRONG_ROOT_TYPES:
        return 2
    if canon in _SUBORDINATE_ROOT_TYPES:
        return 0
    return 1  # unknown / generic agreement — still a better root than a schedule


async def _pick_root(
    db: AsyncSession,
    component: set[uuid.UUID],
    children: set[uuid.UUID],
    adjacency: dict[uuid.UUID, set[uuid.UUID]],
) -> uuid.UUID:
    """Root = the family's master. Prefer a real master agreement by contract
    type, then a contract that is nobody's child, then the biggest hub, then the
    oldest; contract id breaks final ties so the choice is deterministic.

    Ranking runs over the whole component (not just non-children) so a genuine
    master that noisy links turned into someone's child still wins.
    """
    rows = (
        await db.execute(
            select(Contract.id, Contract.created_at, Contract.contract_type).where(
                Contract.id.in_(component)
            )
        )
    ).all()
    meta = {r[0]: (r[1], r[2]) for r in rows}

    def key(c: uuid.UUID):
        created, ctype = meta.get(c, (None, None))
        return (
            -_root_type_rank(ctype),                       # master type first
            0 if c not in children else 1,                 # then not-a-child
            -len(adjacency.get(c, ())),                    # then hub-ness
            created.timestamp() if created else float("inf"),  # then oldest
            str(c),
        )

    return min(component, key=key)


def _find_bridges(
    adjacency: dict[uuid.UUID, set[uuid.UUID]], nodes: set[uuid.UUID]
) -> set[frozenset]:
    """Undirected bridge edges within `nodes` (recursive Tarjan; components are
    tiny so recursion depth is never a concern)."""
    bridges: set[frozenset] = set()
    disc: dict[uuid.UUID, int] = {}
    low: dict[uuid.UUID, int] = {}
    timer = [0]

    def dfs(u: uuid.UUID, parent: uuid.UUID | None) -> None:
        disc[u] = low[u] = timer[0]
        timer[0] += 1
        skip_parent = True
        for v in adjacency.get(u, ()):
            if v not in nodes:
                continue
            if v == parent and skip_parent:
                skip_parent = False  # skip only one parent edge (handles multi-edges)
                continue
            if v not in disc:
                dfs(v, u)
                low[u] = min(low[u], low[v])
                if low[v] > disc[u]:
                    bridges.add(frozenset((u, v)))
            else:
                low[u] = min(low[u], disc[v])

    for s in nodes:
        if s not in disc:
            dfs(s, None)
    return bridges


async def _family_name(
    db: AsyncSession, root: uuid.UUID, component: set[uuid.UUID]
) -> str:
    """Name an auto_family group after the family's real counterparty.

    Prefer the root's counterparty; when it's unreliable (blank, a document
    title like "Exhibit 34 (Benchmarking) ...", or a filename echo) borrow a
    reliable counterparty from any family member — every contract in a family
    shares one. Only when the whole family lacks a reliable counterparty do we
    fall back to the root's filename stem; a group is never named after junk.
    """
    rows = (
        await db.execute(
            select(Contract.id, Contract.counterparty, Contract.filename).where(
                Contract.id.in_(component)
            )
        )
    ).all()
    by_id = {r[0]: (r[1], r[2]) for r in rows}
    root_cp, root_fn = by_id.get(root, (None, None))
    if root_cp and not is_unreliable_counterparty(root_cp, root_fn):
        return f"{root_cp} family"
    for _cid, (cp, fn) in by_id.items():
        if cp and not is_unreliable_counterparty(cp, fn):
            return f"{cp} family"
    if root_fn:
        return f"{root_fn.rsplit('.', 1)[0]} family"
    return "Contract family"


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

    # Existing auto_family groups for this tenant, with their member rows
    # preloaded so we can detect a group by its membership — not just its root.
    # A group's root can go NULL (root contract deleted, FK ON DELETE SET NULL)
    # or migrate (a new parent appears above the old root); keying purely on
    # root_contract_id then strands the old group and a duplicate is created.
    existing_groups = list(
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
    group_ids = [g.id for g in existing_groups]
    members_by_group: dict[uuid.UUID, list[ContractGroupMember]] = defaultdict(list)
    if group_ids:
        for m in (
            (
                await db.execute(
                    select(ContractGroupMember).where(
                        ContractGroupMember.group_id.in_(group_ids)
                    )
                )
            )
            .scalars()
            .all()
        ):
            members_by_group[m.group_id].append(m)
    contracts_by_group: dict[uuid.UUID, set[uuid.UUID]] = {
        g.id: {m.contract_id for m in members_by_group.get(g.id, [])}
        for g in existing_groups
    }

    # Which components to process. Seed from the requested contracts (or the
    # whole graph for the nightly job) AND from the members of any existing
    # auto_family group — so orphaned/duplicate groups get revisited and
    # collapsed even when the seed contracts don't touch them directly.
    seeds = list(contract_ids) if contract_ids is not None else list(adjacency.keys())
    if contract_ids is not None:
        for g in existing_groups:
            if g.root_contract_id is None or g.root_contract_id not in adjacency:
                seeds.extend(contracts_by_group.get(g.id, ()))

    processed: set[uuid.UUID] = set()
    components: list[set[uuid.UUID]] = []
    for seed in seeds:
        if seed in processed:
            continue
        component = _component_of(seed, adjacency)
        processed |= component
        if len(component) >= 2:
            components.append(component)

    async def _merge_into(survivor: ContractGroup, dup: ContractGroup) -> None:
        """Fold a duplicate group into the survivor: rescue its manual pins and
        completeness findings, then delete it (cascade drops the rest)."""
        survivor_cids = contracts_by_group.setdefault(survivor.id, set())
        for m in members_by_group.get(dup.id, []):
            # auto_family rows are recomputed below; only manual pins are moved.
            if m.source != "auto_family" and m.contract_id not in survivor_cids:
                m.group_id = survivor.id
                survivor_cids.add(m.contract_id)
                members_by_group[survivor.id].append(m)
        await db.execute(
            update(ContractGroupFinding)
            .where(ContractGroupFinding.group_id == dup.id)
            .values(group_id=survivor.id)
        )
        members_by_group.pop(dup.id, None)
        contracts_by_group.pop(dup.id, None)
        if dup in existing_groups:
            existing_groups.remove(dup)
        await db.delete(dup)

    touched = 0
    claimed: set[uuid.UUID] = set()  # group ids already assigned to a component
    for component in components:
        root = await _pick_root(db, component, children, adjacency)

        # Every existing auto_family group that overlaps this component — by
        # root or by any shared member (catches NULL/migrated roots and the
        # stale duplicates a prior run left behind).
        overlapping = [
            g
            for g in existing_groups
            if g.id not in claimed
            and (
                (g.root_contract_id is not None and g.root_contract_id in component)
                or (contracts_by_group.get(g.id, set()) & component)
            )
        ]
        # Survivor: prefer one already anchored at the chosen root.
        survivor = next(
            (g for g in overlapping if g.root_contract_id == root), None
        ) or (overlapping[0] if overlapping else None)

        name = await _family_name(db, root, component)
        if survivor is None:
            survivor = ContractGroup(
                tenant_id=tenant_id,
                name=name,
                group_type="auto_family",
                root_contract_id=root,
            )
            db.add(survivor)
            await db.flush()
            existing_groups.append(survivor)
            members_by_group[survivor.id] = []
            contracts_by_group[survivor.id] = set()
        else:
            survivor.root_contract_id = root
            # auto_family names are system-derived, not user-owned — keep them
            # fresh as the root migrates and as counterparty extraction improves.
            if survivor.name != name:
                survivor.name = name
        claimed.add(survivor.id)

        # Collapse the extras into the survivor before reconciling membership.
        for dup in overlapping:
            if dup.id != survivor.id:
                await _merge_into(survivor, dup)

        # Reconcile auto_family members only (manual pins are left untouched)
        current = {m.contract_id: m for m in members_by_group.get(survivor.id, [])}
        for cid in component:
            if cid not in current:
                row = ContractGroupMember(
                    tenant_id=tenant_id,
                    group_id=survivor.id,
                    contract_id=cid,
                    source="auto_family",
                )
                db.add(row)
                members_by_group[survivor.id].append(row)
        for cid, member in current.items():
            if member.source == "auto_family" and cid not in component:
                await db.delete(member)
        touched += 1

    # Cleanup: auto groups whose component dissolved, including NULL-root
    # orphans (root contract deleted) that no live component reclaimed above.
    scope = set(contract_ids) if contract_ids is not None else None
    for group in list(existing_groups):
        if group.id in claimed:
            continue
        root = group.root_contract_id
        if root is not None:
            component = _component_of(root, adjacency)
            if len(component) >= 2:
                continue  # still a live family reachable from the root
            if scope is not None and root not in scope and not (
                contracts_by_group.get(group.id, set()) & scope
            ):
                continue  # out of this scoped run's reach
        # NULL-root or dissolved: drop its auto members, keep only if manual
        # pins remain (then it becomes an empty-family manual group).
        members = members_by_group.get(group.id, [])
        non_auto = [m for m in members if m.source != "auto_family"]
        for m in members:
            if m.source == "auto_family":
                await db.delete(m)
        if not non_auto:
            await db.delete(group)
            existing_groups.remove(group)
        touched += 1

    # Session has autoflush=False — flush so callers (e.g. the missing-
    # reference detector) see the reconciled groups/members immediately.
    await db.flush()

    if touched:
        logger.info(
            f"Auto-family sync touched {touched} group(s) for tenant {tenant_id}"
        )
    return touched


async def prune_redundant_family_links(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    contract_ids: list[uuid.UUID] | None = None,
) -> int:
    """De-web families so they render as trees.

    Sibling↔sibling cross-links (schedule→schedule, exhibit→exhibit) accumulate
    from different linking rules and turn a family into a tangle. This removes
    the redundant ones: a machine-created link is deactivated only when neither
    endpoint is the family root AND the edge is not a bridge — i.e. both
    endpoints stay connected to the family without it. Human links, links
    touching the root, and bridges are always kept, so nothing is ever
    disconnected and family membership is unchanged. Reversible
    (is_active=False). Does not commit — the caller owns the transaction.
    """
    from app.services.link_authority import rank_of

    adjacency, children = await _load_link_graph(db, tenant_id)

    link_rows = (
        (
            await db.execute(
                select(ContractLink)
                .join(Contract, ContractLink.parent_contract_id == Contract.id)
                .where(
                    Contract.tenant_id == tenant_id,
                    ContractLink.is_active == True,  # noqa: E712
                    ContractLink.link_type.notin_(_FAMILY_LINK_TYPES_EXCLUDED),
                )
            )
        )
        .scalars()
        .all()
    )
    links_by_pair: dict[frozenset, list[ContractLink]] = defaultdict(list)
    for link in link_rows:
        links_by_pair[
            frozenset((link.parent_contract_id, link.child_contract_id))
        ].append(link)

    def _still_connected(work, a, b) -> bool:
        """Are a and b connected after dropping the a–b edge from `work`?"""
        work[a].discard(b)
        work[b].discard(a)
        seen, stack = {a}, [a]
        while stack:
            n = stack.pop()
            for x in work[n]:
                if x not in seen:
                    seen.add(x)
                    stack.append(x)
        work[a].add(b)
        work[b].add(a)
        return b in seen

    seeds = list(contract_ids) if contract_ids is not None else list(adjacency.keys())
    processed: set[uuid.UUID] = set()
    pruned = 0
    for seed in seeds:
        if seed in processed:
            continue
        component = _component_of(seed, adjacency)
        processed |= component
        if len(component) < 3:  # a single edge is never redundant
            continue
        root = await _pick_root(db, component, children, adjacency)

        # Mutable adjacency for this component; we drop edges as we go so
        # connectivity is re-checked against the shrinking graph.
        work = {n: {x for x in adjacency.get(n, ()) if x in component} for n in component}

        # Candidate edges: fully machine-made, neither endpoint the root.
        candidates = []
        for pair, links in links_by_pair.items():
            if not pair <= component or root in pair:
                continue
            if any(link.created_by_rule is None for link in links):
                continue  # human-anchored — never prune
            candidates.append((pair, links))
        # Drop the weakest-evidence links first (deterministic).
        candidates.sort(
            key=lambda pl: (
                min(rank_of(link.created_by_rule) for link in pl[1]),
                sorted(str(x) for x in pl[0]),
            )
        )
        for pair, links in candidates:
            a, b = tuple(pair)
            if b not in work.get(a, ()):
                continue  # already removed
            if not _still_connected(work, a, b):
                continue  # bridge in the current graph — keep it
            work[a].discard(b)
            work[b].discard(a)
            for link in links:
                link.is_active = False
                pruned += 1

    if pruned:
        await db.flush()
        logger.info(
            f"Pruned {pruned} redundant family link(s) for tenant {tenant_id}"
        )
    return pruned


# ---------------------------------------------------------------------------
# Missing-reference detection (grouping Phase 2)
# ---------------------------------------------------------------------------

_REFERENCE_TYPE_MAP = {
    "schedule": "schedule",
    "exhibit": "exhibit",
    "appendix": "appendix",
    "annex": "appendix",
    "attachment": "attachment",
    "sow": "sow",
    "statement": "sow",
    "amendment": "amendment",
    "addendum": "addendum",
}


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


async def detect_missing_references(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    contract_ids: list[uuid.UUID] | None = None,
) -> int:
    """Open/resolve missing-reference findings for referencing contracts.

    A contract whose AI extraction lists child_references ("Schedule A",
    "Exhibit B", ...) gets one finding per reference that has no matching
    linked child or group co-member in the system. Findings auto-resolve
    when a matching document appears, and re-open if it disappears.
    Dismissed findings stay dismissed. Does not commit.
    """
    # Parents to scan: contracts with child_references — scoped to the given
    # contracts plus any parent that currently has an unresolved finding
    # (a newly uploaded document may resolve someone else's finding).
    parent_query = (
        select(Contract)
        .where(
            Contract.tenant_id == tenant_id,
            Contract.schema_data.isnot(None),
        )
    )
    parents = [
        c
        for c in (await db.execute(parent_query)).scalars().all()
        if (c.schema_data or {}).get("_contract_references", {}).get("child_references")
    ]
    if contract_ids is not None:
        scope = set(contract_ids)
        open_parent_ids = set(
            (
                await db.execute(
                    select(ContractGroupFinding.contract_id).where(
                        ContractGroupFinding.tenant_id == tenant_id,
                        ContractGroupFinding.status == "open",
                    )
                )
            )
            .scalars()
            .all()
        )
        parents = [c for c in parents if c.id in scope or c.id in open_parent_ids]

    if not parents:
        return 0

    # Existing findings for these parents
    findings = (
        (
            await db.execute(
                select(ContractGroupFinding).where(
                    ContractGroupFinding.tenant_id == tenant_id,
                    ContractGroupFinding.contract_id.in_([c.id for c in parents]),
                )
            )
        )
        .scalars()
        .all()
    )
    findings_by_parent: dict[uuid.UUID, dict[str, ContractGroupFinding]] = defaultdict(dict)
    for f in findings:
        findings_by_parent[f.contract_id][f.reference_label] = f

    changed = 0
    for parent in parents:
        refs = (parent.schema_data or {}).get("_contract_references", {})
        labels = [l for l in refs.get("child_references", []) if isinstance(l, str) and l.strip()]
        if not labels:
            continue

        # Candidate documents: linked children (+ link reference numbers)
        # and co-members of any group containing this contract.
        link_rows = (
            await db.execute(
                select(Contract.filename, ContractLink.reference_number, Contract.id)
                .join(Contract, ContractLink.child_contract_id == Contract.id)
                .where(
                    ContractLink.parent_contract_id == parent.id,
                    ContractLink.is_active == True,  # noqa: E712
                )
            )
        ).all()
        group_ids = (
            (
                await db.execute(
                    select(ContractGroupMember.group_id).where(
                        ContractGroupMember.contract_id == parent.id
                    )
                )
            )
            .scalars()
            .all()
        )
        member_rows = []
        if group_ids:
            member_rows = (
                await db.execute(
                    select(Contract.filename, Contract.id)
                    .join(
                        ContractGroupMember,
                        ContractGroupMember.contract_id == Contract.id,
                    )
                    .where(
                        ContractGroupMember.group_id.in_(group_ids),
                        Contract.id != parent.id,
                    )
                )
            ).all()

        candidates: list[tuple[str, uuid.UUID]] = []
        for filename, ref_number, cid in link_rows:
            candidates.append((_norm(filename), cid))
            if ref_number:
                candidates.append((_norm(ref_number), cid))
        for filename, cid in member_rows:
            candidates.append((_norm(filename), cid))

        # Preferred group for new findings: auto_family first, else any
        finding_group_id = None
        if group_ids:
            auto_group = (
                await db.execute(
                    select(ContractGroup.id)
                    .where(
                        ContractGroup.id.in_(group_ids),
                        ContractGroup.group_type == "auto_family",
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            finding_group_id = auto_group or group_ids[0]

        existing = findings_by_parent.get(parent.id, {})
        for label in labels:
            label_norm = _norm(label)
            if not label_norm:
                continue
            match_id = next(
                (cid for cand, cid in candidates if label_norm in cand), None
            )
            finding = existing.get(label)

            # Re-home findings onto the parent's current group (they may have
            # been created before the group existed, or the group changed)
            if finding is not None and finding.group_id != finding_group_id:
                finding.group_id = finding_group_id
                changed += 1

            if match_id is not None:
                if finding and finding.status == "open":
                    finding.status = "resolved"
                    finding.resolved_by_contract_id = match_id
                    changed += 1
            else:
                if finding is None:
                    first_word = label_norm.split()[0] if label_norm else ""
                    db.add(
                        ContractGroupFinding(
                            tenant_id=tenant_id,
                            group_id=finding_group_id,
                            contract_id=parent.id,
                            finding_type="missing_reference",
                            reference_label=label[:255],
                            reference_type=_REFERENCE_TYPE_MAP.get(first_word),
                            details={"source": "child_references"},
                            status="open",
                        )
                    )
                    changed += 1
                elif finding.status == "resolved":
                    finding.status = "open"
                    finding.resolved_by_contract_id = None
                    changed += 1

    if changed:
        logger.info(
            f"Missing-reference detection changed {changed} finding(s) for tenant {tenant_id}"
        )
    return changed
