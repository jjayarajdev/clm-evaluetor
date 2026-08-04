"""Cross-tenant isolation (IDOR) regression tests.

Guards the by-id / aggregate endpoints that previously loaded rows by id
without scoping to the caller's tenant. A Tenant-A user must get a 404 (or an
empty/own-tenant-only aggregate) for Tenant-B resources; super admins keep
their cross-tenant visibility by design.

Also covers the survey → PerceptionScore write, which previously constructed
the model with wrong kwargs (respondent_org_id / score_value / is_external)
that do not exist on the model.
"""

import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timedelta, date

from httpx import AsyncClient, ASGITransport
from sqlalchemy import event, JSON, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.database import Base, get_db
from app.core.deps import get_current_user, get_current_tenant_id
from app.models.user import User, Role
from app.models.tenant import Tenant
from app.models.contract import Contract, ContractStatus, ContractType, RiskLevel
from app.models.organization import Organization
from app.models.relationship import BusinessRelationship
from app.models.survey import SurveyTemplate, SurveyInstance, SurveyResponse
from app.models.clause import Clause, ClauseType, RiskLevel as ClauseRiskLevel
from app.models.exhibit import ContractExhibit, ExhibitType
from app.models.sla_alert import SLAAlert, AlertCategory, AlertPriority, AlertStatus
from app.models.suggested_link import SuggestedContractLink
from app.models.kpi import KPI, PerceptionScore


TENANT_A_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ── Database fixtures (mirror test_tenant_isolation.py) ─────────────

@pytest_asyncio.fixture(scope="function")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)

    @event.listens_for(eng.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()

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


@pytest_asyncio.fixture(scope="function")
async def seed(db: AsyncSession):
    """Two tenants, each with a contract carrying a clause + exhibit + alert."""
    ta = Tenant(id=TENANT_A_ID, name="Tenant A", slug="tenant-a", is_active=True)
    tb = Tenant(id=TENANT_B_ID, name="Tenant B", slug="tenant-b", is_active=True)
    db.add_all([ta, tb])
    await db.flush()

    ua = User(id=uuid.uuid4(), tenant_id=TENANT_A_ID, username="user_a",
              email="a@a.com", full_name="User A", password_hash="x",
              role=Role.ADMIN, is_active=True)
    ub = User(id=uuid.uuid4(), tenant_id=TENANT_B_ID, username="user_b",
              email="b@b.com", full_name="User B", password_hash="x",
              role=Role.ADMIN, is_active=True)
    sa = User(id=uuid.uuid4(), tenant_id=None, username="super",
              email="s@s.com", full_name="Super", password_hash="x",
              role=Role.SUPER_ADMIN, is_active=True)
    db.add_all([ua, ub, sa])
    await db.flush()

    oa1 = Organization(id=uuid.uuid4(), tenant_id=TENANT_A_ID, name="Org A1", code="OA1", org_type="customer", is_active=True)
    oa2 = Organization(id=uuid.uuid4(), tenant_id=TENANT_A_ID, name="Org A2", code="OA2", org_type="vendor", is_active=True)
    ob1 = Organization(id=uuid.uuid4(), tenant_id=TENANT_B_ID, name="Org B1", code="OB1", org_type="customer", is_active=True)
    ob2 = Organization(id=uuid.uuid4(), tenant_id=TENANT_B_ID, name="Org B2", code="OB2", org_type="vendor", is_active=True)
    db.add_all([oa1, oa2, ob1, ob2])
    await db.flush()

    ca = Contract(id=uuid.uuid4(), tenant_id=TENANT_A_ID,
                  filename="a.pdf", file_path="/data/a/a.pdf", file_size=100,
                  status=ContractStatus.COMPLETED, counterparty="Vendor Alpha",
                  contract_type=ContractType.MSA, effective_date=date.today(),
                  expiration_date=date.today() + timedelta(days=365),
                  contract_value=50000, currency="USD", risk_level=RiskLevel.LOW,
                  uploaded_by=ua.id)
    cb = Contract(id=uuid.uuid4(), tenant_id=TENANT_B_ID,
                  filename="b.pdf", file_path="/data/b/b.pdf", file_size=100,
                  status=ContractStatus.COMPLETED, counterparty="Vendor Beta",
                  contract_type=ContractType.MSA, effective_date=date.today(),
                  expiration_date=date.today() + timedelta(days=365),
                  contract_value=80000, currency="USD", risk_level=RiskLevel.HIGH,
                  uploaded_by=ub.id)
    # Second tenant-B contract so a suggested link has two B endpoints.
    cb2 = Contract(id=uuid.uuid4(), tenant_id=TENANT_B_ID,
                   filename="b2.pdf", file_path="/data/b2/b2.pdf", file_size=100,
                   status=ContractStatus.COMPLETED, counterparty="Vendor Beta 2",
                   contract_type=ContractType.SOW, effective_date=date.today(),
                   expiration_date=date.today() + timedelta(days=365),
                   contract_value=20000, currency="USD", risk_level=RiskLevel.LOW,
                   uploaded_by=ub.id)
    db.add_all([ca, cb, cb2])
    await db.flush()

    clause_a = Clause(id=uuid.uuid4(), contract_id=ca.id, clause_type=ClauseType.TERMINATION,
                      text="A termination clause.", risk_level=ClauseRiskLevel.LOW)
    clause_b = Clause(id=uuid.uuid4(), contract_id=cb.id, clause_type=ClauseType.TERMINATION,
                      text="B termination clause.", risk_level=ClauseRiskLevel.HIGH)
    db.add_all([clause_a, clause_b])

    exhibit_b = ContractExhibit(id=uuid.uuid4(), contract_id=cb.id,
                                exhibit_identifier="A", exhibit_type=ExhibitType.PRICING,
                                title="B Pricing Exhibit")
    db.add(exhibit_b)

    alert_a = SLAAlert(id=uuid.uuid4(), contract_id=ca.id, category=AlertCategory.SLA_BREACH,
                       priority=AlertPriority.HIGH, status=AlertStatus.ACTIVE,
                       title="A alert", description="a")
    alert_b = SLAAlert(id=uuid.uuid4(), contract_id=cb.id, category=AlertCategory.SLA_BREACH,
                       priority=AlertPriority.HIGH, status=AlertStatus.ACTIVE,
                       title="B alert", description="b")
    db.add_all([alert_a, alert_b])

    # Suggested link entirely within Tenant B.
    suggestion_b = SuggestedContractLink(
        id=uuid.uuid4(), tenant_id=TENANT_B_ID,
        source_contract_id=cb.id, target_contract_id=cb2.id,
        suggested_link_type="sow", suggested_direction="source_is_parent",
        confidence_score=0.9, status="pending",
    )
    db.add(suggestion_b)

    # Relationships + a tenant-B survey template (external template).
    ra = BusinessRelationship(id=uuid.uuid4(), tenant_id=TENANT_A_ID,
                              org_a_id=oa1.id, org_b_id=oa2.id,
                              relationship_type="customer", status="active", name="A Rel")
    db.add(ra)
    tmpl_b = SurveyTemplate(id=uuid.uuid4(), tenant_id=TENANT_B_ID, name="B Template",
                            frequency="quarterly", is_active=True, version=1)
    db.add(tmpl_b)

    await db.commit()

    return {
        "ua": ua, "ub": ub, "sa": sa,
        "ca": ca, "cb": cb, "cb2": cb2,
        "clause_a": clause_a, "clause_b": clause_b,
        "exhibit_b": exhibit_b,
        "alert_a": alert_a, "alert_b": alert_b,
        "suggestion_b": suggestion_b,
        "ra": ra, "tmpl_b": tmpl_b,
        "oa1": oa1,
    }


def _client_as(db_session, user, tenant_id):
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


# ── Dashboard by-id endpoints ───────────────────────────────────────

class TestDashboardIsolation:

    @pytest.mark.asyncio
    async def test_cockpit_cross_tenant_404(self, db, seed):
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            assert (await c.get(f"/api/dashboard/cockpit/{seed['ca'].id}")).status_code == 200
            assert (await c.get(f"/api/dashboard/cockpit/{seed['cb'].id}")).status_code == 404

    @pytest.mark.asyncio
    async def test_super_admin_sees_other_tenant_cockpit(self, db, seed):
        async with _client_as(db, seed["sa"], None) as c:
            assert (await c.get(f"/api/dashboard/cockpit/{seed['cb'].id}")).status_code == 200

    @pytest.mark.asyncio
    async def test_clause_detail_cross_tenant_404(self, db, seed):
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            assert (await c.get(f"/api/dashboard/clauses/{seed['clause_a'].id}")).status_code == 200
            assert (await c.get(f"/api/dashboard/clauses/{seed['clause_b'].id}")).status_code == 404

    @pytest.mark.asyncio
    async def test_contract_exhibits_cross_tenant_404(self, db, seed):
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            assert (await c.get(f"/api/dashboard/exhibits/{seed['cb'].id}")).status_code == 404

    @pytest.mark.asyncio
    async def test_financials_cross_tenant_404(self, db, seed):
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            assert (await c.get(f"/api/dashboard/financials/{seed['cb'].id}")).status_code == 404

    @pytest.mark.asyncio
    async def test_exhibits_summary_is_tenant_scoped(self, db, seed):
        # Tenant A has no exhibits; the only exhibit belongs to Tenant B.
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.get("/api/dashboard/exhibits-summary")
            assert r.status_code == 200
            assert r.json()["total_exhibits"] == 0
        # Tenant B sees its exhibit.
        async with _client_as(db, seed["ub"], TENANT_B_ID) as c:
            r = await c.get("/api/dashboard/exhibits-summary")
            assert r.status_code == 200
            assert r.json()["total_exhibits"] == 1
        # Super admin sees all.
        async with _client_as(db, seed["sa"], None) as c:
            r = await c.get("/api/dashboard/exhibits-summary")
            assert r.status_code == 200
            assert r.json()["total_exhibits"] == 1


# ── Contracts router ────────────────────────────────────────────────

class TestContractsIsolation:

    @pytest.mark.asyncio
    async def test_get_contract_clauses_cross_tenant_404(self, db, seed):
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            assert (await c.get(f"/api/contracts/{seed['ca'].id}/clauses")).status_code == 200
            assert (await c.get(f"/api/contracts/{seed['cb'].id}/clauses")).status_code == 404

    @pytest.mark.asyncio
    async def test_add_file_cross_tenant_404(self, db, seed):
        files = {"file": ("x.txt", b"hello", "text/plain")}
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.post(f"/api/contracts/{seed['cb'].id}/files", files=files)
            assert r.status_code == 404


# ── Alerts router ───────────────────────────────────────────────────

class TestAlertsIsolation:

    @pytest.mark.asyncio
    async def test_bulk_action_cannot_touch_other_tenant(self, db, seed):
        payload = {"alert_ids": [str(seed["alert_b"].id)], "action": "dismiss"}
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.post("/api/alerts/bulk-action", json=payload)
            assert r.status_code == 200
            assert r.json()["processed_count"] == 0
            assert r.json()["failed_count"] == 1

        # The tenant-B alert must remain untouched (still ACTIVE).
        alert_b = (await db.execute(
            select(SLAAlert).where(SLAAlert.id == seed["alert_b"].id)
        )).scalar_one()
        assert alert_b.status == AlertStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_bulk_action_resolve_other_tenant_denied(self, db, seed):
        payload = {"alert_ids": [str(seed["alert_b"].id)], "action": "resolve"}
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.post("/api/alerts/bulk-action", json=payload)
            assert r.status_code == 200
            assert r.json()["failed_count"] == 1


# ── Suggested links router ──────────────────────────────────────────

class TestSuggestedLinkIsolation:

    @pytest.mark.asyncio
    async def test_review_other_tenant_suggestion_404(self, db, seed):
        # Tenant A tries to approve Tenant B's suggestion (read is tenant-scoped).
        body = {"action": "approve"}
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.post(
                f"/api/contracts/{seed['cb'].id}/suggested-links/{seed['suggestion_b'].id}/review",
                json=body,
            )
            assert r.status_code == 404


# ── Surveys router ──────────────────────────────────────────────────

class TestSurveyInstanceCreation:

    @pytest.mark.asyncio
    async def test_create_instance_rejects_cross_tenant_template(self, db, seed):
        # Tenant A supplies its own relationship but a Tenant-B template id.
        body = {
            "template_id": str(seed["tmpl_b"].id),
            "relationship_id": str(seed["ra"].id),
            "period": "2026-Q1",
        }
        async with _client_as(db, seed["ua"], TENANT_A_ID) as c:
            r = await c.post("/api/surveys/instances", json=body)
            assert r.status_code == 400
            assert "template" in r.json()["detail"].lower()


# ── PerceptionScore kwargs (data-bug fix) ───────────────────────────

class TestPerceptionScoreKwargs:

    @pytest.mark.asyncio
    async def test_perception_score_constructs_with_model_kwargs(self, db, seed):
        """The survey → perception path must use the real model columns
        (scorer_org_id / score / is_internal), not the old bogus kwargs."""
        rel = seed["ra"]
        kpi = KPI(id=uuid.uuid4(), relationship_id=rel.id, name="KPI A",
                  category="service_delivery", is_active=True)
        db.add(kpi)
        await db.flush()

        score = PerceptionScore(
            kpi_id=kpi.id,
            scorer_org_id=seed["oa1"].id,
            score=8.0,
            period="2026-Q1",
            is_internal=False,
            approval_status="pending_approval",
        )
        db.add(score)
        await db.commit()

        loaded = (await db.execute(
            select(PerceptionScore).where(PerceptionScore.id == score.id)
        )).scalar_one()
        assert float(loaded.score) == 8.0
        assert loaded.is_internal is False
        assert loaded.scorer_org_id == seed["oa1"].id
        # Prove the old kwargs are not attributes on the model.
        assert not hasattr(loaded, "score_value")
        assert not hasattr(loaded, "is_external")
