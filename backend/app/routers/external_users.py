"""API endpoints for External User management."""

from uuid import UUID
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import get_current_user, require_role, RequiredTenantId
from app.models import User, Role, Organization
from app.models.external_user import ExternalUser
from app.models.contract_share import ContractShare
from app.models.external_access import ExternalAccessToken, TokenType
from app.models.contract import Contract
from app.schemas.external_user import (
    ExternalUserCreate,
    ExternalUserUpdate,
    ExternalUserInvite,
    ExternalUserResponse,
    ExternalUserListResponse,
    ExternalUserWithShares,
)

router = APIRouter(prefix="/external-users", tags=["External Users"])


@router.get("", response_model=ExternalUserListResponse)
async def list_external_users(
    tenant_id: RequiredTenantId,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    organization_id: Optional[UUID] = None,
    is_active: Optional[bool] = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List external users with filtering and pagination."""
    query = select(ExternalUser).where(ExternalUser.tenant_id == tenant_id)

    # Apply filters
    if search:
        search_filter = f"%{search}%"
        query = query.where(
            or_(
                ExternalUser.email.ilike(search_filter),
                ExternalUser.full_name.ilike(search_filter),
                ExternalUser.company_name.ilike(search_filter),
            )
        )

    if organization_id:
        query = query.where(ExternalUser.organization_id == organization_id)

    if is_active is not None:
        query = query.where(ExternalUser.is_active == is_active)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(ExternalUser.email)

    result = await db.execute(query)
    items = result.scalars().all()

    return ExternalUserListResponse(
        items=[ExternalUserResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("", response_model=ExternalUserResponse, status_code=status.HTTP_201_CREATED)
async def create_external_user(
    data: ExternalUserCreate,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.LEGAL)),
):
    """Create/invite a new external user."""
    # Check for existing user with same email in tenant
    existing_query = select(ExternalUser).where(
        ExternalUser.tenant_id == tenant_id,
        ExternalUser.email == data.email,
    )
    existing = (await db.execute(existing_query)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"External user with email '{data.email}' already exists",
        )

    # Validate organization_id if provided
    if data.organization_id:
        org_query = select(Organization).where(
            Organization.id == data.organization_id,
            Organization.tenant_id == tenant_id,
        )
        org = (await db.execute(org_query)).scalar_one_or_none()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization not found",
            )

    external_user = ExternalUser(
        tenant_id=tenant_id,
        invited_by_id=current_user.id,
        invited_at=datetime.utcnow(),
        **data.model_dump(),
    )
    db.add(external_user)
    await db.commit()
    await db.refresh(external_user)

    return ExternalUserResponse.model_validate(external_user)


@router.post("/invite", response_model=dict, status_code=status.HTTP_201_CREATED)
async def invite_external_user(
    data: ExternalUserInvite,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.LEGAL)),
):
    """Invite an external user and optionally share contracts with them."""
    # Check for existing user or create new one
    existing_query = select(ExternalUser).where(
        ExternalUser.tenant_id == tenant_id,
        ExternalUser.email == data.email,
    )
    external_user = (await db.execute(existing_query)).scalar_one_or_none()

    if external_user:
        # Reactivate if inactive
        if not external_user.is_active:
            external_user.is_active = True
            external_user.invited_by_id = current_user.id
            external_user.invited_at = datetime.utcnow()
    else:
        # Create new external user
        external_user = ExternalUser(
            tenant_id=tenant_id,
            email=data.email,
            full_name=data.full_name,
            company_name=data.company_name,
            organization_id=data.organization_id,
            invited_by_id=current_user.id,
            invited_at=datetime.utcnow(),
        )
        db.add(external_user)
        await db.flush()

    # Create shares for each contract
    shares_created = []
    for contract_id in data.contract_ids:
        # Verify contract exists and belongs to tenant
        contract_query = select(Contract).where(
            Contract.id == contract_id,
            Contract.tenant_id == tenant_id,
        )
        contract = (await db.execute(contract_query)).scalar_one_or_none()
        if not contract:
            continue  # Skip invalid contracts

        # Check if share already exists
        existing_share_query = select(ContractShare).where(
            ContractShare.contract_id == contract_id,
            ContractShare.external_user_id == external_user.id,
            ContractShare.is_revoked == False,
        )
        existing_share = (await db.execute(existing_share_query)).scalar_one_or_none()
        if existing_share:
            continue  # Skip if already shared

        # Calculate expiration
        expires_at = None
        if data.expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=data.expires_in_days)

        # Create share
        share = ContractShare(
            contract_id=contract_id,
            external_user_id=external_user.id,
            shared_by_id=current_user.id,
            can_download=data.can_download,
            can_comment=data.can_comment,
            expires_at=expires_at,
            message=data.message,
        )
        db.add(share)
        shares_created.append(share)

    # Create access token for the external user
    access_token = ExternalAccessToken.create_token(
        token_type=TokenType.CONTRACT_ACCESS,
        expires_in_days=data.expires_in_days or 30,
        external_user_id=external_user.id,
        recipient_email=data.email,
        recipient_name=data.full_name,
        max_uses=None,  # Unlimited uses
        created_by_id=current_user.id,
    )
    db.add(access_token)

    await db.commit()
    await db.refresh(external_user)

    return {
        "external_user": ExternalUserResponse.model_validate(external_user).model_dump(),
        "shares_created": len(shares_created),
        "access_token": access_token.token,
        "access_url": f"/external/contracts?token={access_token.token}",
    }


@router.get("/{external_user_id}", response_model=ExternalUserWithShares)
async def get_external_user(
    external_user_id: UUID,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get external user by ID with share count."""
    query = select(ExternalUser).where(
        ExternalUser.id == external_user_id,
        ExternalUser.tenant_id == tenant_id,
    )
    result = await db.execute(query)
    external_user = result.scalar_one_or_none()

    if not external_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External user not found",
        )

    # Get share count
    share_count_query = select(func.count()).select_from(ContractShare).where(
        ContractShare.external_user_id == external_user_id,
        ContractShare.is_revoked == False,
    )
    share_count = (await db.execute(share_count_query)).scalar() or 0

    response = ExternalUserWithShares.model_validate(external_user)
    response.shared_contracts_count = share_count
    return response


@router.put("/{external_user_id}", response_model=ExternalUserResponse)
async def update_external_user(
    external_user_id: UUID,
    data: ExternalUserUpdate,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.LEGAL)),
):
    """Update an external user."""
    query = select(ExternalUser).where(
        ExternalUser.id == external_user_id,
        ExternalUser.tenant_id == tenant_id,
    )
    result = await db.execute(query)
    external_user = result.scalar_one_or_none()

    if not external_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External user not found",
        )

    # Check for duplicate email if changing
    if data.email and data.email != external_user.email:
        conflict_query = select(ExternalUser).where(
            ExternalUser.tenant_id == tenant_id,
            ExternalUser.email == data.email,
            ExternalUser.id != external_user_id,
        )
        existing = (await db.execute(conflict_query)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"External user with email '{data.email}' already exists",
            )

    # Validate organization_id if changing
    if data.organization_id is not None and data.organization_id != external_user.organization_id:
        org_query = select(Organization).where(
            Organization.id == data.organization_id,
            Organization.tenant_id == tenant_id,
        )
        org = (await db.execute(org_query)).scalar_one_or_none()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization not found",
            )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(external_user, field, value)

    await db.commit()
    await db.refresh(external_user)

    return ExternalUserResponse.model_validate(external_user)


@router.delete("/{external_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_external_user(
    external_user_id: UUID,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.LEGAL)),
):
    """Revoke an external user's access (deactivate)."""
    query = select(ExternalUser).where(
        ExternalUser.id == external_user_id,
        ExternalUser.tenant_id == tenant_id,
    )
    result = await db.execute(query)
    external_user = result.scalar_one_or_none()

    if not external_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External user not found",
        )

    # Deactivate user
    external_user.is_active = False

    # Revoke all active shares
    shares_query = select(ContractShare).where(
        ContractShare.external_user_id == external_user_id,
        ContractShare.is_revoked == False,
    )
    shares = (await db.execute(shares_query)).scalars().all()
    for share in shares:
        share.revoke(current_user.id)

    # Revoke all active tokens
    tokens_query = select(ExternalAccessToken).where(
        ExternalAccessToken.external_user_id == external_user_id,
        ExternalAccessToken.is_revoked == False,
    )
    tokens = (await db.execute(tokens_query)).scalars().all()
    for token in tokens:
        token.revoke("User access revoked")

    await db.commit()


@router.post("/{external_user_id}/resend-invite", response_model=dict)
async def resend_invite(
    external_user_id: UUID,
    tenant_id: RequiredTenantId,
    expires_in_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.LEGAL)),
):
    """Resend invitation to an external user with a new token."""
    query = select(ExternalUser).where(
        ExternalUser.id == external_user_id,
        ExternalUser.tenant_id == tenant_id,
    )
    result = await db.execute(query)
    external_user = result.scalar_one_or_none()

    if not external_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External user not found",
        )

    if not external_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send invite to inactive user",
        )

    # Create new access token
    access_token = ExternalAccessToken.create_token(
        token_type=TokenType.CONTRACT_ACCESS,
        expires_in_days=expires_in_days,
        external_user_id=external_user.id,
        recipient_email=external_user.email,
        recipient_name=external_user.full_name,
        max_uses=None,
        created_by_id=current_user.id,
    )
    db.add(access_token)
    await db.commit()

    return {
        "external_user_id": str(external_user_id),
        "access_token": access_token.token,
        "access_url": f"/external/contracts?token={access_token.token}",
        "expires_at": access_token.expires_at.isoformat(),
    }


@router.get("/{external_user_id}/shares", response_model=dict)
async def get_external_user_shares(
    external_user_id: UUID,
    tenant_id: RequiredTenantId,
    include_revoked: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all contract shares for an external user."""
    # Verify user exists
    user_query = select(ExternalUser).where(
        ExternalUser.id == external_user_id,
        ExternalUser.tenant_id == tenant_id,
    )
    external_user = (await db.execute(user_query)).scalar_one_or_none()
    if not external_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External user not found",
        )

    # Get shares
    shares_query = select(ContractShare).where(
        ContractShare.external_user_id == external_user_id,
    )
    if not include_revoked:
        shares_query = shares_query.where(ContractShare.is_revoked == False)

    result = await db.execute(shares_query)
    shares = result.scalars().all()

    return {
        "external_user_id": str(external_user_id),
        "shares": [
            {
                "id": str(s.id),
                "contract_id": str(s.contract_id),
                "contract_filename": s.contract.filename if s.contract else None,
                "can_download": s.can_download,
                "can_comment": s.can_comment,
                "is_active": s.is_active,
                "is_revoked": s.is_revoked,
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                "access_count": s.access_count,
                "last_access_at": s.last_access_at.isoformat() if s.last_access_at else None,
                "created_at": s.created_at.isoformat(),
            }
            for s in shares
        ],
    }
