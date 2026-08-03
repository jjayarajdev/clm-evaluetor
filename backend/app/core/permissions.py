"""DB-driven role→permission matrix — the single source of truth for RBAC.

The matrix lives in the `roles` / `role_permissions` tables (platform-wide,
edited only by super admin). It drives BOTH layers:

  * backend endpoint guards via require_permission() / has_permission()
  * the frontend, via the `permissions` list on /auth/login and /auth/me
    (frontend permissionsForUser() prefers a backend-provided list)

Resolution rules:
  * super_admin ALWAYS passes has_permission() — a hard security floor that is
    deliberately not DB-configurable.
  * When the tables are empty or unreadable (fresh boot before migration/seed,
    SQLite tests where startup seeding never runs, DB hiccup), the matrix falls
    back to DEFAULT_ROLE_PERMISSIONS below — which mirrors frontend
    rbac.ts ROLE_PERMISSIONS verbatim plus the backend guard keys.

Caching: per-worker in-memory matrix with a 60s TTL, refreshed eagerly on
save and on /auth/login + /auth/me (force=True). Multi-worker propagation of
an edit is therefore bounded at ~60s.
"""

import logging
import time
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Role, User

logger = logging.getLogger(__name__)

MATRIX_TTL_SECONDS = 60

# ── Permission catalog ───────────────────────────────────────────────
# Frontend keys (must stay in sync with frontend/src/lib/rbac.ts Permission).
_FRONTEND_PERMISSIONS = (
    "dashboard", "contracts", "groups", "postSigning", "renewals",
    "vendors", "reports", "upload", "organizations", "relationships",
    "kpiApprovals", "surveys", "askAi", "usage", "settings",
    "admin", "superadmin",
    "contract.edit", "contract.editFields", "sla.edit", "extraction.configure",
)
# Backend guard keys (API-layer capabilities; deliberately distinct from the
# UI keys where the role sets differ — e.g. kpiApprovals nav is admin-only
# but kpi.approve capability is admin+legal).
_BACKEND_PERMISSIONS = (
    "contracts.write",
    "admin.aiSettings",
    "surveys.manageTemplates", "surveys.manageInstances",
    "businessUnits.manage",
    "dashboard.admin", "dashboard.legal", "dashboard.procurement",
    "organizations.write", "organizations.delete",
    "relationships.write", "relationships.delete",
    "services.write", "services.delete",
    "contractDocuments.write",
    "externalUsers.manage",
    "kpi.approve",
    "usage.viewCost",
)
PERMISSIONS: frozenset[str] = frozenset(_FRONTEND_PERMISSIONS + _BACKEND_PERMISSIONS)

# ── Default matrix ───────────────────────────────────────────────────
# UI portions mirror frontend rbac.ts ROLE_PERMISSIONS verbatim; backend keys
# are granted so that every pre-existing endpoint guard keeps its exact
# access set (proven by tests/test_rbac_permissions.py equivalence tests).
DEFAULT_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "super_admin": frozenset({
        # Stored/advertised UI permissions only — enforcement-wise super_admin
        # bypasses all checks via the has_permission() floor.
        "superadmin", "extraction.configure", "contract.edit", "contract.editFields",
    }),
    "admin": frozenset({
        "dashboard", "contracts", "groups", "postSigning", "renewals",
        "vendors", "reports", "upload",
        "organizations", "relationships", "kpiApprovals", "surveys",
        "askAi", "usage", "settings", "admin",
        "contract.edit", "contract.editFields", "sla.edit", "extraction.configure",
        # backend capabilities
        "contracts.write", "admin.aiSettings",
        "surveys.manageTemplates", "surveys.manageInstances",
        "businessUnits.manage",
        "dashboard.admin", "dashboard.legal", "dashboard.procurement",
        "organizations.write", "organizations.delete",
        "relationships.write", "relationships.delete",
        "services.write", "services.delete",
        "contractDocuments.write", "externalUsers.manage",
        "kpi.approve", "usage.viewCost",
    }),
    "legal": frozenset({
        "dashboard", "contracts", "groups", "postSigning", "renewals",
        "reports", "upload",
        "organizations", "relationships", "surveys", "askAi", "usage",
        "contract.edit", "contract.editFields", "sla.edit",
        # backend capabilities
        "contracts.write", "surveys.manageInstances", "dashboard.legal",
        "organizations.write", "relationships.write", "services.write",
        "contractDocuments.write", "externalUsers.manage", "kpi.approve",
    }),
    "procurement": frozenset({
        "dashboard", "contracts", "groups", "postSigning", "renewals",
        "vendors", "upload",
        "organizations", "relationships", "askAi", "usage",
        "contract.editFields",
        # backend capabilities
        "contracts.write", "dashboard.procurement",
    }),
    "bu_head": frozenset({
        "dashboard", "contracts", "groups", "postSigning", "renewals",
        "vendors", "reports", "usage",
        # backend capabilities
        "contracts.write",
    }),
    "viewer": frozenset({
        "dashboard", "contracts", "groups", "postSigning", "renewals",
        "reports", "usage",
    }),
}

ROLE_DESCRIPTIONS = {
    "super_admin": "Platform operator across all tenants (permissions are a floor — always passes)",
    "admin": "Tenant administrator",
    "legal": "Legal team — contract and governance workflows",
    "procurement": "Procurement team — vendor-facing workflows",
    "bu_head": "Business-unit head — BU-scoped portfolio",
    "viewer": "Read-only portfolio access",
}

# ── Per-worker cache ─────────────────────────────────────────────────
_matrix: dict[str, frozenset[str]] | None = None
_loaded_at: float = 0.0


def reset_permissions_cache() -> None:
    """Testing/ops helper: drop the cached matrix."""
    global _matrix, _loaded_at
    _matrix = None
    _loaded_at = 0.0


async def get_matrix(db: AsyncSession, force: bool = False) -> dict[str, frozenset[str]]:
    """Effective role→permission matrix (DB-backed, cached, default-fallback)."""
    global _matrix, _loaded_at
    if not force and _matrix is not None and (time.monotonic() - _loaded_at) < MATRIX_TTL_SECONDS:
        return _matrix
    try:
        from app.models.role_permission import RolePermission

        rows = (await db.execute(select(RolePermission.role_name, RolePermission.permission))).all()
        if rows:
            loaded: dict[str, set[str]] = {}
            for role_name, permission in rows:
                loaded.setdefault(role_name, set()).add(permission)
            # Roles with no rows (e.g. a role stripped to nothing) resolve to empty.
            _matrix = {role.value: frozenset(loaded.get(role.value, set())) for role in Role}
            _loaded_at = time.monotonic()
            return _matrix
        # Empty tables: fresh boot before seed, or test DB — use defaults.
        _matrix = dict(DEFAULT_ROLE_PERMISSIONS)
        _loaded_at = time.monotonic()
        return _matrix
    except Exception:  # noqa: BLE001 — auth must never hard-fail on the matrix
        logger.warning("Role-permission matrix load failed; using last-known/defaults", exc_info=True)
        if _matrix is None:
            _matrix = dict(DEFAULT_ROLE_PERMISSIONS)
            _loaded_at = time.monotonic()
        return _matrix


def effective_matrix() -> dict[str, frozenset[str]]:
    """Currently cached matrix (defaults if never loaded). Sync, no I/O."""
    return _matrix if _matrix is not None else DEFAULT_ROLE_PERMISSIONS


def has_permission(user: User, *permissions: str) -> bool:
    """Whether the user holds ANY of the given permissions.

    super_admin always passes — a hard security floor, not DB-configurable.
    Reads the cached matrix (no I/O); callers on cold paths should have
    awaited get_matrix() first (require_permission does).
    """
    if user.role == Role.SUPER_ADMIN:
        return True
    granted = effective_matrix().get(user.role.value, frozenset())
    return any(p in granted for p in permissions)


async def user_has_permission(db: AsyncSession, user: User, *permissions: str) -> bool:
    """has_permission with a (cached) matrix refresh — for inline endpoint checks."""
    await get_matrix(db)
    return has_permission(user, *permissions)


def require_permission(*permissions: str):
    """Dependency factory: allow users holding ANY of the given permissions.

    Replaces the hardcoded role-list guards; the role→permission grants live
    in the DB matrix (defaults in DEFAULT_ROLE_PERMISSIONS).
    """
    from app.core.deps import get_current_active_user
    from app.database import get_db

    async def permission_checker(
        current_user: Annotated[User, Depends(get_current_active_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> User:
        await get_matrix(db)
        if not has_permission(current_user, *permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required permission: {' or '.join(permissions)}",
            )
        return current_user

    return permission_checker


async def seed_default_role_permissions(db: AsyncSession) -> int:
    """Seed the six roles + default grants — ONLY when the roles table is
    empty, so super-admin edits survive restarts. Returns rows inserted."""
    from app.models.role_permission import RoleDef, RolePermission

    existing = (await db.execute(select(RoleDef.name).limit(1))).scalar_one_or_none()
    if existing is not None:
        return 0

    inserted = 0
    for role in Role:
        db.add(RoleDef(
            name=role.value,
            description=ROLE_DESCRIPTIONS.get(role.value),
            is_system=True,
        ))
        for permission in sorted(DEFAULT_ROLE_PERMISSIONS.get(role.value, frozenset())):
            db.add(RolePermission(role_name=role.value, permission=permission))
            inserted += 1
    await db.commit()
    logger.info("Seeded default role-permission matrix (%d grants for %d roles)", inserted, len(Role))
    return inserted
