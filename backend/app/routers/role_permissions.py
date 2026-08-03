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

from app.core.deps import SuperAdminUser
from app.core.permissions import PERMISSIONS, get_matrix
from app.database import get_db
from app.models.audit import AuditAction
from app.models.role_permission import RoleDef, RolePermission
from app.core.audit import log_audit

router = APIRouter(prefix="/api/admin/role-permissions", tags=["Role Permissions"])

ADMIN_LOCKOUT_FLOOR = {"admin", "settings"}


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
