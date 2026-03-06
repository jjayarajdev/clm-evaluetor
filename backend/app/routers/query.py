"""Query router for contract Q&A and AI interactions."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit
from app.core.deps import CurrentUser, CurrentTenantId
from app.database import get_db
from app.models.audit import AuditAction

router = APIRouter(prefix="/api/query", tags=["Query"])


class QueryRequest(BaseModel):
    """Request for Q&A query."""

    question: str = Field(..., min_length=3, max_length=2000)
    contract_id: str | None = None
    session_id: str | None = None


class SourceReference(BaseModel):
    """Reference to a source in the answer."""

    contract_id: str
    filename: str | None = None
    section_number: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    relevance_score: float | None = None
    excerpt: str | None = None
    chunk_index: int | None = None


class Visualization(BaseModel):
    """Chart/visualization data for rich Q&A responses."""

    chart_type: str  # "bar", "pie", "timeline", "table", "stat_cards"
    title: str
    data: list[dict] | dict


class QueryResponse(BaseModel):
    """Response from Q&A query."""

    answer: str
    confidence: float
    sources: list[SourceReference]
    follow_up_questions: list[str]
    session_id: str
    visualizations: list[Visualization] = []


class SuggestionsResponse(BaseModel):
    """Response with suggested questions."""

    questions: list[str]
    contract_id: str | None = None


@router.post("", response_model=QueryResponse)
async def query_contracts(
    request_body: QueryRequest,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QueryResponse:
    """Ask a question about contracts using AI.

    This endpoint uses RAG (Retrieval Augmented Generation) to:
    1. Search for relevant contract content
    2. Generate an answer using the AI agent
    3. Include source citations and follow-up suggestions

    Args:
        request_body: Query request with question and optional contract scope.
        current_user: Authenticated user.
        tenant_id: Current tenant ID for isolation.
        request: FastAPI request for audit logging.
        db: Database session.

    Returns:
        QueryResponse with answer, sources, and suggestions.
    """
    from app.agents.contract_qa import ask_question

    session_id = request_body.session_id or f"session_{current_user.id}"

    try:
        result = await ask_question(
            question=request_body.question,
            user_id=str(current_user.id),
            session_id=session_id,
            contract_id=request_body.contract_id,
            user_role=current_user.role.value,
            tenant_id=str(tenant_id) if tenant_id else None,
        )

        # Convert sources
        sources = [
            SourceReference(
                contract_id=s.contract_id,
                filename=s.filename,
                section_number=s.section_number,
                page_start=s.page_start,
                page_end=s.page_end,
                relevance_score=s.relevance_score,
                excerpt=s.excerpt,
                chunk_index=s.chunk_index,
            )
            for s in result.sources
        ]

        # Audit log
        await log_audit(
            db=db,
            action=AuditAction.QUERY_EXECUTE,
            user_id=str(current_user.id),
            resource_type="query",
            resource_id=request_body.contract_id or "all",
            details={
                "question": request_body.question[:200],
                "confidence": result.confidence,
                "source_count": len(sources),
            },
            request=request,
        )

        await db.commit()

        # Convert visualizations if present
        visualizations = []
        if hasattr(result, 'visualizations') and result.visualizations:
            visualizations = [
                Visualization(
                    chart_type=v.get("chart_type", "table"),
                    title=v.get("title", ""),
                    data=v.get("data", []),
                )
                for v in result.visualizations
            ]

        return QueryResponse(
            answer=result.answer,
            confidence=result.confidence,
            sources=sources,
            follow_up_questions=result.follow_up_questions,
            session_id=session_id,
            visualizations=visualizations,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing query: {str(e)}",
        )


@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_suggested_questions(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    contract_id: str | None = None,
) -> SuggestionsResponse:
    """Get suggested questions for contracts.

    Args:
        current_user: Authenticated user.
        tenant_id: Current tenant ID for isolation.
        contract_id: Optional contract ID for specific suggestions.

    Returns:
        SuggestionsResponse with suggested questions.
    """
    from app.agents.contract_qa import suggest_questions

    questions = await suggest_questions(
        contract_id=contract_id or "",
        user_id=str(current_user.id),
        user_role=current_user.role.value,
        tenant_id=str(tenant_id) if tenant_id else None,
    )

    return SuggestionsResponse(
        questions=questions,
        contract_id=contract_id,
    )


@router.post("/analyze", response_model=dict[str, Any])
async def analyze_contract(
    contract_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    analysis_type: str = "full",
) -> dict[str, Any]:
    """Run full AI analysis on a contract.

    This triggers all analysis agents:
    - Metadata extraction
    - Clause extraction
    - Obligation tracking
    - Risk assessment
    - Renewal monitoring

    Args:
        contract_id: ID of the contract to analyze.
        current_user: Authenticated user.
        tenant_id: Current tenant ID for isolation.
        request: FastAPI request for audit logging.
        db: Database session.
        analysis_type: Type of analysis ("full", "metadata", "risk", "renewal").

    Returns:
        Analysis results summary.
    """
    import uuid

    from sqlalchemy import select

    from app.models.contract import Contract
    from app.agents import (
        extract_metadata,
        update_contract_metadata,
        extract_clauses,
        store_extracted_clauses,
        extract_obligations,
        store_extracted_obligations,
        assess_risk,
        update_contract_risk,
        analyze_renewal_terms,
        update_contract_renewal,
    )
    from app.services.parser import get_parser

    # Get contract with tenant filter
    query = select(Contract).where(Contract.id == uuid.UUID(contract_id))
    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)
    result = await db.execute(query)
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Parse the document
    parser = get_parser()
    parsed = parser.parse_file(contract.file_path)

    if not parsed.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse contract: {parsed.error}",
        )

    results = {"contract_id": contract_id, "analyses": {}}

    # Run requested analyses
    if analysis_type in ["full", "metadata"]:
        metadata = await extract_metadata(
            parsed.full_text, contract_id, str(current_user.id)
        )
        await update_contract_metadata(db, contract, metadata)
        results["analyses"]["metadata"] = {
            "confidence": metadata.overall_confidence,
            "fields_extracted": len([f for f in [
                metadata.contract_type, metadata.counterparty,
                metadata.effective_date, metadata.expiration_date,
                metadata.contract_value, metadata.jurisdiction
            ] if f is not None]),
        }

    if analysis_type in ["full", "clauses"]:
        clauses = await extract_clauses(parsed.full_text, contract_id, str(current_user.id))
        await store_extracted_clauses(db, contract.id, clauses)
        results["analyses"]["clauses"] = {
            "confidence": clauses.overall_confidence,
            "clauses_found": len(clauses.extracted_clauses),
            "missing_clauses": clauses.missing_clauses,
        }

    if analysis_type in ["full", "obligations"]:
        obligations = await extract_obligations(parsed.full_text, contract_id, str(current_user.id))
        await store_extracted_obligations(db, contract.id, obligations)
        results["analyses"]["obligations"] = {
            "confidence": obligations.overall_confidence,
            "obligations_found": len(obligations.obligations),
        }

    if analysis_type in ["full", "risk"]:
        risk = await assess_risk(parsed.full_text, contract_id, str(current_user.id))
        await update_contract_risk(db, contract, risk)
        results["analyses"]["risk"] = {
            "score": risk.overall_score,
            "level": risk.risk_level,
            "factors": len(risk.risk_factors),
        }

    if analysis_type in ["full", "renewal"]:
        renewal = await analyze_renewal_terms(parsed.full_text, contract_id, str(current_user.id))
        await update_contract_renewal(db, contract, renewal)
        results["analyses"]["renewal"] = {
            "confidence": renewal.terms.confidence,
            "has_auto_renewal": renewal.terms.has_auto_renewal,
            "urgency": renewal.urgency_level,
        }

    # Audit log
    await log_audit(
        db=db,
        action=AuditAction.AGENT_INVOKE,
        user_id=str(current_user.id),
        resource_type="contract",
        resource_id=contract_id,
        details={
            "analysis_type": analysis_type,
            "analyses_run": list(results["analyses"].keys()),
        },
        request=request,
    )

    await db.commit()

    return results
