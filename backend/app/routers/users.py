"""User management router."""

import math
import uuid as uuid_mod
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import AdminUser, CurrentUser, CurrentTenantId
from app.database import get_db
from app.models.user import Role
from app.schemas.user import (
    UserCreate,
    UserFilter,
    UserListResponse,
    UserPasswordUpdate,
    UserResponse,
    UserUpdate,
)
from app.services.users import UserService

router = APIRouter(prefix="/api/users", tags=["Users"])


def user_to_response(user) -> UserResponse:
    """Convert User model to UserResponse schema."""
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
        tenant_id=str(user.tenant_id) if user.tenant_id else None,
        tenant_name=user.tenant.name if user.tenant else None,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("", response_model=UserListResponse)
async def list_users(
    admin: AdminUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    role: Role | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    filter_tenant_id: str | None = Query(None, alias="tenant_id"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> UserListResponse:
    """List all users with optional filters (admin only).

    Args:
        admin: Authenticated admin user.
        tenant_id: Current tenant ID from auth (None for super admin).
        db: Database session.
        role: Filter by role.
        is_active: Filter by active status.
        search: Search in username/email.
        filter_tenant_id: Optional tenant filter (super admin only).
        page: Page number.
        page_size: Results per page.

    Returns:
        Paginated list of users.
    """
    # Super admins can filter by a specific tenant via query param
    effective_tenant_id = tenant_id
    if tenant_id is None and filter_tenant_id:
        effective_tenant_id = uuid_mod.UUID(filter_tenant_id)

    service = UserService(db, tenant_id=effective_tenant_id)
    filters = UserFilter(role=role, is_active=is_active, search=search)

    users, total = await service.list_users(filters, page, page_size)

    return UserListResponse(
        users=[user_to_response(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    admin: AdminUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Create a new user (admin only).

    Super admins can specify tenant_id in the request body to create users
    in any tenant. Regular admins create users in their own tenant.

    Args:
        data: User creation data.
        admin: Authenticated admin user.
        tenant_id: Current tenant ID from JWT.
        db: Database session.

    Returns:
        Created user.
    """
    # Super admin can target any tenant via request body
    effective_tenant_id = tenant_id
    if admin.role == Role.SUPER_ADMIN and data.tenant_id:
        effective_tenant_id = uuid_mod.UUID(data.tenant_id)
    elif admin.role == Role.SUPER_ADMIN and not data.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Super admin must specify tenant_id when creating a user",
        )

    service = UserService(db, tenant_id=effective_tenant_id)

    try:
        user = await service.create(data)
        await db.commit()
        return user_to_response(user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_details(
    current_user: CurrentUser,
) -> UserResponse:
    """Get current user's full details.

    Args:
        current_user: Authenticated user.

    Returns:
        Current user details.
    """
    return user_to_response(current_user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Get user by ID.

    Args:
        user_id: User's UUID.
        current_user: Authenticated user.
        tenant_id: Current tenant ID for isolation.
        db: Database session.

    Returns:
        User details.

    Notes:
        - Admin can view any user in their tenant
        - Non-admin can only view themselves
    """
    # Non-admin can only view themselves
    if current_user.role != Role.ADMIN and str(current_user.id) != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    service = UserService(db, tenant_id=tenant_id)
    user = await service.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user_to_response(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    data: UserUpdate,
    admin: AdminUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Update a user (admin only).

    Args:
        user_id: User's UUID.
        data: Update data.
        admin: Authenticated admin user.
        tenant_id: Current tenant ID for isolation.
        db: Database session.

    Returns:
        Updated user.
    """
    service = UserService(db, tenant_id=tenant_id)
    user = await service.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    try:
        updated = await service.update(user, data)
        await db.commit()
        await db.refresh(updated)
        return user_to_response(updated)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/{user_id}/password", response_model=UserResponse)
async def update_user_password(
    user_id: str,
    data: UserPasswordUpdate,
    admin: AdminUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Update a user's password (admin only).

    Args:
        user_id: User's UUID.
        data: New password data.
        admin: Authenticated admin user.
        tenant_id: Current tenant ID for isolation.
        db: Database session.

    Returns:
        Updated user.
    """
    service = UserService(db, tenant_id=tenant_id)
    user = await service.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    updated = await service.update_password(user, data.new_password)
    await db.commit()
    await db.refresh(updated)
    return user_to_response(updated)


@router.delete("/{user_id}", response_model=UserResponse)
async def deactivate_user(
    user_id: str,
    admin: AdminUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Deactivate a user (soft delete, admin only).

    Args:
        user_id: User's UUID.
        admin: Authenticated admin user.
        tenant_id: Current tenant ID for isolation.
        db: Database session.

    Returns:
        Deactivated user.

    Notes:
        Admin cannot deactivate themselves.
    """
    # Prevent self-deactivation
    if str(admin.id) == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate yourself",
        )

    service = UserService(db, tenant_id=tenant_id)
    user = await service.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    deactivated = await service.deactivate(user)
    await db.commit()
    await db.refresh(deactivated)
    return user_to_response(deactivated)


@router.post("/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: str,
    admin: AdminUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Reactivate a deactivated user (admin only).

    Args:
        user_id: User's UUID.
        admin: Authenticated admin user.
        tenant_id: Current tenant ID for isolation.
        db: Database session.

    Returns:
        Activated user.
    """
    service = UserService(db, tenant_id=tenant_id)
    user = await service.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    activated = await service.activate(user)
    await db.commit()
    await db.refresh(activated)
    return user_to_response(activated)
