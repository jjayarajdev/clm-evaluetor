"""Tests for contract-group deletion: single, bulk, and auto-family dissolve.

Rules under test: deleting a group never touches contracts; auto_family
groups require dissolve_links=true (they'd be re-created by the sync
otherwise), which removes the members' contract links and rejects their
pending suggestions.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import JSON, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base, get_db
from app.core.deps import get_current_user, get_current_tenant_id
from app.models.contract import Contract, ContractStatus
from app.models.contract_group import ContractGroup, ContractGroupMember
from app.models.contract_link import ContractLink
from app.models.suggested_link import SuggestedContractLink
from app.models.tenant import Tenant
from app.models.user import Role, User

TENANT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
USER_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


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


def _contract(name: str) -> Contract:
    return Contract(
        id=uuid.uuid4(), tenant_id=TENANT_ID, filename=name,
        file_path=f"/tmp/{name}", status=ContractStatus.COMPLETED,
        uploaded_by=USER_ID,
    )


def _group(name: str, group_type: str) -> ContractGroup:
    return ContractGroup(
        id=uuid.uuid4(), tenant_id=TENANT_ID, name=name, group_type=group_type,
    )


def _member(group: ContractGroup, contract: Contract) -> ContractGroupMember:
    return ContractGroupMember(
        tenant_id=TENANT_ID, group_id=group.id, contract_id=contract.id,
        source=group.group_type,
    )


@pytest_asyncio.fixture
async def seeded(db):
    """An auto_family group (MSA + 2 SOWs, linked) and a manual group."""
    msa, sow1, sow2, other = (
        _contract("msa.pdf"), _contract("sow1.pdf"),
        _contract("sow2.pdf"), _contract("other.pdf"),
    )
    family = _group("Family", "auto_family")
    manual = _group("Manual", "manual")

    db.add(Tenant(id=TENANT_ID, name="T", slug="t", is_active=True))
    db.add(User(
        id=USER_ID, tenant_id=TENANT_ID, username="u", email="u@t.com",
        full_name="U", password_hash="x", role=Role.ADMIN, is_active=True,
    ))
    db.add_all([msa, sow1, sow2, other, family, manual])
    db.add_all([
        _member(family, msa), _member(family, sow1), _member(family, sow2),
        _member(manual, other),
    ])
    db.add_all([
        ContractLink(parent_contract_id=msa.id, child_contract_id=sow1.id, link_type="sow"),
        ContractLink(parent_contract_id=msa.id, child_contract_id=sow2.id, link_type="sow"),
        # Link to a non-member — must survive a dissolve
        ContractLink(parent_contract_id=msa.id, child_contract_id=other.id, link_type="related"),
    ])
    db.add(SuggestedContractLink(
        source_contract_id=sow1.id, target_contract_id=sow2.id,
        suggested_link_type="related", suggested_direction="source_is_child",
        confidence_score=0.8, status="pending", tenant_id=TENANT_ID,
    ))
    await db.commit()
    return {"msa": msa, "sow1": sow1, "sow2": sow2, "other": other,
            "family": family, "manual": manual}


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


async def _count(db, model):
    return len((await db.execute(select(model))).scalars().all())


class TestSingleDelete:
    @pytest.mark.asyncio
    async def test_manual_group_delete_leaves_contracts(self, db, seeded):
        async with _client(db) as c:
            r = await c.delete(f"/api/groups/{seeded['manual'].id}")
        assert r.status_code == 204
        assert await _count(db, Contract) == 4  # contracts untouched
        groups = (await db.execute(select(ContractGroup))).scalars().all()
        assert [g.name for g in groups] == ["Family"]

    @pytest.mark.asyncio
    async def test_auto_family_requires_dissolve_flag(self, db, seeded):
        async with _client(db) as c:
            r = await c.delete(f"/api/groups/{seeded['family'].id}")
        assert r.status_code == 400
        assert "dissolve_links" in r.json()["detail"]
        assert await _count(db, ContractGroup) == 2  # nothing deleted

    @pytest.mark.asyncio
    async def test_auto_family_dissolve_removes_member_links_only(self, db, seeded):
        async with _client(db) as c:
            r = await c.delete(f"/api/groups/{seeded['family'].id}?dissolve_links=true")
        assert r.status_code == 204

        links = (await db.execute(select(ContractLink))).scalars().all()
        # The two intra-family links are gone; the link to the non-member survives
        assert len(links) == 1
        assert links[0].child_contract_id == seeded["other"].id

        suggestion = (await db.execute(select(SuggestedContractLink))).scalars().one()
        assert suggestion.status == "rejected"

        assert await _count(db, Contract) == 4  # contracts never touched
        assert await _count(db, ContractGroup) == 1  # manual group remains


class TestBulkDelete:
    @pytest.mark.asyncio
    async def test_bulk_skips_auto_family_without_dissolve(self, db, seeded):
        async with _client(db) as c:
            r = await c.post("/api/groups/bulk-delete", json={
                "group_ids": [str(seeded["manual"].id), str(seeded["family"].id)],
            })
        assert r.status_code == 200
        data = r.json()
        assert data["deleted"] == 1
        assert data["skipped"] == [{
            "group_id": str(seeded["family"].id),
            "reason": "auto_family_requires_dissolve",
        }]
        assert await _count(db, ContractGroup) == 1  # family remains

    @pytest.mark.asyncio
    async def test_bulk_with_dissolve_deletes_everything(self, db, seeded):
        async with _client(db) as c:
            r = await c.post("/api/groups/bulk-delete", json={
                "group_ids": [str(seeded["manual"].id), str(seeded["family"].id)],
                "dissolve_links": True,
            })
        data = r.json()
        assert data["deleted"] == 2
        assert data["links_removed"] == 2
        assert data["skipped"] == []
        assert await _count(db, ContractGroup) == 0
        assert await _count(db, Contract) == 4

    @pytest.mark.asyncio
    async def test_bulk_reports_unknown_ids(self, db, seeded):
        ghost = str(uuid.uuid4())
        async with _client(db) as c:
            r = await c.post("/api/groups/bulk-delete", json={"group_ids": [ghost]})
        assert r.json()["skipped"] == [{"group_id": ghost, "reason": "not_found"}]
