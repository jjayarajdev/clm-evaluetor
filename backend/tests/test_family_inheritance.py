"""Family counterparty inheritance + unreliable-counterparty detection."""

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

from app.agents.metadata_extraction import is_unreliable_counterparty
from app.database import Base
from app.models.contract import Contract, ContractStatus
from app.models.contract_link import ContractLink
from app.services.family_enrichment import enrich_from_family

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# --- pure predicate -------------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [
        # real organizations must NOT be flagged
        ("ING Bank N.V.", False),
        ("Medi Optiek B.V.", False),
        ("Algoleap Technologies Pvt. Ltd.", False),
        ("DemoSup1 BPO Limited", False),
        ("NUON", False),
        # junk / titles / fragments
        ("", True),
        (None, True),
        ("Schedule 03 Service Levels", True),  # document-structure prefix
        ("the parties", True),
        ("Exhibit A", True),
    ],
)
def test_is_unreliable_counterparty(value, expected):
    assert is_unreliable_counterparty(value) is expected


def test_is_unreliable_counterparty_filename_echo():
    # A counterparty that just echoes its filename is unreliable.
    assert is_unreliable_counterparty(
        "Service Levels-Nov2022", "Schedule 03 - Service Levels-Nov2022.docx"
    ) is True


# --- db fixtures (JSONB → JSON for SQLite) --------------------------------

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


# --- family inheritance ---------------------------------------------------

def _contract(tenant_id, name, cp, ctype, cid=None):
    return Contract(
        id=cid or uuid.uuid4(),
        tenant_id=tenant_id,
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


@pytest.mark.asyncio
async def test_inheritance_overrides_junk_keeps_corroborated(db):
    tid = uuid.uuid4()

    master = _contract(tid, "Sigma_MSA.docx", "DemoSup1 BPO Limited", "msa")
    junk = _contract(tid, "Schedule 03 - Service Levels-Nov2022.docx", "Service Levels-Nov2022", "schedule")
    client_master = _contract(tid, "ClientAA_MSA.docx", "ClientAA Nobel N.V.", "msa")
    corroborated = _contract(tid, "Schedule 16 Exit plan.docx", "ClientAA Nobel N.V.", "schedule")
    differing = _contract(tid, "Schedule 04 - Transition.docx", "Transition-Nov2022", "schedule")

    db.add_all([master, junk, client_master, corroborated, differing])
    db.add_all([
        _link(master, junk),
        _link(master, corroborated),
        _link(master, differing),
    ])
    await db.flush()

    changed = await enrich_from_family(db, tid)

    await db.refresh(junk)
    await db.refresh(corroborated)
    await db.refresh(differing)

    assert junk.counterparty == "DemoSup1 BPO Limited"        # junk -> master
    assert differing.counterparty == "DemoSup1 BPO Limited"   # uncorroborated -> master
    assert corroborated.counterparty == "ClientAA Nobel N.V." # corroborated -> kept
    assert changed == 2
