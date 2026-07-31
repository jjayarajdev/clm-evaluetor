"""Tests for /api/usage — role-based field visibility and tenant scoping.

Rule under test: tenant admins (and super admin) see pages + tokens + cost;
every other role sees pages only. Enforced by the API, not the UI.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base, get_db
from app.core.deps import get_current_user, get_current_tenant_id
from app.models.tenant import Tenant
from app.models.usage_event import UsageEvent, UsageMetric
from app.models.user import User, Role

TENANT_A_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest_asyncio.fixture(scope="function")
async def db():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
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


def _user(role: Role, tenant_id) -> User:
    return User(
        id=uuid.uuid4(), tenant_id=tenant_id, username=f"u-{role.value}",
        email=f"{role.value}@test.com", full_name=role.value,
        password_hash="x", role=role, is_active=True,
    )


@pytest_asyncio.fixture
async def seed(db):
    now = datetime.now(timezone.utc)
    db.add_all([
        Tenant(id=TENANT_A_ID, name="Tenant A", slug="tenant-a", is_active=True),
        Tenant(id=TENANT_B_ID, name="Tenant B", slug="tenant-b", is_active=True),
    ])
    events = [
        # Tenant A, current month
        (TENANT_A_ID, UsageMetric.PAGES_PROCESSED, 40, None),
        (TENANT_A_ID, UsageMetric.DOCUMENTS_INGESTED, 4, None),
        (TENANT_A_ID, UsageMetric.AI_ACTIONS, 10, "gpt-4o"),
        (TENANT_A_ID, UsageMetric.TOKENS_PROMPT, 1_000_000, "gpt-4o"),      # $2.50
        (TENANT_A_ID, UsageMetric.TOKENS_COMPLETION, 100_000, "gpt-4o"),    # $1.00
        (TENANT_A_ID, UsageMetric.TOKENS_PROMPT, 2_000_000, "gpt-4o-mini"), # $0.30
        # Tenant B — must never leak into A's numbers
        (TENANT_B_ID, UsageMetric.PAGES_PROCESSED, 999, None),
        (TENANT_B_ID, UsageMetric.TOKENS_PROMPT, 5_000_000, "gpt-4o"),
    ]
    db.add_all([
        UsageEvent(tenant_id=t, metric=m, quantity=q, model=model, occurred_at=now)
        for t, m, q, model in events
    ])
    await db.commit()


def _client_as(db, user, tenant_id):
    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


class TestVisibility:
    @pytest.mark.asyncio
    async def test_tenant_admin_sees_pages_tokens_and_cost(self, db, seed):
        async with _client_as(db, _user(Role.ADMIN, TENANT_A_ID), TENANT_A_ID) as c:
            r = await c.get("/api/usage/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["can_view_ai_usage"] is True
        totals = data["totals"]
        assert totals["pages_processed"] == 40
        assert totals["documents_ingested"] == 4
        assert totals["tokens_prompt"] == 3_000_000
        assert totals["tokens_completion"] == 100_000
        assert totals["ai_actions"] == 10
        # 2.50 (4o in) + 1.00 (4o out) + 0.30 (4o-mini in)
        assert totals["estimated_cost_usd"] == pytest.approx(3.80)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", [Role.LEGAL, Role.PROCUREMENT, Role.BU_HEAD, Role.VIEWER])
    async def test_non_admin_sees_pages_only(self, db, seed, role):
        async with _client_as(db, _user(role, TENANT_A_ID), TENANT_A_ID) as c:
            r = await c.get("/api/usage/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["can_view_ai_usage"] is False
        totals = data["totals"]
        assert totals["pages_processed"] == 40
        assert totals["documents_ingested"] == 4
        for hidden in ("tokens_prompt", "tokens_completion", "tokens_embedding",
                       "ai_actions", "estimated_cost_usd"):
            assert hidden not in totals
        for month in data["months"]:
            assert "estimated_cost_usd" not in month

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, db, seed):
        async with _client_as(db, _user(Role.ADMIN, TENANT_A_ID), TENANT_A_ID) as c:
            r = await c.get("/api/usage/summary")
        totals = r.json()["totals"]
        assert totals["pages_processed"] == 40  # not 40 + 999
        assert totals["tokens_prompt"] == 3_000_000  # not + 5M

    @pytest.mark.asyncio
    async def test_super_admin_platform_wide_and_scoped(self, db, seed):
        su = _user(Role.SUPER_ADMIN, None)
        async with _client_as(db, su, None) as c:
            r_all = await c.get("/api/usage/summary")
            r_a = await c.get(f"/api/usage/summary?tenant_id={TENANT_A_ID}")
        assert r_all.json()["totals"]["pages_processed"] == 40 + 999
        assert r_a.json()["totals"]["pages_processed"] == 40

    @pytest.mark.asyncio
    async def test_non_admin_cannot_scope_other_tenant(self, db, seed):
        """The tenant_id query param must be ignored for non-super-admins."""
        async with _client_as(db, _user(Role.LEGAL, TENANT_A_ID), TENANT_A_ID) as c:
            r = await c.get(f"/api/usage/summary?tenant_id={TENANT_B_ID}")
        assert r.json()["totals"]["pages_processed"] == 40


class TestByTenant:
    @pytest.mark.asyncio
    async def test_super_admin_fleet_view(self, db, seed):
        async with _client_as(db, _user(Role.SUPER_ADMIN, None), None) as c:
            r = await c.get("/api/usage/by-tenant")
        assert r.status_code == 200
        items = {i["tenant_name"]: i for i in r.json()["items"]}
        assert items["Tenant A"]["estimated_cost_usd"] == pytest.approx(3.80)
        assert items["Tenant B"]["pages_processed"] == 999

    @pytest.mark.asyncio
    async def test_tenant_admin_forbidden(self, db, seed):
        async with _client_as(db, _user(Role.ADMIN, TENANT_A_ID), TENANT_A_ID) as c:
            r = await c.get("/api/usage/by-tenant")
        assert r.status_code in (401, 403)
