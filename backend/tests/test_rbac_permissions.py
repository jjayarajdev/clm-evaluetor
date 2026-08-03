"""Tests for the DB-driven RBAC matrix.

The equivalence tests are the migration's proof obligation: under the default
matrix, every migrated guard admits exactly the same roles as the legacy
hardcoded role lists did.
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
from app.core.permissions import (
    DEFAULT_ROLE_PERMISSIONS,
    PERMISSIONS,
    get_matrix,
    has_permission,
    reset_permissions_cache,
    seed_default_role_permissions,
)
from app.models.role_permission import RoleDef, RolePermission
from app.models.tenant import Tenant
from app.models.user import Role, User

TENANT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

# The legacy hardcoded role lists each migrated guard used before the
# DB-driven matrix. THE source for the zero-behavior-change proof.
LEGACY_GUARDS = {
    "admin": {"admin"},
    "contracts.write": {"admin", "legal", "procurement", "bu_head"},
    "admin.aiSettings": {"admin"},
    "surveys.manageTemplates": {"admin"},
    "surveys.manageInstances": {"admin", "legal"},
    "businessUnits.manage": {"admin"},
    "dashboard.admin": {"admin"},
    "dashboard.legal": {"admin", "legal"},
    "dashboard.procurement": {"admin", "procurement"},
    "organizations.write": {"admin", "legal"},
    "organizations.delete": {"admin"},
    "relationships.write": {"admin", "legal"},
    "relationships.delete": {"admin"},
    "services.write": {"admin", "legal"},
    "services.delete": {"admin"},
    "contractDocuments.write": {"admin", "legal"},
    "externalUsers.manage": {"admin", "legal"},
    "kpi.approve": {"admin", "legal"},
    "usage.viewCost": {"admin"},
}

TENANT_ROLES = [Role.ADMIN, Role.LEGAL, Role.PROCUREMENT, Role.BU_HEAD, Role.VIEWER]


def _user(role: Role) -> User:
    return User(
        id=uuid.uuid4(), tenant_id=None if role == Role.SUPER_ADMIN else TENANT_ID,
        username=f"u-{role.value}", email=f"{role.value}@t.com", full_name=role.value,
        password_hash="x", role=role, is_active=True, preferred_language="en",
    )


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


class TestEquivalence:
    """Default matrix grants == legacy hardcoded role lists, for every guard."""

    @pytest.mark.parametrize("permission", sorted(LEGACY_GUARDS))
    @pytest.mark.parametrize("role", TENANT_ROLES)
    def test_default_matrix_matches_legacy_guard(self, permission, role):
        expected = role.value in LEGACY_GUARDS[permission]
        assert has_permission(_user(role), permission) is expected, (
            f"{role.value} × {permission}: matrix disagrees with legacy guard"
        )

    @pytest.mark.parametrize("permission", sorted(LEGACY_GUARDS))
    def test_super_admin_floor(self, permission):
        assert has_permission(_user(Role.SUPER_ADMIN), permission) is True

    def test_all_guard_keys_in_catalog(self):
        assert set(LEGACY_GUARDS) <= PERMISSIONS

    def test_defaults_only_use_catalog_keys(self):
        for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
            assert perms <= PERMISSIONS, f"{role} grants unknown keys: {perms - PERMISSIONS}"


class TestHasPermission:
    def test_any_of_semantics(self):
        legal = _user(Role.LEGAL)
        assert has_permission(legal, "admin", "kpi.approve") is True  # holds the 2nd
        assert has_permission(legal, "admin", "usage.viewCost") is False

    def test_super_admin_passes_even_unknown_permission(self):
        assert has_permission(_user(Role.SUPER_ADMIN), "not.a.permission") is True

    def test_viewer_denied_writes(self):
        viewer = _user(Role.VIEWER)
        assert has_permission(viewer, "contracts.write") is False
        assert has_permission(viewer, "dashboard") is True


class TestMatrixLoading:
    @pytest.mark.asyncio
    async def test_empty_tables_fall_back_to_defaults(self, db):
        matrix = await get_matrix(db, force=True)
        assert matrix == DEFAULT_ROLE_PERMISSIONS

    @pytest.mark.asyncio
    async def test_seed_then_load_round_trips(self, db):
        inserted = await seed_default_role_permissions(db)
        assert inserted > 0
        reset_permissions_cache()
        matrix = await get_matrix(db, force=True)
        assert matrix == {r.value: DEFAULT_ROLE_PERMISSIONS[r.value] for r in Role}

    @pytest.mark.asyncio
    async def test_seed_is_idempotent_and_preserves_edits(self, db):
        await seed_default_role_permissions(db)
        # Super-admin-style edit: strip viewer down to dashboard only
        from sqlalchemy import delete as sa_delete

        await db.execute(sa_delete(RolePermission).where(RolePermission.role_name == "viewer"))
        db.add(RolePermission(role_name="viewer", permission="dashboard"))
        await db.commit()

        assert await seed_default_role_permissions(db) == 0  # no reseed
        matrix = await get_matrix(db, force=True)
        assert matrix["viewer"] == frozenset({"dashboard"})


class TestAuthMePermissions:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("role", TENANT_ROLES + [Role.SUPER_ADMIN])
    async def test_me_returns_effective_permissions(self, db, role):
        db.add(Tenant(id=TENANT_ID, name="T", slug="t", is_active=True))
        await db.commit()
        user = _user(role)
        async with _client(db, user) as c:
            r = await c.get("/api/auth/me")
        assert r.status_code == 200
        perms = r.json()["permissions"]
        assert perms == sorted(DEFAULT_ROLE_PERMISSIONS[role.value])

    @pytest.mark.asyncio
    async def test_super_admin_gets_stored_row_not_full_catalog(self, db):
        async with _client(db, _user(Role.SUPER_ADMIN)) as c:
            r = await c.get("/api/auth/me")
        perms = set(r.json()["permissions"])
        assert perms == {"superadmin", "extraction.configure", "contract.edit", "contract.editFields"}
        assert perms != PERMISSIONS  # never the whole catalog


class TestEditorEndpoints:
    @pytest_asyncio.fixture
    async def seeded(self, db):
        await seed_default_role_permissions(db)

    @pytest.mark.asyncio
    async def test_non_super_admin_forbidden(self, db, seeded):
        async with _client(db, _user(Role.ADMIN)) as c:
            r = await c.get("/api/admin/role-permissions")
        assert r.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_get_matrix_and_catalog(self, db, seeded):
        async with _client(db, _user(Role.SUPER_ADMIN)) as c:
            r = await c.get("/api/admin/role-permissions")
        assert r.status_code == 200
        data = r.json()
        assert set(data["catalog"]) == PERMISSIONS
        roles = {row["name"]: row for row in data["roles"]}
        assert set(roles) == {r.value for r in Role}
        assert roles["viewer"]["permissions"] == sorted(DEFAULT_ROLE_PERMISSIONS["viewer"])

    @pytest.mark.asyncio
    async def test_unknown_role_404(self, db, seeded):
        async with _client(db, _user(Role.SUPER_ADMIN)) as c:
            r = await c.put("/api/admin/role-permissions/ghost", json={"permissions": []})
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_super_admin_row_immutable(self, db, seeded):
        async with _client(db, _user(Role.SUPER_ADMIN)) as c:
            r = await c.put("/api/admin/role-permissions/super_admin", json={"permissions": []})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_unknown_permission_rejected(self, db, seeded):
        async with _client(db, _user(Role.SUPER_ADMIN)) as c:
            r = await c.put("/api/admin/role-permissions/viewer",
                            json={"permissions": ["dashboard", "not.a.key"]})
        assert r.status_code == 422
        assert "not.a.key" in r.json()["detail"]

    @pytest.mark.asyncio
    async def test_admin_lockout_prevented(self, db, seeded):
        async with _client(db, _user(Role.SUPER_ADMIN)) as c:
            r = await c.put("/api/admin/role-permissions/admin",
                            json={"permissions": ["dashboard", "admin"]})  # missing 'settings'
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_grant_takes_effect_on_endpoints(self, db, seeded):
        """403 → (grant) → 404 proves both enforcement and cache refresh."""
        db.add(Tenant(id=TENANT_ID, name="T", slug="t", is_active=True))
        await db.commit()
        viewer = _user(Role.VIEWER)
        ghost_org = uuid.uuid4()

        async with _client(db, viewer) as c:
            before = await c.put(f"/api/organizations/{ghost_org}", json={"name": "x"})
        assert before.status_code == 403  # viewer lacks organizations.write

        async with _client(db, _user(Role.SUPER_ADMIN)) as c:
            grant = await c.put(
                "/api/admin/role-permissions/viewer",
                json={"permissions": sorted(DEFAULT_ROLE_PERMISSIONS["viewer"] | {"organizations.write"})},
            )
        assert grant.status_code == 200

        async with _client(db, viewer) as c:
            after = await c.put(f"/api/organizations/{ghost_org}", json={"name": "x"})
        assert after.status_code == 404  # now permitted; org just doesn't exist

    @pytest.mark.asyncio
    async def test_update_persists_to_db(self, db, seeded):
        async with _client(db, _user(Role.SUPER_ADMIN)) as c:
            await c.put("/api/admin/role-permissions/bu_head", json={"permissions": ["dashboard"]})
        rows = (await db.execute(
            select(RolePermission.permission).where(RolePermission.role_name == "bu_head")
        )).scalars().all()
        assert rows == ["dashboard"]


class TestTenantOverrides:
    """Per-tenant overrides layered on the platform matrix."""

    def test_context_override_wins_for_present_role(self):
        from app.core.permissions import set_request_role_overrides

        set_request_role_overrides({"viewer": ["contracts.write"]})
        try:
            viewer = _user(Role.VIEWER)
            assert has_permission(viewer, "contracts.write") is True   # granted by override
            assert has_permission(viewer, "dashboard") is False        # override replaces fully
            legal = _user(Role.LEGAL)
            assert has_permission(legal, "contracts.write") is True    # untouched role -> platform
        finally:
            set_request_role_overrides(None)

    def test_empty_override_locks_role_down(self):
        from app.core.permissions import set_request_role_overrides

        set_request_role_overrides({"viewer": []})
        try:
            assert has_permission(_user(Role.VIEWER), "dashboard") is False
        finally:
            set_request_role_overrides(None)

    def test_super_admin_floor_ignores_overrides(self):
        from app.core.permissions import set_request_role_overrides

        set_request_role_overrides({"super_admin": []})
        try:
            assert has_permission(_user(Role.SUPER_ADMIN), "anything") is True
        finally:
            set_request_role_overrides(None)

    def test_validate_tenant_override_guardrails(self):
        from app.core.permissions import validate_tenant_override

        assert validate_tenant_override("super_admin", set()) is not None
        assert validate_tenant_override("viewer", {"superadmin"}) is not None
        assert validate_tenant_override("viewer", {"not.a.key"}) is not None
        assert validate_tenant_override("admin", {"dashboard"}) is not None  # missing floor
        assert validate_tenant_override("admin", {"admin", "settings"}) is None
        assert validate_tenant_override("viewer", {"dashboard", "upload"}) is None

    @pytest.mark.asyncio
    async def test_effective_permissions_overlay_and_isolation(self, db):
        other_tenant = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        db.add(Tenant(
            id=TENANT_ID, name="A", slug="a", is_active=True,
            config_overrides={"role_permissions": {"viewer": ["dashboard", "upload"]}},
        ))
        db.add(Tenant(id=other_tenant, name="B", slug="b", is_active=True))
        await db.commit()

        from app.core.permissions import get_effective_permissions

        viewer_a = _user(Role.VIEWER)
        assert await get_effective_permissions(db, viewer_a) == ["dashboard", "upload"]

        viewer_b = _user(Role.VIEWER)
        viewer_b.tenant_id = other_tenant
        assert await get_effective_permissions(db, viewer_b) == sorted(
            DEFAULT_ROLE_PERMISSIONS["viewer"]
        )

    @pytest.mark.asyncio
    async def test_tenant_editor_endpoints(self, db):
        db.add(Tenant(id=TENANT_ID, name="A", slug="a", is_active=True, config_overrides={}))
        await db.commit()
        admin = _user(Role.ADMIN)

        async with _client(db, admin) as c:
            # Baseline: viewer not overridden
            r = await c.get("/api/admin/tenant-role-permissions")
            assert r.status_code == 200
            data = r.json()
            assert "superadmin" not in data["catalog"]
            viewer_row = next(x for x in data["roles"] if x["name"] == "viewer")
            assert viewer_row["overridden"] is False

            # Guardrails
            assert (await c.put("/api/admin/tenant-role-permissions/super_admin",
                                json={"permissions": []})).status_code == 404
            assert (await c.put("/api/admin/tenant-role-permissions/viewer",
                                json={"permissions": ["superadmin"]})).status_code == 422
            assert (await c.put("/api/admin/tenant-role-permissions/admin",
                                json={"permissions": ["dashboard"]})).status_code == 422

            # Set override, read back, reset
            r = await c.put("/api/admin/tenant-role-permissions/viewer",
                            json={"permissions": ["dashboard", "upload"]})
            assert r.status_code == 200 and r.json()["overridden"] is True

            r = await c.get("/api/admin/tenant-role-permissions")
            viewer_row = next(x for x in r.json()["roles"] if x["name"] == "viewer")
            assert viewer_row["overridden"] is True
            assert viewer_row["permissions"] == ["dashboard", "upload"]
            assert viewer_row["platform_permissions"] == sorted(DEFAULT_ROLE_PERMISSIONS["viewer"])

            r = await c.delete("/api/admin/tenant-role-permissions/viewer")
            assert r.status_code == 200 and r.json()["overridden"] is False

        # Persisted state is clean after reset
        tenant = (await db.execute(select(Tenant).where(Tenant.id == TENANT_ID))).scalar_one()
        assert "role_permissions" not in (tenant.config_overrides or {})

    @pytest.mark.asyncio
    async def test_tenant_editor_requires_admin(self, db):
        db.add(Tenant(id=TENANT_ID, name="A", slug="a", is_active=True))
        await db.commit()
        async with _client(db, _user(Role.LEGAL)) as c:
            r = await c.get("/api/admin/tenant-role-permissions")
        assert r.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_override_enforced_on_endpoints(self, db):
        """Viewer granted organizations.write via tenant override passes the
        real endpoint guard (403 -> 404 flip), simulating get_current_user's
        per-request override binding."""
        from app.core.permissions import set_request_role_overrides

        db.add(Tenant(id=TENANT_ID, name="A", slug="a", is_active=True))
        await db.commit()
        viewer = _user(Role.VIEWER)

        # Async, like the real get_current_user — sync overrides run in a
        # threadpool where ContextVar writes don't reach the request context.
        async def with_override():
            set_request_role_overrides({"viewer": ["organizations.write"]})
            return viewer

        async def override_db():
            yield db
        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_current_user] = with_override
        app.dependency_overrides[get_current_tenant_id] = lambda: TENANT_ID

        ghost = uuid.uuid4()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.put(f"/api/organizations/{ghost}", json={"name": "x"})
        assert r.status_code == 404  # permitted by override; org just missing

        app.dependency_overrides[get_current_user] = lambda: viewer
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.put(f"/api/organizations/{ghost}", json={"name": "x"})
        assert r.status_code == 403  # without override: platform viewer denied
