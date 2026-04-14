"""Tenant isolation regression tests.

Verifies that logging in as Tenant A returns zero Tenant B data
across all routers that query tenant-scoped models.
"""

import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timedelta, date

from httpx import AsyncClient, ASGITransport
from sqlalchemy import event, JSON, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.exc import OperationalError as SAOperationalError

from app.main import app
from app.database import Base, get_db
from app.core.deps import get_current_user, get_current_tenant_id
from app.models.user import User, Role
from app.models.tenant import Tenant
from app.models.contract import Contract, ContractStatus, ContractType, RiskLevel
from app.models.organization import Organization
from app.models.relationship import BusinessRelationship, RelationshipTeam
from app.models.survey import SurveyTemplate, SurveyInstance
from app.models.kpi import KPI


# ── Constants ───────────────────────────────────────────────────────

TENANT_A_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ── Database fixtures ───────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)

    # Map PostgreSQL JSONB → JSON for SQLite
    @event.listens_for(eng.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    # Swap JSONB → JSON in column definitions so SQLite can create tables
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()

    # Deduplicate indexes: some models define both column-level index=True
    # and explicit Index() in __table_args__, causing "already exists" on SQLite
    seen_idx = set()
    for table in Base.metadata.tables.values():
        deduped = []
        for idx in table.indexes:
            if idx.name not in seen_idx:
                seen_idx.add(idx.name)
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
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
        await session.rollback()


# ── Seed data ───────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def seed(db: AsyncSession):
    """Create data for two tenants. Returns dict of all objects."""

    # Tenants
    ta = Tenant(id=TENANT_A_ID, name="Tenant A", slug="tenant-a", is_active=True)
    tb = Tenant(id=TENANT_B_ID, name="Tenant B", slug="tenant-b", is_active=True)
    db.add_all([ta, tb])
    await db.flush()

    # Users
    ua = User(
        id=uuid.uuid4(), tenant_id=TENANT_A_ID, username="user_a",
        email="a@a.com", full_name="User A", password_hash="x",
        role=Role.ADMIN, is_active=True,
    )
    ub = User(
        id=uuid.uuid4(), tenant_id=TENANT_B_ID, username="user_b",
        email="b@b.com", full_name="User B", password_hash="x",
        role=Role.ADMIN, is_active=True,
    )
    db.add_all([ua, ub])
    await db.flush()

    # Organizations
    oa1 = Organization(id=uuid.uuid4(), tenant_id=TENANT_A_ID, name="Org A1", code="OA1", org_type="customer", is_active=True)
    oa2 = Organization(id=uuid.uuid4(), tenant_id=TENANT_A_ID, name="Org A2", code="OA2", org_type="vendor", is_active=True)
    ob1 = Organization(id=uuid.uuid4(), tenant_id=TENANT_B_ID, name="Org B1", code="OB1", org_type="customer", is_active=True)
    ob2 = Organization(id=uuid.uuid4(), tenant_id=TENANT_B_ID, name="Org B2", code="OB2", org_type="vendor", is_active=True)
    db.add_all([oa1, oa2, ob1, ob2])
    await db.flush()

    # Contracts
    ca = Contract(
        id=uuid.uuid4(), tenant_id=TENANT_A_ID,
        filename="a.pdf", file_path="/a.pdf", file_size=100,
        status=ContractStatus.COMPLETED, counterparty="Vendor Alpha",
        contract_type=ContractType.MSA,
        effective_date=date.today(), expiration_date=date.today() + timedelta(days=365),
        contract_value=50000, currency="USD", risk_level=RiskLevel.LOW,
        uploaded_by=ua.id,
    )
    cb = Contract(
        id=uuid.uuid4(), tenant_id=TENANT_B_ID,
        filename="b.pdf", file_path="/b.pdf", file_size=100,
        status=ContractStatus.COMPLETED, counterparty="Vendor Beta",
        contract_type=ContractType.MSA,
        effective_date=date.today(), expiration_date=date.today() + timedelta(days=365),
        contract_value=80000, currency="USD", risk_level=RiskLevel.HIGH,
        uploaded_by=ub.id,
    )
    db.add_all([ca, cb])
    await db.flush()

    # Relationships
    ra = BusinessRelationship(
        id=uuid.uuid4(), tenant_id=TENANT_A_ID,
        org_a_id=oa1.id, org_b_id=oa2.id,
        relationship_type="customer", status="active", name="A Relationship",
    )
    rb = BusinessRelationship(
        id=uuid.uuid4(), tenant_id=TENANT_B_ID,
        org_a_id=ob1.id, org_b_id=ob2.id,
        relationship_type="supplier", status="active", name="B Relationship",
    )
    db.add_all([ra, rb])
    await db.flush()

    # Teams
    tma = RelationshipTeam(id=uuid.uuid4(), relationship_id=ra.id, user_id=ua.id, role="member", is_active=True)
    tmb = RelationshipTeam(id=uuid.uuid4(), relationship_id=rb.id, user_id=ub.id, role="member", is_active=True)
    db.add_all([tma, tmb])
    await db.flush()

    # Survey template (global)
    tmpl = SurveyTemplate(id=uuid.uuid4(), name="Shared Template", frequency="quarterly", is_active=True, version=1)
    db.add(tmpl)
    await db.flush()

    # Survey instances
    sia = SurveyInstance(id=uuid.uuid4(), template_id=tmpl.id, relationship_id=ra.id, period="2026-Q1", status="draft")
    sib = SurveyInstance(id=uuid.uuid4(), template_id=tmpl.id, relationship_id=rb.id, period="2026-Q1", status="draft")
    db.add_all([sia, sib])
    await db.flush()

    # KPIs (scoped via relationship, no tenant_id column)
    ka = KPI(id=uuid.uuid4(), relationship_id=ra.id, name="KPI A", category="service_delivery", is_active=True)
    kb = KPI(id=uuid.uuid4(), relationship_id=rb.id, name="KPI B", category="service_delivery", is_active=True)
    db.add_all([ka, kb])

    await db.commit()

    return {
        "ua": ua, "ub": ub,
        "oa1": oa1, "oa2": oa2, "ob1": ob1, "ob2": ob2,
        "ca": ca, "cb": cb,
        "ra": ra, "rb": rb,
        "tma": tma, "tmb": tmb,
        "tmpl": tmpl, "sia": sia, "sib": sib,
        "ka": ka, "kb": kb,
    }


# ── Helpers ─────────────────────────────────────────────────────────

def _client_as(db_session, user, tenant_id):
    """Return an AsyncClient wired to the given user + tenant."""

    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _b_ids(s) -> set[str]:
    """Collect all Tenant B UUID strings."""
    ids = set()
    for key in ("ub", "ob1", "ob2", "cb", "rb", "tmb", "sib", "kb"):
        ids.add(str(s[key].id))
    ids.add(str(TENANT_B_ID))
    return ids


def _assert_no_leak(data, b_ids: set[str], ctx: str):
    """Recursively assert no Tenant B UUID strings appear in response."""
    if isinstance(data, dict):
        for k, v in data.items():
            _assert_no_leak(v, b_ids, f"{ctx}.{k}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            _assert_no_leak(item, b_ids, f"{ctx}[{i}]")
    elif isinstance(data, str) and data in b_ids:
        pytest.fail(f"Tenant B ID {data} leaked at {ctx}")


# ── Organization Tests ──────────────────────────────────────────────

class TestOrganizationIsolation:

    @pytest.mark.asyncio
    async def test_list_returns_only_own_tenant(self, db, seed):
        bids = _b_ids(seed)
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.get("/api/organizations")
            assert r.status_code == 200
            names = [o["name"] for o in r.json()["items"]]
            assert "Org A1" in names
            assert "Org B1" not in names
            _assert_no_leak(r.json(), bids, "list_orgs")

    @pytest.mark.asyncio
    async def test_get_cross_tenant_org_404(self, db, seed):
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.get(f"/api/organizations/{seed['ob1'].id}")
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_org_relationships_cross_tenant_404(self, db, seed):
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            # Own org → 200
            r = await c.get(f"/api/organizations/{seed['oa1'].id}/relationships")
            assert r.status_code == 200
            # Other tenant's org → 404
            r = await c.get(f"/api/organizations/{seed['ob1'].id}/relationships")
            assert r.status_code == 404


# ── Relationship Tests ──────────────────────────────────────────────

class TestRelationshipIsolation:

    @pytest.mark.asyncio
    async def test_list_returns_only_own_tenant(self, db, seed):
        bids = _b_ids(seed)
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.get("/api/relationships")
            assert r.status_code == 200
            names = [x["name"] for x in r.json()["items"]]
            assert "A Relationship" in names
            assert "B Relationship" not in names
            _assert_no_leak(r.json(), bids, "list_rels")

    @pytest.mark.asyncio
    async def test_get_cross_tenant_relationship_404(self, db, seed):
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.get(f"/api/relationships/{seed['rb'].id}")
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_team_cross_tenant_404(self, db, seed):
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.get(f"/api/relationships/{seed['ra'].id}/team")
            assert r.status_code == 200
            r = await c.get(f"/api/relationships/{seed['rb'].id}/team")
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_health_cross_tenant_404(self, db, seed):
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.get(f"/api/relationships/{seed['ra'].id}/health")
            assert r.status_code == 200
            r = await c.get(f"/api/relationships/{seed['rb'].id}/health")
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_history_cross_tenant_404(self, db, seed):
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.get(f"/api/relationships/{seed['ra'].id}/history")
            assert r.status_code == 200
            r = await c.get(f"/api/relationships/{seed['rb'].id}/history")
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_performance_trend_cross_tenant_404(self, db, seed):
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.get(f"/api/relationships/{seed['ra'].id}/performance-trend")
            assert r.status_code == 200
            r = await c.get(f"/api/relationships/{seed['rb'].id}/performance-trend")
            assert r.status_code == 404


# ── Vendor Tests ────────────────────────────────────────────────────

class TestVendorIsolation:

    @pytest.mark.asyncio
    async def test_list_vendors_isolation(self, db, seed):
        bids = _b_ids(seed)
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.get("/api/vendors")
            assert r.status_code == 200
            names = [v["vendor_name"] for v in r.json()["vendors"]]
            assert "Vendor Beta" not in names
            _assert_no_leak(r.json(), bids, "list_vendors")

    @pytest.mark.asyncio
    async def test_vendor_performance_cross_tenant_404(self, db, seed):
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.get("/api/vendors/Vendor Alpha/performance")
            assert r.status_code == 200
            r = await c.get("/api/vendors/Vendor Beta/performance")
            assert r.status_code == 404


# ── Survey Tests ────────────────────────────────────────────────────

class TestSurveyIsolation:

    @pytest.mark.asyncio
    async def test_list_instances_isolation(self, db, seed):
        bids = _b_ids(seed)
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.get("/api/surveys/instances")
            assert r.status_code == 200
            ids = [i["id"] for i in r.json()["items"]]
            assert str(seed["sia"].id) in ids
            assert str(seed["sib"].id) not in ids
            _assert_no_leak(r.json(), bids, "list_instances")

    @pytest.mark.asyncio
    async def test_get_instance_cross_tenant_404(self, db, seed):
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.get(f"/api/surveys/instances/{seed['sia'].id}")
            assert r.status_code == 200
            r = await c.get(f"/api/surveys/instances/{seed['sib'].id}")
            assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_instance_responses_cross_tenant_404(self, db, seed):
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.get(f"/api/surveys/instances/{seed['sia'].id}/responses")
            assert r.status_code == 200
            r = await c.get(f"/api/surveys/instances/{seed['sib'].id}/responses")
            assert r.status_code == 404


# ── Compliance Tests (regression guard — already secure) ────────────

class TestComplianceIsolation:

    @pytest.mark.asyncio
    async def test_dashboard_isolation(self, db, seed):
        bids = _b_ids(seed)
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.get("/api/compliance/dashboard")
            assert r.status_code == 200
            _assert_no_leak(r.json(), bids, "compliance_dashboard")
