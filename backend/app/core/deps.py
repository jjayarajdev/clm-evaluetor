"""FastAPI dependencies for authentication and authorization."""

import uuid
from contextvars import ContextVar
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.core.logging import user_id_var
from app.database import get_db
from app.models.user import Role, User
from app.models.tenant import Tenant


# HTTP Bearer token security scheme
security = HTTPBearer()

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

    # Set tenant context
    if user.tenant_id:
        tenant_id_var.set(user.tenant_id)

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
    async def role_checker(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        # Super admin can access everything
        if current_user.is_super_admin:
            return current_user

        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}",
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


# Pre-configured role dependencies
require_admin = require_role(Role.ADMIN)
require_legal = require_role(Role.ADMIN, Role.LEGAL)
require_procurement = require_role(Role.ADMIN, Role.PROCUREMENT)


# Type aliases for cleaner annotations
CurrentUser = Annotated[User, Depends(get_current_active_user)]
CurrentTenantId = Annotated[uuid.UUID | None, Depends(get_current_tenant_id)]
RequiredTenantId = Annotated[uuid.UUID, Depends(require_tenant)]
AdminUser = Annotated[User, Depends(require_admin)]
LegalUser = Annotated[User, Depends(require_legal)]
ProcurementUser = Annotated[User, Depends(require_procurement)]
SuperAdminUser = Annotated[User, Depends(require_super_admin())]
