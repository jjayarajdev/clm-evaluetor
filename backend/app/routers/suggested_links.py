"""Suggested contract links router for AI-detected relationship management."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import log_audit
from app.core.deps import CurrentUser, CurrentTenantId
from app.database import get_db
from app.models.audit import AuditAction
from app.models.contract import Contract
from app.models.contract_link import ContractLink, LinkType
from app.models.suggested_link import SuggestedContractLink, SuggestionStatus
from app.schemas.suggested_link import (
    BatchReviewRequest,
    BatchReviewResponse,
    PendingSuggestionsResponse,
    SuggestedLinkResponse,
    SuggestedLinkReviewRequest,
    SuggestedLinkReviewResponse,
    SuggestedLinksListResponse,
)

router = APIRouter(prefix="/api/contracts", tags=["Suggested Links"])


# ============ ESTABLISHED CONTRACT LINKS ============


class ContractLinkBrief(BaseModel):
    """Brief contract info for link display."""

    id: str
    filename: str
    contract_type: str | None = None
    counterparty: str | None = None
    effective_date: str | None = None
    expiration_date: str | None = None
    risk_level: str | None = None
    status: str | None = None


class ContractLinkOut(BaseModel):
    """An established link between two contracts."""

    id: str
    link_type: str
    link_description: str | None = None
    direction: str  # "parent" or "child"
    effective_date: str | None = None
    reference_number: str | None = None
    is_active: bool = True
    linked_contract: ContractLinkBrief
    created_at: str | None = None


class ContractLinksResponse(BaseModel):
    """Response for established contract links."""

    links: list[ContractLinkOut]
    total: int


@router.get("/{contract_id}/links", response_model=ContractLinksResponse)
async def get_contract_links(
    contract_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContractLinksResponse:
    """Get established (approved) contract links for a contract.

    Returns both parent and child links with related contract details.
    """
    contract_uuid = uuid.UUID(contract_id)

    # Verify contract exists
    contract = await db.get(Contract, contract_uuid)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Get links where this contract is the parent
    child_query = (
        select(ContractLink)
        .where(
            ContractLink.parent_contract_id == contract_uuid,
            ContractLink.is_active == True,
        )
        .options(selectinload(ContractLink.child_contract))
    )
    child_result = await db.execute(child_query)
    child_links = child_result.scalars().all()

    # Get links where this contract is the child
    parent_query = (
        select(ContractLink)
        .where(
            ContractLink.child_contract_id == contract_uuid,
            ContractLink.is_active == True,
        )
        .options(selectinload(ContractLink.parent_contract))
    )
    parent_result = await db.execute(parent_query)
    parent_links = parent_result.scalars().all()

    links_out = []

    for link in child_links:
        c = link.child_contract
        links_out.append(ContractLinkOut(
            id=str(link.id),
            link_type=link.link_type if isinstance(link.link_type, str) else link.link_type.value,
            link_description=link.link_description,
            direction="child",
            effective_date=str(link.effective_date) if link.effective_date else None,
            reference_number=link.reference_number,
            is_active=link.is_active,
            linked_contract=ContractLinkBrief(
                id=str(c.id),
                filename=c.filename,
                contract_type=c.contract_type.value if c.contract_type else None,
                counterparty=c.counterparty,
                effective_date=str(c.effective_date) if c.effective_date else None,
                expiration_date=str(c.expiration_date) if c.expiration_date else None,
                risk_level=c.risk_level.value if c.risk_level else None,
                status=c.status.value if c.status else None,
            ),
            created_at=str(link.created_at) if link.created_at else None,
        ))

    for link in parent_links:
        c = link.parent_contract
        links_out.append(ContractLinkOut(
            id=str(link.id),
            link_type=link.link_type if isinstance(link.link_type, str) else link.link_type.value,
            link_description=link.link_description,
            direction="parent",
            effective_date=str(link.effective_date) if link.effective_date else None,
            reference_number=link.reference_number,
            is_active=link.is_active,
            linked_contract=ContractLinkBrief(
                id=str(c.id),
                filename=c.filename,
                contract_type=c.contract_type.value if c.contract_type else None,
                counterparty=c.counterparty,
                effective_date=str(c.effective_date) if c.effective_date else None,
                expiration_date=str(c.expiration_date) if c.expiration_date else None,
                risk_level=c.risk_level.value if c.risk_level else None,
                status=c.status.value if c.status else None,
            ),
            created_at=str(link.created_at) if link.created_at else None,
        ))

    return ContractLinksResponse(
        links=links_out,
        total=len(links_out),
    )


# ============ SUGGESTED CONTRACT LINKS ============


@router.get("/{contract_id}/suggested-links", response_model=SuggestedLinksListResponse)
async def get_suggested_links(
    contract_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: str | None = None,
) -> SuggestedLinksListResponse:
    """Get suggested links for a specific contract.

    Args:
        contract_id: ID of the contract to get suggestions for.
        current_user: Authenticated user.
        tenant_id: Current tenant ID.
        db: Database session.
        status_filter: Optional filter by status (pending, approved, rejected).

    Returns:
        List of suggested links with metadata.
    """
    # Verify contract exists
    contract = await db.get(Contract, uuid.UUID(contract_id))
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Build query — show suggestions where this contract is source OR target
    from sqlalchemy import or_
    contract_uuid = uuid.UUID(contract_id)
    query = (
        select(SuggestedContractLink)
        .where(or_(
            SuggestedContractLink.source_contract_id == contract_uuid,
            SuggestedContractLink.target_contract_id == contract_uuid,
        ))
        .options(
            selectinload(SuggestedContractLink.target_contract),
            selectinload(SuggestedContractLink.source_contract),
        )
        .order_by(SuggestedContractLink.confidence_score.desc())
    )

    if tenant_id:
        query = query.where(SuggestedContractLink.tenant_id == tenant_id)

    if status_filter:
        # Filter by status string (pending, approved, rejected, expired)
        query = query.where(SuggestedContractLink.status == status_filter)

    result = await db.execute(query)
    suggestions = result.scalars().all()

    # Count pending
    pending_count = sum(1 for s in suggestions if s.status == "pending")

    return SuggestedLinksListResponse(
        suggestions=[
            SuggestedLinkResponse.from_model(s) for s in suggestions
        ],
        total=len(suggestions),
        pending_count=pending_count,
    )


@router.post(
    "/{contract_id}/suggested-links/{suggestion_id}/review",
    response_model=SuggestedLinkReviewResponse,
)
async def review_suggested_link(
    contract_id: str,
    suggestion_id: str,
    review: SuggestedLinkReviewRequest,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SuggestedLinkReviewResponse:
    """Review (approve/reject/modify) a suggested link.

    Args:
        contract_id: ID of the source contract.
        suggestion_id: ID of the suggestion to review.
        review: Review action and details.
        current_user: Authenticated user.
        tenant_id: Current tenant ID.
        request: FastAPI request for audit logging.
        db: Database session.

    Returns:
        Review result with created link ID if approved.
    """
    # Get the suggestion with related contracts
    # Accept either source or target contract_id so reviews work from either side
    from sqlalchemy import or_
    contract_uuid = uuid.UUID(contract_id)
    query = (
        select(SuggestedContractLink)
        .where(SuggestedContractLink.id == uuid.UUID(suggestion_id))
        .where(or_(
            SuggestedContractLink.source_contract_id == contract_uuid,
            SuggestedContractLink.target_contract_id == contract_uuid,
        ))
        .options(
            selectinload(SuggestedContractLink.source_contract),
            selectinload(SuggestedContractLink.target_contract),
        )
    )

    if tenant_id:
        query = query.where(SuggestedContractLink.tenant_id == tenant_id)

    result = await db.execute(query)
    suggestion = result.scalar_one_or_none()

    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Suggestion not found: {suggestion_id}",
        )

    if suggestion.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Suggestion already {suggestion.status}",
        )

    created_link_id = None
    message = ""

    if review.action == "approve":
        # Create the actual ContractLink
        # Use the string value directly (matches PostgreSQL enum)
        link_type = suggestion.suggested_link_type  # Already a string like "sow"

        # Determine parent/child based on direction
        if suggestion.suggested_direction == "source_is_child":
            parent_id = suggestion.target_contract_id
            child_id = suggestion.source_contract_id
        else:
            parent_id = suggestion.source_contract_id
            child_id = suggestion.target_contract_id

        # Check if link already exists
        existing = await db.execute(
            select(ContractLink).where(
                ContractLink.parent_contract_id == parent_id,
                ContractLink.child_contract_id == child_id,
                ContractLink.link_type == link_type,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This link already exists",
            )

        # Create the link
        contract_link = ContractLink(
            parent_contract_id=parent_id,
            child_contract_id=child_id,
            link_type=link_type,
            link_description=f"Auto-detected: {suggestion.reasoning}" if suggestion.reasoning else None,
            is_active=True,
        )
        db.add(contract_link)
        await db.flush()

        created_link_id = str(contract_link.id)
        suggestion.created_link_id = contract_link.id
        suggestion.status = "approved"
        message = f"Link created: {link_type}"

    elif review.action == "reject":
        suggestion.status = "rejected"
        message = "Suggestion rejected"

    elif review.action == "modify":
        if not review.modified_link_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="modified_link_type required for modify action",
            )

        try:
            new_link_type = LinkType(review.modified_link_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid link type: {review.modified_link_type}",
            )

        # Update suggestion type and approve
        suggestion.suggested_link_type = new_link_type.value  # Store string value

        # Create the link with modified type
        if suggestion.suggested_direction == "source_is_child":
            parent_id = suggestion.target_contract_id
            child_id = suggestion.source_contract_id
        else:
            parent_id = suggestion.source_contract_id
            child_id = suggestion.target_contract_id

        contract_link = ContractLink(
            parent_contract_id=parent_id,
            child_contract_id=child_id,
            link_type=new_link_type,
            link_description=f"Modified from AI suggestion: {suggestion.reasoning}" if suggestion.reasoning else None,
            is_active=True,
        )
        db.add(contract_link)
        await db.flush()

        created_link_id = str(contract_link.id)
        suggestion.created_link_id = contract_link.id
        suggestion.status = "approved"
        message = f"Link created with modified type: {new_link_type.value}"

    # Update review metadata
    suggestion.reviewed_by = current_user.id
    suggestion.reviewed_at = datetime.utcnow()

    await db.commit()

    # Audit log
    await log_audit(
        db=db,
        action=AuditAction.CONTRACT_VIEW,  # TODO: Add SUGGESTION_REVIEWED action
        user_id=str(current_user.id),
        resource_type="suggested_link",
        resource_id=suggestion_id,
        details={
            "action": review.action,
            "contract_id": contract_id,
            "created_link_id": created_link_id,
        },
        request=request,
    )

    return SuggestedLinkReviewResponse(
        suggestion_id=suggestion_id,
        action=review.action,
        status=suggestion.status,  # Already a string
        created_link_id=created_link_id,
        message=message,
    )


@router.get("/pending-suggestions", response_model=PendingSuggestionsResponse)
async def get_all_pending_suggestions(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
) -> PendingSuggestionsResponse:
    """Get all pending suggestions for the current tenant.

    Args:
        current_user: Authenticated user.
        tenant_id: Current tenant ID.
        db: Database session.
        limit: Maximum suggestions to return.

    Returns:
        All pending suggestions grouped by contract.
    """
    query = (
        select(SuggestedContractLink)
        .where(SuggestedContractLink.status == "pending")
        .options(selectinload(SuggestedContractLink.target_contract))
        .order_by(
            SuggestedContractLink.created_at.desc(),
            SuggestedContractLink.confidence_score.desc(),
        )
        .limit(limit)
    )

    if tenant_id:
        query = query.where(SuggestedContractLink.tenant_id == tenant_id)

    result = await db.execute(query)
    suggestions = result.scalars().all()

    # Group by contract
    by_contract: dict[str, int] = {}
    for s in suggestions:
        cid = str(s.source_contract_id)
        by_contract[cid] = by_contract.get(cid, 0) + 1

    return PendingSuggestionsResponse(
        total_pending=len(suggestions),
        by_contract=by_contract,
        suggestions=[SuggestedLinkResponse.from_model(s) for s in suggestions],
    )


@router.post(
    "/{contract_id}/suggested-links/batch-review",
    response_model=BatchReviewResponse,
)
async def batch_review_suggestions(
    contract_id: str,
    batch_review: BatchReviewRequest,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BatchReviewResponse:
    """Batch approve or reject multiple suggestions.

    Args:
        contract_id: ID of the source contract.
        batch_review: Batch review request with IDs and action.
        current_user: Authenticated user.
        tenant_id: Current tenant ID.
        request: FastAPI request for audit logging.
        db: Database session.

    Returns:
        Batch review results.
    """
    results: list[SuggestedLinkReviewResponse] = []
    succeeded = 0
    failed = 0

    for suggestion_id in batch_review.suggestion_ids:
        try:
            review_request = SuggestedLinkReviewRequest(
                action=batch_review.action,
                notes=batch_review.notes,
            )
            result = await review_suggested_link(
                contract_id=contract_id,
                suggestion_id=suggestion_id,
                review=review_request,
                current_user=current_user,
                tenant_id=tenant_id,
                request=request,
                db=db,
            )
            results.append(result)
            succeeded += 1
        except HTTPException as e:
            results.append(
                SuggestedLinkReviewResponse(
                    suggestion_id=suggestion_id,
                    action=batch_review.action,
                    status="error",
                    message=e.detail,
                )
            )
            failed += 1
        except Exception as e:
            results.append(
                SuggestedLinkReviewResponse(
                    suggestion_id=suggestion_id,
                    action=batch_review.action,
                    status="error",
                    message=str(e),
                )
            )
            failed += 1

    return BatchReviewResponse(
        processed=len(batch_review.suggestion_ids),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )


# -- Hierarchy detection endpoint --


class HierarchyDetectionRequest(BaseModel):
    """Request body for hierarchy detection."""
    contract_ids: list[str] | None = None  # Optional: specific contract IDs to analyse


class HierarchyDetectionResponse(BaseModel):
    """Response from hierarchy detection."""
    suggestions_created: int
    contracts_analysed: int
    message: str


@router.post(
    "/hierarchy-detect",
    response_model=HierarchyDetectionResponse,
    tags=["Hierarchy Detection"],
)
async def run_hierarchy_detection(
    body: HierarchyDetectionRequest | None = None,
    current_user: CurrentUser = None,
    tenant_id: CurrentTenantId = None,
    db: AsyncSession = Depends(get_db),
) -> HierarchyDetectionResponse:
    """Run hierarchy detection on tenant's contracts.

    If contract_ids are provided, only those contracts are analysed.
    Otherwise, all completed contracts for the tenant are used.
    """
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant context required for hierarchy detection",
        )

    from app.models.contract import ContractStatus

    # Resolve contract IDs
    if body and body.contract_ids:
        contract_uuids = [uuid.UUID(cid) for cid in body.contract_ids]
    else:
        result = await db.execute(
            select(Contract.id).where(
                Contract.tenant_id == tenant_id,
                Contract.status == ContractStatus.COMPLETED,
            )
        )
        contract_uuids = list(result.scalars().all())

    if len(contract_uuids) < 2:
        return HierarchyDetectionResponse(
            suggestions_created=0,
            contracts_analysed=len(contract_uuids),
            message="Need at least 2 contracts for hierarchy detection",
        )

    try:
        from app.services.hierarchy_detection import detect_hierarchy

        num_suggestions = await detect_hierarchy(
            db=db,
            contract_ids=contract_uuids,
            tenant_id=tenant_id,
            batch_id=f"manual_{tenant_id}",
        )
        await db.commit()

        return HierarchyDetectionResponse(
            suggestions_created=num_suggestions,
            contracts_analysed=len(contract_uuids),
            message=f"Hierarchy detection complete: {num_suggestions} suggestions created from {len(contract_uuids)} contracts",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hierarchy detection failed: {str(e)}",
        )
