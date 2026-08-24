"""Authentication router for login and user info."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.audit import get_client_ip, get_user_agent, log_audit
from app.core.deps import CurrentUser
from app.core.security import (
    TIMING_EQUALIZATION_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models.audit import AuditAction
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    TokenResponse,
    UserInfo,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    login_request: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Authenticate user and return JWT token.

    Args:
        login_request: Login credentials (username/password).
        request: FastAPI request for audit logging.
        db: Database session.

    Returns:
        TokenResponse with access token and user info.

    Raises:
        HTTPException: If credentials are invalid.
    """
    # Find user by username
    result = await db.execute(
        select(User).where(User.username == login_request.username)
    )
    user = result.scalar_one_or_none()

    # Verify user exists and password is correct. Always run the bcrypt check —
    # against a dummy hash when the user doesn't exist — so response timing
    # doesn't reveal which usernames are valid.
    password_ok = verify_password(
        login_request.password,
        user.password_hash if user else TIMING_EQUALIZATION_HASH,
    )
    if user is None or not password_ok:
        # Log failed login attempt
        await log_audit(
            db=db,
            action=AuditAction.LOGIN_FAILED,
            details={"username": login_request.username, "reason": "invalid_credentials"},
            request=request,
        )
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        # Log failed login for inactive user
        await log_audit(
            db=db,
            action=AuditAction.LOGIN_FAILED,
            user_id=str(user.id),
            details={"reason": "account_deactivated"},
            request=request,
        )
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    # Log successful login
    await log_audit(
        db=db,
        action=AuditAction.LOGIN,
        user_id=str(user.id),
        resource_type="user",
        resource_id=str(user.id),
        request=request,
    )
    await db.commit()

    # Create access token
    access_token = create_access_token(
        user_id=str(user.id),
        username=user.username,
        role=user.role.value,
        tenant_id=str(user.tenant_id) if user.tenant_id else None,
        business_unit_id=str(user.business_unit_id) if user.business_unit_id else None,
    )

    # Get tenant name if user has a tenant
    tenant_name = None
    if user.tenant_id and user.tenant:
        tenant_name = user.tenant.name

    from app.core.permissions import get_effective_permissions

    effective_permissions = await get_effective_permissions(db, user)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expiration_hours * 3600,
        user=UserInfo(
            id=str(user.id),
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role.value,
            preferred_language=user.preferred_language,
            tenant_id=str(user.tenant_id) if user.tenant_id else None,
            tenant_name=tenant_name,
            business_unit_id=str(user.business_unit_id) if user.business_unit_id else None,
            business_unit_name=user.business_unit.name if user.business_unit else None,
            permissions=effective_permissions,
        ),
    )


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserInfo:
    """Get current authenticated user's information.

    Args:
        current_user: Authenticated user from token.

    Returns:
        UserInfo with user details.
    """
    from app.core.permissions import get_effective_permissions

    effective_permissions = await get_effective_permissions(db, current_user)

    tenant_name = None
    if current_user.tenant_id and current_user.tenant:
        tenant_name = current_user.tenant.name

    return UserInfo(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        preferred_language=current_user.preferred_language,
        tenant_id=str(current_user.tenant_id) if current_user.tenant_id else None,
        tenant_name=tenant_name,
        business_unit_id=str(current_user.business_unit_id) if current_user.business_unit_id else None,
        business_unit_name=current_user.business_unit.name if current_user.business_unit else None,
        permissions=effective_permissions,
    )


@router.post("/logout")
async def logout(
    current_user: CurrentUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Logout current user.

    Note: JWT tokens are stateless, so this endpoint is mainly
    for audit logging. Client should discard the token.

    Args:
        current_user: Authenticated user.
        request: FastAPI request for audit logging.
        db: Database session.

    Returns:
        Success message.
    """
    # Log logout
    await log_audit(
        db=db,
        action=AuditAction.LOGOUT,
        user_id=str(current_user.id),
        resource_type="user",
        resource_id=str(current_user.id),
        request=request,
    )
    await db.commit()

    return {"message": "Successfully logged out"}


@router.post("/change-password")
async def change_password(
    data: PasswordChangeRequest,
    current_user: CurrentUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Change the authenticated user's own password.

    Self-service: any authenticated user can change their own password after
    proving they know the current one. (Admins changing *other* users' passwords
    use PUT /users/{id}/password instead.)

    Args:
        data: Current and new password.
        current_user: Authenticated user (the one being changed).
        request: FastAPI request for audit logging.
        db: Database session.

    Returns:
        Success message.

    Raises:
        HTTPException: 400 if the current password is incorrect.
    """
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.password_hash = hash_password(data.new_password)

    await log_audit(
        db=db,
        action=AuditAction.USER_UPDATE,
        user_id=str(current_user.id),
        resource_type="user",
        resource_id=str(current_user.id),
        request=request,
        details={"action": "self_password_change"},
    )
    await db.commit()

    return {"message": "Password changed successfully"}
