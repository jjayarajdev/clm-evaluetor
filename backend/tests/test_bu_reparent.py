"""Reproduction test for the tester-reported BU re-parenting bug:
"change Business Unit relative position … it does not change anything
after the update".

Exercises PUT /api/business-units/{id} with a new parent_id through the
real app, then verifies both the row and the /tree endpoint reflect it.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.deps import get_current_user, get_current_tenant_id
from app.database import Base, get_db
from app.main import app
from app.models.business_unit import BusinessUnit
from app.models.tenant import Tenant
from app.models.user import Role, User

TENANT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()


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


def _client(db) -> AsyncClient:
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


def _bu(name: str, parent_id=None) -> BusinessUnit:
    return BusinessUnit(
        id=uuid.uuid4(), tenant_id=TENANT_ID, name=name,
        code=name.upper()[:10], parent_id=parent_id, is_active=True,
    )


async def _seed(db):
    db.add(Tenant(id=TENANT_ID, name="T", slug="t", is_active=True))
    root = _bu("Vialto")
    advisory = _bu("Advisory", parent_id=root.id)
    board = _bu("Board", parent_id=root.id)
    db.add_all([root, advisory, board])
    await db.commit()
    return root, advisory, board


def _find(tree: list[dict], name: str) -> dict | None:
    for node in tree:
        if node["name"] == name:
            return node
        found = _find(node.get("children") or [], name)
        if found:
            return found
    return None


@pytest.mark.asyncio
class TestReparent:
    async def test_move_bu_under_sibling(self, db):
        root, advisory, board = await _seed(db)
        async with _client(db) as client:
            resp = await client.put(
                f"/api/business-units/{board.id}",
                json={
                    # What the UI drawer sends on save
                    "name": "Board",
                    "code": "BOARD",
                    "parent_id": str(advisory.id),
                    "is_active": True,
                },
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["parent_id"] == str(advisory.id)

            tree = (await client.get("/api/business-units/tree")).json()
        advisory_node = _find(tree, "Advisory")
        assert advisory_node is not None
        assert [c["name"] for c in advisory_node["children"]] == ["Board"]

    async def test_move_under_own_descendant_rejected(self, db):
        root, advisory, board = await _seed(db)
        # advisory -> board makes a chain root > board > advisory; then moving
        # board under advisory would be circular.
        async with _client(db) as client:
            resp = await client.put(
                f"/api/business-units/{advisory.id}",
                json={"name": "Advisory", "code": "ADVISORY", "parent_id": str(board.id)},
            )
            assert resp.status_code == 200, resp.text
            resp = await client.put(
                f"/api/business-units/{board.id}",
                json={"name": "Board", "code": "BOARD", "parent_id": str(advisory.id)},
            )
        assert resp.status_code == 400
        assert "circular" in resp.json()["detail"].lower()

    async def test_move_bu_to_root(self, db):
        root, advisory, board = await _seed(db)
        async with _client(db) as client:
            resp = await client.put(
                f"/api/business-units/{board.id}",
                json={"name": "Board", "code": "BOARD", "parent_id": None},
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["parent_id"] is None

            tree = (await client.get("/api/business-units/tree")).json()
        assert _find(tree, "Board") is not None
        root_names = [n["name"] for n in tree]
        assert "Board" in root_names
