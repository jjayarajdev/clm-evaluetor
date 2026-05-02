"""API endpoints for External Portal access (no authentication required)."""

from decimal import Decimal
from uuid import UUID
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.contract import Contract
from app.models.contract_share import ContractShare
from app.models.contract_comment import ContractComment
from app.models.external_user import ExternalUser
from app.models.external_access import ExternalAccessToken, TokenType
from app.models.kpi import KPI, PerceptionScore, PerceptionGap
from app.models.improvement import ImprovementPoint
from app.models.relationship import BusinessRelationship
from app.models.obligation import Obligation
from app.models.sla import ContractSLA
from app.services.kpi_service import recalculate_gap
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


async def validate_governance_token(
    token: str,
    db: AsyncSession,
) -> tuple[ExternalAccessToken, ExternalUser]:
    """Validate an external access token for governance/perception scoring.

    Accepts PERCEPTION_SCORING or MULTI_PURPOSE token types and requires
    the token to have a relationship_id linked.

    Returns:
        Tuple of (token, external_user).

    Raises:
        HTTPException: If token is invalid, expired, or wrong type.
    """
    # Get token — accept perception scoring or multi-purpose types
    token_query = select(ExternalAccessToken).where(
        ExternalAccessToken.token == token,
        ExternalAccessToken.token_type.in_([
            TokenType.PERCEPTION_SCORING,
            TokenType.MULTI_PURPOSE,
        ]),
    )
    access_token = (await db.execute(token_query)).scalar_one_or_none()

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unsupported access token",
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

    # Require relationship_id on the token
    if not access_token.relationship_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token is not linked to a business relationship",
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

    # Record token use
    access_token.record_use()
    external_user.record_access()

    return access_token, external_user


class ExternalScoreSubmission(BaseModel):
    """Request body for external perception score submission."""
    kpi_id: UUID = Field(..., description="KPI to score")
    score: float = Field(..., ge=1, le=10, description="Score from 1-10")
    period: str = Field(..., description="Scoring period, e.g. '2026-Q2'")
    comments: Optional[str] = Field(None, description="Optional comments")


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
            "contract_type": contract.contract_type or None,
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
        "contract_type": contract.contract_type or None,
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


@router.get("/contracts/{contract_id}/governance")
async def get_contract_governance(
    contract_id: str,
    token: str = Query(..., description="Access token"),
    db: AsyncSession = Depends(get_db),
):
    """View governance data (KPIs, improvements) linked to a shared contract.

    Uses the contract's business_relationship_id to find the relationship,
    then returns KPIs with latest scores/gaps and improvement points.
    Works with CONTRACT_ACCESS tokens.
    """
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

    share.record_access()
    await db.commit()

    # Get the contract and its relationship link
    contract_result = await db.execute(
        select(Contract).where(Contract.id == UUID(contract_id))
    )
    contract = contract_result.scalar_one_or_none()

    if not contract or not contract.business_relationship_id:
        return {
            "has_governance": False,
            "relationship": None,
            "kpis": [],
            "improvements": [],
        }

    relationship_id = contract.business_relationship_id

    # Load the business relationship with orgs
    rel_result = await db.execute(
        select(BusinessRelationship).where(
            BusinessRelationship.id == relationship_id,
        ).options(
            selectinload(BusinessRelationship.org_a),
            selectinload(BusinessRelationship.org_b),
        )
    )
    relationship = rel_result.scalar_one_or_none()

    if not relationship:
        return {
            "has_governance": False,
            "relationship": None,
            "kpis": [],
            "improvements": [],
        }

    # Load KPIs
    kpis_result = await db.execute(
        select(KPI).where(
            KPI.relationship_id == relationship_id,
            KPI.is_active == True,
        ).order_by(KPI.category, KPI.name)
    )
    kpis = kpis_result.scalars().all()

    kpi_items = []
    for kpi in kpis:
        # Latest approved scores
        scores_result = await db.execute(
            select(PerceptionScore).where(
                PerceptionScore.kpi_id == kpi.id,
                PerceptionScore.approval_status == "approved",
            ).order_by(PerceptionScore.scored_at.desc()).limit(4)
        )
        recent_scores = scores_result.scalars().all()

        # Latest gap
        gap_result = await db.execute(
            select(PerceptionGap).where(
                PerceptionGap.kpi_id == kpi.id,
            ).order_by(PerceptionGap.period.desc()).limit(1)
        )
        latest_gap = gap_result.scalar_one_or_none()

        kpi_items.append({
            "id": str(kpi.id),
            "name": kpi.name,
            "description": kpi.description,
            "category": kpi.category,
            "measurement_type": kpi.measurement_type,
            "target_value": float(kpi.target_value) if kpi.target_value else None,
            "weight": float(kpi.weight) if kpi.weight else None,
            "is_perception_based": kpi.is_perception_based,
            "recent_scores": [
                {
                    "id": str(s.id),
                    "score": float(s.score),
                    "period": s.period,
                    "is_internal": s.is_internal,
                    "scored_at": s.scored_at.isoformat() if s.scored_at else None,
                }
                for s in recent_scores
            ],
            "latest_gap": {
                "period": latest_gap.period,
                "internal_score": float(latest_gap.internal_score) if latest_gap.internal_score else None,
                "external_score": float(latest_gap.external_score) if latest_gap.external_score else None,
                "gap": float(latest_gap.gap) if latest_gap.gap else None,
                "gap_severity": latest_gap.gap_severity,
                "requires_action": latest_gap.requires_action,
            } if latest_gap else None,
        })

    # Load improvements
    improvements_result = await db.execute(
        select(ImprovementPoint).where(
            ImprovementPoint.relationship_id == relationship_id,
        ).order_by(ImprovementPoint.priority.desc(), ImprovementPoint.created_at.desc())
    )
    improvements = improvements_result.scalars().all()

    improvement_items = []
    for imp in improvements:
        kpi_name = None
        if imp.kpi_id:
            kpi_result = await db.execute(
                select(KPI.name).where(KPI.id == imp.kpi_id)
            )
            kpi_name = kpi_result.scalar_one_or_none()

        improvement_items.append({
            "id": str(imp.id),
            "title": imp.title,
            "description": imp.description,
            "source": imp.source,
            "priority": imp.priority,
            "status": imp.status,
            "kpi_name": kpi_name,
            "due_date": imp.due_date.isoformat() if imp.due_date else None,
            "target_outcome": imp.target_outcome,
            "actual_outcome": imp.actual_outcome,
            "impact_score": imp.impact_score,
            "created_at": imp.created_at.isoformat() if imp.created_at else None,
        })

    org_a_name = relationship.org_a.name if relationship.org_a else None
    org_b_name = relationship.org_b.name if relationship.org_b else None

    return {
        "has_governance": True,
        "relationship": {
            "id": str(relationship.id),
            "name": relationship.name,
            "relationship_type": relationship.relationship_type,
            "status": relationship.status,
            "org_a_name": org_a_name,
            "org_b_name": org_b_name,
            "health_score": relationship.health_score,
            "governance_tier": relationship.governance_tier,
        },
        "kpis": kpi_items,
        "improvements": improvement_items,
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


# ---------------------------------------------------------------------------
# External Governance Endpoints (perception scoring, KPI view, improvements)
# ---------------------------------------------------------------------------


@router.get("/governance")
async def get_external_governance(
    token: str = Query(..., description="Access token"),
    db: AsyncSession = Depends(get_db),
):
    """View governance dashboard for a business relationship.

    Returns relationship info, KPIs with latest scores, and gap summary.
    Requires a PERCEPTION_SCORING or MULTI_PURPOSE token.
    """
    access_token, external_user = await validate_governance_token(token, db)
    await db.commit()

    relationship_id = access_token.relationship_id

    # Load the business relationship
    rel_result = await db.execute(
        select(BusinessRelationship).where(
            BusinessRelationship.id == relationship_id,
        ).options(
            selectinload(BusinessRelationship.org_a),
            selectinload(BusinessRelationship.org_b),
        )
    )
    relationship = rel_result.scalar_one_or_none()

    if not relationship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business relationship not found",
        )

    # Load KPIs for this relationship (lazy="dynamic" — use separate query)
    kpis_result = await db.execute(
        select(KPI).where(
            KPI.relationship_id == relationship_id,
            KPI.is_active == True,
        ).order_by(KPI.category, KPI.name)
    )
    kpis = kpis_result.scalars().all()

    # Build KPI data with latest scores and gaps
    kpi_items = []
    for kpi in kpis:
        # Get latest approved scores for this KPI
        latest_score_result = await db.execute(
            select(PerceptionScore).where(
                PerceptionScore.kpi_id == kpi.id,
                PerceptionScore.approval_status == "approved",
            ).order_by(PerceptionScore.scored_at.desc()).limit(5)
        )
        recent_scores = latest_score_result.scalars().all()

        # Get latest gap for this KPI
        gap_result = await db.execute(
            select(PerceptionGap).where(
                PerceptionGap.kpi_id == kpi.id,
            ).order_by(PerceptionGap.period.desc()).limit(1)
        )
        latest_gap = gap_result.scalar_one_or_none()

        kpi_items.append({
            "id": str(kpi.id),
            "name": kpi.name,
            "code": kpi.code,
            "description": kpi.description,
            "category": kpi.category,
            "measurement_type": kpi.measurement_type,
            "target_value": float(kpi.target_value) if kpi.target_value else None,
            "weight": float(kpi.weight) if kpi.weight else None,
            "is_perception_based": kpi.is_perception_based,
            "recent_scores": [
                {
                    "id": str(s.id),
                    "score": float(s.score),
                    "period": s.period,
                    "is_internal": s.is_internal,
                    "scored_at": s.scored_at.isoformat() if s.scored_at else None,
                }
                for s in recent_scores
            ],
            "latest_gap": {
                "period": latest_gap.period,
                "internal_score": float(latest_gap.internal_score) if latest_gap.internal_score else None,
                "external_score": float(latest_gap.external_score) if latest_gap.external_score else None,
                "gap": float(latest_gap.gap) if latest_gap.gap else None,
                "gap_severity": latest_gap.gap_severity,
                "requires_action": latest_gap.requires_action,
            } if latest_gap else None,
        })

    # Build gap summary across all KPIs
    all_gaps_result = await db.execute(
        select(PerceptionGap).join(KPI, PerceptionGap.kpi_id == KPI.id).where(
            KPI.relationship_id == relationship_id,
            KPI.is_active == True,
        ).order_by(PerceptionGap.period.desc())
    )
    all_gaps = all_gaps_result.scalars().all()

    # Count gaps by severity (use the most recent period per KPI)
    seen_kpis = set()
    severity_counts = {"minor": 0, "moderate": 0, "significant": 0, "critical": 0}
    action_required_count = 0
    for gap in all_gaps:
        if gap.kpi_id in seen_kpis:
            continue
        seen_kpis.add(gap.kpi_id)
        if gap.gap_severity:
            severity_counts[gap.gap_severity] = severity_counts.get(gap.gap_severity, 0) + 1
        if gap.requires_action:
            action_required_count += 1

    # Get org names for display
    org_a_name = relationship.org_a.name if relationship.org_a else None
    org_b_name = relationship.org_b.name if relationship.org_b else None

    return {
        "relationship": {
            "id": str(relationship.id),
            "name": relationship.name,
            "relationship_type": relationship.relationship_type,
            "status": relationship.status,
            "org_a_name": org_a_name,
            "org_b_name": org_b_name,
            "health_score": relationship.health_score,
            "governance_tier": relationship.governance_tier,
            "next_review_date": relationship.next_review_date.isoformat() if relationship.next_review_date else None,
        },
        "kpis": kpi_items,
        "gap_summary": {
            "total_kpis": len(kpis),
            "severity_counts": severity_counts,
            "action_required": action_required_count,
        },
    }


@router.post("/governance/score", status_code=status.HTTP_201_CREATED)
async def submit_external_score(
    score_data: ExternalScoreSubmission,
    token: str = Query(..., description="Access token"),
    db: AsyncSession = Depends(get_db),
):
    """Submit an external perception score for a KPI.

    Creates a PerceptionScore with is_internal=False, auto-approved.
    Recalculates the perception gap for the scored KPI/period.
    """
    access_token, external_user = await validate_governance_token(token, db)

    relationship_id = access_token.relationship_id

    # Verify the KPI belongs to the token's relationship
    kpi_result = await db.execute(
        select(KPI).where(
            KPI.id == score_data.kpi_id,
            KPI.relationship_id == relationship_id,
            KPI.is_active == True,
        )
    )
    kpi = kpi_result.scalar_one_or_none()

    if not kpi:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KPI not found or not linked to this relationship",
        )

    # External user must have an organization_id for scorer_org_id
    if not external_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="External user is not linked to an organization",
        )

    # Create the perception score
    perception_score = PerceptionScore(
        kpi_id=score_data.kpi_id,
        scorer_org_id=external_user.organization_id,
        scored_by_user_id=None,  # External user — no internal user ID
        score=Decimal(str(score_data.score)),
        period=score_data.period,
        comments=score_data.comments,
        is_internal=False,
        approval_status="approved",  # Auto-approve external submissions
        approved_at=datetime.utcnow(),
    )
    db.add(perception_score)
    await db.commit()
    await db.refresh(perception_score)

    # Recalculate gap for this KPI/period
    await recalculate_gap(kpi_id=score_data.kpi_id, period=score_data.period, db=db)

    return {
        "id": str(perception_score.id),
        "kpi_id": str(perception_score.kpi_id),
        "kpi_name": kpi.name,
        "score": float(perception_score.score),
        "period": perception_score.period,
        "comments": perception_score.comments,
        "is_internal": perception_score.is_internal,
        "approval_status": perception_score.approval_status,
        "scored_at": perception_score.scored_at.isoformat() if perception_score.scored_at else None,
    }


@router.get("/governance/improvements")
async def get_external_improvements(
    token: str = Query(..., description="Access token"),
    db: AsyncSession = Depends(get_db),
):
    """View improvement points for a business relationship.

    Returns non-sensitive improvement points filtered to the token's
    relationship. Internal audit details and owner information are excluded.
    """
    access_token, external_user = await validate_governance_token(token, db)
    await db.commit()

    relationship_id = access_token.relationship_id

    # Load improvement points for this relationship (lazy="dynamic" — separate query)
    improvements_result = await db.execute(
        select(ImprovementPoint).where(
            ImprovementPoint.relationship_id == relationship_id,
        ).order_by(ImprovementPoint.priority.desc(), ImprovementPoint.created_at.desc())
    )
    improvements = improvements_result.scalars().all()

    items = []
    for imp in improvements:
        # Get KPI name if linked
        kpi_name = None
        if imp.kpi_id:
            kpi_result = await db.execute(
                select(KPI.name).where(KPI.id == imp.kpi_id)
            )
            kpi_name = kpi_result.scalar_one_or_none()

        items.append({
            "id": str(imp.id),
            "title": imp.title,
            "description": imp.description,
            "source": imp.source,
            "priority": imp.priority,
            "status": imp.status,
            "kpi_name": kpi_name,
            "due_date": imp.due_date.isoformat() if imp.due_date else None,
            "target_outcome": imp.target_outcome,
            "actual_outcome": imp.actual_outcome,
            "impact_score": imp.impact_score,
            "created_at": imp.created_at.isoformat() if imp.created_at else None,
            "updated_at": imp.updated_at.isoformat() if imp.updated_at else None,
        })

    return {
        "improvements": items,
        "total": len(items),
    }
