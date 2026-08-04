"""Configurable vendor scoring: config resolution, weights, risk bands, at-risk counting.

Covers the "vendor" section of DEFAULT_SCORING_CONFIG and its consumers:
vendor_service (composite score + risk level), the vendors list endpoint
(resolved "scoring" block), and the post-signing vendor widget (at-risk count).
"""

import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.deps import get_current_tenant_id, get_current_user
from app.database import Base, get_db
from app.main import app
from app.models.business_unit import BusinessUnit
from app.models.tenant import Tenant
from app.models.user import Role, User
from app.services.scoring_config import DEFAULT_SCORING_CONFIG, resolve_scoring_config
from app.services.vendor_service import (
    calculate_composite_score,
    determine_risk_level,
    resolve_vendor_scoring,
)

TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest_asyncio.fixture(scope="function")
async def db():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    # SQLite can't create JSONB columns or duplicate index names.
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
    seen_idx = set()
    for table in Base.metadata.tables.values():
        deduped = [i for i in table.indexes if i.name not in seen_idx and not seen_idx.add(i.name)]
        table.indexes.clear()
        table.indexes.update(deduped)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(eng, expire_on_commit=False)
    async with maker() as session:
        yield session
    await eng.dispose()


def _client(db) -> AsyncClient:
    user = User(
        id=uuid.uuid4(), tenant_id=TENANT_ID, username="vendor-admin",
        email="vendor-admin@t.com", full_name="Vendor Admin", password_hash="x",
        role=Role.ADMIN, is_active=True, preferred_language="en",
    )

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_tenant_id] = lambda: TENANT_ID
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _vendor_cfg(**overrides) -> dict:
    """Resolved vendor block with the given tenant-level overrides applied."""
    return resolve_scoring_config({"scoring": {"vendor": overrides}})["vendor"]


# ── Config resolution ───────────────────────────────────────────────

class TestVendorConfigResolution:

    def test_defaults(self):
        cfg = resolve_scoring_config()["vendor"]
        assert cfg == DEFAULT_SCORING_CONFIG["vendor"]
        assert cfg["obligation_weight"] == 0.40
        assert cfg["sla_weight"] == 0.30
        assert cfg["responsiveness_weight"] == 0.20
        assert cfg["issue_rate_weight"] == 0.10
        assert cfg["low_threshold"] == 80
        assert cfg["medium_threshold"] == 60
        assert cfg["high_threshold"] == 40
        assert cfg["at_risk_threshold"] == 60

    def test_tenant_then_bu_override(self):
        tenant = {"scoring": {"vendor": {"at_risk_threshold": 70, "obligation_weight": 0.5}}}
        bu = {"scoring": {"vendor": {"at_risk_threshold": 50}}}
        cfg = resolve_scoring_config(tenant, bu)["vendor"]
        assert cfg["at_risk_threshold"] == 50      # BU wins over tenant
        assert cfg["obligation_weight"] == 0.5     # tenant survives where BU is silent
        assert cfg["sla_weight"] == 0.30           # default fills the rest

    def test_unknown_keys_and_bad_values_ignored(self):
        cfg = _vendor_cfg(bogus_key=99, low_threshold="eighty", medium_threshold=65)
        assert "bogus_key" not in cfg
        assert cfg["low_threshold"] == 80          # non-numeric override rejected
        assert cfg["medium_threshold"] == 65

    def test_vendor_override_does_not_leak_into_other_sections(self):
        full = resolve_scoring_config({"scoring": {"vendor": {"obligation_weight": 0.9}}})
        assert full["vendor"]["obligation_weight"] == 0.9
        assert full["compliance"]["obligation_weight"] == 0.6

    @pytest.mark.asyncio
    async def test_resolve_from_db_tenant_and_bu(self, db):
        tenant = Tenant(
            id=uuid.uuid4(), name="Cfg Tenant", slug="cfg-tenant", is_active=True,
            config_overrides={"scoring": {"vendor": {"at_risk_threshold": 75, "sla_weight": 0.5}}},
        )
        bu = BusinessUnit(
            id=uuid.uuid4(), tenant_id=tenant.id, name="Cfg BU", code="CFG",
            config_overrides={"scoring": {"vendor": {"at_risk_threshold": 55}}},
        )
        db.add_all([tenant, bu])
        await db.flush()

        cfg = await resolve_vendor_scoring(db, tenant.id, bu.id)
        assert cfg["at_risk_threshold"] == 55       # BU beats tenant
        assert cfg["sla_weight"] == 0.5             # tenant beats default
        assert cfg["obligation_weight"] == 0.40     # default retained

        # No tenant/BU rows -> pure defaults.
        cfg = await resolve_vendor_scoring(db, uuid.uuid4(), None)
        assert cfg == DEFAULT_SCORING_CONFIG["vendor"]


# ── Composite score ─────────────────────────────────────────────────

class TestCompositeScore:

    def test_default_weights_unchanged(self):
        b = calculate_composite_score(100.0, 50.0)
        # (100*0.4 + 50*0.3) / 0.7
        assert b.weighted_total == 78.57
        assert b.obligation_compliance_weight == 0.40
        assert b.sla_compliance_weight == 0.30

    def test_overridden_weights(self):
        cfg = _vendor_cfg(obligation_weight=0.9, sla_weight=0.1)
        b = calculate_composite_score(100.0, 50.0, cfg)
        assert b.weighted_total == 95.0
        # Breakdown reports the weights actually used.
        assert b.obligation_compliance_weight == 0.9
        assert b.sla_compliance_weight == 0.1
        assert b.responsiveness_weight == 0.20
        assert b.issue_rate_weight == 0.10

    def test_renormalizes_when_signal_missing(self):
        cfg = _vendor_cfg(obligation_weight=0.7)
        b = calculate_composite_score(80.0, None, cfg)
        assert b.weighted_total == 80.0             # single signal, full weight

    def test_unrated_when_no_signal(self):
        assert calculate_composite_score(None, None).weighted_total is None

    def test_zero_weights_give_unrated_not_crash(self):
        cfg = _vendor_cfg(obligation_weight=0, sla_weight=0)
        assert calculate_composite_score(90.0, 90.0, cfg).weighted_total is None


# ── Risk banding ────────────────────────────────────────────────────

class TestRiskLevel:

    def test_default_bands(self):
        assert determine_risk_level(None) == "unrated"
        assert determine_risk_level(80) == "low"
        assert determine_risk_level(79.9) == "medium"
        assert determine_risk_level(60) == "medium"
        assert determine_risk_level(59.9) == "high"
        assert determine_risk_level(40) == "high"
        assert determine_risk_level(39.9) == "critical"

    def test_overridden_bands(self):
        cfg = _vendor_cfg(low_threshold=90, medium_threshold=70, high_threshold=50)
        assert determine_risk_level(85, cfg) == "medium"
        assert determine_risk_level(90, cfg) == "low"
        assert determine_risk_level(69, cfg) == "high"
        assert determine_risk_level(49, cfg) == "critical"
        assert determine_risk_level(None, cfg) == "unrated"


# ── At-risk counting (post-signing vendor widget) ───────────────────

def _widget_inputs():
    """Two rated vendors: scores 55 and 70 (SLA compliance only)."""
    c1 = SimpleNamespace(id=uuid.uuid4(), counterparty="Vendor Alpha Inc", organization_id=None)
    c2 = SimpleNamespace(id=uuid.uuid4(), counterparty="Vendor Beta LLC", organization_id=None)
    slas = [
        SimpleNamespace(contract_id=c1.id, current_compliance_rate=55),
        SimpleNamespace(contract_id=c2.id, current_compliance_rate=70),
    ]
    return [c1, c2], [], slas


class TestVendorWidgetAtRisk:

    def _service(self, overrides=None):
        from app.services.postsigning_service import PostSigningService
        svc = PostSigningService(db=None)
        if overrides:
            svc.scoring = resolve_scoring_config({"scoring": {"vendor": overrides}})
        return svc

    def test_default_threshold(self):
        contracts, obls, slas = _widget_inputs()
        widget = self._service()._build_vendor_widget(contracts, obls, slas)
        assert widget.total_vendors == 2
        assert widget.at_risk_vendors == 1          # only the 55 is below 60

    def test_overridden_threshold(self):
        contracts, obls, slas = _widget_inputs()
        widget = self._service({"at_risk_threshold": 75})._build_vendor_widget(contracts, obls, slas)
        assert widget.at_risk_vendors == 2          # both below 75

        widget = self._service({"at_risk_threshold": 50})._build_vendor_widget(contracts, obls, slas)
        assert widget.at_risk_vendors == 0


# ── Vendors list endpoint exposes resolved scoring ──────────────────

class TestVendorsListScoringField:

    @pytest.mark.asyncio
    async def test_scoring_block_defaults(self, db):
        async with _client(db) as c:
            r = await c.get("/api/vendors")
        assert r.status_code == 200
        assert r.json()["scoring"] == {
            "obligation_weight": 0.40,
            "sla_weight": 0.30,
            "responsiveness_weight": 0.20,
            "issue_rate_weight": 0.10,
            "low_threshold": 80,
            "medium_threshold": 60,
            "high_threshold": 40,
            "at_risk_threshold": 60,
        }

    @pytest.mark.asyncio
    async def test_scoring_block_reflects_tenant_override(self, db):
        db.add(Tenant(
            id=TENANT_ID, name="T", slug="t", is_active=True,
            config_overrides={"scoring": {"vendor": {"at_risk_threshold": 75, "low_threshold": 90}}},
        ))
        await db.flush()

        async with _client(db) as c:
            r = await c.get("/api/vendors")
        assert r.status_code == 200
        s = r.json()["scoring"]
        assert s["at_risk_threshold"] == 75
        assert s["low_threshold"] == 90
        assert s["medium_threshold"] == 60          # untouched keys stay default
