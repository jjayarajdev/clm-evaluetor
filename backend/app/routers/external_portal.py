"""API endpoints for External Portal access (no authentication required)."""

from uuid import UUID
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.contract import Contract
from app.models.contract_share import ContractShare
from app.models.contract_comment import ContractComment
from app.models.external_user import ExternalUser
from app.models.external_access import ExternalAccessToken, TokenType
from app.models.obligation import Obligation
from app.models.sla import ContractSLA
from app.schemas.contract_comment import (
    ContractCommentCreate,
    ContractCommentResponse,
    ContractCommentListResponse,
)

router = APIRouter(prefix="/api/external", tags=["External Portal"])


async def validate_token(
    token: str,
    db: AsyncSession,
    require_contract: bool = False,
) -> tuple[ExternalAccessToken, ExternalUser, ContractShare | None]:
    """Validate an external access token and return related objects.

    Args:
        token: The access token string.
        db: Database session.
        require_contract: If True, require a contract share to exist.

    Returns:
        Tuple of (token, external_user, contract_share).

    Raises:
        HTTPException: If token is invalid or expired.
    """
    # Get token
    token_query = select(ExternalAccessToken).where(
        ExternalAccessToken.token == token,
        ExternalAccessToken.token_type == TokenType.CONTRACT_ACCESS,
    )
    access_token = (await db.execute(token_query)).scalar_one_or_none()

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        )

    if not access_token.is_valid:
        if access_token.is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access token has been revoked",
            )
        if datetime.utcnow() > access_token.expires_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access token has expired",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is no longer valid",
        )

    # Get external user
    if not access_token.external_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token not linked to external user",
        )

    ext_user_query = select(ExternalUser).where(
        ExternalUser.id == access_token.external_user_id,
        ExternalUser.is_active == True,
    )
    external_user = (await db.execute(ext_user_query)).scalar_one_or_none()

    if not external_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="External user not found or inactive",
        )

    # Get contract share if token has contract_id
    contract_share = None
    if access_token.contract_id:
        share_query = select(ContractShare).where(
            ContractShare.contract_id == access_token.contract_id,
            ContractShare.external_user_id == external_user.id,
            ContractShare.is_revoked == False,
        )
        contract_share = (await db.execute(share_query)).scalar_one_or_none()

        if require_contract and not contract_share:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this contract",
            )

    # Record token use
    access_token.record_use()
    external_user.record_access()

    return access_token, external_user, contract_share


@router.get("/validate")
async def validate_access_token(
    token: str = Query(..., description="Access token"),
    db: AsyncSession = Depends(get_db),
):
    """Validate an access token and return user/contract info."""
    access_token, external_user, contract_share = await validate_token(token, db)
    await db.commit()

    # Get all active shares for this user
    shares_query = select(ContractShare).where(
        ContractShare.external_user_id == external_user.id,
        ContractShare.is_revoked == False,
    )
    result = await db.execute(shares_query)
    shares = result.scalars().all()

    # Filter to only include non-expired shares
    active_shares = [s for s in shares if s.is_active]

    return {
        "valid": True,
        "external_user": {
            "id": str(external_user.id),
            "email": external_user.email,
            "full_name": external_user.full_name,
            "company_name": external_user.company_name,
        },
        "contracts": [
            {
                "id": str(s.contract_id),
                "filename": s.contract.filename if s.contract else None,
                "can_download": s.can_download,
                "can_comment": s.can_comment,
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
            }
            for s in active_shares
        ],
        "token_expires_at": access_token.expires_at.isoformat(),
    }


@router.get("/contracts")
async def list_shared_contracts(
    token: str = Query(..., description="Access token"),
    db: AsyncSession = Depends(get_db),
):
    """List all contracts shared with the external user."""
    access_token, external_user, _ = await validate_token(token, db)
    await db.commit()

    # Get all active shares
    shares_query = select(ContractShare).where(
        ContractShare.external_user_id == external_user.id,
        ContractShare.is_revoked == False,
    )
    result = await db.execute(shares_query)
    shares = result.scalars().all()

    contracts = []
    for share in shares:
        if not share.is_active:
            continue

        contract = share.contract
        if not contract:
            continue

        contracts.append({
            "id": str(contract.id),
            "filename": contract.filename,
            "contract_type": contract.contract_type.value if contract.contract_type else None,
            "counterparty": contract.counterparty,
            "effective_date": contract.effective_date.isoformat() if contract.effective_date else None,
            "expiration_date": contract.expiration_date.isoformat() if contract.expiration_date else None,
            "status": contract.status.value,
            "can_download": share.can_download,
            "can_comment": share.can_comment,
            "shared_at": share.created_at.isoformat(),
            "expires_at": share.expires_at.isoformat() if share.expires_at else None,
        })

    return {
        "contracts": contracts,
        "total": len(contracts),
    }


@router.get("/contracts/{contract_id}")
async def get_shared_contract(
    contract_id: str,
    token: str = Query(..., description="Access token"),
    db: AsyncSession = Depends(get_db),
):
    """View a shared contract's details."""
    access_token, external_user, _ = await validate_token(token, db)

    # Verify access to this specific contract
    share_query = select(ContractShare).where(
        ContractShare.contract_id == UUID(contract_id),
        ContractShare.external_user_id == external_user.id,
        ContractShare.is_revoked == False,
    )
    share = (await db.execute(share_query)).scalar_one_or_none()

    if not share or not share.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this contract",
        )

    # Record access
    share.record_access()
    await db.commit()

    contract = share.contract
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found",
        )

    # Load obligations for this contract
    obligations_result = await db.execute(
        select(Obligation)
        .where(Obligation.contract_id == contract.id)
        .order_by(Obligation.deadline.asc().nullslast())
    )
    obligations = obligations_result.scalars().all()

    # Load SLAs for this contract
    sla_result = await db.execute(
        select(ContractSLA)
        .where(ContractSLA.contract_id == contract.id, ContractSLA.is_active == True)
    )
    slas = sla_result.scalars().all()

    # Build response with full context for external user
    return {
        "id": str(contract.id),
        "filename": contract.filename,
        "contract_type": contract.contract_type.value if contract.contract_type else None,
        "counterparty": contract.counterparty,
        "effective_date": contract.effective_date.isoformat() if contract.effective_date else None,
        "expiration_date": contract.expiration_date.isoformat() if contract.expiration_date else None,
        "contract_value": float(contract.contract_value) if contract.contract_value else None,
        "currency": contract.currency,
        "jurisdiction": contract.jurisdiction,
        "governing_law": contract.governing_law,
        "status": contract.status.value,
        "risk_level": contract.risk_level.value if contract.risk_level else None,
        "risk_score": contract.risk_score,
        "auto_renewal": contract.auto_renewal,
        "notice_period_days": contract.notice_period_days,
        "summary": getattr(contract, 'ai_summary', None),
        "clauses": [
            {
                "id": str(c.id),
                "clause_type": c.clause_type.value if c.clause_type else None,
                "title": getattr(c, 'title', None),
                "text": c.text[:800] + "..." if c.text and len(c.text) > 800 else c.text,
                "section_number": c.section_number,
                "risk_level": c.risk_level.value if hasattr(c, 'risk_level') and c.risk_level else None,
            }
            for c in (contract.clauses or [])[:30]
        ],
        "obligations": [
            {
                "id": str(o.id),
                "description": o.description,
                "obligation_type": o.obligation_type.value if hasattr(o.obligation_type, 'value') else str(o.obligation_type) if o.obligation_type else None,
                "responsible_party": o.obligated_party,
                "deadline": o.deadline.isoformat() if o.deadline else None,
                "status": o.status.value if hasattr(o.status, 'value') else o.status,
                "priority": o.priority,
                "is_critical": o.is_critical,
                "consequence": o.consequence_of_breach,
            }
            for o in obligations
        ],
        "slas": [
            {
                "id": str(s.id),
                "sla_name": s.sla_name,
                "sla_description": s.sla_description,
                "metric_type": s.metric_type.value if s.metric_type else None,
                "metric_unit": s.metric_unit.value if hasattr(s.metric_unit, 'value') else s.metric_unit,
                "target_value": float(s.target_value) if s.target_value else None,
                "target_operator": s.target_operator,
                "severity": s.severity.value if s.severity else None,
                "current_compliance_rate": float(s.current_compliance_rate) if s.current_compliance_rate else None,
                "measurement_period": s.measurement_period,
                "has_penalty": s.has_penalty,
                "penalty_description": s.penalty_description,
            }
            for s in slas
        ],
        "can_download": share.can_download,
        "can_comment": share.can_comment,
        "shared_message": share.message,
    }


@router.get("/contracts/{contract_id}/download")
async def download_shared_contract(
    contract_id: str,
    token: str = Query(..., description="Access token"),
    db: AsyncSession = Depends(get_db),
):
    """Download a shared contract file."""
    access_token, external_user, _ = await validate_token(token, db)

    # Verify access to this specific contract
    share_query = select(ContractShare).where(
        ContractShare.contract_id == UUID(contract_id),
        ContractShare.external_user_id == external_user.id,
        ContractShare.is_revoked == False,
    )
    share = (await db.execute(share_query)).scalar_one_or_none()

    if not share or not share.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this contract",
        )

    if not share.can_download:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Download not permitted for this share",
        )

    contract = share.contract
    if not contract or not contract.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract file not found",
        )

    # Record access
    share.record_access()
    await db.commit()

    # Stream the file
    import os
    from pathlib import Path

    file_path = Path(contract.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract file not found on disk",
        )

    def iterfile():
        with open(file_path, "rb") as f:
            yield from f

    return StreamingResponse(
        iterfile(),
        media_type=contract.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{contract.filename}"',
            "Content-Length": str(os.path.getsize(file_path)),
        },
    )


@router.get("/contracts/{contract_id}/view")
async def view_shared_contract(
    contract_id: str,
    token: str = Query(..., description="Access token"),
    db: AsyncSession = Depends(get_db),
):
    """View a shared contract file inline (no download permission required)."""
    access_token, external_user, _ = await validate_token(token, db)

    # Verify access to this specific contract
    share_query = select(ContractShare).where(
        ContractShare.contract_id == UUID(contract_id),
        ContractShare.external_user_id == external_user.id,
        ContractShare.is_revoked == False,
    )
    share = (await db.execute(share_query)).scalar_one_or_none()

    if not share or not share.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this contract",
        )

    contract = share.contract
    if not contract or not contract.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract file not found",
        )

    # Record access
    share.record_access()
    await db.commit()

    # Stream the file inline (for preview)
    import os
    from pathlib import Path

    file_path = Path(contract.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract file not found on disk",
        )

    def iterfile():
        with open(file_path, "rb") as f:
            yield from f

    return StreamingResponse(
        iterfile(),
        media_type=contract.mime_type or "application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{contract.filename}"',
            "Content-Length": str(os.path.getsize(file_path)),
        },
    )


@router.get("/contracts/{contract_id}/comments", response_model=ContractCommentListResponse)
async def list_shared_contract_comments(
    contract_id: str,
    token: str = Query(..., description="Access token"),
    db: AsyncSession = Depends(get_db),
):
    """List comments on a shared contract (excluding internal comments)."""
    access_token, external_user, _ = await validate_token(token, db)

    # Verify access
    share_query = select(ContractShare).where(
        ContractShare.contract_id == UUID(contract_id),
        ContractShare.external_user_id == external_user.id,
        ContractShare.is_revoked == False,
    )
    share = (await db.execute(share_query)).scalar_one_or_none()

    if not share or not share.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this contract",
        )

    await db.commit()

    # Get non-internal comments
    comments_query = select(ContractComment).where(
        ContractComment.contract_id == UUID(contract_id),
        ContractComment.is_deleted == False,
        ContractComment.is_internal == False,  # External users can't see internal comments
    ).order_by(ContractComment.created_at.desc())

    result = await db.execute(comments_query)
    comments = result.scalars().all()

    items = []
    for comment in comments:
        # Count replies (also excluding internal)
        reply_count_query = select(func.count()).select_from(ContractComment).where(
            ContractComment.parent_id == comment.id,
            ContractComment.is_deleted == False,
            ContractComment.is_internal == False,
        )
        reply_count = (await db.execute(reply_count_query)).scalar() or 0

        items.append(ContractCommentResponse(
            id=comment.id,
            contract_id=comment.contract_id,
            user_id=comment.user_id,
            external_user_id=comment.external_user_id,
            parent_id=comment.parent_id,
            content=comment.content,
            clause_id=comment.clause_id,
            section_reference=comment.section_reference,
            is_internal=comment.is_internal,
            is_resolved=comment.is_resolved,
            resolved_by_id=comment.resolved_by_id,
            resolved_at=comment.resolved_at,
            is_deleted=comment.is_deleted,
            author_name=comment.author_name,
            author_email=comment.author_email,
            is_internal_author=comment.is_internal_author,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            reply_count=reply_count,
        ))

    return ContractCommentListResponse(items=items, total=len(items))


@router.post("/contracts/{contract_id}/comments", response_model=ContractCommentResponse, status_code=status.HTTP_201_CREATED)
async def add_external_comment(
    contract_id: str,
    comment_data: ContractCommentCreate,
    token: str = Query(..., description="Access token"),
    db: AsyncSession = Depends(get_db),
):
    """Add a comment to a shared contract (as external user)."""
    access_token, external_user, _ = await validate_token(token, db)

    # Verify access
    share_query = select(ContractShare).where(
        ContractShare.contract_id == UUID(contract_id),
        ContractShare.external_user_id == external_user.id,
        ContractShare.is_revoked == False,
    )
    share = (await db.execute(share_query)).scalar_one_or_none()

    if not share or not share.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this contract",
        )

    if not share.can_comment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Commenting not permitted for this share",
        )

    # External users cannot create internal comments
    if comment_data.is_internal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="External users cannot create internal comments",
        )

    # Validate parent_id if provided
    if comment_data.parent_id:
        parent_query = select(ContractComment).where(
            ContractComment.id == comment_data.parent_id,
            ContractComment.contract_id == UUID(contract_id),
            ContractComment.is_deleted == False,
            ContractComment.is_internal == False,  # Can only reply to non-internal
        )
        parent = (await db.execute(parent_query)).scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent comment not found",
            )

    # Create comment
    comment = ContractComment(
        contract_id=UUID(contract_id),
        external_user_id=external_user.id,
        parent_id=comment_data.parent_id,
        content=comment_data.content,
        clause_id=comment_data.clause_id,
        section_reference=comment_data.section_reference,
        is_internal=False,  # Always false for external users
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return ContractCommentResponse(
        id=comment.id,
        contract_id=comment.contract_id,
        user_id=comment.user_id,
        external_user_id=comment.external_user_id,
        parent_id=comment.parent_id,
        content=comment.content,
        clause_id=comment.clause_id,
        section_reference=comment.section_reference,
        is_internal=comment.is_internal,
        is_resolved=comment.is_resolved,
        resolved_by_id=comment.resolved_by_id,
        resolved_at=comment.resolved_at,
        is_deleted=comment.is_deleted,
        author_name=comment.author_name,
        author_email=comment.author_email,
        is_internal_author=comment.is_internal_author,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        reply_count=0,
    )
