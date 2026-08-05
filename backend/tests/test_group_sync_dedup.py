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
from app.services.group_sync import sync_auto_family_groups

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


def _link(parent, child, link_type="schedule"):
    return ContractLink(
        parent_contract_id=parent.id,
        child_contract_id=child.id,
        link_type=link_type,
        created_by_rule="framework_set",
        is_active=True,
    )


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
