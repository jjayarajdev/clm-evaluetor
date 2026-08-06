"""The Tree view is a read of the materialized auto_family groups: its families
and roots match the Groups page exactly, never a second live derivation from the
link graph."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import JSON, event
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
from app.models.tenant import Tenant
from app.models.user import Role, User
from app.routers.contracts import get_contract_hierarchy

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


def _contract(tid, name, ctype="schedule"):
    return Contract(
        id=uuid.uuid4(), tenant_id=tid, filename=name, file_path=f"/u/{name}",
        status=ContractStatus.COMPLETED, uploaded_by=uuid.uuid4(), version=1,
        contract_type=ctype, counterparty="NUON",
    )


def _link(parent, child, lt="schedule"):
    return ContractLink(
        parent_contract_id=parent.id, child_contract_id=child.id, link_type=lt,
        created_by_rule="framework_set", is_active=True,
    )


def _all_ids(node) -> set:
    ids = {node.id}
    for c in node.children:
        ids |= _all_ids(c)
    return ids


async def _hierarchy(db, tid):
    user = User(
        id=uuid.uuid4(), tenant_id=tid, username="admin", email="a@a.com",
        full_name="Admin", password_hash="x", role=Role.ADMIN, is_active=True,
        business_unit_id=None,
    )
    return await get_contract_hierarchy(current_user=user, tenant_id=tid, db=db)


@pytest.mark.asyncio
async def test_tree_root_matches_group_root_not_link_hub(db):
    """Even when a non-root member is the structural hub (nobody's child, most
    links), the tree roots at the group's root_contract_id — same as Groups."""
    tid = uuid.uuid4()
    db.add(Tenant(id=tid, name="T", slug="t", is_active=True))
    master = _contract(tid, "NUON Outsourcing Agreement.doc", ctype="other")
    hub = _contract(tid, "Schedule 13.docx")
    s1 = _contract(tid, "Schedule 01.docx")
    s2 = _contract(tid, "Schedule 02.docx")
    db.add_all([master, hub, s1, s2])
    # hub is the big link hub; master links to just one schedule.
    db.add_all([_link(master, s1), _link(hub, s1), _link(hub, s2)])
    await db.flush()

    grp = ContractGroup(
        tenant_id=tid, name="NUON family", group_type="auto_family",
        root_contract_id=master.id,
    )
    db.add(grp)
    await db.flush()
    for c in (master, hub, s1, s2):
        db.add(ContractGroupMember(
            tenant_id=tid, group_id=grp.id, contract_id=c.id, source="auto_family"))
    await db.flush()

    resp = await _hierarchy(db, tid)
    assert len(resp.roots) == 1
    assert resp.roots[0].id == str(master.id)               # group root, not the hub
    assert _all_ids(resp.roots[0]) == {str(master.id), str(hub.id), str(s1.id), str(s2.id)}


@pytest.mark.asyncio
async def test_pinned_member_without_link_still_shown(db):
    """A manually-pinned member with no link path to the root still appears in
    the family tree (attached under the root)."""
    tid = uuid.uuid4()
    db.add(Tenant(id=tid, name="T", slug="t", is_active=True))
    master = _contract(tid, "MSA.doc", ctype="msa")
    linked = _contract(tid, "Schedule A.docx")
    pinned = _contract(tid, "Side Letter.docx")
    db.add_all([master, linked, pinned, _link(master, linked)])
    await db.flush()

    grp = ContractGroup(
        tenant_id=tid, name="Fam", group_type="auto_family", root_contract_id=master.id)
    db.add(grp)
    await db.flush()
    db.add_all([
        ContractGroupMember(tenant_id=tid, group_id=grp.id, contract_id=master.id, source="auto_family"),
        ContractGroupMember(tenant_id=tid, group_id=grp.id, contract_id=linked.id, source="auto_family"),
        ContractGroupMember(tenant_id=tid, group_id=grp.id, contract_id=pinned.id, source="manual"),
    ])
    await db.flush()

    resp = await _hierarchy(db, tid)
    assert len(resp.roots) == 1
    assert _all_ids(resp.roots[0]) == {str(master.id), str(linked.id), str(pinned.id)}


@pytest.mark.asyncio
async def test_ungrouped_contracts_are_singleton_roots(db):
    """Contracts in no auto_family group render as their own singleton roots."""
    tid = uuid.uuid4()
    db.add(Tenant(id=tid, name="T", slug="t", is_active=True))
    a = _contract(tid, "Standalone A.pdf", ctype="nda")
    b = _contract(tid, "Standalone B.pdf", ctype="nda")
    db.add_all([a, b])
    await db.flush()

    resp = await _hierarchy(db, tid)
    assert {r.id for r in resp.roots} == {str(a.id), str(b.id)}
    assert all(not r.children for r in resp.roots)
