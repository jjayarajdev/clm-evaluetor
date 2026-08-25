"""Tests for usage threshold alerts + limits endpoints (metering phase 3).

80%/100% of a configured monthly limit notifies tenant admins once per
(tenant, metric, threshold, month); escalation 80→100 re-alerts; tenants
without limits are skipped. The super-admin endpoints manage limits in
tenant.config_overrides and surface utilization in /by-tenant.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.deps import get_current_user, get_current_tenant_id
from app.database import Base, get_db
from app.main import app
from app.models.notification import NotificationLog
from app.models.tenant import Tenant
from app.models.usage_event import UsageEvent, UsageMetric
from app.models.user import Role, User
from app.services.usage_alerts import check_usage_thresholds

TENANT_ID = uuid.uuid4()
ADMIN_ID = uuid.uuid4()
SUPER_ID = uuid.uuid4()


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
    seen_idx = set()
    for table in Base.metadata.tables.values():
        deduped = [i for i in table.indexes if i.name not in seen_idx and not seen_idx.add(i.name)]
        table.indexes.clear()
        table.indexes.update(deduped)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


async def _seed(db, limits: dict | None):
    db.add(Tenant(
        id=TENANT_ID, name="T", slug="t", is_active=True,
        config_overrides={"usage_limits": limits} if limits else {},
    ))
    db.add(User(
        id=ADMIN_ID, tenant_id=TENANT_ID, username="a", email="a@t.com",
        full_name="A", password_hash="x", role=Role.ADMIN, is_active=True,
    ))
    await db.commit()


def _pages(quantity: int) -> UsageEvent:
    return UsageEvent(
        id=uuid.uuid4(), tenant_id=TENANT_ID,
        metric=UsageMetric.PAGES_PROCESSED, quantity=quantity,
        occurred_at=datetime.now(timezone.utc),
    )


async def _alert_logs(db) -> list[NotificationLog]:
    rows = (await db.execute(select(NotificationLog))).scalars().all()
    return [r for r in rows if (r.variables_used or {}).get("kind") == "usage_threshold"]


@pytest.mark.asyncio
class TestThresholdAlerts:
    async def test_80_percent_alerts_once(self, db):
        await _seed(db, {"monthly_pages": 100})
        db.add(_pages(85))
        await db.commit()

        result = await check_usage_thresholds(db)
        assert result["alerts_sent"] == 1
        logs = await _alert_logs(db)
        assert len(logs) == 1
        assert logs[0].recipient_email == "a@t.com"
        assert logs[0].variables_used["threshold"] == 80

        # Second run: deduped.
        result = await check_usage_thresholds(db)
        assert result["alerts_sent"] == 0
        assert len(await _alert_logs(db)) == 1

    async def test_escalates_to_100_percent(self, db):
        await _seed(db, {"monthly_pages": 100})
        db.add(_pages(85))
        await db.commit()
        await check_usage_thresholds(db)

        db.add(_pages(20))  # now 105 -> 100% threshold
        await db.commit()
        result = await check_usage_thresholds(db)
        assert result["alerts_sent"] == 1
        thresholds = sorted(l.variables_used["threshold"] for l in await _alert_logs(db))
        assert thresholds == [80, 100]

        # 100% recorded -> nothing further this month.
        assert (await check_usage_thresholds(db))["alerts_sent"] == 0

    async def test_under_threshold_no_alert(self, db):
        await _seed(db, {"monthly_pages": 100})
        db.add(_pages(50))
        await db.commit()
        assert (await check_usage_thresholds(db))["alerts_sent"] == 0
        assert await _alert_logs(db) == []

    async def test_tenant_without_limits_skipped(self, db):
        await _seed(db, None)
        db.add(_pages(10_000))
        await db.commit()
        result = await check_usage_thresholds(db)
        assert result["tenants_with_limits"] == 0
        assert result["alerts_sent"] == 0


def _super_client(db) -> AsyncClient:
    async def override_db():
        yield db

    user = User(
        id=SUPER_ID, tenant_id=None, username="root", email="root@x.com",
        full_name="Root", password_hash="x", role=Role.SUPER_ADMIN, is_active=True,
    )
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_tenant_id] = lambda: None
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
class TestLimitsEndpoints:
    async def test_set_get_and_fleet_utilization(self, db):
        await _seed(db, None)
        db.add(_pages(50))
        await db.commit()

        async with _super_client(db) as client:
            resp = await client.put(
                f"/api/usage/limits/{TENANT_ID}",
                json={"monthly_pages": 200},
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["usage_limits"] == {"monthly_pages": 200}

            resp = await client.get(f"/api/usage/limits/{TENANT_ID}")
            assert resp.json()["usage_limits"] == {"monthly_pages": 200}

            fleet = (await client.get("/api/usage/by-tenant")).json()
        row = next(i for i in fleet["items"] if i["tenant_id"] == str(TENANT_ID))
        assert row["limits"]["monthly_pages"]["limit"] == 200
        assert row["limits"]["monthly_pages"]["current"] == 50
        assert row["limits"]["monthly_pages"]["pct"] == 25.0

    async def test_null_clears_limits(self, db):
        await _seed(db, {"monthly_pages": 100})
        async with _super_client(db) as client:
            resp = await client.put(
                f"/api/usage/limits/{TENANT_ID}",
                json={"monthly_pages": None},
            )
            assert resp.status_code == 200
            assert resp.json()["usage_limits"] == {}

    async def test_zero_usage_tenant_listed(self, db):
        await _seed(db, None)
        async with _super_client(db) as client:
            fleet = (await client.get("/api/usage/by-tenant")).json()
        assert any(i["tenant_id"] == str(TENANT_ID) for i in fleet["items"])
