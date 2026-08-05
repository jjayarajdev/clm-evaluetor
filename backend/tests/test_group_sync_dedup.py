"""auto_family group reconciliation: dedup overlapping groups and reap the
NULL-root / migrated-root orphans that a deleted or re-rooted family leaves
behind (regression for the "same family listed 5×" bug)."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import JSON, event, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import Base
from app.models.contract import Contract, ContractStatus
from app.models.contract_group import ContractGroup, ContractGroupMember
from app.models.contract_link import ContractLink
from app.services.group_sync import (
    prune_redundant_family_links,
    sync_auto_family_groups,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)

    @event.listens_for(eng.sync_engine, "connect")
    def _pragma(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=OFF")
        cur.close()

    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()

    seen = set()
    for table in Base.metadata.tables.values():
        deduped = []
        for idx in table.indexes:
            if idx.name not in seen:
                seen.add(idx.name)
                deduped.append(idx)
        table.indexes.clear()
        table.indexes.update(deduped)

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture(scope="function")
async def db(engine):
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
        await session.rollback()


def _contract(tid, name, cp="Algoleap Technologies Pvt. Ltd.", ctype="sow", cid=None):
    return Contract(
        id=cid or uuid.uuid4(),
        tenant_id=tid,
        filename=name,
        file_path=f"/uploads/{name}",
        status=ContractStatus.COMPLETED,
        uploaded_by=uuid.uuid4(),
        version=1,
        contract_type=ctype,
        counterparty=cp,
    )


def _link(parent, child, link_type="schedule", rule="framework_set"):
    return ContractLink(
        parent_contract_id=parent.id,
        child_contract_id=child.id,
        link_type=link_type,
        created_by_rule=rule,
        is_active=True,
    )


async def _active_pairs(db, tid):
    links = (
        (
            await db.execute(
                select(ContractLink).where(ContractLink.is_active == True)  # noqa: E712
            )
        )
        .scalars()
        .all()
    )
    return {
        frozenset((l.parent_contract_id, l.child_contract_id)) for l in links
    }


async def _auto_groups(db, tid):
    return (
        (
            await db.execute(
                select(ContractGroup).where(
                    ContractGroup.tenant_id == tid,
                    ContractGroup.group_type == "auto_family",
                )
            )
        )
        .scalars()
        .all()
    )


@pytest.mark.asyncio
async def test_sync_creates_single_group(db):
    tid = uuid.uuid4()
    msa = _contract(tid, "MSA.docx", ctype="msa")
    a = _contract(tid, "SOW_A.docx")
    b = _contract(tid, "SOW_B.docx")
    db.add_all([msa, a, b, _link(msa, a), _link(msa, b)])
    await db.flush()

    await sync_auto_family_groups(db, tid)

    groups = await _auto_groups(db, tid)
    assert len(groups) == 1
    assert groups[0].root_contract_id == msa.id


@pytest.mark.asyncio
async def test_sync_collapses_duplicate_and_null_root_orphans(db):
    """Two stale duplicates (one NULL-root, one migrated-root) plus a manual pin
    on a duplicate — all fold into a single surviving group; the pin survives."""
    tid = uuid.uuid4()
    msa = _contract(tid, "MSA.docx", ctype="msa")
    a = _contract(tid, "SOW_A.docx")
    b = _contract(tid, "SOW_B.docx")
    db.add_all([msa, a, b, _link(msa, a), _link(msa, b)])
    await db.flush()

    # Pre-existing mess, as prod accumulated it:
    #  g_null  — root deleted -> NULL, overlaps the family by members
    #  g_stale — anchored at a NON-root member (a), a migrated-root leftover
    g_null = ContractGroup(tenant_id=tid, name="Algoleap family", group_type="auto_family", root_contract_id=None)
    g_stale = ContractGroup(tenant_id=tid, name="Algoleap family", group_type="auto_family", root_contract_id=a.id)
    db.add_all([g_null, g_stale])
    await db.flush()
    pin = ContractGroupMember(tenant_id=tid, group_id=g_null.id, contract_id=a.id, source="manual")
    db.add_all([
        pin,
        ContractGroupMember(tenant_id=tid, group_id=g_null.id, contract_id=b.id, source="auto_family"),
        ContractGroupMember(tenant_id=tid, group_id=g_stale.id, contract_id=a.id, source="auto_family"),
        ContractGroupMember(tenant_id=tid, group_id=g_stale.id, contract_id=msa.id, source="auto_family"),
    ])
    await db.flush()

    await sync_auto_family_groups(db, tid, contract_ids=[msa.id])

    groups = await _auto_groups(db, tid)
    assert len(groups) == 1, "duplicates and NULL-root orphan must collapse to one"
    survivor = groups[0]
    assert survivor.root_contract_id == msa.id

    members = (
        (
            await db.execute(
                select(ContractGroupMember).where(
                    ContractGroupMember.group_id == survivor.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert {m.contract_id for m in members} == {msa.id, a.id, b.id}
    # the manual pin was rescued onto the survivor (not dropped with its group)
    assert any(m.source == "manual" for m in members)


@pytest.mark.asyncio
async def test_group_named_after_reliable_counterparty(db):
    """The group is named after the family's real counterparty even when the
    root's own counterparty is junk (a document title), and the name is
    recomputed on a later sync rather than frozen at creation."""
    tid = uuid.uuid4()
    # Root has a junk (document-title) counterparty; a child carries the real one.
    root = _contract(tid, "Exhibit 34 (Benchmarking) Final v1.91.doc",
                     cp="Exhibit 34 (Benchmarking) Final v1.91", ctype="msa")
    child = _contract(tid, "LSA Belgium.doc", cp="KPN Outsourcing Services Belgium N.V.")
    db.add_all([root, child, _link(root, child)])
    await db.flush()

    await sync_auto_family_groups(db, tid)
    groups = await _auto_groups(db, tid)
    assert len(groups) == 1
    assert groups[0].name == "KPN Outsourcing Services Belgium N.V. family"

    # A stale name from an earlier run is refreshed, not left frozen.
    groups[0].name = "Exhibit 34 (Benchmarking) Final v1.91 family"
    await db.flush()
    await sync_auto_family_groups(db, tid)
    groups = await _auto_groups(db, tid)
    assert groups[0].name == "KPN Outsourcing Services Belgium N.V. family"


@pytest.mark.asyncio
async def test_group_name_falls_back_to_filename_when_no_reliable_party(db):
    """When no family member has a reliable counterparty, fall back to the
    root's filename stem — never to a junk counterparty string."""
    tid = uuid.uuid4()
    root = _contract(tid, "Master_Frame.docx", cp="the parties", ctype="msa")
    child = _contract(tid, "Schedule A.docx", cp=None, ctype="schedule")
    db.add_all([root, child, _link(root, child)])
    await db.flush()

    await sync_auto_family_groups(db, tid)
    groups = await _auto_groups(db, tid)
    assert len(groups) == 1
    assert groups[0].name == "Master_Frame family"


@pytest.mark.asyncio
async def test_pick_root_uses_type_only_to_break_structural_ties(db):
    """Type is a gentle nudge, not a hijack: when two candidates are
    structurally tied (both non-children, equal degree/age) the master-typed one
    wins — but structure, not the (often mis-extracted) type, comes first."""
    tid = uuid.uuid4()
    msa = _contract(tid, "Master.docx", ctype="msa")
    other = _contract(tid, "Side Agreement.docx", ctype="sla")
    shared = _contract(tid, "Schedule 1.docx", ctype="schedule")
    # msa and 'other' are both non-children with equal degree → type breaks it.
    db.add_all([msa, other, shared, _link(msa, shared), _link(other, shared)])
    await db.flush()

    await sync_auto_family_groups(db, tid)
    groups = await _auto_groups(db, tid)
    assert len(groups) == 1
    assert groups[0].root_contract_id == msa.id


@pytest.mark.asyncio
async def test_pick_root_rejects_subordinate_filename_hub(db):
    """A schedule-named hub never becomes root over a real agreement, even with
    far more links — filename structure beats link degree, and works when the
    real master is untyped (the Demo Logistic case)."""
    tid = uuid.uuid4()
    master = _contract(tid, "NUON ETRM Outsourcing Agreement.doc", cp="NUON", ctype="other")
    hub = _contract(tid, "Schedule 13 Audit Controls.docx", cp="NUON", ctype="other")
    s1 = _contract(tid, "Schedule 01 Definitions.docx", cp="NUON", ctype="other")
    s2 = _contract(tid, "Schedule 02 Services.docx", cp="NUON", ctype="other")
    s3 = _contract(tid, "Schedule 09 Technology.docx", cp="NUON", ctype="other")
    db.add_all([master, hub, s1, s2, s3])
    # hub is the big hub (3 kids); the master links to only one schedule.
    db.add_all([_link(master, s1), _link(hub, s1), _link(hub, s2), _link(hub, s3)])
    await db.flush()

    await sync_auto_family_groups(db, tid)
    groups = await _auto_groups(db, tid)
    assert len(groups) == 1
    assert groups[0].root_contract_id == master.id


@pytest.mark.asyncio
async def test_prune_collapses_sibling_web_to_star(db):
    """Siblings each linked to the root make their cross-links redundant — all of
    them prune away, leaving a clean star; root links stay."""
    tid = uuid.uuid4()
    msa = _contract(tid, "Master.docx", ctype="msa")
    s1 = _contract(tid, "Schedule 1.docx", ctype="schedule")
    s2 = _contract(tid, "Schedule 2.docx", ctype="schedule")
    s3 = _contract(tid, "Schedule 3.docx", ctype="schedule")
    db.add_all([msa, s1, s2, s3])
    db.add_all([_link(msa, s1), _link(msa, s2), _link(msa, s3)])  # root links
    db.add_all([_link(s1, s2), _link(s2, s3), _link(s1, s3)])     # redundant web
    await db.flush()

    pruned = await prune_redundant_family_links(db, tid)
    assert pruned == 3
    pairs = await _active_pairs(db, tid)
    assert pairs == {
        frozenset((msa.id, s1.id)),
        frozenset((msa.id, s2.id)),
        frozenset((msa.id, s3.id)),
    }


@pytest.mark.asyncio
async def test_prune_keeps_bridges_and_human_links(db):
    """A bridge (only path to a leaf) and any human-created link are never
    pruned — connectivity and human intent are preserved."""
    tid = uuid.uuid4()
    msa = _contract(tid, "Master.docx", ctype="msa")
    s1 = _contract(tid, "Schedule 1.docx", ctype="schedule")
    s2 = _contract(tid, "Schedule 2.docx", ctype="schedule")
    leaf = _contract(tid, "Deep Leaf.docx", ctype="schedule")
    db.add_all([msa, s1, s2, leaf])
    db.add_all([_link(msa, s1), _link(msa, s2)])
    db.add(_link(s1, s2, rule=None))          # human sibling link — keep
    db.add(_link(s2, leaf))                     # bridge: leaf's only path — keep
    await db.flush()

    pruned = await prune_redundant_family_links(db, tid)
    assert pruned == 0
    pairs = await _active_pairs(db, tid)
    assert frozenset((s1.id, s2.id)) in pairs   # human link survived
    assert frozenset((s2.id, leaf.id)) in pairs  # bridge survived


@pytest.mark.asyncio
async def test_sync_reaps_orphan_when_family_dissolves(db):
    """Root contract deleted and links gone: the leftover NULL-root auto group
    with only auto members is removed entirely."""
    tid = uuid.uuid4()
    a = _contract(tid, "SOW_A.docx")
    b = _contract(tid, "SOW_B.docx")
    db.add_all([a, b])
    await db.flush()
    orphan = ContractGroup(tenant_id=tid, name="Algoleap family", group_type="auto_family", root_contract_id=None)
    db.add(orphan)
    await db.flush()
    db.add_all([
        ContractGroupMember(tenant_id=tid, group_id=orphan.id, contract_id=a.id, source="auto_family"),
        ContractGroupMember(tenant_id=tid, group_id=orphan.id, contract_id=b.id, source="auto_family"),
    ])
    await db.flush()

    # No links exist -> no live component. Sync over the whole tenant.
    await sync_auto_family_groups(db, tid)

    assert len(await _auto_groups(db, tid)) == 0
