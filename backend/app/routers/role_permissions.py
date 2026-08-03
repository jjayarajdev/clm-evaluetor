"""Super-admin editor for the platform role→permission matrix.

The matrix is platform-wide (no tenant scoping) and is THE source of truth for
both backend endpoint guards and the frontend permission list. Guardrails:
  * super_admin's row is immutable (its access is a hard code-level floor)
  * the admin role must keep 'admin' + 'settings' (lockout prevention)
  * permission keys must exist in the catalog
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import AdminUser, RequiredTenantId, SuperAdminUser
from app.core.permissions import (
    ADMIN_LOCKOUT_FLOOR,
    PERMISSIONS,
    TENANT_EDITABLE_ROLES,
    get_matrix,
    validate_tenant_override,
)
from app.database import get_db
from app.models.audit import AuditAction
from app.models.role_permission import RoleDef, RolePermission
from app.core.audit import log_audit

router = APIRouter(prefix="/api/admin/role-permissions", tags=["Role Permissions"])

# Tenant-admin variant: per-tenant overrides layered on the platform matrix.
tenant_router = APIRouter(
    prefix="/api/admin/tenant-role-permissions", tags=["Role Permissions"]
)


class RolePermissionsUpdate(BaseModel):
    permissions: list[str] = Field(..., max_length=200)


class RoleRow(BaseModel):
    name: str
    description: str | None
    is_system: bool
    permissions: list[str]


@router.get("")
async def get_role_permissions(
    current_user: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """The full matrix + permission catalog."""
    matrix = await get_matrix(db, force=True)
    roles = (await db.execute(select(RoleDef).order_by(RoleDef.name))).scalars().all()
    role_rows = [
        RoleRow(
            name=r.name,
            description=r.description,
            is_system=r.is_system,
            permissions=sorted(matrix.get(r.name, frozenset())),
        )
        for r in roles
    ]
    # Before first seed (or in tests) the roles table may be empty — expose
    # the effective (default) matrix so the editor is never blank.
    if not role_rows:
        role_rows = [
            RoleRow(name=name, description=None, is_system=True, permissions=sorted(perms))
            for name, perms in matrix.items()
        ]
    return {
        "catalog": sorted(PERMISSIONS),
        "roles": [r.model_dump() for r in role_rows],
    }


@router.put("/{role_name}")
async def update_role_permissions(
    role_name: str,
    body: RolePermissionsUpdate,
    request: Request,
    current_user: SuperAdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Replace a role's permission set (platform-wide)."""
    role = (
        await db.execute(select(RoleDef).where(RoleDef.name == role_name))
    ).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    if role_name == "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The super_admin role is immutable — its access is a platform floor.",
        )

    requested = set(body.permissions)
    unknown = requested - PERMISSIONS
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown permission keys: {sorted(unknown)}",
        )
    if role_name == "admin" and not ADMIN_LOCKOUT_FLOOR.issubset(requested):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The admin role must keep 'admin' and 'settings' (lockout prevention).",
        )

    await db.execute(sa_delete(RolePermission).where(RolePermission.role_name == role_name))
    for permission in sorted(requested):
        db.add(RolePermission(role_name=role_name, permission=permission))

    await log_audit(
        db=db,
        action=AuditAction.SETTINGS_UPDATE,
        user_id=str(current_user.id),
        resource_type="role_permissions",
        resource_id=role_name,
        details={"permissions": sorted(requested)},
        request=request,
    )
    await db.commit()

    matrix = await get_matrix(db, force=True)
    return {
        "name": role_name,
        "permissions": sorted(matrix.get(role_name, frozenset())),
    }


# ═════ Tenant-admin overrides ════════════════════════════════════════
# A tenant admin can tailor role permissions for THEIR tenant only. An
# override fully replaces that role's platform grants for the tenant;
# removing the override restores platform defaults. Stored in
# tenant.config_overrides["role_permissions"] and applied per request by
# get_current_user → set_request_role_overrides.


async def _get_tenant(db: AsyncSession, tenant_id):
    from app.models.tenant import Tenant

    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


@tenant_router.get("")
async def get_tenant_role_permissions(
    current_user: AdminUser,
    tenant_id: RequiredTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """The tenant's effective matrix: platform defaults + this tenant's overrides."""
    matrix = await get_matrix(db, force=True)
    tenant = await _get_tenant(db, tenant_id)
    overrides = (tenant.config_overrides or {}).get("role_permissions") or {}

    roles = []
    for role_name in TENANT_EDITABLE_ROLES:
        platform = sorted(matrix.get(role_name, frozenset()))
        overridden = role_name in overrides
        roles.append({
            "name": role_name,
            "platform_permissions": platform,
            "permissions": sorted(overrides[role_name]) if overridden else platform,
            "overridden": overridden,
        })
    # Tenant admins may grant anything in the catalog except forbidden keys.
    catalog = sorted(PERMISSIONS - {"superadmin"})
    return {"catalog": catalog, "roles": roles}


@tenant_router.put("/{role_name}")
async def set_tenant_role_override(
    role_name: str,
    body: RolePermissionsUpdate,
    request: Request,
    current_user: AdminUser,
    tenant_id: RequiredTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Create/replace this tenant's override for one role."""
    requested = set(body.permissions)
    error = validate_tenant_override(role_name, requested)
    if error:
        code = (
            status.HTTP_404_NOT_FOUND
            if role_name not in TENANT_EDITABLE_ROLES
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=code, detail=error)

    tenant = await _get_tenant(db, tenant_id)
    overrides = dict((tenant.config_overrides or {}).get("role_permissions") or {})
    overrides[role_name] = sorted(requested)
    tenant.config_overrides = {**(tenant.config_overrides or {}), "role_permissions": overrides}

    await log_audit(
        db=db,
        action=AuditAction.SETTINGS_UPDATE,
        user_id=str(current_user.id),
        resource_type="tenant_role_permissions",
        resource_id=role_name,
        details={"permissions": sorted(requested)},
        request=request,
    )
    await db.commit()
    return {"name": role_name, "permissions": sorted(requested), "overridden": True}


@tenant_router.delete("/{role_name}")
async def reset_tenant_role_override(
    role_name: str,
    request: Request,
    current_user: AdminUser,
    tenant_id: RequiredTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Remove this tenant's override for one role (back to platform defaults)."""
    if role_name not in TENANT_EDITABLE_ROLES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    tenant = await _get_tenant(db, tenant_id)
    overrides = dict((tenant.config_overrides or {}).get("role_permissions") or {})
    overrides.pop(role_name, None)
    new_config = {**(tenant.config_overrides or {})}
    if overrides:
        new_config["role_permissions"] = overrides
    else:
        new_config.pop("role_permissions", None)
    tenant.config_overrides = new_config

    await log_audit(
        db=db,
        action=AuditAction.SETTINGS_UPDATE,
        user_id=str(current_user.id),
        resource_type="tenant_role_permissions",
        resource_id=role_name,
        details={"reset": True},
        request=request,
    )
    await db.commit()

    matrix = await get_matrix(db, force=True)
    return {
        "name": role_name,
        "permissions": sorted(matrix.get(role_name, frozenset())),
        "overridden": False,
    }
