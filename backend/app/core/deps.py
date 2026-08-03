"""FastAPI dependencies for authentication and authorization."""

import uuid
from contextvars import ContextVar
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import decode_token
from app.core.logging import user_id_var
from app.database import get_db
from app.models.user import Role, User
from app.models.tenant import Tenant


# HTTP Bearer token security scheme
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)

# Context variable for current tenant
tenant_id_var: ContextVar[Optional[uuid.UUID]] = ContextVar("tenant_id", default=None)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Extract and validate the current user from JWT token.

    Args:
        credentials: Bearer token from Authorization header.
        db: Database session.

    Returns:
        The authenticated User object.

    Raises:
        HTTPException: If token is invalid or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise credentials_exception

    # Get user from database
    result = await db.execute(
        select(User).where(User.id == payload.sub)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    # Set user context for logging
    user_id_var.set(str(user.id))

    # Set tenant context (incl. the LLM factory's context, so per-tenant AI
    # provider is resolved for any AI call made during this request).
    if user.tenant_id:
        tenant_id_var.set(user.tenant_id)
        from app.core.llm import current_tenant_id, set_request_azure
        current_tenant_id.set(str(user.tenant_id))
        # Load this tenant's AI-provider config fresh from the DB — authoritative
        # across all workers (the in-memory cache only updates the worker that saved).
        try:
            from app.models.tenant import Tenant
            co = (await db.execute(
                select(Tenant.config_overrides).where(Tenant.id == user.tenant_id)
            )).scalar_one_or_none() or {}
            set_request_azure(co.get("azure_openai"))
        except Exception:  # noqa: BLE001 — never block auth on this
            pass

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current user and verify they are active.

    Args:
        current_user: User from get_current_user dependency.

    Returns:
        The active User object.

    Raises:
        HTTPException: If user is not active.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


async def get_current_tenant_id(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> uuid.UUID | None:
    """Get the current tenant ID from the authenticated user.

    Super admins return None (can access all tenants).
    Regular users return their tenant_id.

    Args:
        current_user: The authenticated user.

    Returns:
        The tenant UUID or None for super admins.
    """
    if current_user.is_super_admin:
        return None
    return current_user.tenant_id


async def require_tenant(
    request: Request,
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> uuid.UUID:
    """Require a valid tenant context.

    This dependency ensures the user belongs to a tenant.
    Super admins can specify a tenant via X-Tenant-ID header.

    Args:
        request: The FastAPI request object.
        current_user: The authenticated user.

    Returns:
        The tenant UUID.

    Raises:
        HTTPException: If no tenant context is available.
    """
    # Check for X-Tenant-ID header (for super admins)
    tenant_id_header = request.headers.get("X-Tenant-ID")

    if current_user.is_super_admin:
        if tenant_id_header:
            try:
                return uuid.UUID(tenant_id_header)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid X-Tenant-ID header format",
                )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Super admin must specify X-Tenant-ID header",
        )

    if current_user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with a tenant",
        )
    return current_user.tenant_id


async def get_current_business_unit_id(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> uuid.UUID | None:
    """Get the current business unit ID from the authenticated user.

    Users without a business unit return None (can access all BUs in their tenant).
    """
    return current_user.business_unit_id


def require_role(*allowed_roles: Role):
    """Create a dependency that requires specific roles.

    Args:
        allowed_roles: Roles that are allowed to access the endpoint.

    Returns:
        A dependency function that validates user role.

    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(
            user: User = Depends(require_role(Role.ADMIN))
        ):
            ...
    """
    # Accept both calling conventions — require_role(Role.ADMIN, Role.LEGAL)
    # and require_role(["admin", "legal"]) — and normalize to role values.
    # Many routers use the list form; with strict varargs it made every
    # membership check fail, so non-super-admins got a 500 on those endpoints.
    role_values: list[str] = []
    for entry in allowed_roles:
        items = entry if isinstance(entry, (list, tuple, set)) else [entry]
        for item in items:
            role_values.append(item.value if isinstance(item, Role) else str(item))

    async def role_checker(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        # Super admin can access everything
        if current_user.is_super_admin:
            return current_user

        if current_user.role.value not in role_values:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {role_values}",
            )
        return current_user

    return role_checker


def require_super_admin():
    """Create a dependency that requires super admin role.

    Returns:
        A dependency function that validates super admin role.
    """
    async def super_admin_checker(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if not current_user.is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Super admin required.",
            )
        return current_user

    return super_admin_checker


async def require_admin_if_enterprise(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(optional_security)
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Optional[User]:
    """Enforce admin auth only when SECURITY_PROFILE=enterprise.

    In the default "demo" profile these endpoints stay open (legacy behavior);
    enterprise deployments require an active admin or super admin.
    """
    if settings.security_profile != "enterprise":
        return None

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_current_user(credentials, db)
    if not user.is_super_admin and user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin role required.",
        )
    return user


# Permission-based guards — the role→permission grants live in the DB matrix
# (app/core/permissions.py; defaults mirror today's role lists exactly).
from app.core.permissions import has_permission, require_permission, user_has_permission  # noqa: E402

require_admin = require_permission("admin")

# Any role that may modify contract data — by default everyone except
# read-only VIEWER (super_admin passes the has_permission floor).
require_write = require_permission("contracts.write")

# Deprecated aliases — zero call sites; kept for backward compatibility.
require_legal = require_role(Role.ADMIN, Role.LEGAL)
require_procurement = require_role(Role.ADMIN, Role.PROCUREMENT)
require_bu_head = require_role(Role.ADMIN, Role.BU_HEAD)


# Type aliases for cleaner annotations
CurrentUser = Annotated[User, Depends(get_current_active_user)]
CurrentTenantId = Annotated[uuid.UUID | None, Depends(get_current_tenant_id)]
CurrentBusinessUnitId = Annotated[uuid.UUID | None, Depends(get_current_business_unit_id)]
RequiredTenantId = Annotated[uuid.UUID, Depends(require_tenant)]
AdminUser = Annotated[User, Depends(require_admin)]
LegalUser = Annotated[User, Depends(require_legal)]
ProcurementUser = Annotated[User, Depends(require_procurement)]
BuHeadUser = Annotated[User, Depends(require_bu_head)]
SuperAdminUser = Annotated[User, Depends(require_super_admin())]
