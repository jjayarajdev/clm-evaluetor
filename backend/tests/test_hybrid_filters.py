"""Hybrid structured-filter core (Phase 3). _apply_contract_filters is the
deterministic DB half of a hybrid query — no LLM — so it's fully testable."""

import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import JSON, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base
from app.models.tenant import Tenant
from app.models.contract import Contract, ContractStatus, RiskLevel
from app.agents.intent_router import _apply_contract_filters

TID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
TODAY = date.today()


@pytest_asyncio.fixture
async def db():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(eng.sync_engine, "connect")
    def _p(c, r):
        cur = c.cursor(); cur.execute("PRAGMA foreign_keys=OFF"); cur.close()

    for t in Base.metadata.tables.values():
        for col in t.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
    seen = set()
    for t in Base.metadata.tables.values():
        d = [i for i in t.indexes if i.name not in seen and not seen.add(i.name)]
        t.indexes.clear(); t.indexes.update(d)

    async with eng.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)() as s:
        s.add(Tenant(id=TID, name="T", slug="t", is_active=True))
        await s.flush()
        yield s
    await eng.dispose()


async def _add(db, **kw):
    c = Contract(
        id=uuid.uuid4(), tenant_id=TID, filename=kw.get("filename", f"{uuid.uuid4().hex[:8]}.pdf"),
        file_path="/x", uploaded_by=uuid.uuid4(), status=ContractStatus.COMPLETED,
        contract_type=kw.get("contract_type"), counterparty=kw.get("counterparty"),
        contract_value=kw.get("value"), risk_level=kw.get("risk"),
        auto_renewal=kw.get("auto_renewal"), expiration_date=kw.get("expiration_date"),
    )
    db.add(c); await db.flush()
    return c


@pytest.mark.asyncio
async def test_filters_risk_and_auto_renewal(db):
    await _add(db, risk=RiskLevel.HIGH, auto_renewal=True, counterparty="Acme")
    await _add(db, risk=RiskLevel.LOW, auto_renewal=True, counterparty="Beta")
    await _add(db, risk=RiskLevel.HIGH, auto_renewal=False, counterparty="Gamma")

    got = await _apply_contract_filters(db, TID, {"risk_levels": ["high", "critical"], "auto_renewal": True})
    assert {c.counterparty for c in got} == {"Acme"}


@pytest.mark.asyncio
async def test_filters_expiring_window(db):
    await _add(db, expiration_date=TODAY + timedelta(days=30), counterparty="Soon")
    await _add(db, expiration_date=TODAY + timedelta(days=200), counterparty="Later")
    await _add(db, expiration_date=TODAY - timedelta(days=10), counterparty="Past")

    got = await _apply_contract_filters(db, TID, {"expiring_within_days": 90})
    assert {c.counterparty for c in got} == {"Soon"}


@pytest.mark.asyncio
async def test_filters_value_and_counterparty(db):
    await _add(db, value=500000, counterparty="Acme Corp")
    await _add(db, value=1000, counterparty="Acme Corp")
    await _add(db, value=900000, counterparty="Other Inc")

    got = await _apply_contract_filters(db, TID, {"min_value": 100000, "counterparty": "acme"})
    assert {round(float(c.contract_value)) for c in got} == {500000}


@pytest.mark.asyncio
async def test_empty_filter_returns_all(db):
    await _add(db, counterparty="A"); await _add(db, counterparty="B")
    got = await _apply_contract_filters(db, TID, {})
    assert len(got) == 2
