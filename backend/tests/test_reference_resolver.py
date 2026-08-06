"""Declared-reference resolution: an explicit, unique parent reference
("Attachment 12-A → Exhibit 12") auto-links; ambiguous or imprecise ones don't."""

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
from app.services.reference_resolver import (
    _identifier_matches,
    resolve_declared_references,
)

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# -- pure predicate -------------------------------------------------------

@pytest.mark.parametrize(
    "ident,filename,expected",
    [
        ("exhibit 12", "exhibit 12 3rd party contracts final v2 9", True),
        ("exhibit 12", "exhibit 120 something", False),   # not a longer number
        ("exhibit 2", "exhibit 20 termination final", False),
        ("exhibit 4", "exhibit 4 pricing final v3 1b", True),
        ("exhibit 12", "attachment 12 a third party", False),  # different token
    ],
)
def test_identifier_matches_is_bounded(ident, filename, expected):
    assert _identifier_matches(ident, filename) is expected


# -- db fixtures (JSONB -> JSON for SQLite) --------------------------------

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


def _parent_ref(ident, rtype="Exhibit"):
    return {
        "reference_identifier": ident, "referenced_type": rtype, "confidence": 0.9,
        "relationship": "parent", "party_names": [], "referenced_date": None,
    }


def _contract(tid, name, ctype="other", parent_refs=None):
    sd = None
    if parent_refs is not None:
        sd = {"_contract_references": {"parent_references": parent_refs}}
    return Contract(
        id=uuid.uuid4(), tenant_id=tid, filename=name, file_path=f"/u/{name}",
        status=ContractStatus.COMPLETED, uploaded_by=uuid.uuid4(), version=1,
        contract_type=ctype, counterparty="ING", schema_data=sd,
    )


async def _links(db, tid):
    return (
        (await db.execute(select(ContractLink).where(ContractLink.is_active == True)))  # noqa: E712
        .scalars()
        .all()
    )


@pytest.mark.asyncio
async def test_explicit_unique_reference_auto_links(db):
    tid = uuid.uuid4()
    ex12 = _contract(tid, "Exhibit 12 (3rd Party Contracts) Final v2.9.doc")
    att = _contract(tid, "Attachment 12-A (Third Party Contracts) Final v2.0.xls",
                    parent_refs=[_parent_ref("Exhibit 12")])
    db.add_all([ex12, att])
    await db.flush()

    links_created, _ = await resolve_declared_references(db, tid)
    assert links_created == 1
    links = await _links(db, tid)
    assert len(links) == 1
    assert links[0].parent_contract_id == ex12.id
    assert links[0].child_contract_id == att.id


@pytest.mark.asyncio
async def test_ambiguous_reference_does_not_link(db):
    tid = uuid.uuid4()
    ex12a = _contract(tid, "Exhibit 12 (Contracts) Final v1.doc")
    ex12b = _contract(tid, "Exhibit 12 (Duplicate) Final v2.doc")
    att = _contract(tid, "Attachment 12-A Final.xls",
                    parent_refs=[_parent_ref("Exhibit 12")])
    db.add_all([ex12a, ex12b, att])
    await db.flush()

    links_created, suggestions = await resolve_declared_references(db, tid)
    assert links_created == 0          # two candidates → not unique → no auto-link
    assert await _links(db, tid) == []
    assert suggestions >= 1            # parked as a suggestion instead


@pytest.mark.asyncio
async def test_lsa_links_to_its_msa_by_party_among_many(db):
    """A Local Service Agreement declaring 'the MSA between ING and the supplier'
    links to the ING MSA — resolved by canonical party ('ING Group' ~ 'ING Bank
    N.V.'), NOT to the Accenture or Javelin MSAs. The multi-supplier case."""
    tid = uuid.uuid4()
    msa_ing = _contract(tid, "MSA GEN Final v3.3.doc", ctype="msa")
    msa_ing.counterparty = "ING Bank N.V."
    msa_acc = _contract(tid, "SWS Landscape.doc", ctype="msa")
    msa_acc.counterparty = "Accenture NV/SA"
    msa_jav = _contract(tid, "Jumbo Javelin.doc", ctype="msa")
    msa_jav.counterparty = "Javelin Group Limited"
    lsa = _contract(
        tid, "LSA Belgium Final v1.3 KPN.doc", ctype="service_agreement",
        parent_refs=[{
            "reference_identifier": "MSA", "referenced_type": "MSA", "confidence": 0.95,
            "relationship": "parent", "referenced_date": None,
            "party_names": ["ING Group", "PST Supplier"],
        }],
    )
    lsa.counterparty = "KPN Outsourcing Services Belgium N.V."
    db.add_all([msa_ing, msa_acc, msa_jav, lsa])
    await db.flush()

    links_created, _ = await resolve_declared_references(db, tid)
    assert links_created == 1
    links = await _links(db, tid)
    assert len(links) == 1
    assert links[0].parent_contract_id == msa_ing.id   # the ING MSA, not Accenture/Javelin
    assert links[0].child_contract_id == lsa.id


@pytest.mark.asyncio
async def test_imprecise_number_does_not_link(db):
    tid = uuid.uuid4()
    ex20 = _contract(tid, "Exhibit 20 (Termination Assistance) Final v1.5.doc")
    att = _contract(tid, "Attachment 2-Z Final.doc",
                    parent_refs=[_parent_ref("Exhibit 2")])  # only Exhibit 20 exists
    db.add_all([ex20, att])
    await db.flush()

    links_created, _ = await resolve_declared_references(db, tid)
    assert links_created == 0          # "Exhibit 2" must not match "Exhibit 20"
    assert await _links(db, tid) == []
