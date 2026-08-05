"""Tiered counterparty-master linking: an MSA anchors a family, but with no MSA
a lone service/supply/vendor agreement anchors it instead; ambiguity anchors
nothing."""

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
from app.models.contract_link import ContractLink
from app.services.framework_linker import link_by_counterparty_master

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


def _contract(tid, name, ctype, cp="NUON N.V."):
    return Contract(
        id=uuid.uuid4(), tenant_id=tid, filename=name, file_path=f"/u/{name}",
        status=ContractStatus.COMPLETED, uploaded_by=uuid.uuid4(), version=1,
        contract_type=ctype, counterparty=cp,
    )


async def _active_links(db):
    return (
        (await db.execute(select(ContractLink).where(ContractLink.is_active == True)))  # noqa: E712
        .scalars()
        .all()
    )


@pytest.mark.asyncio
async def test_service_agreement_anchors_family_when_no_msa(db):
    tid = uuid.uuid4()
    master = _contract(tid, "Outsourcing Agreement.pdf", "service_agreement")
    sow = _contract(tid, "SOW 1.pdf", "sow")
    sched = _contract(tid, "Schedule A.pdf", "schedule")
    db.add_all([master, sow, sched])
    await db.flush()

    n = await link_by_counterparty_master(db, tid)
    assert n == 2
    links = await _active_links(db)
    assert {l.child_contract_id for l in links} == {sow.id, sched.id}
    assert all(l.parent_contract_id == master.id for l in links)


@pytest.mark.asyncio
async def test_msa_outranks_service_agreement(db):
    tid = uuid.uuid4()
    msa = _contract(tid, "MSA.pdf", "msa")
    svc = _contract(tid, "Service Agreement.pdf", "service_agreement")
    sow = _contract(tid, "SOW 1.pdf", "sow")
    db.add_all([msa, svc, sow])
    await db.flush()

    n = await link_by_counterparty_master(db, tid)
    # both the SOW and the (subordinate) service agreement hang under the MSA
    assert n == 2
    links = await _active_links(db)
    assert all(l.parent_contract_id == msa.id for l in links)
    assert {l.child_contract_id for l in links} == {svc.id, sow.id}


@pytest.mark.asyncio
async def test_ambiguous_tier_anchors_nothing(db):
    tid = uuid.uuid4()
    a = _contract(tid, "Service Agreement A.pdf", "service_agreement")
    b = _contract(tid, "Service Agreement B.pdf", "service_agreement")
    sow = _contract(tid, "SOW 1.pdf", "sow")
    db.add_all([a, b, sow])
    await db.flush()

    n = await link_by_counterparty_master(db, tid)
    assert n == 0  # two candidate masters in the top tier → no guess
    assert await _active_links(db) == []
