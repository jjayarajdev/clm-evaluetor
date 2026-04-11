"""Contracts router for upload and management."""

import asyncio
import json
import logging
import uuid
from typing import Annotated, Any

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit
from app.core.deps import AdminUser, CurrentUser, CurrentTenantId
from app.models.contract import Contract
from app.database import get_db
from app.models.audit import AuditAction
from app.models.contract import ContractStatus, ContractType, RiskLevel
from app.schemas.contract import (
    BatchUploadResponse,
    ContractFilter,
    ContractListResponse,
    ContractResponse,
    ContractSummary,
    ContractUpdate,
    ContractUploadResponse,
    UploadStatusResponse,
)
from app.services.upload import UploadError, UploadService
from app.services.progress_tracker import get_progress_tracker, ProcessingStage

router = APIRouter(prefix="/api/contracts", tags=["Contracts"])



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
    from app.database import async_session_maker
    from app.services.indexer import IndexingService
    from app.models.contract import Contract, ContractStatus
    from sqlalchemy import select
    import uuid as uuid_mod

    try:
        logger.info(f"Auto-processing contract {contract_id}")

        async with async_session_maker() as session:
            result = await session.execute(
                select(Contract).where(Contract.id == uuid_mod.UUID(contract_id))
            )
            contract = result.scalar_one_or_none()
            if not contract:
                logger.error(f"Contract not found: {contract_id}")
                return

            contract.status = ContractStatus.PROCESSING
            await session.commit()

            indexer = IndexingService(session)
            success = await indexer.index_contract(
                contract=contract,
                user_id=user_id,
                user_role="admin",
            )

            if success:
                contract.status = ContractStatus.COMPLETED
                logger.info(f"Contract {contract_id} processed successfully")
                await session.commit()
                await _run_deep_analysis(contract_id, user_id, file_path)
            else:
                contract.status = ContractStatus.FAILED
                contract.processing_error = "Indexing failed"
                logger.error(f"Contract {contract_id} processing failed")
                await session.commit()

    except Exception as e:
        logger.exception(f"Auto-process failed for {contract_id}: {e}")
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
            logger.error(f"Failed to mark contract {contract_id} as failed")


async def _process_batch_concurrently(
    contracts: list[tuple[str, str, str]],
    max_concurrent: int = 2,
):
    """Process multiple contracts concurrently with a concurrency limit.

    Args:
        contracts: List of (contract_id, user_id, file_path) tuples.
        max_concurrent: Max contracts to process at the same time.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _limited(contract_id, user_id, file_path):
        async with semaphore:
            await _auto_process_contract(contract_id, user_id, file_path)

    await asyncio.gather(
        *[_limited(cid, uid, fp) for cid, uid, fp in contracts],
        return_exceptions=True,
    )


@router.post("/upload", response_model=ContractUploadResponse)
async def upload_single_file(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
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
    # Require tenant for uploads (super-admin must specify context)
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required for upload. Super-admin must specify tenant.",
        )

    service = UploadService(db, tenant_id=tenant_id)

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

        # Enqueue for reliable processing via the job queue
        from app.services.processing_queue import ProcessingQueueService
        queue = ProcessingQueueService(db)
        await queue.enqueue_contract(
            contract_id=str(contract.id),
            user_id=str(current_user.id),
            file_path=contract.file_path,
            tenant_id=str(tenant_id),
        )
        await db.commit()

        return ContractUploadResponse(
            id=str(contract.id),
            filename=contract.filename,
            status=contract.status.value,
            message="File uploaded successfully. Processing queued.",
        )

    except UploadError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


async def _run_deep_analysis(contract_id: str, user_id: str, file_path: str):
    """Run deep AI analysis on a contract.

    Uses separate sessions for each major stage to ensure fault isolation —
    a failure in one stage doesn't roll back earlier successful stages.
    """
    from app.services.parser import get_parser
    from app.agents.clause_extraction import extract_clauses, store_extracted_clauses, reclassify_sla_chunks
    from app.agents.obligation_tracking import extract_obligations, store_extracted_obligations
    from app.agents.sla_extraction import extract_slas, store_extracted_slas
    from app.agents import register_all_agents
    from app.services.orchestrator import initialize_default_agents
    from app.database import async_session_maker
    from app.models.contract import Contract
    from app.models.clause import Clause, ClauseType
    from app.models.obligation import Obligation
    from app.models.sla import ContractSLA
    from app.schemas import get_schema_registry, extract_with_schema
    from sqlalchemy import delete, select
    import uuid as uuid_mod

    from app.services.progress_tracker import get_progress_tracker, ProcessingStage
    tracker = get_progress_tracker()
    cid_uuid = uuid_mod.UUID(contract_id)

    try:
        logger.info(f"[DEEP ANALYSIS] Starting for contract {contract_id}")
        tracker.update_progress(contract_id, ProcessingStage.CLAUSE_EXTRACTION, "Preparing deep analysis...")

        # Ensure agents are registered
        initialize_default_agents()
        register_all_agents()

        # Parse the document
        parser = get_parser()
        parsed = parser.parse_file(file_path)

        if not parsed.success:
            logger.error(f"[DEEP ANALYSIS] Parse failed: {parsed.error}")
            return

        full_text = parsed.full_text
        logger.info(f"[DEEP ANALYSIS] Parsed {len(full_text)} chars for {contract_id}")

        # Store extracted text on contract
        async with async_session_maker() as session:
            result = await session.execute(
                select(Contract).where(Contract.id == cid_uuid)
            )
            contract = result.scalar_one_or_none()
            if contract:
                contract.extracted_text = full_text
                await session.commit()

        # --- AI extraction stage (no DB needed) ---
        tracker.update_progress(contract_id, ProcessingStage.CLAUSE_EXTRACTION, "Extracting clauses...")
        clause_result = await extract_clauses(
            contract_text=full_text,
            contract_id=contract_id,
            user_id=user_id,
        )
        logger.info(f"[DEEP ANALYSIS] Extracted {len(clause_result.extracted_clauses) if clause_result else 0} clauses")

        tracker.update_progress(contract_id, ProcessingStage.OBLIGATION_DETECTION, "Extracting obligations...")
        obligation_result = await extract_obligations(
            contract_text=full_text,
            contract_id=contract_id,
            user_id=user_id,
        )
        logger.info(f"[DEEP ANALYSIS] Extracted {len(obligation_result.obligations) if obligation_result else 0} obligations")

        tracker.update_progress(contract_id, ProcessingStage.SLA_EXTRACTION, "Extracting SLAs...")
        sla_result = await extract_slas(
            contract_text=full_text,
            contract_id=contract_id,
            user_id=user_id,
        )
        logger.info(f"[DEEP ANALYSIS] Extracted {len(sla_result.slas) if sla_result else 0} SLAs")

        # --- Store all extraction results in one session ---
        async with async_session_maker() as session:
            # Clean up existing
            await session.execute(
                delete(Clause)
                .where(Clause.contract_id == cid_uuid)
                .where(Clause.clause_type != ClauseType.OTHER)
            )
            await session.execute(
                delete(Obligation).where(Obligation.contract_id == cid_uuid)
            )
            await session.execute(
                delete(ContractSLA).where(ContractSLA.contract_id == cid_uuid)
            )

            # For Excel files, try structured SLA extraction first
            if file_path.lower().endswith(('.xlsx', '.xls')):
                from app.services.sla_benchmark_service import extract_and_store_excel_slas
                excel_sla_count = await extract_and_store_excel_slas(
                    db=session, contract_id=cid_uuid, file_path=file_path,
                )
                if excel_sla_count > 0:
                    logger.info(f"[DEEP ANALYSIS] Extracted {excel_sla_count} structured SLAs from Excel")

            if clause_result and clause_result.extracted_clauses:
                await store_extracted_clauses(db=session, contract_id=cid_uuid, result=clause_result)

            reclassified = await reclassify_sla_chunks(db=session, contract_id=cid_uuid)
            if reclassified > 0:
                logger.info(f"[DEEP ANALYSIS] Reclassified {reclassified} chunks as SERVICE_LEVEL")

            if obligation_result and obligation_result.obligations:
                await store_extracted_obligations(db=session, contract_id=cid_uuid, result=obligation_result)

            if sla_result and sla_result.slas:
                await store_extracted_slas(db=session, contract_id=cid_uuid, result=sla_result)

            await session.commit()
            logger.info(f"[DEEP ANALYSIS] Clause/obligation/SLA extraction stored for {contract_id}")

        # --- Renewal + Schema + Type classification in one session ---
        tracker.update_progress(contract_id, ProcessingStage.RENEWAL_ANALYSIS, "Analyzing renewal terms...")
        try:
            from app.agents.renewal_monitoring import analyze_renewal_terms, update_contract_renewal

            renewal_result = await analyze_renewal_terms(
                contract_text=full_text,
                contract_id=contract_id,
                user_id=user_id,
            )

            async with async_session_maker() as session:
                result = await session.execute(
                    select(Contract).where(Contract.id == cid_uuid)
                )
                contract = result.scalar_one_or_none()
                if not contract:
                    logger.error(f"[DEEP ANALYSIS] Contract {contract_id} not found for renewal/schema stage")
                else:
                    # Store renewal terms
                    if renewal_result and renewal_result.terms:
                        await update_contract_renewal(session, contract, renewal_result)
                        logger.info(f"[DEEP ANALYSIS] Renewal terms stored for {contract_id}")

                    # Schema extraction
                    tracker.update_progress(contract_id, ProcessingStage.SCHEMA_EXTRACTION, "Running structured data extraction...")
                    if contract.contract_type:
                        registry = get_schema_registry()
                        schema = registry.get_schema_for_contract_type(contract.contract_type.value)
                        if schema:
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
                                    from app.services.schema_sync import sync_schema_to_db
                                    await sync_schema_to_db(session, contract)
                                    logger.info(f"[DEEP ANALYSIS] Schema extraction completed for {contract_id}")
                            except Exception as e:
                                logger.warning(f"Schema extraction failed for {contract_id}: {e}")

                    # Classify contract_type if still NULL
                    if not contract.contract_type:
                        try:
                            from app.models.contract import ContractType as CT
                            from app.services.orchestrator import get_orchestrator, AgentRequest

                            orchestrator = get_orchestrator()
                            classify_prompt = (
                                f"Classify this contract into exactly ONE of these types: "
                                f"NDA, MSA, SOW, AMENDMENT, VENDOR_AGREEMENT, EMPLOYMENT_CONTRACT.\n\n"
                                f"Rules:\n"
                                f"- NDA: non-disclosure, confidentiality agreements\n"
                                f"- MSA: master services, framework, consulting, professional services, BPO agreements\n"
                                f"- SOW: statement of work, work order, schedule, service order, purchase order\n"
                                f"- AMENDMENT: amendments, addenda, modifications, change orders, supplements\n"
                                f"- VENDOR_AGREEMENT: license, SaaS, subscription, supply, lease, distribution agreements\n"
                                f"- EMPLOYMENT_CONTRACT: employment, offer letters, contractor, non-compete agreements\n\n"
                                f"Respond with ONLY the type name (e.g., 'MSA'). No explanation.\n\n"
                                f"Document title: {contract.filename}\n"
                                f"Counterparty: {contract.counterparty or 'unknown'}\n\n"
                                f"First 3000 chars:\n{full_text[:3000]}"
                            )
                            resp = await orchestrator.route_request(
                                AgentRequest(
                                    query=classify_prompt,
                                    user_id=user_id,
                                    session_id=f"classify_{contract_id}",
                                    contract_id=contract_id,
                                    context={"task": "contract_type_classification"},
                                )
                            )
                            classified = resp.response.strip().upper().replace(" ", "_")
                            type_enum_map = {t.name: t for t in CT}
                            if classified in type_enum_map:
                                contract.contract_type = type_enum_map[classified]
                                logger.info(f"[DEEP ANALYSIS] Classified contract type as: {classified}")
                            else:
                                logger.warning(f"Fallback classification returned unrecognized type: {classified}")
                        except Exception as e:
                            logger.warning(f"Fallback type classification failed for {contract_id}: {e}")

                    await session.commit()

        except Exception as e:
            logger.warning(f"[DEEP ANALYSIS] Renewal/schema stage failed for {contract_id}: {e}")

        # --- Reference extraction + child document corrections in one session ---
        async with async_session_maker() as session:
            result = await session.execute(
                select(Contract).where(Contract.id == cid_uuid)
            )
            contract = result.scalar_one_or_none()
            if contract:
                existing_refs = (contract.schema_data or {}).get("_contract_references", {})
                has_parent_refs = bool(existing_refs.get("parent_references"))
                changed = False

                if not has_parent_refs:
                    try:
                        from app.services.orchestrator import get_orchestrator, AgentRequest
                        from app.agents.base import extract_json_from_response

                        orchestrator = get_orchestrator()
                        rel_prompt = (
                            f"You are a contract relationship analyst. Read this contract carefully and answer:\n\n"
                            f"1. Does this contract explicitly reference, amend, supplement, or attach to another agreement?\n"
                            f"2. If yes, what is the exact name/type of that parent agreement?\n"
                            f"3. Who are the parties in the referenced agreement?\n"
                            f"4. What date was the referenced agreement signed/effective?\n\n"
                            f"Look for phrases like:\n"
                            f"- 'pursuant to the Master Services Agreement...'\n"
                            f"- 'This Amendment modifies the Agreement dated...'\n"
                            f"- 'under the terms of the [Agreement Name]...'\n"
                            f"- 'This Schedule is part of...'\n"
                            f"- 'as referenced in the [Agreement] between...'\n\n"
                            f"Respond ONLY with JSON:\n"
                            f'{{"is_child_document": true/false, "document_role": "amendment|schedule|exhibit|sow|standalone", '
                            f'"parent_references": [{{"referenced_type": "MSA", "relationship": "parent|amends|renews", '
                            f'"party_names": ["Company A", "Company B"], "referenced_date": "YYYY-MM-DD", '
                            f'"reference_identifier": "Amendment No. 2", '
                            f'"reference_text": "exact quote from document", "confidence": 0.9}}], '
                            f'"child_references": [], "overall_confidence": 0.9}}\n\n'
                            f"If this is a standalone contract with NO references to other agreements, return:\n"
                            f'{{"is_child_document": false, "document_role": "standalone", '
                            f'"parent_references": [], "child_references": [], "overall_confidence": 0.9}}\n\n'
                            f"Document filename: {contract.filename}\n"
                            f"---\n{full_text[:10000]}\n---"
                        )
                        resp = await orchestrator.route_request(
                            AgentRequest(
                                query=rel_prompt,
                                user_id=user_id,
                                session_id=f"rel_extract_{contract_id}",
                                contract_id=contract_id,
                                context={"task": "contract_reference_extraction"},
                            )
                        )
                        json_data = extract_json_from_response(resp.response)
                        if json_data and json_data.get("parent_references"):
                            from app.agents.contract_reference_extraction import (
                                _parse_reference_response,
                                store_contract_references,
                            )
                            ref_result = _parse_reference_response(json_data)
                            if ref_result.parent_references:
                                await store_contract_references(session, contract, ref_result)
                                changed = True
                                logger.info(f"[DEEP ANALYSIS] Found {len(ref_result.parent_references)} parent refs for {contract_id}")
                    except Exception as e:
                        logger.warning(f"Focused relationship extraction failed for {contract_id}: {e}")

                # Post-reference corrections: fix type and counterparty for child docs
                refs = (contract.schema_data or {}).get("_contract_references", {})
                is_child = refs.get("is_child_document", False)
                doc_role = refs.get("document_role", "")

                # Child documents (exhibits, attachments, schedules) should be SOW, not MSA
                if is_child and doc_role in ("exhibit", "attachment", "schedule", "appendix", "annex", "sow"):
                    if contract.contract_type and contract.contract_type.value == "msa":
                        contract.contract_type = CT.SOW
                        changed = True
                        logger.info(f"[DEEP ANALYSIS] Reclassified child document from MSA -> SOW (role={doc_role})")

                # If counterparty looks like filename fallback, use parent reference parties
                if contract.counterparty and contract.filename:
                    fname_base = contract.filename.rsplit(".", 1)[0]
                    cp = contract.counterparty.strip()
                    is_filename_fallback = (
                        cp == fname_base
                        or cp == contract.filename
                        or (len(cp) > 40 and fname_base[:30] in cp)
                    )
                    if is_filename_fallback:
                        parent_refs = refs.get("parent_references", [])
                        for pref in parent_refs:
                            parties = pref.get("party_names", [])
                            for party in parties:
                                if party and len(party.strip()) >= 3 and party.strip().lower() not in (
                                    "client", "vendor", "supplier", "company", "party",
                                    "party a", "party b", "the company", "the client",
                                ):
                                    contract.counterparty = party.strip()
                                    changed = True
                                    logger.info(f"[DEEP ANALYSIS] Fixed counterparty -> '{party.strip()}'")
                                    break
                            if changed:
                                break

                if changed:
                    await session.commit()

        # --- Hierarchy detection ---
        tracker.update_progress(contract_id, ProcessingStage.LINK_DETECTION, "Finding related contracts...")
        try:
            from app.services.hierarchy_detection import detect_hierarchy

            async with async_session_maker() as session:
                result = await session.execute(
                    select(Contract).where(Contract.id == cid_uuid)
                )
                contract = result.scalar_one_or_none()

                if contract and contract.tenant_id:
                    tenant_contracts = await session.execute(
                        select(Contract.id).where(
                            Contract.tenant_id == contract.tenant_id,
                            Contract.status == ContractStatus.COMPLETED,
                        ).order_by(Contract.created_at.desc()).limit(50)
                    )
                    contract_ids_for_hierarchy = list(tenant_contracts.scalars().all())

                    if len(contract_ids_for_hierarchy) >= 2:
                        num_suggestions = await detect_hierarchy(
                            db=session,
                            contract_ids=contract_ids_for_hierarchy,
                            tenant_id=contract.tenant_id,
                            batch_id=f"deep_analysis_{contract_id}",
                        )
                        await session.commit()
                        logger.info(f"[DEEP ANALYSIS] Hierarchy detection created {num_suggestions} suggestions")
        except Exception as e:
            logger.warning(f"[DEEP ANALYSIS] Hierarchy detection failed for {contract_id}: {e}")

        # --- Industry detection and compliance check ---
        tracker.update_progress(contract_id, ProcessingStage.COMPLIANCE_CHECK, "Running compliance analysis...")
        try:
            from app.services.industry_detector import IndustryDetector
            from app.services.compliance_gap_detector import ComplianceGapDetector
            from app.services.compliance_alert_service import create_compliance_alerts_for_gaps
            from app.agents.regulatory_extraction import (
                extract_regulatory_obligations,
                store_regulatory_obligations,
            )
            from app.models.industry import REGULATED_INDUSTRIES
            from datetime import datetime

            async with async_session_maker() as session:
                result = await session.execute(
                    select(Contract).where(Contract.id == cid_uuid)
                )
                contract = result.scalar_one_or_none()

                if contract:
                    industry_detector = IndustryDetector(session)
                    industry_result = await industry_detector.detect_industry(contract)
                    contract.detected_industry = industry_result.industry
                    contract.industry_confidence = industry_result.confidence
                    logger.info(f"[DEEP ANALYSIS] Detected industry: {industry_result.industry.value} "
                          f"(confidence: {industry_result.confidence:.2f})")

                    # 2. Check compliance gaps
                    gap_detector = ComplianceGapDetector(session, contract.tenant_id)
                    check_result = await gap_detector.check_compliance(
                        contract=contract,
                        industry=industry_result.industry,
                        create_gaps=True,
                    )
                    contract.compliance_score = check_result.compliance_score
                    contract.last_compliance_check = datetime.utcnow()
                    print(f"[DEEP ANALYSIS] Compliance score: {check_result.compliance_score}, "
                          f"gaps: {len(check_result.gaps_found)}")
                    logging.info(f"Compliance check: score={check_result.compliance_score}, "
                               f"gaps={len(check_result.gaps_found)} for {contract_id}")

                    if check_result.gaps_found:
                        alerts = await create_compliance_alerts_for_gaps(
                            session, contract.id, check_result.gaps_found
                        )
                        if alerts:
                            logger.info(f"[DEEP ANALYSIS] Created {len(alerts)} compliance alerts for {contract_id}")

                    if industry_result.industry in REGULATED_INDUSTRIES and full_text:
                        reg_result = await extract_regulatory_obligations(
                            contract_text=full_text,
                            industry=industry_result.industry,
                            contract_id=contract_id,
                            user_id=user_id,
                        )
                        if reg_result.obligations:
                            await store_regulatory_obligations(
                                db=session,
                                contract_id=cid_uuid,
                                industry=industry_result.industry,
                                result=reg_result,
                            )
                            logger.info(f"[DEEP ANALYSIS] Extracted {len(reg_result.obligations)} "
                                       f"regulatory obligations for {contract_id}")

                    await session.commit()

        except Exception as e:
            logger.warning(f"[DEEP ANALYSIS] Compliance analysis failed for {contract_id}: {e}")

        # --- Governance bridge ---
        tracker.update_progress(contract_id, ProcessingStage.GOVERNANCE_BRIDGE, "Setting up governance...")
        try:
            from app.services.governance_bridge import GovernanceBridgeService

            async with async_session_maker() as session:
                result = await session.execute(
                    select(Contract).where(Contract.id == cid_uuid)
                )
                contract = result.scalar_one_or_none()
                if contract and contract.tenant_id:
                    bridge = GovernanceBridgeService(session)
                    summary = await bridge.bridge_contract_to_governance(
                        contract_id=contract.id,
                        tenant_id=contract.tenant_id,
                    )
                    await session.commit()
                    logger.info(f"[DEEP ANALYSIS] Governance bridge completed for {contract_id}: {summary}")
        except Exception as e:
            logger.warning(f"[DEEP ANALYSIS] Governance bridge failed for {contract_id}: {e}")

        tracker.update_progress(contract_id, ProcessingStage.COMPLETED, "Processing complete")
        logger.info(f"[DEEP ANALYSIS] Completed for {contract_id}")

    except Exception as e:
        tracker.update_progress(contract_id, ProcessingStage.FAILED, error=str(e))
        logger.exception(f"[DEEP ANALYSIS] FAILED for {contract_id}: {e}")


@router.post("/upload/batch", response_model=BatchUploadResponse)
async def upload_batch_files(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(..., description="Multiple PDF or DOCX files"),
    folder_name: str | None = None,
    client_id: str | None = Form(None, description="Optional client ID to associate files with"),
) -> BatchUploadResponse:
    """Upload multiple related contract files.

    If client_id is provided, files are stored in client folder with versioning:
    - storage/uploads/{client_code}/{YYYYMMDD}/
    - Duplicate hash = reject
    - Same filename, different hash = create new version

    Otherwise, files are grouped in a shared folder.

    Args:
        current_user: Authenticated user.
        request: FastAPI request for audit logging.
        db: Database session.
        background_tasks: Background task runner.
        files: List of uploaded files.
        folder_name: Optional name for the folder (e.g., counterparty name).
        client_id: Optional client ID to associate files with.

    Returns:
        Batch upload response with status for each file.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided",
        )

    if len(files) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 100 files per batch",
        )

    # Require tenant for uploads
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required for upload. Super-admin must specify tenant.",
        )

    service = UploadService(db, tenant_id=tenant_id)

    # Use client-based upload if client_id provided
    if client_id:
        batch_id, successful, failed = await service.upload_for_client(
            files,
            str(current_user.id),
            client_id,
        )
    else:
        # Legacy: Group all files into one folder
        batch_id, successful, failed = await service.upload_batch(
            files,
            str(current_user.id),
            group_in_folder=True,
            folder_name=folder_name,
        )

    # Enqueue for reliable processing via the job queue
    from app.services.processing_queue import ProcessingQueueService
    queue_svc = ProcessingQueueService(db)
    batch_items = [
        (str(contract.id), str(current_user.id), contract.file_path)
        for contract in successful
    ]
    await queue_svc.enqueue_batch(batch_items, batch_id, str(tenant_id))

    # Build response
    file_responses = []

    for contract in successful:
        file_responses.append(
            ContractUploadResponse(
                id=str(contract.id),
                filename=contract.filename,
                status="accepted",
                message="Uploaded successfully, analysis queued",
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
    tenant_id: CurrentTenantId,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
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

    # Require tenant for uploads
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required for upload. Super-admin must specify tenant.",
        )

    service = UploadService(db, tenant_id=tenant_id)
    batch_id, successful, failed = await service.extract_zip(file, str(current_user.id))

    # Enqueue for reliable processing via the job queue
    from app.services.processing_queue import ProcessingQueueService
    zip_queue = ProcessingQueueService(db)
    batch_items = [
        (str(contract.id), str(current_user.id), contract.file_path)
        for contract in successful
    ]
    await zip_queue.enqueue_batch(batch_items, batch_id, str(tenant_id))

    # Build response
    file_responses = []

    for contract in successful:
        file_responses.append(
            ContractUploadResponse(
                id=str(contract.id),
                filename=contract.filename,
                status=contract.status.value,
                message="Extracted and uploaded, analysis queued",
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

    Uses the DB-backed processing queue to look up batch status.

    Args:
        batch_id: The batch ID from upload response.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        Status of all files in the batch.
    """
    from app.services.processing_queue import ProcessingQueueService

    queue = ProcessingQueueService(db)
    progress = await queue.get_batch_progress(batch_id)

    if progress["total"] == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found or expired",
        )

    # Get contract records for summaries
    contract_ids = [j["contract_id"] for j in progress["jobs"]]
    service = UploadService(db)
    contracts = await service.get_contracts_by_ids(contract_ids)

    return UploadStatusResponse(
        batch_id=batch_id,
        total=progress["total"],
        pending=progress.get("queued", 0),
        processing=progress.get("processing", 0),
        completed=progress.get("completed", 0),
        failed=progress.get("failed", 0),
        contracts=[contract_to_summary(c) for c in contracts],
    )


@router.get("/batch/{batch_id}/progress")
async def get_batch_progress(
    batch_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get detailed processing progress for a batch upload.

    Returns per-contract stage, progress percentage, and messages
    from the persistent job queue.
    """
    from app.services.processing_queue import ProcessingQueueService
    queue = ProcessingQueueService(db)
    progress = await queue.get_batch_progress(batch_id)

    if progress["total"] == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    return progress


@router.get("/processing-queue/stats")
async def get_queue_stats(
    current_user: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get processing queue statistics (admin only)."""
    from app.services.processing_queue import ProcessingQueueService
    queue = ProcessingQueueService(db)
    return await queue.get_queue_stats()


@router.get("/{contract_id}/processing-job")
async def get_contract_processing_job(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get processing queue job status for a specific contract."""
    from app.services.processing_queue import ProcessingQueueService
    queue = ProcessingQueueService(db)
    job = await queue.get_job_by_contract(contract_id)
    if not job:
        return {"status": "no_job", "message": "No processing job found for this contract"}
    return {
        "contract_id": str(job.contract_id),
        "status": job.status,
        "stage": job.stage,
        "progress_percent": job.progress_percent,
        "message": job.message,
        "error": job.error,
        "retry_count": job.retry_count,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


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
    current_user: AdminUser,
    tenant_id: CurrentTenantId,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProcessingResponse:
    """Trigger processing for uploaded contracts (admin only).

    This initiates the parsing, chunking, and indexing pipeline
    for the specified contracts as a background task.

    Args:
        request_body: Request with contract IDs to process.
        current_user: Authenticated admin user.
        tenant_id: Current tenant ID for isolation.
        request: FastAPI request for audit logging.
        background_tasks: FastAPI background tasks.
        db: Database session.

    Returns:
        Response confirming processing has been queued.
    """
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

    # Enqueue contracts via the persistent job queue
    from app.services.processing_queue import ProcessingQueueService

    queue = ProcessingQueueService(db)
    batch_id = uuid.uuid4().hex[:16]

    for cid in contract_ids:
        # Fetch contract with tenant isolation
        query = select(Contract).where(Contract.id == uuid.UUID(cid))
        if tenant_id is not None:
            query = query.where(Contract.tenant_id == tenant_id)
        result = await db.execute(query)
        contract = result.scalar_one_or_none()
        if contract:
            await queue.enqueue_contract(
                contract_id=cid,
                user_id=str(current_user.id),
                file_path=contract.file_path,
                tenant_id=str(contract.tenant_id),
                batch_id=batch_id,
            )

    # Audit log
    await log_audit(
        db=db,
        action=AuditAction.CONTRACT_PROCESS,
        user_id=str(current_user.id),
        resource_type="batch",
        resource_id=contract_ids[0] if contract_ids else "none",
        details={"contract_count": len(contract_ids), "contract_ids": contract_ids},
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
    tenant_id: CurrentTenantId,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProcessingResponse:
    """Trigger processing for a single contract.

    Args:
        contract_id: ID of the contract to process.
        current_user: Authenticated user.
        tenant_id: Current tenant ID for isolation.
        request: FastAPI request for audit logging.
        background_tasks: FastAPI background tasks.
        db: Database session.

    Returns:
        Response confirming processing has been queued.
    """
    # Enqueue via the persistent job queue
    from app.services.processing_queue import ProcessingQueueService

    query = select(Contract).where(Contract.id == uuid.UUID(contract_id))
    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)
    result = await db.execute(query)
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found",
        )

    queue = ProcessingQueueService(db)
    await queue.enqueue_contract(
        contract_id=contract_id,
        user_id=str(current_user.id),
        file_path=contract.file_path,
        tenant_id=str(contract.tenant_id),
    )

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


def contract_to_response(contract, clause_count=None, obligation_count=None, sla_count=None) -> ContractResponse:
    """Convert Contract model to ContractResponse schema."""
    # Use explicit counts if provided, otherwise try loaded relationships
    _clause_count = clause_count if clause_count is not None else (len(contract.clauses) if contract.clauses else 0)
    _obligation_count = obligation_count if obligation_count is not None else (len(contract.obligations) if contract.obligations else 0)
    _sla_count = sla_count if sla_count is not None else (len(contract.slas) if contract.slas else 0)
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
        custom_fields=contract.custom_fields or {},
        business_relationship_id=str(contract.business_relationship_id) if contract.business_relationship_id else None,
        uploaded_by=str(contract.uploaded_by),
        clause_count=_clause_count,
        obligation_count=_obligation_count,
        sla_count=_sla_count,
        created_at=contract.created_at,
        updated_at=contract.updated_at,
    )


@router.get("/filter-options")
async def get_filter_options(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Get available filter options for contracts.

    Returns unique values for counterparties, contract types, and risk levels
    to populate filter dropdowns.

    Args:
        current_user: Authenticated user.
        tenant_id: Current tenant ID.
        db: Database session.

    Returns:
        Dictionary with available filter options.
    """
    from sqlalchemy import select, func, distinct
    from app.models.contract import Contract

    # Build tenant filter
    def add_tenant_filter(query):
        if tenant_id is not None:
            return query.where(Contract.tenant_id == tenant_id)
        return query

    # Get unique counterparties (non-null, non-empty) - with tenant filter
    counterparty_query = (
        select(distinct(Contract.counterparty))
        .where(Contract.counterparty.isnot(None))
        .where(Contract.counterparty != "")
        .order_by(Contract.counterparty)
    )
    counterparty_result = await db.execute(add_tenant_filter(counterparty_query))
    counterparties = [r[0] for r in counterparty_result.fetchall() if r[0]]

    # Get unique contract types - with tenant filter
    type_query = (
        select(distinct(Contract.contract_type))
        .where(Contract.contract_type.isnot(None))
    )
    type_result = await db.execute(add_tenant_filter(type_query))
    contract_types = [r[0].value for r in type_result.fetchall() if r[0]]

    # Get unique risk levels - with tenant filter
    risk_query = (
        select(distinct(Contract.risk_level))
        .where(Contract.risk_level.isnot(None))
    )
    risk_result = await db.execute(add_tenant_filter(risk_query))
    risk_levels = [r[0].value for r in risk_result.fetchall() if r[0]]

    # Get counts per counterparty - with tenant filter
    count_query = (
        select(Contract.counterparty, func.count(Contract.id))
        .where(Contract.counterparty.isnot(None))
        .where(Contract.counterparty != "")
        .group_by(Contract.counterparty)
        .order_by(func.count(Contract.id).desc())
    )
    count_result = await db.execute(add_tenant_filter(count_query))
    counterparty_counts = {r[0]: r[1] for r in count_result.fetchall() if r[0]}

    # Get clients with contract counts - with tenant filter
    from app.models.client import Client
    client_query = (
        select(Client.id, Client.name, Client.code, func.count(Contract.id))
        .outerjoin(Contract, Contract.client_id == Client.id)
        .group_by(Client.id, Client.name, Client.code)
        .order_by(Client.name)
    )
    if tenant_id is not None:
        client_query = client_query.where(Client.tenant_id == tenant_id)
    client_result = await db.execute(client_query)
    clients = [
        {"id": str(r[0]), "name": r[1], "code": r[2], "contract_count": r[3]}
        for r in client_result.fetchall()
    ]

    return {
        "counterparties": counterparties,
        "counterparty_counts": counterparty_counts,
        "contract_types": sorted(contract_types),
        "risk_levels": risk_levels,
        "clients": clients,
    }


@router.get("", response_model=ContractListResponse)
async def list_contracts(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    contract_type: str | None = None,
    counterparty: str | None = None,
    risk_level: str | None = None,
    status_filter: str | None = None,
    search: str | None = None,
    client_id: str | None = None,
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
        client_id: Filter by client ID.
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

    service = ContractService(db, tenant_id=tenant_id)
    contracts, total = await service.list_contracts(
        page=page,
        page_size=page_size,
        contract_type=type_enum,
        counterparty=counterparty,
        risk_level=risk_enum,
        status=status_enum,
        search=search,
        client_id=client_id,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )

    pages = (total + page_size - 1) // page_size

    return ContractListResponse(
        items=[contract_to_summary(c) for c in contracts],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/search")
async def search_contracts(
    query: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 20,
) -> list[dict]:
    """Search contracts using semantic similarity.

    Args:
        query: Search query text.
        current_user: Authenticated user.
        tenant_id: Current tenant ID (None for super-admin).
        request: FastAPI request for audit logging.
        db: Database session.
        limit: Maximum results.

    Returns:
        List of matching contracts with relevance scores.
    """
    from app.services.contracts import ContractService

    service = ContractService(db, tenant_id=tenant_id)
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
    tenant_id: CurrentTenantId,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContractResponse:
    """Get a contract by ID with full details.

    Args:
        contract_id: Contract ID.
        current_user: Authenticated user.
        tenant_id: Current tenant ID (None for super-admin).
        request: FastAPI request for audit logging.
        db: Database session.

    Returns:
        Full contract details.
    """
    from app.services.contracts import ContractService

    service = ContractService(db, tenant_id=tenant_id)
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
    tenant_id: CurrentTenantId,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Delete a contract and all associated data.

    Args:
        contract_id: Contract ID to delete.
        current_user: Authenticated user.
        tenant_id: Current tenant ID (None for super-admin).
        request: FastAPI request for audit logging.
        db: Database session.

    Returns:
        Confirmation message.
    """
    from app.services.contracts import ContractService

    service = ContractService(db, tenant_id=tenant_id)
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


class BatchDeleteRequest(BaseModel):
    """Request for batch deletion of contracts."""
    contract_ids: list[str]


class BatchDeleteResponse(BaseModel):
    """Response for batch deletion."""
    deleted: list[str]
    failed: list[dict]
    total_deleted: int
    total_failed: int


@router.post("/batch-delete", response_model=BatchDeleteResponse)
async def batch_delete_contracts(
    request_body: BatchDeleteRequest,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BatchDeleteResponse:
    """Delete multiple contracts and all associated data.

    Deletes files, ChromaDB records, and database records for each contract.

    Args:
        request_body: List of contract IDs to delete.
        current_user: Authenticated user.
        tenant_id: Current tenant ID (None for super-admin).
        request: FastAPI request for audit logging.
        db: Database session.

    Returns:
        Summary of deleted and failed contracts.
    """
    from app.services.contracts import ContractService

    service = ContractService(db, tenant_id=tenant_id)
    deleted: list[str] = []
    failed: list[dict] = []

    for contract_id in request_body.contract_ids:
        try:
            success = await service.delete_contract(contract_id)
            if success:
                deleted.append(contract_id)
                # Audit log for each deletion
                await log_audit(
                    db=db,
                    action=AuditAction.CONTRACT_DELETE,
                    user_id=str(current_user.id),
                    resource_type="contract",
                    resource_id=contract_id,
                    details={"batch_delete": True},
                    request=request,
                )
            else:
                failed.append({"contract_id": contract_id, "error": "Contract not found"})
        except Exception as e:
            failed.append({"contract_id": contract_id, "error": str(e)})

    await db.commit()

    return BatchDeleteResponse(
        deleted=deleted,
        failed=failed,
        total_deleted=len(deleted),
        total_failed=len(failed),
    )


@router.get("/{contract_id}/files")
async def list_contract_files(
    contract_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """List all files in a contract's folder.

    Args:
        contract_id: Contract ID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        List of files in the contract folder.
    """
    from sqlalchemy import select
    from app.models.contract import Contract
    from app.services.upload import UploadService
    from pathlib import Path

    # Get contract
    result = await db.execute(
        select(Contract).where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Get folder path
    folder_path = Path(contract.file_path).parent

    # List files
    service = UploadService(db)
    files = service.list_folder_files(folder_path)

    return {
        "contract_id": contract_id,
        "folder": str(folder_path),
        "files": files,
        "total": len(files),
    }


@router.post("/{contract_id}/files")
async def add_file_to_contract(
    contract_id: str,
    current_user: CurrentUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(..., description="Additional file to add to contract folder"),
) -> dict:
    """Add an additional file to a contract's folder (e.g., attachments, exhibits).

    Args:
        contract_id: Contract ID.
        current_user: Authenticated user.
        request: FastAPI request for audit logging.
        db: Database session.
        file: The file to add.

    Returns:
        Info about the added file.
    """
    from sqlalchemy import select
    from app.models.contract import Contract
    from app.services.upload import UploadService
    from pathlib import Path

    # Get contract
    result = await db.execute(
        select(Contract).where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Get folder path
    folder_path = Path(contract.file_path).parent

    # Save file to folder
    service = UploadService(db)
    is_valid, error = service.validate_file(file)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    content = await file.read()
    filename, file_path, file_size, content_hash = await service.save_file(
        file, content, folder_path=folder_path, preserve_filename=True
    )

    # Audit log
    await log_audit(
        db=db,
        action=AuditAction.CONTRACT_UPLOAD,
        user_id=str(current_user.id),
        resource_type="contract_attachment",
        resource_id=contract_id,
        details={"filename": filename, "size": file_size},
        request=request,
    )

    await db.commit()

    return {
        "message": "File added successfully",
        "contract_id": contract_id,
        "filename": filename,
        "file_path": file_path,
        "file_size": file_size,
    }


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
        from app.agents.clause_extraction import extract_clauses, store_extracted_clauses, reclassify_sla_chunks
        from app.agents.obligation_tracking import extract_obligations, store_extracted_obligations
        from app.agents.sla_extraction import extract_slas, store_extracted_slas
        from app.agents import register_all_agents
        from app.services.orchestrator import initialize_default_agents
        from app.database import async_session_maker
        from app.models.sla import ContractSLA
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

            # Run SLA extraction (AI call)
            sla_result = await extract_slas(
                contract_text=full_text,
                contract_id=contract_id,
                user_id=str(current_user.id),
            )
            logging.info(f"Extracted {len(sla_result.slas) if sla_result else 0} SLAs")

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

                # Clean up existing SLAs
                await session.execute(
                    delete(ContractSLA)
                    .where(ContractSLA.contract_id == uuid_mod.UUID(contract_id))
                )
                logging.info(f"Cleaned up existing SLAs for {contract_id}")

                # Store clauses
                if clause_result and clause_result.extracted_clauses:
                    await store_extracted_clauses(
                        db=session,
                        contract_id=uuid_mod.UUID(contract_id),
                        result=clause_result,
                    )
                    logging.info(f"Stored {len(clause_result.extracted_clauses)} clauses")

                # Reclassify uncategorized chunks that contain SLA patterns
                logging.warning(f"[DEBUG] About to call reclassify_sla_chunks for {contract_id}")
                reclassified = await reclassify_sla_chunks(
                    db=session,
                    contract_id=uuid_mod.UUID(contract_id),
                )
                logging.warning(f"[DEBUG] reclassify_sla_chunks returned: {reclassified}")
                if reclassified > 0:
                    logging.info(f"Reclassified {reclassified} chunks as SERVICE_LEVEL")

                # Store obligations
                if obligation_result and obligation_result.obligations:
                    await store_extracted_obligations(
                        db=session,
                        contract_id=uuid_mod.UUID(contract_id),
                        result=obligation_result,
                    )
                    logging.info(f"Stored {len(obligation_result.obligations)} obligations")

                # Store SLAs
                if sla_result and sla_result.slas:
                    await store_extracted_slas(
                        db=session,
                        contract_id=uuid_mod.UUID(contract_id),
                        result=sla_result,
                    )
                    logging.info(f"Stored {len(sla_result.slas)} SLAs")

                await session.commit()
                logging.info(f"Clause/obligation/SLA extraction completed for {contract_id}")

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

            # Extract renewal terms
            try:
                from app.agents.renewal_monitoring import analyze_renewal_terms, update_contract_renewal

                renewal_result = await analyze_renewal_terms(
                    contract_text=full_text,
                    contract_id=contract_id,
                    user_id=str(current_user.id),
                )

                if renewal_result and renewal_result.terms:
                    async with async_session_maker() as session:
                        result = await session.execute(
                            select(Contract).where(Contract.id == uuid_mod.UUID(contract_id))
                        )
                        contract_obj = result.scalar_one_or_none()
                        if contract_obj:
                            await update_contract_renewal(session, contract_obj, renewal_result)
                            await session.commit()
                            logging.info(f"Renewal terms extracted for {contract_id}: "
                                       f"auto_renewal={renewal_result.terms.has_auto_renewal}, "
                                       f"expiration={renewal_result.terms.expiration_date}")
            except Exception as e:
                logging.warning(f"Renewal extraction failed for {contract_id}: {e}")

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
        "analyses": ["clause_extraction", "obligation_tracking", "sla_extraction"],
    }


@router.get("/{contract_id}/processing-status")
async def get_processing_status_sse(
    contract_id: str,
    request: Request,
    token: str | None = None,
) -> StreamingResponse:
    """Stream processing status updates via Server-Sent Events (SSE).

    Supports both Authorization header and ?token= query parameter
    (needed for EventSource which cannot send custom headers).

    The stream sends JSON events with the following structure:
    ```
    {
        "contract_id": "...",
        "stage": "parsing|metadata|risk|knowledge_graph|completed|failed",
        "stage_description": "Human readable description",
        "progress_percent": 0-100,
        "message": "Current status message",
        "error": null or "Error message if failed"
    }
    ```

    The stream will automatically close when processing completes or fails.
    """
    from app.core.security import decode_token

    # Accept token from Authorization header or query param
    auth_token = token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        auth_token = auth_header[7:]

    if not auth_token:
        raise HTTPException(status_code=401, detail="Authentication required")

    payload = decode_token(auth_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    tracker = get_progress_tracker()

    async def event_generator():
        """Generate SSE events."""
        try:
            async for progress in tracker.subscribe(contract_id):
                data = json.dumps(progress.to_dict())
                yield f"data: {data}\n\n"

                # Stop streaming if completed or failed
                if progress.stage in (ProcessingStage.COMPLETED, ProcessingStage.FAILED):
                    break
        except Exception as e:
            error_data = json.dumps({
                "contract_id": contract_id,
                "stage": "failed",
                "error": str(e),
            })
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/{contract_id}/processing-status/current")
async def get_current_processing_status(
    contract_id: str,
    current_user: CurrentUser,
) -> dict:
    """Get the current processing status (non-streaming).

    Returns the current state of processing without streaming.
    Useful for initial state check before connecting to SSE.
    """
    tracker = get_progress_tracker()
    progress = tracker.get_progress(contract_id)

    if not progress:
        return {
            "contract_id": contract_id,
            "stage": "idle",
            "stage_description": "Not currently processing",
            "progress_percent": 0,
            "message": "Contract is not being processed",
            "error": None,
        }

    return progress.to_dict()


@router.patch("/{contract_id}", response_model=ContractResponse)
async def update_contract_metadata(
    contract_id: str,
    update_data: "ContractUpdate",
    current_user: CurrentUser,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContractResponse:
    """Update contract metadata.

    Allows updating extracted metadata fields like counterparty, dates, etc.
    """
    from sqlalchemy import select
    from app.models.contract import Contract
    from app.schemas.contract import ContractUpdate
    import uuid

    # Get contract
    result = await db.execute(
        select(Contract).where(Contract.id == uuid.UUID(contract_id))
    )
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract {contract_id} not found"
        )

    # Update fields that were provided
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if hasattr(contract, field):
            setattr(contract, field, value)

    await db.commit()
    await db.refresh(contract)

    # Get counts via subqueries to avoid lazy-loading
    from app.models.clause import Clause
    from app.models.obligation import Obligation
    from app.models.sla import ContractSLA
    from sqlalchemy import func

    counts = await db.execute(
        select(
            func.count(Clause.id).filter(Clause.contract_id == contract.id),
            func.count(Obligation.id).filter(Obligation.contract_id == contract.id),
            func.count(ContractSLA.id).filter(ContractSLA.contract_id == contract.id),
        )
    )
    clause_ct, obligation_ct, sla_ct = counts.one()

    return contract_to_response(contract, clause_count=clause_ct, obligation_count=obligation_ct, sla_count=sla_ct)


@router.put("/{contract_id}/custom-fields", response_model=ContractResponse)
async def update_contract_custom_fields(
    contract_id: str,
    custom_fields: dict[str, Any],
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ContractResponse:
    """Update custom fields for a contract.

    Custom fields are validated against the tenant's field definitions.
    Invalid fields are rejected with an error.

    Args:
        contract_id: Contract ID.
        custom_fields: Dictionary of custom field values.
        current_user: Authenticated user.
        tenant_id: Current tenant ID.
        db: Database session.

    Returns:
        Updated contract.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.contract import Contract
    from app.models.tenant import Tenant
    from app.services.custom_field_validator import CustomFieldValidator
    import uuid

    # Get contract with tenant filter
    query = select(Contract).where(Contract.id == uuid.UUID(contract_id))
    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)
    query = query.options(
        selectinload(Contract.clauses),
        selectinload(Contract.obligations),
        selectinload(Contract.slas),
    )

    result = await db.execute(query)
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract {contract_id} not found"
        )

    # Get tenant for validation
    tenant = await db.get(Tenant, contract.tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tenant not found for contract"
        )

    # Validate custom fields
    validator = CustomFieldValidator(tenant, "contract")
    validation_result = validator.validate(custom_fields)

    if not validation_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Custom field validation failed",
                "errors": validation_result.errors,
            }
        )

    # Normalize and save
    normalized = validator.normalize_values(custom_fields)
    contract.custom_fields = normalized

    await db.commit()
    await db.refresh(contract)

    return contract_to_response(contract)


class CustomFieldExtractionResult(BaseModel):
    """Result of custom field extraction for a contract."""
    contract_id: str
    success: bool
    fields_extracted: int = 0
    custom_fields: dict[str, Any] = {}
    error: str | None = None


class BatchCustomFieldExtractionRequest(BaseModel):
    """Request for batch custom field extraction."""
    contract_ids: list[str] | None = None  # None = all contracts
    overwrite_existing: bool = False  # If True, replace existing custom_fields


class BatchCustomFieldExtractionResponse(BaseModel):
    """Response for batch custom field extraction."""
    total: int
    successful: int
    failed: int
    results: list[CustomFieldExtractionResult]


@router.post("/{contract_id}/extract-custom-fields", response_model=CustomFieldExtractionResult)
async def extract_contract_custom_fields(
    contract_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    overwrite: bool = False,
) -> CustomFieldExtractionResult:
    """Re-extract custom fields for a single contract.

    This is a lightweight operation that only extracts custom fields
    without full reprocessing (no re-parsing, re-indexing, etc.).

    Args:
        contract_id: Contract ID.
        current_user: Authenticated user.
        tenant_id: Current tenant ID.
        db: Database session.
        overwrite: If True, replace existing custom fields. If False, merge.

    Returns:
        Extraction result with extracted fields.
    """
    from sqlalchemy import select
    from app.models.contract import Contract
    from app.models.tenant import Tenant
    from app.services.custom_field_extraction import extract_custom_fields
    import uuid

    # Get contract with tenant filter
    query = select(Contract).where(Contract.id == uuid.UUID(contract_id))
    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)

    result = await db.execute(query)
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract {contract_id} not found"
        )

    # Get tenant
    tenant = await db.get(Tenant, contract.tenant_id)
    if not tenant:
        return CustomFieldExtractionResult(
            contract_id=contract_id,
            success=False,
            error="Tenant not found"
        )

    # Check if tenant has custom fields defined
    if not tenant.custom_field_definitions or not tenant.custom_field_definitions.get("contract"):
        return CustomFieldExtractionResult(
            contract_id=contract_id,
            success=True,
            fields_extracted=0,
            custom_fields={},
            error="No custom fields defined for contracts"
        )

    # Get contract text
    contract_text = contract.extracted_text
    if not contract_text:
        return CustomFieldExtractionResult(
            contract_id=contract_id,
            success=False,
            error="No extracted text available. Run full processing first."
        )

    try:
        # Extract custom fields
        extracted = await extract_custom_fields(
            tenant=tenant,
            contract_text=contract_text,
            contract_id=contract_id,
            entity_type="contract",
        )

        # Update contract
        if overwrite:
            contract.custom_fields = extracted
        else:
            # Merge with existing
            existing = contract.custom_fields or {}
            existing.update(extracted)
            contract.custom_fields = existing

        await db.commit()

        return CustomFieldExtractionResult(
            contract_id=contract_id,
            success=True,
            fields_extracted=len(extracted),
            custom_fields=extracted,
        )

    except Exception as e:
        return CustomFieldExtractionResult(
            contract_id=contract_id,
            success=False,
            error=str(e)
        )


@router.post("/batch/extract-custom-fields", response_model=BatchCustomFieldExtractionResponse)
async def batch_extract_custom_fields(
    request_data: BatchCustomFieldExtractionRequest,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BatchCustomFieldExtractionResponse:
    """Re-extract custom fields for multiple contracts.

    This is a lightweight batch operation that only extracts custom fields
    without full reprocessing.

    Args:
        request_data: Batch extraction request with contract IDs.
        current_user: Authenticated user.
        tenant_id: Current tenant ID.
        db: Database session.

    Returns:
        Batch extraction results.
    """
    from sqlalchemy import select
    from app.models.contract import Contract, ContractStatus
    from app.models.tenant import Tenant
    from app.services.custom_field_extraction import extract_custom_fields
    import uuid

    # Get tenant first to check custom fields
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required for batch extraction"
        )

    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )

    # Check if tenant has custom fields defined
    if not tenant.custom_field_definitions or not tenant.custom_field_definitions.get("contract"):
        return BatchCustomFieldExtractionResponse(
            total=0,
            successful=0,
            failed=0,
            results=[],
        )

    # Build query for contracts
    query = select(Contract).where(Contract.tenant_id == tenant_id)

    if request_data.contract_ids:
        # Specific contracts
        contract_uuids = [uuid.UUID(cid) for cid in request_data.contract_ids]
        query = query.where(Contract.id.in_(contract_uuids))
    else:
        # All completed contracts with extracted text
        query = query.where(
            Contract.status == ContractStatus.COMPLETED,
            Contract.extracted_text.isnot(None),
        )

    result = await db.execute(query)
    contracts = result.scalars().all()

    results: list[CustomFieldExtractionResult] = []
    successful = 0
    failed = 0

    for contract in contracts:
        contract_text = contract.extracted_text
        if not contract_text:
            results.append(CustomFieldExtractionResult(
                contract_id=str(contract.id),
                success=False,
                error="No extracted text available"
            ))
            failed += 1
            continue

        try:
            extracted = await extract_custom_fields(
                tenant=tenant,
                contract_text=contract_text,
                contract_id=str(contract.id),
                entity_type="contract",
            )

            # Update contract
            if request_data.overwrite_existing:
                contract.custom_fields = extracted
            else:
                existing = contract.custom_fields or {}
                existing.update(extracted)
                contract.custom_fields = existing

            results.append(CustomFieldExtractionResult(
                contract_id=str(contract.id),
                success=True,
                fields_extracted=len(extracted),
                custom_fields=extracted,
            ))
            successful += 1

        except Exception as e:
            results.append(CustomFieldExtractionResult(
                contract_id=str(contract.id),
                success=False,
                error=str(e)
            ))
            failed += 1

    # Commit all updates
    await db.commit()

    return BatchCustomFieldExtractionResponse(
        total=len(contracts),
        successful=successful,
        failed=failed,
        results=results,
    )


class ReindexResponse(BaseModel):
    """Response for reindex operation."""
    total: int
    indexed: int
    failed: int
    errors: list[str]


@router.post("/admin/reindex-all", response_model=ReindexResponse)
async def reindex_all_contracts(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReindexResponse:
    """Reindex all contracts into the vector store for Q&A.

    This operation:
    1. Finds all COMPLETED contracts
    2. Parses and chunks each contract
    3. Stores chunks in ChromaDB vector store

    Use this if Q&A is not finding contract content.

    Requires admin role.
    """
    from sqlalchemy import select
    from app.models.contract import Contract, ContractStatus
    from app.services.indexer import IndexingService
    from app.services.vector_store import get_vector_store

    # Check admin role
    if current_user.role.value not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required"
        )

    # Get all completed contracts
    query = select(Contract).where(Contract.status == ContractStatus.COMPLETED)
    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)

    result = await db.execute(query)
    contracts = list(result.scalars().all())

    if not contracts:
        return ReindexResponse(total=0, indexed=0, failed=0, errors=[])

    # Index each contract
    indexer = IndexingService(db)
    vector_store = get_vector_store()
    indexed = 0
    failed = 0
    errors = []

    for contract in contracts:
        try:
            # Clear existing chunks for this contract
            vector_store.delete_by_contract_id(str(contract.id))

            # Re-index (just the vector store part, not full analysis)
            from app.services.parser import DocumentParser
            from app.services.chunker import get_chunker

            parser = DocumentParser()
            chunker = get_chunker()

            # Parse the document
            if not contract.file_path:
                errors.append(f"{contract.filename}: No file path")
                failed += 1
                continue

            parsed = parser.parse_file(contract.file_path)
            if not parsed.success:
                errors.append(f"{contract.filename}: {parsed.error}")
                failed += 1
                continue

            # Chunk the content
            chunked = chunker.chunk_document(parsed)

            if not chunked.chunks:
                errors.append(f"{contract.filename}: No chunks extracted")
                failed += 1
                continue

            # Prepare data for vector store
            from app.services.vector_store import ChunkMetadata
            import uuid as uuid_mod

            texts = [chunk.text for chunk in chunked.chunks]
            chunk_ids = [str(uuid_mod.uuid4()) for _ in chunked.chunks]
            metadatas = [
                ChunkMetadata(
                    contract_id=str(contract.id),
                    filename=contract.filename,
                    section_number=chunk.section_number,
                    page_number=chunk.page_start,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    access_level="public",
                    uploaded_by=str(contract.uploaded_by) if contract.uploaded_by else None,
                )
                for chunk in chunked.chunks
            ]

            # Store in vector store
            vector_store.add_documents(texts, metadatas, chunk_ids)

            indexed += 1

        except Exception as e:
            errors.append(f"{contract.filename}: {str(e)}")
            failed += 1

    return ReindexResponse(
        total=len(contracts),
        indexed=indexed,
        failed=failed,
        errors=errors[:20],  # Limit error list
    )


# ===== Contract Sharing Endpoints =====

from uuid import UUID
from datetime import timedelta

from app.models.contract_share import ContractShare
from app.models.contract_comment import ContractComment
from app.models.external_user import ExternalUser
from app.models.external_access import ExternalAccessToken, TokenType
from app.schemas.contract_share import (
    ContractShareCreate,
    ContractShareBulkCreate,
    ContractShareResponse,
    ContractShareWithUser,
    ContractShareListResponse,
    ShareInviteResponse,
)
from app.schemas.contract_comment import (
    ContractCommentCreate,
    ContractCommentResponse,
    ContractCommentListResponse,
)
from app.schemas.external_user import ExternalUserSummary
from sqlalchemy import select, func


@router.post("/{contract_id}/share", response_model=ShareInviteResponse)
async def share_contract(
    contract_id: str,
    share_data: ContractShareCreate,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Share a contract with an external user."""
    from app.services.contracts import ContractService
    import uuid as uuid_mod

    # Verify contract exists and user has access
    service = ContractService(db, tenant_id=tenant_id)
    contract = await service.get_contract(contract_id)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Verify external user exists and belongs to same tenant
    ext_user_query = select(ExternalUser).where(
        ExternalUser.id == share_data.external_user_id,
        ExternalUser.tenant_id == contract.tenant_id,
        ExternalUser.is_active == True,
    )
    ext_user = (await db.execute(ext_user_query)).scalar_one_or_none()
    if not ext_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="External user not found or inactive",
        )

    # Check if already shared
    existing_query = select(ContractShare).where(
        ContractShare.contract_id == uuid_mod.UUID(contract_id),
        ContractShare.external_user_id == share_data.external_user_id,
        ContractShare.is_revoked == False,
    )
    existing = (await db.execute(existing_query)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contract is already shared with this user",
        )

    # Calculate expiration
    from datetime import datetime
    expires_at = None
    if share_data.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=share_data.expires_in_days)

    # Create share
    share = ContractShare(
        contract_id=uuid_mod.UUID(contract_id),
        external_user_id=share_data.external_user_id,
        shared_by_id=current_user.id,
        can_download=share_data.can_download,
        can_comment=share_data.can_comment,
        expires_at=expires_at,
        message=share_data.message,
    )
    db.add(share)

    # Create access token
    access_token = ExternalAccessToken.create_token(
        token_type=TokenType.CONTRACT_ACCESS,
        expires_in_days=share_data.expires_in_days or 30,
        external_user_id=share_data.external_user_id,
        contract_id=uuid_mod.UUID(contract_id),
        recipient_email=ext_user.email,
        recipient_name=ext_user.full_name,
        max_uses=None,
        created_by_id=current_user.id,
    )
    db.add(access_token)

    await db.commit()
    await db.refresh(share)

    # Send email notification to the external user
    access_url = f"/external/contracts/{access_token.token}"
    try:
        from app.integrations.email import EmailService
        from app.core.config import settings

        email_service = EmailService(db)

        # Build the full URL
        base_url = getattr(settings, 'FRONTEND_URL', None) or "https://34.204.15.143"
        full_url = f"{base_url}{access_url}"

        # Create email body
        shared_by_name = current_user.full_name or current_user.email
        email_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <div style="background: linear-gradient(135deg, #7c3aed, #6d28d9); color: white; padding: 15px 25px; border-radius: 10px; display: inline-block;">
                        <h1 style="margin: 0; font-size: 24px;">Evaluetor</h1>
                    </div>
                </div>

                <h2 style="color: #1f2937; margin-bottom: 20px;">A contract has been shared with you</h2>

                <p>Hello{' ' + ext_user.full_name if ext_user.full_name else ''},</p>

                <p><strong>{shared_by_name}</strong> has shared the following contract with you:</p>

                <div style="background: #f3f4f6; border-radius: 8px; padding: 15px; margin: 20px 0;">
                    <p style="margin: 0; font-weight: bold; color: #374151;">{contract.filename}</p>
                    {f'<p style="margin: 5px 0 0; color: #6b7280; font-size: 14px;">{contract.counterparty or ""}</p>' if contract.counterparty else ''}
                </div>

                {f'<div style="background: #ede9fe; border-left: 4px solid #7c3aed; padding: 15px; margin: 20px 0;"><p style="margin: 0; color: #5b21b6; font-style: italic;">{share_data.message}</p></div>' if share_data.message else ''}

                <p>Your permissions:</p>
                <ul style="color: #4b5563;">
                    <li>View contract details</li>
                    {'<li>Download contract document</li>' if share_data.can_download else ''}
                    {'<li>Add comments</li>' if share_data.can_comment else ''}
                </ul>

                <div style="text-align: center; margin: 30px 0;">
                    <a href="{full_url}" style="background: #7c3aed; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">View Contract</a>
                </div>

                <p style="color: #6b7280; font-size: 14px;">Or copy this link: <a href="{full_url}" style="color: #7c3aed;">{full_url}</a></p>

                {f'<p style="color: #dc2626; font-size: 14px;"><strong>Note:</strong> This link expires on {expires_at.strftime("%B %d, %Y") if expires_at else "never"}.</p>' if expires_at else ''}

                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

                <p style="color: #9ca3af; font-size: 12px; text-align: center;">
                    Powered by Evaluetor Contract Intelligence Platform
                </p>
            </div>
        </body>
        </html>
        """

        await email_service.send_email(
            to_email=ext_user.email,
            to_name=ext_user.full_name or "",
            subject=f"Contract Shared: {contract.filename}",
            body=email_body,
            is_html=True,
        )
        logger.info(f"Sent share notification email to {ext_user.email}")
    except Exception as e:
        # Log error but don't fail the share operation
        logger.warning(f"Failed to send share notification email: {e}")

    return ShareInviteResponse(
        share=ContractShareResponse.model_validate(share),
        access_url=access_url,
        token=access_token.token,
    )


@router.get("/{contract_id}/shares", response_model=ContractShareListResponse)
async def list_contract_shares(
    contract_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    include_revoked: bool = False,
):
    """List all shares for a contract."""
    from app.services.contracts import ContractService
    import uuid as uuid_mod

    # Verify contract exists
    service = ContractService(db, tenant_id=tenant_id)
    contract = await service.get_contract(contract_id, include_clauses=False, include_obligations=False)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Get shares
    query = select(ContractShare).where(
        ContractShare.contract_id == uuid_mod.UUID(contract_id),
    )
    if not include_revoked:
        query = query.where(ContractShare.is_revoked == False)

    result = await db.execute(query)
    shares = result.scalars().all()

    # Build response with external user details
    items = []
    for share in shares:
        share_response = ContractShareWithUser(
            **ContractShareResponse.model_validate(share).model_dump(),
            external_user=ExternalUserSummary.model_validate(share.external_user),
        )
        items.append(share_response)

    return ContractShareListResponse(items=items, total=len(items))


@router.delete("/{contract_id}/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_contract_share(
    contract_id: str,
    share_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Revoke a contract share."""
    from app.services.contracts import ContractService
    import uuid as uuid_mod

    # Verify contract exists
    service = ContractService(db, tenant_id=tenant_id)
    contract = await service.get_contract(contract_id, include_clauses=False, include_obligations=False)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Get share
    share_query = select(ContractShare).where(
        ContractShare.id == uuid_mod.UUID(share_id),
        ContractShare.contract_id == uuid_mod.UUID(contract_id),
    )
    share = (await db.execute(share_query)).scalar_one_or_none()
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found",
        )

    if share.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Share is already revoked",
        )

    # Revoke share
    share.revoke(current_user.id)
    await db.commit()


# ===== Contract Comments Endpoints =====

@router.get("/{contract_id}/comments", response_model=ContractCommentListResponse)
async def list_contract_comments(
    contract_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    include_resolved: bool = True,
    include_internal: bool = True,
):
    """List all comments for a contract."""
    from app.services.contracts import ContractService
    import uuid as uuid_mod

    # Verify contract exists
    service = ContractService(db, tenant_id=tenant_id)
    contract = await service.get_contract(contract_id, include_clauses=False, include_obligations=False)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Build query
    query = select(ContractComment).where(
        ContractComment.contract_id == uuid_mod.UUID(contract_id),
        ContractComment.is_deleted == False,
    )

    if not include_resolved:
        query = query.where(ContractComment.is_resolved == False)

    if not include_internal:
        query = query.where(ContractComment.is_internal == False)

    query = query.order_by(ContractComment.created_at.desc())

    result = await db.execute(query)
    comments = result.scalars().all()

    # Build response
    items = []
    for comment in comments:
        # Count replies
        reply_count_query = select(func.count()).select_from(ContractComment).where(
            ContractComment.parent_id == comment.id,
            ContractComment.is_deleted == False,
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


@router.post("/{contract_id}/comments", response_model=ContractCommentResponse, status_code=status.HTTP_201_CREATED)
async def add_contract_comment(
    contract_id: str,
    comment_data: ContractCommentCreate,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Add a comment to a contract (internal user)."""
    from app.services.contracts import ContractService
    import uuid as uuid_mod

    # Verify contract exists
    service = ContractService(db, tenant_id=tenant_id)
    contract = await service.get_contract(contract_id, include_clauses=False, include_obligations=False)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Validate parent_id if provided
    if comment_data.parent_id:
        parent_query = select(ContractComment).where(
            ContractComment.id == comment_data.parent_id,
            ContractComment.contract_id == uuid_mod.UUID(contract_id),
            ContractComment.is_deleted == False,
        )
        parent = (await db.execute(parent_query)).scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent comment not found",
            )

    # Create comment
    comment = ContractComment(
        contract_id=uuid_mod.UUID(contract_id),
        user_id=current_user.id,
        parent_id=comment_data.parent_id,
        content=comment_data.content,
        clause_id=comment_data.clause_id,
        section_reference=comment_data.section_reference,
        is_internal=comment_data.is_internal,
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


@router.post("/{contract_id}/comments/{comment_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
async def resolve_contract_comment(
    contract_id: str,
    comment_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Mark a comment as resolved."""
    from app.services.contracts import ContractService
    import uuid as uuid_mod

    # Verify contract exists
    service = ContractService(db, tenant_id=tenant_id)
    contract = await service.get_contract(contract_id, include_clauses=False, include_obligations=False)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Get comment
    comment_query = select(ContractComment).where(
        ContractComment.id == uuid_mod.UUID(comment_id),
        ContractComment.contract_id == uuid_mod.UUID(contract_id),
        ContractComment.is_deleted == False,
    )
    comment = (await db.execute(comment_query)).scalar_one_or_none()
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    comment.resolve(current_user.id)
    await db.commit()


@router.delete("/{contract_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract_comment(
    contract_id: str,
    comment_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Soft delete a comment."""
    from app.services.contracts import ContractService
    import uuid as uuid_mod

    # Verify contract exists
    service = ContractService(db, tenant_id=tenant_id)
    contract = await service.get_contract(contract_id, include_clauses=False, include_obligations=False)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Get comment
    comment_query = select(ContractComment).where(
        ContractComment.id == uuid_mod.UUID(comment_id),
        ContractComment.contract_id == uuid_mod.UUID(contract_id),
    )
    comment = (await db.execute(comment_query)).scalar_one_or_none()
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )

    # Only author or admin can delete
    if comment.user_id != current_user.id and current_user.role.value not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only comment author or admin can delete",
        )

    comment.soft_delete()
    await db.commit()


# --- Clause Update Schema ---

class ClauseUpdate(BaseModel):
    clause_type: str | None = None
    text: str | None = None
    summary: str | None = None
    risk_level: str | None = None
    risk_reason: str | None = None
    section_number: str | None = None
    page_number: int | None = None


@router.get("/{contract_id}/download")
async def download_contract_file(
    contract_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    as_pdf: bool = False,
):
    """Download the contract file. Use as_pdf=true to get a PDF version of DOCX files."""
    import os
    import subprocess
    import tempfile
    from pathlib import Path
    from app.services.contracts import ContractService

    service = ContractService(db, tenant_id=tenant_id)
    contract = await service.get_contract(contract_id, include_clauses=False, include_obligations=False)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    if not contract.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract file not found",
        )

    file_path = Path(contract.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract file not found on disk",
        )

    # Convert DOCX to PDF if requested
    mime = contract.mime_type or ""
    is_docx = "wordprocessingml" in mime or "msword" in mime
    if as_pdf and is_docx:
        # Check for cached PDF
        cached_pdf = file_path.with_suffix(".pdf")
        if not cached_pdf.exists():
            # Convert using LibreOffice
            try:
                out_dir = str(file_path.parent)
                subprocess.run(
                    [
                        "libreoffice", "--headless", "--convert-to", "pdf",
                        "--outdir", out_dir, str(file_path),
                    ],
                    check=True,
                    timeout=60,
                    capture_output=True,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to convert document to PDF",
                )

        if not cached_pdf.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PDF conversion produced no output",
            )

        serve_path = cached_pdf
        serve_mime = "application/pdf"
        serve_name = Path(contract.filename).with_suffix(".pdf").name
    else:
        serve_path = file_path
        serve_mime = contract.mime_type or "application/octet-stream"
        serve_name = contract.filename

    def iterfile():
        with open(serve_path, "rb") as f:
            yield from f

    return StreamingResponse(
        iterfile(),
        media_type=serve_mime,
        headers={
            "Content-Disposition": f'attachment; filename="{serve_name}"',
            "Content-Length": str(os.path.getsize(serve_path)),
        },
    )


@router.patch("/{contract_id}/clauses/{clause_id}")
async def update_clause(
    contract_id: str,
    clause_id: str,
    update: ClauseUpdate,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a clause's metadata (type, text, summary, risk info, location)."""
    import uuid as uuid_mod
    from app.services.contracts import ContractService
    from app.models.clause import Clause, ClauseType

    # Verify contract exists and belongs to tenant
    service = ContractService(db, tenant_id=tenant_id)
    contract = await service.get_contract(contract_id, include_clauses=False, include_obligations=False)
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract not found: {contract_id}",
        )

    # Fetch the clause and verify it belongs to this contract
    clause_query = select(Clause).where(
        Clause.id == uuid_mod.UUID(clause_id),
        Clause.contract_id == uuid_mod.UUID(contract_id),
    )
    clause = (await db.execute(clause_query)).scalar_one_or_none()
    if not clause:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clause not found",
        )

    # Apply updates for non-None fields
    if update.clause_type is not None:
        clause.clause_type = ClauseType(update.clause_type)
    if update.text is not None:
        clause.text = update.text
    if update.summary is not None:
        clause.summary = update.summary
    if update.risk_level is not None:
        clause.risk_level = RiskLevel(update.risk_level)
    if update.risk_reason is not None:
        clause.risk_reason = update.risk_reason
    if update.section_number is not None:
        clause.section_number = update.section_number
    if update.page_number is not None:
        clause.page_number = update.page_number

    await db.commit()
    await db.refresh(clause)

    return {
        "id": str(clause.id),
        "contract_id": str(clause.contract_id),
        "clause_type": clause.clause_type.value if clause.clause_type else None,
        "text": clause.text,
        "summary": clause.summary,
        "section_number": clause.section_number,
        "page_number": clause.page_number,
        "risk_level": clause.risk_level.value if clause.risk_level else None,
        "risk_reason": clause.risk_reason,
        "confidence_score": clause.confidence_score,
        "char_start": clause.char_start,
        "char_end": clause.char_end,
    }
