"""Tests for the in-memory rate limiter and its endpoint wiring.

Login is limited per client IP, change-password and uploads per user.
Limited requests get 429 + Retry-After; requests under the limit are
untouched. The conftest autouse fixture resets the limiter between tests.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.core.rate_limit as rate_limit_module
from app.config import settings
from app.core.deps import get_current_user
from app.core.rate_limit import SlidingWindowLimiter, limiter
from app.database import Base, get_db
from app.main import app
from app.models.user import Role, User

TENANT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


class TestSlidingWindowLimiter:
    def test_allows_under_limit(self):
        lim = SlidingWindowLimiter()
        for _ in range(5):
            assert lim.check("k", 5, 60) is None

    def test_blocks_at_limit_with_retry_after(self):
        lim = SlidingWindowLimiter()
        for _ in range(3):
            assert lim.check("k", 3, 60) is None
        retry = lim.check("k", 3, 60)
        assert retry is not None and 0 < retry <= 60

    def test_blocked_hit_not_recorded(self):
        # A rejected request must not extend the lockout.
        lim = SlidingWindowLimiter()
        for _ in range(3):
            lim.check("k", 3, 60)
        first_retry = lim.check("k", 3, 60)
        second_retry = lim.check("k", 3, 60)
        assert second_retry <= first_retry

    def test_keys_are_independent(self):
        lim = SlidingWindowLimiter()
        for _ in range(3):
            assert lim.check("a", 3, 60) is None
        assert lim.check("a", 3, 60) is not None
        assert lim.check("b", 3, 60) is None

    def test_window_slides(self, monkeypatch):
        lim = SlidingWindowLimiter()
        now = [1000.0]
        monkeypatch.setattr(
            rate_limit_module.time, "monotonic", lambda: now[0]
        )
        for _ in range(3):
            assert lim.check("k", 3, 60) is None
        assert lim.check("k", 3, 60) is not None
        now[0] += 61
        assert lim.check("k", 3, 60) is None

    def test_reset(self):
        lim = SlidingWindowLimiter()
        for _ in range(3):
            lim.check("k", 3, 60)
        lim.reset()
        assert lim.check("k", 3, 60) is None


@pytest_asyncio.fixture
async def db():
    # Same sqlite-compat shim as test_governance_delete: JSONB → JSON and
    # index-name dedupe so the PG-flavored metadata creates on sqlite.
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


def _client(db, with_user: bool = False) -> AsyncClient:
    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    if with_user:
        user = User(
            id=USER_ID, tenant_id=TENANT_ID, username="u", email="u@t.com",
            full_name="U", password_hash="x", role=Role.ADMIN, is_active=True,
        )
        app.dependency_overrides[get_current_user] = lambda: user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


BAD_LOGIN = {"username": "no-such-user", "password": "wrong-pass-1"}


@pytest.mark.asyncio
class TestLoginRateLimit:
    async def test_flood_gets_429_with_retry_after(self, db):
        async with _client(db) as client:
            for _ in range(settings.rate_limit_login_per_minute):
                resp = await client.post("/api/auth/login", json=BAD_LOGIN)
                assert resp.status_code == 401
            resp = await client.post("/api/auth/login", json=BAD_LOGIN)
        assert resp.status_code == 429
        assert int(resp.headers["Retry-After"]) >= 1

    async def test_limited_per_ip_not_globally(self, db):
        async with _client(db) as client:
            for _ in range(settings.rate_limit_login_per_minute):
                await client.post(
                    "/api/auth/login", json=BAD_LOGIN,
                    headers={"X-Forwarded-For": "203.0.113.1"},
                )
            blocked = await client.post(
                "/api/auth/login", json=BAD_LOGIN,
                headers={"X-Forwarded-For": "203.0.113.1"},
            )
            other_ip = await client.post(
                "/api/auth/login", json=BAD_LOGIN,
                headers={"X-Forwarded-For": "203.0.113.2"},
            )
        assert blocked.status_code == 429
        assert other_ip.status_code == 401


@pytest.mark.asyncio
class TestPerUserRateLimit:
    async def test_change_password_flood_gets_429(self, db):
        payload = {
            "current_password": "wrong-pass-1",
            "new_password": "Valid-new-pass-123",
        }
        async with _client(db, with_user=True) as client:
            for _ in range(settings.rate_limit_password_change_per_minute):
                resp = await client.post("/api/auth/change-password", json=payload)
                assert resp.status_code != 429
            resp = await client.post("/api/auth/change-password", json=payload)
        assert resp.status_code == 429

    async def test_upload_blocked_when_user_budget_spent(self, db):
        # Pre-fill this user's upload window instead of issuing 30 uploads.
        for _ in range(settings.rate_limit_upload_per_minute):
            assert limiter.check(
                f"upload:{USER_ID}", settings.rate_limit_upload_per_minute, 60
            ) is None
        async with _client(db, with_user=True) as client:
            resp = await client.post("/api/contracts/upload")
        assert resp.status_code == 429
