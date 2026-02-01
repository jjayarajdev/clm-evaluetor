"""Contracts router for upload and management."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit
from app.core.deps import CurrentUser
from app.database import get_db
from app.models.audit import AuditAction
from app.models.contract import ContractStatus, ContractType, RiskLevel
from app.schemas.contract import (
    BatchUploadResponse,
    ContractFilter,
    ContractListResponse,
    ContractResponse,
    ContractSummary,
    ContractUploadResponse,
    UploadStatusResponse,
)
from app.services.upload import UploadError, UploadService

router = APIRouter(prefix="/api/contracts", tags=["Contracts"])

# In-memory batch tracking (replace with Redis in production)
_batch_contracts: dict[str, list[str]] = {}


def contract_to_summary(contract) -> ContractSummary:
    """Convert Contract model to ContractSummary schema."""
    return ContractSummary(
        id=str(contract.id),
        filename=contract.filename,
        contract_type=contract.contract_type.value if contract.contract_type else None,
        counterparty=contract.counterparty,
        status=contract.status.value,
        risk_level=contract.risk_level.value if contract.risk_level else None,
        uploaded_at=contract.created_at,
    )


async def _auto_process_contract(contract_id: str, user_id: str, file_path: str):
    """Automatically process and analyze an uploaded contract in the background."""
    import logging
    from app.database import async_session_maker
    from app.services.indexer import IndexingService
    from app.models.contract import Contract, ContractStatus
    from sqlalchemy import select
    import uuid as uuid_mod

    try:
        logging.info(f"Auto-processing contract {contract_id}")

        async with async_session_maker() as session:
            # Get the contract
            result = await session.execute(
                select(Contract).where(Contract.id == uuid_mod.UUID(contract_id))
            )
            contract = result.scalar_one_or_none()
            if not contract:
                logging.error(f"Contract not found: {contract_id}")
                return

            # Update status to processing
            contract.status = ContractStatus.PROCESSING
            await session.commit()

            # Run indexer
            indexer = IndexingService(session)
            success = await indexer.index_contract(
                contract=contract,
                user_id=user_id,
                user_role="admin",
            )

            if success:
                contract.status = ContractStatus.COMPLETED
                logging.info(f"Contract {contract_id} processed successfully")
                await session.commit()

                # Also run deep analysis (clause and obligation extraction)
                await _run_deep_analysis(contract_id, user_id, file_path)
            else:
                contract.status = ContractStatus.FAILED
                contract.processing_error = "Indexing failed"
                logging.error(f"Contract {contract_id} processing failed")
                await session.commit()

    except Exception as e:
        logging.exception(f"Auto-process failed for {contract_id}: {e}")
        # Try to mark as failed
        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(Contract).where(Contract.id == uuid_mod.UUID(contract_id))
                )
                contract = result.scalar_one_or_none()
                if contract:
                    contract.status = ContractStatus.FAILED
                    contract.processing_error = str(e)[:500]
                    await session.commit()
        except Exception:
            pass


@router.post("/upload", response_model=ContractUploadResponse)
async def upload_single_file(
    current_user: CurrentUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF or DOCX contract file"),
) -> ContractUploadResponse:
    """Upload a single contract file.

    Args:
        current_user: Authenticated user.
        request: FastAPI request for audit logging.
        db: Database session.
        background_tasks: Background task runner.
        file: The uploaded file (PDF or DOCX).

    Returns:
        Upload response with contract ID and status.
    """
    service = UploadService(db)

    try:
        contract = await service.upload_single(file, str(current_user.id))

        # Audit log
        await log_audit(
            db=db,
            action=AuditAction.CONTRACT_UPLOAD,
            user_id=str(current_user.id),
            resource_type="contract",
            resource_id=str(contract.id),
            details={"filename": contract.filename, "size": contract.file_size},
            request=request,
        )

        await db.commit()

        # Queue automatic processing in background using asyncio.create_task
        contract_id = str(contract.id)
        user_id = str(current_user.id)
        file_path = contract.file_path

        import asyncio
        asyncio.create_task(_auto_process_contract(contract_id, user_id, file_path))

        return ContractUploadResponse(
            id=str(contract.id),
            filename=contract.filename,
            status=contract.status.value,
            message="File uploaded successfully. Processing started automatically.",
        )

    except UploadError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


async def _run_deep_analysis(contract_id: str, user_id: str, file_path: str):
    """Run deep AI analysis on a contract."""
    import logging
    from app.services.parser import get_parser
    from app.agents.clause_extraction import extract_clauses, store_extracted_clauses
    from app.agents.obligation_tracking import extract_obligations, store_extracted_obligations
    from app.agents import register_all_agents
    from app.services.orchestrator import initialize_default_agents
    from app.database import async_session_maker
    from app.models.contract import Contract
    from app.models.clause import Clause, ClauseType
    from app.models.obligation import Obligation
    from app.schemas import get_schema_registry, extract_with_schema
    from sqlalchemy import delete, select
    import uuid as uuid_mod

    try:
        # Ensure agents are registered
        initialize_default_agents()
        register_all_agents()

        # Parse the document
        parser = get_parser()
        parsed = parser.parse_file(file_path)

        if not parsed.success:
            logging.error(f"Parse failed for deep analysis: {parsed.error}")
            return

        full_text = parsed.full_text
        logging.info(f"Running deep analysis on {len(full_text)} chars for {contract_id}")

        # Store extracted text on contract
        async with async_session_maker() as session:
            result = await session.execute(
                select(Contract).where(Contract.id == uuid_mod.UUID(contract_id))
            )
            contract = result.scalar_one_or_none()
            if contract:
                contract.extracted_text = full_text
                await session.commit()
                logging.info(f"Stored extracted text ({len(full_text)} chars) for {contract_id}")

        # Extract clauses
        clause_result = await extract_clauses(
            contract_text=full_text,
            contract_id=contract_id,
            user_id=user_id,
        )
        logging.info(f"Extracted {len(clause_result.extracted_clauses) if clause_result else 0} clauses")

        # Extract obligations
        obligation_result = await extract_obligations(
            contract_text=full_text,
            contract_id=contract_id,
            user_id=user_id,
        )
        logging.info(f"Extracted {len(obligation_result.obligations) if obligation_result else 0} obligations")

        # Store results
        async with async_session_maker() as session:
            # Clean up existing
            await session.execute(
                delete(Clause)
                .where(Clause.contract_id == uuid_mod.UUID(contract_id))
                .where(Clause.clause_type != ClauseType.OTHER)
            )
            await session.execute(
                delete(Obligation)
                .where(Obligation.contract_id == uuid_mod.UUID(contract_id))
            )

            # Store new
            if clause_result and clause_result.extracted_clauses:
                await store_extracted_clauses(
                    db=session,
                    contract_id=uuid_mod.UUID(contract_id),
                    result=clause_result,
                )

            if obligation_result and obligation_result.obligations:
                await store_extracted_obligations(
                    db=session,
                    contract_id=uuid_mod.UUID(contract_id),
                    result=obligation_result,
                )

            await session.commit()
            logging.info(f"Clause/obligation extraction completed for {contract_id}")

        # Run schema-based extraction if a schema is available
        async with async_session_maker() as session:
            result = await session.execute(
                select(Contract).where(Contract.id == uuid_mod.UUID(contract_id))
            )
            contract = result.scalar_one_or_none()

            if contract and contract.contract_type:
                registry = get_schema_registry()
                schema = registry.get_schema_for_contract_type(contract.contract_type.value)

                if schema:
                    logging.info(f"Running schema extraction with {schema.schema_id} for {contract_id}")
                    try:
                        extraction_result = await extract_with_schema(
                            contract_text=full_text,
                            schema_id=schema.schema_id,
                            contract_id=contract_id,
                            user_id=user_id,
                        )

                        if extraction_result.extracted_data:
                            contract.schema_data = extraction_result.extracted_data
                            contract.schema_id = extraction_result.schema_id

                            # Sync schema data to relational structure (hybrid approach)
                            from app.services.schema_sync import sync_schema_to_db
                            await sync_schema_to_db(session, contract)

                            await session.commit()
                            logging.info(f"Schema extraction and sync completed for {contract_id} "
                                       f"(confidence: {extraction_result.overall_confidence:.2f})")
                    except Exception as e:
                        logging.warning(f"Schema extraction failed for {contract_id}: {e}")
                else:
                    logging.info(f"No schema available for contract type: {contract.contract_type.value}")

        logging.info(f"Deep analysis completed for {contract_id}")

    except Exception as e:
        logging.exception(f"Deep analysis failed for {contract_id}: {e}")


@router.post("/upload/batch", response_model=BatchUploadResponse)
async def upload_batch_files(
    current_user: CurrentUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    files: list[UploadFile] = File(..., description="Multiple PDF or DOCX files"),
) -> BatchUploadResponse:
    """Upload multiple contract files.

    Args:
        current_user: Authenticated user.
        request: FastAPI request for audit logging.
        db: Database session.
        files: List of uploaded files.

    Returns:
        Batch upload response with status for each file.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided",
        )

    if len(files) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 50 files per batch",
        )

    service = UploadService(db)
    batch_id, successful, failed = await service.upload_batch(files, str(current_user.id))

    # Store batch for status tracking
    _batch_contracts[batch_id] = [str(c.id) for c in successful]

    # Build response
    file_responses = []

    for contract in successful:
        file_responses.append(
            ContractUploadResponse(
                id=str(contract.id),
                filename=contract.filename,
                status=contract.status.value,
                message="Uploaded successfully",
            )
        )

    for filename, error in failed:
        file_responses.append(
            ContractUploadResponse(
                id="",
                filename=filename,
                status="rejected",
                message=error,
            )
        )

    # Audit log
    await log_audit(
        db=db,
        action=AuditAction.CONTRACT_UPLOAD,
        user_id=str(current_user.id),
        resource_type="batch",
        resource_id=batch_id,
        details={
            "total": len(files),
            "accepted": len(successful),
            "rejected": len(failed),
        },
        request=request,
    )

    await db.commit()

    return BatchUploadResponse(
        batch_id=batch_id,
        total_files=len(files),
        accepted=len(successful),
        rejected=len(failed),
        files=file_responses,
    )


@router.post("/upload/zip", response_model=BatchUploadResponse)
async def upload_zip_archive(
    current_user: CurrentUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(..., description="ZIP archive containing PDF/DOCX files"),
) -> BatchUploadResponse:
    """Upload a ZIP archive containing contract files.

    Args:
        current_user: Authenticated user.
        request: FastAPI request for audit logging.
        db: Database session.
        file: ZIP archive file.

    Returns:
        Batch upload response with status for each extracted file.
    """
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a ZIP archive",
        )

    service = UploadService(db)
    batch_id, successful, failed = await service.extract_zip(file, str(current_user.id))

    # Store batch for status tracking
    _batch_contracts[batch_id] = [str(c.id) for c in successful]

    # Build response
    file_responses = []

    for contract in successful:
        file_responses.append(
            ContractUploadResponse(
                id=str(contract.id),
                filename=contract.filename,
                status=contract.status.value,
                message="Extracted and uploaded successfully",
            )
        )

    for filename, error in failed:
        file_responses.append(
            ContractUploadResponse(
                id="",
                filename=filename,
                status="rejected",
                message=error,
            )
        )

    # Audit log
    await log_audit(
        db=db,
        action=AuditAction.CONTRACT_UPLOAD,
        user_id=str(current_user.id),
        resource_type="batch",
        resource_id=batch_id,
        details={
            "source": "zip",
            "archive_name": file.filename,
            "total": len(successful) + len(failed),
            "accepted": len(successful),
            "rejected": len(failed),
        },
        request=request,
    )

    await db.commit()

    return BatchUploadResponse(
        batch_id=batch_id,
        total_files=len(successful) + len(failed),
        accepted=len(successful),
        rejected=len(failed),
        files=file_responses,
    )


@router.get("/upload-status/{batch_id}", response_model=UploadStatusResponse)
async def get_upload_status(
    batch_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UploadStatusResponse:
    """Get the processing status of a batch upload.

    Args:
        batch_id: The batch ID from upload response.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Status of all files in the batch.
    """
    contract_ids = _batch_contracts.get(batch_id)

    if not contract_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found or expired",
        )

    service = UploadService(db)
    status_counts = await service.get_upload_status(contract_ids)
    contracts = await service.get_contracts_by_ids(contract_ids)

    return UploadStatusResponse(
        batch_id=batch_id,
        total=len(contract_ids),
        pending=status_counts.get("pending", 0),
        processing=status_counts.get("processing", 0),
        completed=status_counts.get("completed", 0),
        failed=status_counts.get("failed", 0),
        contracts=[contract_to_summary(c) for c in contracts],
    )


class ProcessingRequest(BaseModel):
    """Request to process contracts."""

    contract_ids: list[str]


class ProcessingResponse(BaseModel):
    """Response from processing request."""

    message: str
    contract_ids: list[str]
    queued: int


@router.post("/process", response_model=ProcessingResponse)
async def process_contracts(
    request_body: ProcessingRequest,
    current_user: CurrentUser,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProcessingResponse:
    """Trigger processing for uploaded contracts.

    This initiates the parsing, chunking, and indexing pipeline
    for the specified contracts as a background task.

    Args:
        request_body: Request with contract IDs to process.
        current_user: Authenticated user.
        request: FastAPI request for audit logging.
        background_tasks: FastAPI background tasks.
        db: Database session.

    Returns:
        Response confirming processing has been queued.
    """
    from app.services.indexer import IngestionPipeline

    contract_ids = request_body.contract_ids

    if not contract_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No contract IDs provided",
        )

    if len(contract_ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 100 contracts per request",
        )

    # Add background task for processing
    async def process_in_background():
        from app.database import async_session_maker

        async with async_session_maker() as session:
            pipeline = IngestionPipeline(session)
            await pipeline.process_batch(
                contract_ids,
                user_id=str(current_user.id),
                user_role=current_user.role.value,
            )
            await session.commit()

    background_tasks.add_task(process_in_background)

    # Audit log
    await log_audit(
        db=db,
        action=AuditAction.CONTRACT_PROCESS,
        user_id=str(current_user.id),
        resource_type="batch",
        resource_id=",".join(contract_ids[:5]),
        details={"contract_count": len(contract_ids)},
        request=request,
    )

    await db.commit()

    return ProcessingResponse(
        message="Processing queued successfully",
        contract_ids=contract_ids,
        queued=len(contract_ids),
    )


@router.post("/{contract_id}/process", response_model=ProcessingResponse)
async def process_single_contract(
    contract_id: str,
    current_user: CurrentUser,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProcessingResponse:
    """Trigger processing for a single contract.

    Args:
        contract_id: ID of the contract to process.
        current_user: Authenticated user.
        request: FastAPI request for audit logging.
        background_tasks: FastAPI background tasks.
        db: Database session.

    Returns:
        Response confirming processing has been queued.
    """
    from app.services.indexer import IngestionPipeline

    # Add background task for processing
    async def process_in_background():
        from app.database import async_session_maker

        async with async_session_maker() as session:
            pipeline = IngestionPipeline(session)
            await pipeline.process_contract(
                contract_id,
                user_id=str(current_user.id),
                user_role=current_user.role.value,
            )
            await session.commit()

    background_tasks.add_task(process_in_background)

    # Audit log
    await log_audit(
        db=db,
        action=AuditAction.CONTRACT_PROCESS,
        user_id=str(current_user.id),
        resource_type="contract",
        resource_id=contract_id,
        details={},
        request=request,
    )

    await db.commit()

    return ProcessingResponse(
        message="Processing queued successfully",
        contract_ids=[contract_id],
        queued=1,
    )


def contract_to_response(contract) -> ContractResponse:
    """Convert Contract model to ContractResponse schema."""
    return ContractResponse(
        id=str(contract.id),
        filename=contract.filename,
        file_path=contract.file_path,
        file_size=contract.file_size,
        mime_type=contract.mime_type,
        contract_type=contract.contract_type.value if contract.contract_type else None,
        counterparty=contract.counterparty,
        effective_date=contract.effective_date,
        expiration_date=contract.expiration_date,
        contract_value=contract.contract_value,
        currency=contract.currency,
        jurisdiction=contract.jurisdiction,
        risk_score=contract.risk_score,
        risk_level=contract.risk_level.value if contract.risk_level else None,
        auto_renewal=contract.auto_renewal,
        notice_period_days=contract.notice_period_days,
        renewal_term_months=contract.renewal_term_months,
        status=contract.status.value,
        processing_error=contract.processing_error,
        schema_id=contract.schema_id,
        schema_data=contract.schema_data,
        uploaded_by=str(contract.uploaded_by),
        clause_count=len(contract.clauses) if contract.clauses else 0,
        obligation_count=len(contract.obligations) if contract.obligations else 0,
        created_at=contract.created_at,
        updated_at=contract.updated_at,
    )


@router.get("", response_model=ContractListResponse)
async def list_contracts(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = 1,
    page_size: int = 20,
    contract_type: str | None = None,
    counterparty: str | None = None,
    risk_level: str | None = None,
    status_filter: str | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_desc: bool = True,
) -> ContractListResponse:
    """List contracts with pagination and filters.

    Args:
        current_user: Authenticated user.
        db: Database session.
        page: Page number (1-indexed).
        page_size: Items per page (max 100).
        contract_type: Filter by contract type.
        counterparty: Filter by counterparty (partial match).
        risk_level: Filter by risk level.
        status_filter: Filter by status.
        search: Search in filename and counterparty.
        sort_by: Sort field (created_at, expiration_date, risk_score).
        sort_desc: Sort descending.

    Returns:
        Paginated contract list.
    """
    from app.services.contracts import ContractService

    # Validate pagination
    page_size = min(max(page_size, 1), 100)
    page = max(page, 1)

    # Parse enum filters
    type_enum = None
    if contract_type:
        try:
            type_enum = ContractType(contract_type)
        except ValueError:
            pass

    risk_enum = None
    if risk_level:
        try:
            risk_enum = RiskLevel(risk_level)
        except ValueError:
            pass

    status_enum = None
    if status_filter:
        try:
            status_enum = ContractStatus(status_filter)
        except ValueError:
            pass

    service = ContractService(db)
    contracts, total = await service.list_contracts(
        page=page,
        page_size=page_size,
        contract_type=type_enum,
        counterparty=counterparty,
        risk_level=risk_enum,
        status=status_enum,
        search=search,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )

    total_pages = (total + page_size - 1) // page_size

    return ContractListResponse(
        contracts=[contract_to_summary(c) for c in contracts],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/search")
async def search_contracts(
    query: str,
    current_user: CurrentUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 20,
) -> list[dict]:
    """Search contracts using semantic similarity.

    Args:
        query: Search query text.
        current_user: Authenticated user.
        request: FastAPI request for audit logging.
        db: Database session.
        limit: Maximum results.

    Returns:
        List of matching contracts with relevance scores.
    """
    from app.services.contracts import ContractService

    service = ContractService(db)
    results = await service.search_contracts(
        query_text=query,
        user_id=str(current_user.id),
        user_role=current_user.role.value,
        n_results=min(limit, 50),
    )

    # Audit log
    await log_audit(
        db=db,
        action=AuditAction.QUERY_EXECUTE,
        user_id=str(current_user.id),
        resource_type="search",
        resource_id=None,
        details={"query": query[:100], "results": len(results)},
        request=request,
    )

    await db.commit()

    return [
        {
            "contract": contract_to_summary(r["contract"]),
            "relevance_score": r["relevance_score"],
        }
        for r in results
    ]


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: str,
    current_user: CurrentUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContractResponse:
    """Get a contract by ID with full details.

    Args:
        contract_id: Contract ID.
        current_user: Authenticated user.
        request: FastAPI request for audit logging.
        db: Database session.

    Returns:
        Full contract details.
    """
    from app.services.contracts import ContractService

    service = ContractService(db)
    contract = await service.get_contract(contract_id)

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Audit log
    await log_audit(
        db=db,
        action=AuditAction.CONTRACT_VIEW,
        user_id=str(current_user.id),
        resource_type="contract",
        resource_id=contract_id,
        details={"filename": contract.filename},
        request=request,
    )

    await db.commit()

    return contract_to_response(contract)


@router.delete("/{contract_id}")
async def delete_contract(
    contract_id: str,
    current_user: CurrentUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Delete a contract and all associated data.

    Args:
        contract_id: Contract ID to delete.
        current_user: Authenticated user.
        request: FastAPI request for audit logging.
        db: Database session.

    Returns:
        Confirmation message.
    """
    from app.services.contracts import ContractService

    service = ContractService(db)
    deleted = await service.delete_contract(contract_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Audit log
    await log_audit(
        db=db,
        action=AuditAction.CONTRACT_DELETE,
        user_id=str(current_user.id),
        resource_type="contract",
        resource_id=contract_id,
        details={},
        request=request,
    )

    await db.commit()

    return {"message": "Contract deleted successfully", "contract_id": contract_id}


@router.post("/{contract_id}/analyze")
async def analyze_contract(
    contract_id: str,
    current_user: CurrentUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> dict:
    """Run deep AI analysis on a contract to extract clauses, obligations, and risks.

    This endpoint triggers comprehensive extraction including:
    - Clause classification (indemnification, termination, liability, etc.)
    - Obligation tracking (who owes what to whom, deadlines)
    - Risk assessment (liability caps, indemnities, force majeure)

    Args:
        contract_id: Contract ID to analyze.
        current_user: Authenticated user.
        request: FastAPI request for audit logging.
        db: Database session.
        background_tasks: Background task runner.

    Returns:
        Confirmation that analysis has been queued.
    """
    from sqlalchemy import select
    from app.models.contract import Contract

    # Verify contract exists
    result = await db.execute(
        select(Contract).where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Queue deep analysis in background
    async def run_deep_analysis():
        from app.services.parser import get_parser
        from app.agents.clause_extraction import extract_clauses, store_extracted_clauses
        from app.agents.obligation_tracking import extract_obligations, store_extracted_obligations
        from app.agents import register_all_agents
        from app.services.orchestrator import initialize_default_agents
        from app.database import async_session_maker
        import uuid as uuid_mod

        try:
            # Ensure agents are registered (needed for background tasks)
            initialize_default_agents()
            register_all_agents()

            # Parse the document to get full text
            parser = get_parser()
            parsed = parser.parse_file(contract.file_path)

            if not parsed.success:
                import logging
                logging.error(f"Parse failed for {contract_id}: {parsed.error}")
                return

            full_text = parsed.full_text
            import logging
            logging.info(f"Parsed {len(full_text)} chars for deep analysis of {contract_id}")

            # Run clause extraction (AI call)
            clause_result = await extract_clauses(
                contract_text=full_text,
                contract_id=contract_id,
                user_id=str(current_user.id),
            )
            logging.info(f"Extracted {len(clause_result.extracted_clauses) if clause_result else 0} clauses")

            # Run obligation extraction (AI call)
            obligation_result = await extract_obligations(
                contract_text=full_text,
                contract_id=contract_id,
                user_id=str(current_user.id),
            )
            logging.info(f"Extracted {len(obligation_result.obligations) if obligation_result else 0} obligations")

            # Store results in database (new session for background task)
            async with async_session_maker() as session:
                from sqlalchemy import delete, text
                from app.models.clause import Clause, ClauseType
                from app.models.obligation import Obligation

                # Clean up existing AI-extracted clauses (keep only 'other' type from initial indexing)
                # This prevents duplicates when re-analyzing
                await session.execute(
                    delete(Clause)
                    .where(Clause.contract_id == uuid_mod.UUID(contract_id))
                    .where(Clause.clause_type != ClauseType.OTHER)
                )
                logging.info(f"Cleaned up existing classified clauses for {contract_id}")

                # Clean up existing obligations
                await session.execute(
                    delete(Obligation)
                    .where(Obligation.contract_id == uuid_mod.UUID(contract_id))
                )
                logging.info(f"Cleaned up existing obligations for {contract_id}")

                # Store clauses
                if clause_result and clause_result.extracted_clauses:
                    await store_extracted_clauses(
                        db=session,
                        contract_id=uuid_mod.UUID(contract_id),
                        result=clause_result,
                    )
                    logging.info(f"Stored {len(clause_result.extracted_clauses)} clauses")

                # Store obligations
                if obligation_result and obligation_result.obligations:
                    await store_extracted_obligations(
                        db=session,
                        contract_id=uuid_mod.UUID(contract_id),
                        result=obligation_result,
                    )
                    logging.info(f"Stored {len(obligation_result.obligations)} obligations")

                await session.commit()
                logging.info(f"Clause/obligation extraction completed for {contract_id}")

            # Extract definitions from DEFINITIONS type clauses
            async with async_session_maker() as session:
                from app.services.definition_extraction import extract_and_save_definitions

                try:
                    defn_count = await extract_and_save_definitions(session, uuid_mod.UUID(contract_id))
                    logging.info(f"Extracted {defn_count} definitions for {contract_id}")
                except Exception as e:
                    logging.warning(f"Definition extraction failed for {contract_id}: {e}")

            # Extract process steps from procedural clauses
            async with async_session_maker() as session:
                from app.services.process_extraction import extract_and_save_process_steps

                try:
                    step_count = await extract_and_save_process_steps(session, uuid_mod.UUID(contract_id))
                    logging.info(f"Extracted {step_count} process steps for {contract_id}")
                except Exception as e:
                    logging.warning(f"Process step extraction failed for {contract_id}: {e}")

            # Extract preamble/header data
            async with async_session_maker() as session:
                from app.services.preamble_extraction import extract_and_save_preamble

                try:
                    preamble_count = await extract_and_save_preamble(session, uuid_mod.UUID(contract_id))
                    logging.info(f"Extracted preamble with {preamble_count} records for {contract_id}")
                except Exception as e:
                    logging.warning(f"Preamble extraction failed for {contract_id}: {e}")

            # Extract exhibits/schedules
            async with async_session_maker() as session:
                from app.services.exhibit_extraction import extract_and_save_exhibits

                try:
                    exhibit_count = await extract_and_save_exhibits(session, uuid_mod.UUID(contract_id))
                    logging.info(f"Extracted {exhibit_count} exhibit records for {contract_id}")
                except Exception as e:
                    logging.warning(f"Exhibit extraction failed for {contract_id}: {e}")

            # Run schema-based extraction if a schema is available for this contract type
            async with async_session_maker() as session:
                from sqlalchemy import select
                from app.models.contract import Contract
                from app.schemas import get_schema_registry, extract_with_schema

                result = await session.execute(
                    select(Contract).where(Contract.id == uuid_mod.UUID(contract_id))
                )
                contract_obj = result.scalar_one_or_none()

                if contract_obj and contract_obj.contract_type:
                    registry = get_schema_registry()
                    schema = registry.get_schema_for_contract_type(contract_obj.contract_type.value)

                    if schema:
                        logging.info(f"Running schema extraction with {schema.schema_id} for {contract_id}")
                        try:
                            extraction_result = await extract_with_schema(
                                contract_text=full_text,
                                schema_id=schema.schema_id,
                                contract_id=contract_id,
                                user_id=str(current_user.id),
                            )

                            if extraction_result.extracted_data:
                                contract_obj.schema_data = extraction_result.extracted_data
                                contract_obj.schema_id = extraction_result.schema_id

                                # Sync schema data to relational structure (hybrid approach)
                                from app.services.schema_sync import sync_schema_to_db
                                await sync_schema_to_db(session, contract_obj)

                                await session.commit()
                                logging.info(f"Schema extraction and sync completed for {contract_id} "
                                           f"(confidence: {extraction_result.overall_confidence:.2f})")
                        except Exception as e:
                            logging.warning(f"Schema extraction failed for {contract_id}: {e}")
                    else:
                        logging.info(f"No schema available for contract type: {contract_obj.contract_type.value}")
                else:
                    logging.info(f"Contract {contract_id} has no contract_type set, skipping schema extraction")

            logging.info(f"Deep analysis completed for {contract_id}")

        except Exception as e:
            import logging
            logging.exception(f"Deep analysis failed for {contract_id}: {e}")

    background_tasks.add_task(run_deep_analysis)

    # Audit log
    await log_audit(
        db=db,
        action=AuditAction.CONTRACT_VIEW,
        user_id=str(current_user.id),
        resource_type="contract",
        resource_id=contract_id,
        details={"action": "deep_analysis_queued"},
        request=request,
    )

    await db.commit()

    return {
        "message": "Deep analysis queued successfully",
        "contract_id": contract_id,
        "analyses": ["clause_extraction", "obligation_tracking"],
    }
