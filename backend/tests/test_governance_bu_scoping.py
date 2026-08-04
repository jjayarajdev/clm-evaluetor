"""BU isolation for governance data: BU-X users must never see BU-Y's
vendors (organizations) and relationships — or their KPIs, surveys,
improvements, and service portfolios.

Visibility is DERIVED (orgs/relationships stay shared per-tenant entities):
an entity is visible iff the user can see >=1 contract linking to it, or it
has no linked contracts at all (tenant-shared, mirrors the NULL-BU rule).
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
from app.core.bu_scope import (
    org_bu_visibility_clause,
    relationship_bu_visibility_clause,
    resolve_visible_bu_ids,
)
from app.core.deps import get_current_user, get_current_tenant_id
from app.models.business_unit import BusinessUnit
from app.models.contract import Contract, ContractStatus
from app.models.kpi import KPI
from app.models.organization import Organization
from app.models.relationship import BusinessRelationship
from app.models.survey import SurveyInstance, SurveyTemplate
from app.models.tenant import Tenant
from app.models.user import Role, User

TENANT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


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


def _user(role: Role, bu_id=None) -> User:
    return User(
        id=uuid.uuid4(), tenant_id=TENANT_ID, username=f"u-{uuid.uuid4().hex[:6]}",
        email=f"{uuid.uuid4().hex[:6]}@t.com", full_name="U", password_hash="x",
        role=role, is_active=True, preferred_language="en", business_unit_id=bu_id,
    )


def _org(name: str, org_type="vendor") -> Organization:
    return Organization(
        id=uuid.uuid4(), tenant_id=TENANT_ID, name=name, code=name.upper()[:10],
        org_type=org_type, is_active=True,
    )


def _rel(org_a, org_b) -> BusinessRelationship:
    return BusinessRelationship(
        id=uuid.uuid4(), tenant_id=TENANT_ID, org_a_id=org_a.id, org_b_id=org_b.id,
        relationship_type="supplier", status="active",
    )


def _contract(name, uploader, bu_id=None, org=None, rel=None) -> Contract:
    return Contract(
        id=uuid.uuid4(), tenant_id=TENANT_ID, filename=name, file_path=f"/tmp/{name}",
        status=ContractStatus.COMPLETED, uploaded_by=uploader.id,
        business_unit_id=bu_id,
        organization_id=org.id if org else None,
        business_relationship_id=rel.id if rel else None,
    )


@pytest_asyncio.fixture
async def seed(db):
    """Two BUs (X with child, Y); vendors exclusive to each; shared; NULL-BU;
    manual (no contracts); orphan rel exercising the org-fallback branch."""
    tenant = Tenant(id=TENANT_ID, name="T", slug="t", is_active=True)
    bu_x = BusinessUnit(id=uuid.uuid4(), tenant_id=TENANT_ID, name="X", code="X")
    bu_y = BusinessUnit(id=uuid.uuid4(), tenant_id=TENANT_ID, name="Y", code="Y")
    bu_x_child = BusinessUnit(id=uuid.uuid4(), tenant_id=TENANT_ID, name="Xc", code="XC", parent_id=bu_x.id)
    db.add_all([tenant, bu_x, bu_y, bu_x_child])

    admin_nobu = _user(Role.ADMIN)
    legal_x = _user(Role.LEGAL, bu_x.id)
    legal_y = _user(Role.LEGAL, bu_y.id)
    bu_head_x = _user(Role.BU_HEAD, bu_x.id)
    super_admin = _user(Role.SUPER_ADMIN)
    super_admin.tenant_id = None
    db.add_all([admin_nobu, legal_x, legal_y, bu_head_x, super_admin])

    internal = _org("Us", org_type="internal")
    vendor_x, vendor_y, vendor_shared, vendor_null, vendor_child, manual_org = (
        _org("VendX"), _org("VendY"), _org("VendShared"), _org("VendNull"),
        _org("VendChild"), _org("Manual"),
    )
    db.add_all([internal, vendor_x, vendor_y, vendor_shared, vendor_null, vendor_child, manual_org])

    rel_x, rel_y = _rel(internal, vendor_x), _rel(internal, vendor_y)
    rel_shared = _rel(internal, vendor_shared)
    manual_rel = _rel(internal, manual_org)          # no contracts at all
    orphan_rel = _rel(internal, vendor_x)            # no direct contracts; org fallback
    db.add_all([rel_x, rel_y, rel_shared, manual_rel, orphan_rel])

    db.add_all([
        _contract("x.pdf", legal_x, bu_x.id, vendor_x, rel_x),
        _contract("y.pdf", legal_y, bu_y.id, vendor_y, rel_y),
        _contract("sx.pdf", legal_x, bu_x.id, vendor_shared, rel_shared),
        _contract("sy.pdf", legal_y, bu_y.id, vendor_shared, rel_shared),
        _contract("n.pdf", admin_nobu, None, vendor_null),
        _contract("c.pdf", legal_x, bu_x_child.id, vendor_child),
    ])

    kpi_x = KPI(id=uuid.uuid4(), relationship_id=rel_x.id, name="QX", category="quality")
    kpi_y = KPI(id=uuid.uuid4(), relationship_id=rel_y.id, name="QY", category="quality")
    db.add_all([kpi_x, kpi_y])

    template = SurveyTemplate(id=uuid.uuid4(), tenant_id=TENANT_ID, name="T")
    db.add(template)
    si_x = SurveyInstance(id=uuid.uuid4(), template_id=template.id, relationship_id=rel_x.id, period="2026-Q3")
    si_y = SurveyInstance(id=uuid.uuid4(), template_id=template.id, relationship_id=rel_y.id, period="2026-Q3")
    db.add_all([si_x, si_y])

    await db.commit()
    return {
        "bu_x": bu_x, "bu_y": bu_y, "bu_x_child": bu_x_child,
        "admin_nobu": admin_nobu, "legal_x": legal_x, "legal_y": legal_y,
        "bu_head_x": bu_head_x, "super_admin": super_admin,
        "internal": internal, "vendor_x": vendor_x, "vendor_y": vendor_y,
        "vendor_shared": vendor_shared, "vendor_null": vendor_null,
        "vendor_child": vendor_child, "manual_org": manual_org,
        "rel_x": rel_x, "rel_y": rel_y, "rel_shared": rel_shared,
        "manual_rel": manual_rel, "orphan_rel": orphan_rel,
        "kpi_x": kpi_x, "kpi_y": kpi_y, "si_x": si_x, "si_y": si_y,
    }


async def _visible_orgs(db, user) -> set[str]:
    clause = org_bu_visibility_clause(await resolve_visible_bu_ids(db, user))
    q = select(Organization.name).where(Organization.tenant_id == TENANT_ID)
    if clause is not None:
        q = q.where(clause)
    return set((await db.execute(q)).scalars().all())


async def _visible_rels(db, user) -> set[uuid.UUID]:
    clause = relationship_bu_visibility_clause(await resolve_visible_bu_ids(db, user))
    q = select(BusinessRelationship.id).where(BusinessRelationship.tenant_id == TENANT_ID)
    if clause is not None:
        q = q.where(clause)
    return set((await db.execute(q)).scalars().all())


class TestClauses:
    @pytest.mark.asyncio
    async def test_org_visibility_per_persona(self, db, seed):
        # legal_x: own-BU vendors + shared + NULL-BU + contract-less (internal, manual)
        assert await _visible_orgs(db, seed["legal_x"]) == {
            "Us", "VendX", "VendShared", "VendNull", "Manual",
        }
        # legal_y: never sees BU-X's vendors
        assert await _visible_orgs(db, seed["legal_y"]) == {
            "Us", "VendY", "VendShared", "VendNull", "Manual",
        }
        # bu_head_x additionally sees the child-BU vendor
        assert "VendChild" in await _visible_orgs(db, seed["bu_head_x"])
        assert "VendChild" not in await _visible_orgs(db, seed["legal_x"])

    @pytest.mark.asyncio
    async def test_unrestricted_personas_see_all(self, db, seed):
        all_names = {"Us", "VendX", "VendY", "VendShared", "VendNull", "VendChild", "Manual"}
        assert await _visible_orgs(db, seed["admin_nobu"]) == all_names
        assert await _visible_orgs(db, seed["super_admin"]) == all_names

    @pytest.mark.asyncio
    async def test_relationship_visibility_and_fallback(self, db, seed):
        x_rels = await _visible_rels(db, seed["legal_x"])
        assert seed["rel_x"].id in x_rels
        assert seed["rel_shared"].id in x_rels
        assert seed["manual_rel"].id in x_rels       # no contracts → tenant-shared
        assert seed["orphan_rel"].id in x_rels       # fallback via vendor_x's contracts
        assert seed["rel_y"].id not in x_rels        # THE isolation requirement

        y_rels = await _visible_rels(db, seed["legal_y"])
        assert seed["rel_y"].id in y_rels
        assert seed["rel_x"].id not in y_rels
        assert seed["orphan_rel"].id not in y_rels   # fallback ANDs the counterparty side

    @pytest.mark.asyncio
    async def test_internal_org_does_not_leak_relationships(self, db, seed):
        """Regression: the internal org has no contracts pointing at it — an
        OR-composed fallback would make every relationship visible."""
        y_rels = await _visible_rels(db, seed["legal_y"])
        assert seed["rel_x"].id not in y_rels
        assert seed["orphan_rel"].id not in y_rels


def _client(db, user):
    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_tenant_id] = lambda: user.tenant_id
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


class TestOrganizationEndpoints:
    @pytest.mark.asyncio
    async def test_list_excludes_other_bu(self, db, seed):
        async with _client(db, seed["legal_x"]) as c:
            r = await c.get("/api/organizations?page_size=100")
        names = {o["name"] for o in r.json()["items"]}
        assert "VendY" not in names
        assert {"VendX", "VendShared", "VendNull", "Manual"} <= names

    @pytest.mark.asyncio
    async def test_get_put_delete_cross_bu_404(self, db, seed):
        vy = seed["vendor_y"].id
        async with _client(db, seed["legal_x"]) as c:
            assert (await c.get(f"/api/organizations/{vy}")).status_code == 404
        async with _client(db, _user(Role.ADMIN, seed["bu_x"].id)) as c:
            assert (await c.put(f"/api/organizations/{vy}", json={"name": "z"})).status_code == 404
            assert (await c.delete(f"/api/organizations/{vy}")).status_code == 404

    @pytest.mark.asyncio
    async def test_admin_nobu_sees_everything(self, db, seed):
        async with _client(db, seed["admin_nobu"]) as c:
            r = await c.get("/api/organizations?page_size=100")
        assert {o["name"] for o in r.json()["items"]} >= {"VendX", "VendY", "VendChild"}

    @pytest.mark.asyncio
    async def test_org_relationships_filtered(self, db, seed):
        """Internal org is visible to everyone, but its relationship list is
        still BU-filtered per requester."""
        internal = seed["internal"].id
        async with _client(db, seed["legal_x"]) as c:
            r = await c.get(f"/api/organizations/{internal}/relationships")
        ids = {x["id"] for x in r.json()}
        assert str(seed["rel_y"].id) not in ids
        assert str(seed["rel_x"].id) in ids


class TestRelationshipEndpoints:
    @pytest.mark.asyncio
    async def test_list_and_get_cross_bu(self, db, seed):
        async with _client(db, seed["legal_x"]) as c:
            r = await c.get("/api/relationships?page_size=100")
            ids = {item["id"] for item in r.json()["items"]}
            assert str(seed["rel_y"].id) not in ids
            assert str(seed["rel_x"].id) in ids
            assert (await c.get(f"/api/relationships/{seed['rel_y'].id}")).status_code == 404
            assert (await c.get(f"/api/relationships/{seed['rel_x'].id}")).status_code == 200

    @pytest.mark.asyncio
    async def test_team_and_history_cross_bu_404(self, db, seed):
        async with _client(db, seed["legal_x"]) as c:
            assert (await c.get(f"/api/relationships/{seed['rel_y'].id}/team")).status_code == 404
            assert (await c.get(f"/api/relationships/{seed['rel_y'].id}/history")).status_code == 404

    @pytest.mark.asyncio
    async def test_create_with_invisible_org_rejected(self, db, seed):
        async with _client(db, _user(Role.ADMIN, seed["bu_x"].id)) as c:
            r = await c.post("/api/relationships", json={
                "org_a_id": str(seed["internal"].id),
                "org_b_id": str(seed["vendor_y"].id),
                "relationship_type": "supplier",
            })
        assert r.status_code == 400


class TestChildrenInherit:
    @pytest.mark.asyncio
    async def test_kpis_filtered_and_cross_bu_404(self, db, seed):
        async with _client(db, seed["legal_x"]) as c:
            r = await c.get("/api/kpis?page_size=100")
            ids = {item["id"] for item in r.json()["items"]}
            assert str(seed["kpi_y"].id) not in ids
            assert str(seed["kpi_x"].id) in ids
            assert (await c.get(f"/api/kpis/{seed['kpi_y'].id}")).status_code == 404

    @pytest.mark.asyncio
    async def test_relationship_gaps_endpoints_guarded(self, db, seed):
        """Previously had NO tenant check at all — now tenant+BU guarded."""
        async with _client(db, seed["legal_x"]) as c:
            assert (await c.get(f"/api/kpis/relationship/{seed['rel_y'].id}/gaps")).status_code == 404
            assert (await c.get(f"/api/kpis/relationship/{seed['rel_y'].id}/summary")).status_code == 404
            assert (await c.get(f"/api/kpis/relationship/{seed['rel_x'].id}/gaps")).status_code == 200

    @pytest.mark.asyncio
    async def test_survey_instances_filtered(self, db, seed):
        async with _client(db, seed["legal_x"]) as c:
            r = await c.get("/api/surveys/instances?page_size=100")
            ids = {item["id"] for item in r.json()["items"]}
            assert str(seed["si_y"].id) not in ids
            assert str(seed["si_x"].id) in ids
            assert (await c.get(f"/api/surveys/instances/{seed['si_y'].id}")).status_code == 404

    @pytest.mark.asyncio
    async def test_kpi_create_on_invisible_relationship_rejected(self, db, seed):
        async with _client(db, _user(Role.ADMIN, seed["bu_x"].id)) as c:
            r = await c.post("/api/kpis", json={
                "relationship_id": str(seed["rel_y"].id),
                "name": "Sneaky", "category": "quality",
            })
        assert r.status_code == 400
