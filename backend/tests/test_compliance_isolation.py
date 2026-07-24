"""Tenant isolation for the compliance engine.

compliance_gaps and regulatory_obligations now carry an explicit tenant_id
(defense-in-depth, in addition to the contract join). These tests assert
tenant A never sees tenant B's gaps or obligations via /api/compliance/*.
"""

import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.deps import get_current_tenant_id, get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.compliance_gap import ComplianceGap
from app.models.contract import Contract, ContractStatus, ContractType, RiskLevel
from app.models.industry import (
    ComplianceDocumentType,
    ComplianceGapSeverity,
    ComplianceGapStatus,
    Industry,
)
from app.models.obligation import RAGStatus
from app.models.regulatory_obligation import (
    ObligationCategory,
    RegulationType,
    RegulatoryObligation,
)
from app.models.user import Role, User

TENANT_A_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
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


def _user(tenant_id, name):
    return User(
        id=uuid.uuid4(), tenant_id=tenant_id, username=name,
        email=f"{name}@x.com", full_name=name, password_hash="x",
        role=Role.ADMIN, is_active=True,
    )


def _contract(tenant_id, uploaded_by):
    return Contract(
        id=uuid.uuid4(), tenant_id=tenant_id,
        filename=f"{tenant_id}.pdf", file_path=f"/{tenant_id}.pdf", file_size=100,
        status=ContractStatus.COMPLETED, counterparty="CP",
        contract_type=ContractType.MSA,
        effective_date=date.today(), expiration_date=date.today() + timedelta(days=365),
        contract_value=1000, currency="USD", risk_level=RiskLevel.LOW,
        uploaded_by=uploaded_by,
    )


@pytest_asyncio.fixture(scope="function")
async def seed(db):
    ua, ub = _user(TENANT_A_ID, "user_a"), _user(TENANT_B_ID, "user_b")
    db.add_all([ua, ub])
    await db.flush()
    ca, cb = _contract(TENANT_A_ID, ua.id), _contract(TENANT_B_ID, ub.id)
    db.add_all([ca, cb])
    await db.flush()

    def gap(tid, cid):
        return ComplianceGap(
            id=uuid.uuid4(), tenant_id=tid, contract_id=cid,
            missing_document_type=ComplianceDocumentType.QUALITY_AGREEMENT,
            gap_description="missing", severity=ComplianceGapSeverity.HIGH,
            status=ComplianceGapStatus.OPEN,
        )

    def obl(tid, cid):
        return RegulatoryObligation(
            id=uuid.uuid4(), tenant_id=tid, contract_id=cid,
            industry=Industry.PHARMACEUTICAL, regulation_type=RegulationType.FDA,
            obligation_category=ObligationCategory.AUDIT_RIGHTS,
            title="Obl", description="desc", compliance_status=RAGStatus.NOT_ASSESSED,
        )

    ga, gb = gap(TENANT_A_ID, ca.id), gap(TENANT_B_ID, cb.id)
    oa, ob = obl(TENANT_A_ID, ca.id), obl(TENANT_B_ID, cb.id)
    db.add_all([ga, gb, oa, ob])
    await db.commit()
    return {"ua": ua, "ub": ub, "ca": ca, "cb": cb, "ga": ga, "gb": gb, "oa": oa, "ob": ob}


def _client_as(db, user, tenant_id):
    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_gaps_isolated(seed, db):
    try:
        async with _client_as(db, seed["ua"], TENANT_A_ID) as client:
            resp = await client.get("/api/compliance/gaps")
        assert resp.status_code == 200, resp.text
        ids = {g["id"] for g in resp.json()}
        assert str(seed["ga"].id) in ids
        assert str(seed["gb"].id) not in ids
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_obligations_isolated(seed, db):
    try:
        async with _client_as(db, seed["ua"], TENANT_A_ID) as client:
            resp = await client.get("/api/compliance/obligations")
        assert resp.status_code == 200, resp.text
        ids = {o["id"] for o in resp.json()}
        assert str(seed["oa"].id) in ids
        assert str(seed["ob"].id) not in ids
    finally:
        app.dependency_overrides.clear()
