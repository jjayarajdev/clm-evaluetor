"""Tests for the renewal radar's expired-contract handling.

Regression under test: contracts that lapsed more than 30 days ago silently
vanished from the renewal calendar ("No contracts approaching renewal, $0 at
risk" on a fully-expired portfolio). Recently lapsed contracts must stay
visible for EXPIRED_LOOKBACK_DAYS and carry their value.
"""

import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base, get_db
from app.core.deps import get_current_user, get_current_tenant_id
from app.models.contract import Contract, ContractStatus
from app.models.tenant import Tenant
from app.models.user import Role, User
from app.routers.renewals import EXPIRED_LOOKBACK_DAYS
from app.services.postsigning_service import PostSigningService

TENANT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
USER_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TODAY = date.today()


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


def _contract(name: str, expires_in_days: int | None, value: float | None = None) -> Contract:
    return Contract(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        filename=name,
        file_path=f"/tmp/{name}",
        status=ContractStatus.COMPLETED,
        uploaded_by=USER_ID,
        expiration_date=(TODAY + timedelta(days=expires_in_days)) if expires_in_days is not None else None,
        contract_value=value,
        currency="USD",
    )


@pytest_asyncio.fixture
async def seeded(db):
    contracts = {
        "lapsed_34d": _contract("lapsed34.pdf", -34, 100_000),
        "lapsed_179d": _contract("lapsed179.pdf", -179, 50_000),
        "long_dead": _contract("dead.pdf", -(EXPIRED_LOOKBACK_DAYS + 20), 999_999),
        "upcoming_20d": _contract("soon.pdf", 20, 70_000),
        "undated": _contract("undated.pdf", None, 10_000),
    }
    db.add(Tenant(id=TENANT_ID, name="T", slug="t", is_active=True))
    db.add(User(
        id=USER_ID, tenant_id=TENANT_ID, username="u", email="u@t.com",
        full_name="U", password_hash="x", role=Role.ADMIN, is_active=True,
    ))
    db.add_all(contracts.values())
    await db.commit()
    return contracts


def _client(db):
    async def override_db():
        yield db

    user = User(
        id=USER_ID, tenant_id=TENANT_ID, username="u", email="u@t.com",
        full_name="U", password_hash="x", role=Role.ADMIN, is_active=True,
    )
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_tenant_id] = lambda: TENANT_ID
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


class TestRenewalCalendarExpired:
    @pytest.mark.asyncio
    async def test_recently_lapsed_contracts_stay_visible(self, db, seeded):
        async with _client(db) as c:
            r = await c.get("/api/renewals/calendar")
        assert r.status_code == 200
        data = r.json()

        expired_files = {e["filename"] for e in data["expired"]}
        # Lapsed within the lookback → visible
        assert "lapsed34.pdf" in expired_files
        assert "lapsed179.pdf" in expired_files
        # Lapsed long ago → excluded from the action radar
        assert "dead.pdf" not in expired_files

    @pytest.mark.asyncio
    async def test_expired_value_and_upcoming_value_split(self, db, seeded):
        async with _client(db) as c:
            r = await c.get("/api/renewals/calendar")
        data = r.json()
        # Lapsed value = 100k + 50k (long-dead 999,999 excluded)
        assert data["expired_value"] == pytest.approx(150_000)
        # Upcoming risk = the 20-day contract only
        assert data["upcoming_value_at_risk"] == pytest.approx(70_000)
        assert data["total_value_at_risk"] == pytest.approx(70_000)

    @pytest.mark.asyncio
    async def test_expired_rows_have_negative_days(self, db, seeded):
        async with _client(db) as c:
            r = await c.get("/api/renewals/calendar")
        lapsed = next(e for e in r.json()["expired"] if e["filename"] == "lapsed34.pdf")
        assert lapsed["days_until_expiration"] == -34
        assert lapsed["renewal_window"] == "expired"

    @pytest.mark.asyncio
    async def test_fully_lapsed_portfolio_is_not_empty(self, db):
        """The original bug: everything expired 34d ago -> page showed nothing."""
        db.add(Tenant(id=TENANT_ID, name="T", slug="t", is_active=True))
        db.add(User(
            id=USER_ID, tenant_id=TENANT_ID, username="u", email="u@t.com",
            full_name="U", password_hash="x", role=Role.ADMIN, is_active=True,
        ))
        db.add_all([_contract(f"sow{i}.pdf", -34, 168_096) for i in range(6)])
        await db.commit()

        async with _client(db) as c:
            r = await c.get("/api/renewals/calendar")
        data = r.json()
        assert len(data["expired"]) == 6
        assert data["expired_value"] == pytest.approx(6 * 168_096)


class TestRenewalWidgetExpired:
    def _widget(self, contracts):
        service = PostSigningService.__new__(PostSigningService)  # pure method, no db needed
        widget, _past_notice = service._build_renewal_widget(contracts, TODAY)
        return widget

    def _fake(self, expires_in_days, value=None):
        return SimpleNamespace(
            id=uuid.uuid4(), filename="x.pdf", counterparty=None,
            expiration_date=(TODAY + timedelta(days=expires_in_days)) if expires_in_days is not None else None,
            contract_value=value, auto_renewal=None, notice_period_days=None,
        )

    def test_recent_vs_ancient_expiry_split(self):
        widget = self._widget([
            self._fake(-10, 100_000),
            self._fake(-(EXPIRED_LOOKBACK_DAYS + 1), 500_000),
            self._fake(15, 30_000),
            self._fake(None, 1),
        ])
        assert widget.expired_count == 2          # all expired, regardless of age
        assert widget.expired_recent_count == 1   # only the recent lapse needs action
        assert widget.expired_value == pytest.approx(100_000)
        assert widget.total_value_at_risk == pytest.approx(30_000)
        assert widget.no_date_count == 1

    def test_boundary_exactly_at_lookback(self):
        widget = self._widget([self._fake(-EXPIRED_LOOKBACK_DAYS, 42_000)])
        assert widget.expired_recent_count == 1
        assert widget.expired_value == pytest.approx(42_000)
