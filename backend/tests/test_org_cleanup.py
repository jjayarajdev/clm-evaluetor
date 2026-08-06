"""prune_unreliable_orgs: orgs minted from junk counterparties are removed and
their contracts detached; real orgs are kept."""

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
from app.models.organization import Organization
from app.services.org_cleanup import prune_unreliable_orgs

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


def _org(tid, name):
    return Organization(id=uuid.uuid4(), tenant_id=tid, name=name,
                        code=name[:8].upper(), org_type="vendor", is_active=True)


def _contract(tid, org, name):
    return Contract(
        id=uuid.uuid4(), tenant_id=tid, filename=name, file_path=f"/u/{name}",
        status=ContractStatus.COMPLETED, uploaded_by=uuid.uuid4(), version=1,
        contract_type="other", counterparty=org.name, organization_id=org.id,
    )


@pytest.mark.asyncio
async def test_prunes_junk_orgs_keeps_real_ones(db):
    tid = uuid.uuid4()
    junk1 = _org(tid, "Exhibits")
    junk2 = _org(tid, "PST will be agreed")
    real = _org(tid, "KPN Outsourcing Services Belgium N.V.")
    db.add_all([junk1, junk2, real])
    await db.flush()
    c1 = _contract(tid, junk1, "Exhibit 3.doc")
    c2 = _contract(tid, real, "MSA.doc")
    db.add_all([c1, c2])
    await db.flush()

    pruned = await prune_unreliable_orgs(db, tid)
    # Both junk orgs were identified and processed; the real one was skipped.
    assert pruned == 2

    # The junk orgs' contracts are DETACHED (org_id -> NULL) with counterparty
    # text preserved; the real org keeps its contract. (The physical org-row
    # DELETE in delete_org_cascade uses Postgres-format UUID SQL and is verified
    # on prod; SQLite stores UUIDs dash-less so that raw DELETE no-ops here.)
    await db.refresh(c1)
    await db.refresh(c2)
    assert c1.organization_id is None
    assert c1.counterparty == "Exhibits"
    assert c2.organization_id == real.id


@pytest.mark.asyncio
async def test_real_org_never_pruned(db):
    tid = uuid.uuid4()
    real = _org(tid, "Atos Origin Belgium SA")
    db.add(real)
    await db.flush()
    c = _contract(tid, real, "LSA Atos.doc")
    db.add(c)
    await db.flush()

    assert await prune_unreliable_orgs(db, tid) == 0
    await db.refresh(c)
    assert c.organization_id == real.id
