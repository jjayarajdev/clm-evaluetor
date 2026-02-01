"""FastAPI dependencies for authentication and authorization."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.database import get_db
from app.models.user import Role, User


# HTTP Bearer token security scheme
security = HTTPBearer()


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
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in allowed_roles]}",
            )
        return current_user

    return role_checker


# Pre-configured role dependencies
require_admin = require_role(Role.ADMIN)
require_legal = require_role(Role.ADMIN, Role.LEGAL)
require_procurement = require_role(Role.ADMIN, Role.PROCUREMENT)


# Type aliases for cleaner annotations
CurrentUser = Annotated[User, Depends(get_current_active_user)]
AdminUser = Annotated[User, Depends(require_admin)]
LegalUser = Annotated[User, Depends(require_legal)]
ProcurementUser = Annotated[User, Depends(require_procurement)]
