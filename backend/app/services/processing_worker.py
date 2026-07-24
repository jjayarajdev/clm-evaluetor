"""Contract processing worker.

Background worker that consumes jobs from the processing queue
and runs the contract indexing + deep analysis pipeline.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.contract import Contract, ContractStatus
from app.models.processing_job import ContractProcessingJob, ProcessingJobStatus
from app.services.processing_queue import ProcessingQueueService

logger = logging.getLogger(__name__)

# Worker state
_worker_task: asyncio.Task | None = None
_worker_running = False


async def _sync_tracker_to_job(job_id, contract_id: str) -> None:
    """Periodically flush in-memory tracker progress into the DB job row.

    The tracker lives in this worker process only; API requests may land on
    other uvicorn workers. Persisting stage/percent lets any process serve
    live step-by-step progress from the job row.
    """
    from app.services.processing_queue import ProcessingQueueService
    from app.services.progress_tracker import get_progress_tracker

    tracker = get_progress_tracker()
    try:
        while True:
            await asyncio.sleep(3)
            progress = tracker.get_progress(contract_id)
            if not progress:
                continue
            try:
                async with async_session_maker() as s:
                    queue = ProcessingQueueService(s)
                    await queue.update_progress(
                        job_id,
                        progress.stage.value if hasattr(progress.stage, "value") else str(progress.stage),
                        progress.progress_percent,
                        progress.message or "",
                    )
                    await s.commit()
            except Exception:
                pass
    except asyncio.CancelledError:
        pass


async def _process_one_job(job, session: AsyncSession) -> None:
    """Process a single contract job through the full pipeline."""
    from app.services.indexer import IndexingService

    contract_id = str(job.contract_id)
    user_id = str(job.user_id)
    file_path = job.file_path
    queue = ProcessingQueueService(session)

    progress_sync = asyncio.create_task(_sync_tracker_to_job(job.id, contract_id))

    try:
        # Get the contract
        result = await session.execute(
            select(Contract).where(Contract.id == job.contract_id)
        )
        contract = result.scalar_one_or_none()
        if not contract:
            await queue.fail_job(job.id, f"Contract not found: {contract_id}")
            await session.commit()
            return

        # Update contract status
        contract.status = ContractStatus.PROCESSING
        await session.commit()

        # Update job progress
        await queue.update_progress(job.id, "parsing", 10, f"Parsing {contract.filename}")

        # Run indexer pipeline
        indexer = IndexingService(session)
        success = await indexer.index_contract(
            contract=contract,
            user_id=user_id,
            user_role="admin",
        )

        if success:
            contract.status = ContractStatus.COMPLETED
            await session.commit()

            await queue.update_progress(job.id, "deep_analysis", 70, "Running deep analysis")
            await session.commit()  # Release locks before long-running deep analysis

            # Run deep analysis (clauses, obligations, SLAs, etc.)
            try:
                from app.routers.contracts import _run_deep_analysis
                await _run_deep_analysis(contract_id, user_id, file_path)
            except Exception as e:
                logger.warning(f"Deep analysis failed for {contract_id}: {e}")
                # Deep analysis failure is non-fatal

            # Complete the job
            await queue.complete_job(job.id, details={
                "counterparty": contract.counterparty,
                "contract_type": contract.contract_type or None,
                "risk_level": contract.risk_level.value if contract.risk_level else None,
            })
            await session.commit()
            logger.info(f"Job completed: contract {contract_id}")

        else:
            contract.status = ContractStatus.FAILED
            contract.processing_error = "Indexing failed"
            await session.commit()
            await queue.fail_job(job.id, "Indexing pipeline returned failure")
            await session.commit()

    except Exception as e:
        logger.exception(f"Job failed for contract {contract_id}: {e}")

        # Mark contract as failed
        try:
            result = await session.execute(
                select(Contract).where(Contract.id == job.contract_id)
            )
            contract = result.scalar_one_or_none()
            if contract:
                contract.status = ContractStatus.FAILED
                contract.processing_error = str(e)[:500]
        except Exception:
            pass

        await queue.fail_job(job.id, str(e))
        await session.commit()

    finally:
        progress_sync.cancel()


async def _check_batch_completion(batch_id: str, session: AsyncSession) -> None:
    """Check if a batch is fully processed, run hierarchy detection, and auto-approve links."""
    queue = ProcessingQueueService(session)
    batch_status = await queue.get_batch_progress(batch_id)

    if not batch_status["all_done"]:
        return

    # All jobs in batch are done
    completed_ids = [
        j["contract_id"] for j in batch_status["jobs"]
        if j["status"] == ProcessingJobStatus.COMPLETED.value
    ]

    if len(completed_ids) < 2:
        return

    # Stage 0: Deterministic framework-set linking from filename structure
    # (Exhibit/Attachment sets under a single master) — runs before the LLM
    # detection so its links take precedence and the LLM only fills gaps.
    try:
        from app.services.framework_linker import link_framework_sets

        result = await session.execute(
            select(Contract).where(Contract.id == completed_ids[0])
        )
        first = result.scalar_one_or_none()
        if first and first.tenant_id:
            from app.services.framework_linker import (
                link_by_counterparty_master,
                link_change_orders,
            )

            n = await link_framework_sets(session, first.tenant_id)
            n += await link_by_counterparty_master(session, first.tenant_id)
            n += await link_change_orders(session, first.tenant_id)
            if n:
                from app.services.family_enrichment import enrich_from_family
                from app.services.group_sync import sync_auto_family_groups

                await sync_auto_family_groups(session, first.tenant_id)
                await enrich_from_family(session, first.tenant_id)
                await session.commit()
                logger.info(f"Batch {batch_id}: framework linking created {n} links")
    except Exception as e:
        logger.warning(f"Framework linking failed for batch {batch_id}: {e}")

    # Stage 1: Run hierarchy detection (new pairwise system)
    try:
        from app.services.hierarchy_detection import detect_hierarchy

        # Get tenant_id from first contract
        result = await session.execute(
            select(Contract).where(Contract.id == completed_ids[0])
        )
        contract = result.scalar_one_or_none()
        tenant_id = contract.tenant_id if contract else None

        if tenant_id:
            import uuid as _uuid
            contract_uuids = [
                cid if isinstance(cid, _uuid.UUID) else _uuid.UUID(str(cid))
                for cid in completed_ids
            ]
            num_suggestions = await detect_hierarchy(
                session, contract_uuids, tenant_id, batch_id
            )
            if num_suggestions:
                await session.commit()
                logger.info(
                    f"Batch {batch_id}: hierarchy detection created "
                    f"{num_suggestions} suggestions"
                )
    except Exception as e:
        logger.warning(f"Hierarchy detection failed for batch {batch_id}: {e}")

    # Stage 2: Auto-approve high-confidence links (existing system)
    try:
        from app.services.auto_link_detector import auto_approve_batch_links
        approved = await auto_approve_batch_links(session, completed_ids)
        if approved:
            await session.commit()
            logger.info(
                f"Batch {batch_id}: auto-approved {len(approved)} contract links"
            )
    except Exception as e:
        logger.warning(f"Auto-approve failed for batch {batch_id}: {e}")


async def _worker_loop() -> None:
    """Main worker loop: poll for jobs, process them."""
    global _worker_running
    _worker_running = True

    semaphore = asyncio.Semaphore(2)  # Max 2 concurrent processing tasks
    stuck_check_counter = 0

    logger.info("Processing worker started")

    while _worker_running:
        try:
            async with async_session_maker() as session:
                queue = ProcessingQueueService(session)

                # Periodically check for stuck jobs (every ~60 iterations = 5 min)
                stuck_check_counter += 1
                if stuck_check_counter >= 60:
                    stuck_check_counter = 0
                    stuck = await queue.detect_stuck_jobs(timeout_minutes=30)
                    if stuck:
                        await session.commit()

                # Claim next job
                job = await queue.claim_next_job()
                if not job:
                    await session.commit()
                    await asyncio.sleep(5)
                    continue

                await session.commit()

                # Process with concurrency limit
                async with semaphore:
                    async with async_session_maker() as process_session:
                        # Re-fetch job in new session
                        result = await process_session.execute(
                            select(ContractProcessingJob)
                            .where(ContractProcessingJob.id == job.id)
                        )
                        fresh_job = result.scalar_one_or_none()
                        if fresh_job:
                            batch_id = fresh_job.batch_id
                            await _process_one_job(fresh_job, process_session)

                            # Check batch completion
                            if batch_id:
                                await _check_batch_completion(batch_id, process_session)

        except asyncio.CancelledError:
            logger.info("Processing worker cancelled")
            break
        except Exception as e:
            logger.exception(f"Worker loop error: {e}")
            await asyncio.sleep(10)  # Back off on errors

    logger.info("Processing worker stopped")


async def start_processing_worker() -> None:
    """Start the background processing worker."""
    global _worker_task
    if _worker_task and not _worker_task.done():
        logger.info("Processing worker already running")
        return

    _worker_task = asyncio.create_task(_worker_loop())
    logger.info("Processing worker task created")


async def stop_processing_worker() -> None:
    """Stop the background processing worker."""
    global _worker_running, _worker_task
    _worker_running = False

    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass

    _worker_task = None
    logger.info("Processing worker stopped")
