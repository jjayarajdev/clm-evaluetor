"""claim_parent: link_type must be a valid relationship type (never a contract
type), and an existing inactive link must be reused rather than collided with."""

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
from app.services.link_authority import claim_parent

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


def _contract(tid, name):
    return Contract(
        id=uuid.uuid4(), tenant_id=tid, filename=name, file_path=f"/u/{name}",
        status=ContractStatus.COMPLETED, uploaded_by=uuid.uuid4(), version=1,
        contract_type="service_agreement", counterparty="KPN N.V.",
    )


async def _links(db, parent, child):
    return (
        (
            await db.execute(
                select(ContractLink).where(
                    ContractLink.parent_contract_id == parent,
                    ContractLink.child_contract_id == child,
                )
            )
        )
        .scalars()
        .all()
    )


@pytest.mark.asyncio
async def test_contract_type_coerced_to_valid_link_type(db):
    tid = uuid.uuid4()
    parent, child = _contract(tid, "MSA.docx"), _contract(tid, "LSA.doc")
    db.add_all([parent, child])
    await db.flush()

    # 'service_agreement' is a contract type, not a LinkType — must be coerced.
    created = await claim_parent(
        db, child_id=child.id, parent_id=parent.id,
        link_type="service_agreement", rule="counterparty_master", description="x",
    )
    assert created is True
    links = await _links(db, parent.id, child.id)
    assert len(links) == 1
    assert links[0].link_type == "child"  # coerced, not the raw contract type


@pytest.mark.asyncio
async def test_reuses_inactive_duplicate_link(db):
    tid = uuid.uuid4()
    parent, child = _contract(tid, "MSA.docx"), _contract(tid, "SOW.doc")
    db.add_all([parent, child])
    await db.flush()
    # A previously-deactivated identical link exists — uq_contract_link ignores
    # is_active, so a naive INSERT would violate the unique constraint.
    db.add(ContractLink(
        parent_contract_id=parent.id, child_contract_id=child.id, link_type="sow",
        created_by_rule="old_rule", is_active=False,
    ))
    await db.flush()

    created = await claim_parent(
        db, child_id=child.id, parent_id=parent.id,
        link_type="sow", rule="counterparty_master", description="new",
    )
    assert created is True
    links = await _links(db, parent.id, child.id)
    assert len(links) == 1, "must reuse the inactive row, not insert a duplicate"
    assert links[0].is_active is True
    assert links[0].created_by_rule == "counterparty_master"


@pytest.mark.asyncio
async def test_active_identical_link_is_noop(db):
    tid = uuid.uuid4()
    parent, child = _contract(tid, "MSA.docx"), _contract(tid, "SOW.doc")
    db.add_all([parent, child])
    await db.flush()
    await claim_parent(
        db, child_id=child.id, parent_id=parent.id,
        link_type="sow", rule="counterparty_master", description="x",
    )
    # Same claim again — nothing new created.
    created = await claim_parent(
        db, child_id=child.id, parent_id=parent.id,
        link_type="sow", rule="counterparty_master", description="x",
    )
    assert created is False
    assert len(await _links(db, parent.id, child.id)) == 1
