"""Contract processing job queue service.

Provides reliable, DB-backed job queue for contract processing
with progress tracking, retry logic, and batch status monitoring.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.processing_job import ContractProcessingJob, ProcessingJobStatus

logger = logging.getLogger(__name__)


class ProcessingQueueService:
    """Manages the contract processing job queue."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def enqueue_contract(
        self,
        contract_id: str,
        user_id: str,
        file_path: str,
        tenant_id: str,
        batch_id: str | None = None,
        priority: int = 0,
    ) -> ContractProcessingJob:
        """Add a contract to the processing queue."""
        job = ContractProcessingJob(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(tenant_id),
            contract_id=uuid.UUID(contract_id),
            user_id=uuid.UUID(user_id),
            file_path=file_path,
            batch_id=batch_id,
            status=ProcessingJobStatus.QUEUED.value,
            priority=priority,
        )
        self.db.add(job)
        await self.db.flush()
        logger.info(f"Enqueued contract {contract_id} (batch={batch_id})")
        return job

    async def enqueue_batch(
        self,
        contracts: list[tuple[str, str, str]],
        batch_id: str,
        tenant_id: str,
    ) -> list[ContractProcessingJob]:
        """Enqueue multiple contracts as a batch.

        Args:
            contracts: List of (contract_id, user_id, file_path) tuples.
            batch_id: Shared batch identifier.
            tenant_id: Tenant ID.

        Returns:
            List of created jobs.
        """
        jobs = []
        for contract_id, user_id, file_path in contracts:
            job = await self.enqueue_contract(
                contract_id=contract_id,
                user_id=user_id,
                file_path=file_path,
                tenant_id=tenant_id,
                batch_id=batch_id,
            )
            jobs.append(job)
        logger.info(f"Enqueued batch {batch_id} with {len(jobs)} contracts")
        return jobs

    async def claim_next_job(self) -> ContractProcessingJob | None:
        """Atomically claim the next queued job for processing.

        Uses SELECT FOR UPDATE SKIP LOCKED to prevent double-processing.
        """
        query = (
            select(ContractProcessingJob)
            .where(ContractProcessingJob.status == ProcessingJobStatus.QUEUED.value)
            .order_by(
                ContractProcessingJob.priority.desc(),
                ContractProcessingJob.created_at.asc(),
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )

        result = await self.db.execute(query)
        job = result.scalar_one_or_none()

        if job:
            job.status = ProcessingJobStatus.PROCESSING.value
            job.started_at = datetime.now(timezone.utc)
            job.stage = "starting"
            job.message = "Processing started"
            await self.db.flush()
            logger.info(f"Claimed job {job.id} for contract {job.contract_id}")

        return job

    async def update_progress(
        self,
        job_id: uuid.UUID,
        stage: str,
        progress_percent: int,
        message: str | None = None,
    ) -> None:
        """Update job progress. Also updates the in-memory progress tracker for SSE."""
        await self.db.execute(
            update(ContractProcessingJob)
            .where(ContractProcessingJob.id == job_id)
            .values(
                stage=stage,
                progress_percent=progress_percent,
                message=message,
                updated_at=datetime.now(timezone.utc),
            )
        )

        # Also update in-memory tracker for SSE subscribers
        try:
            from app.services.progress_tracker import get_progress_tracker
            tracker = get_progress_tracker()
            # Find the contract_id for this job
            result = await self.db.execute(
                select(ContractProcessingJob.contract_id)
                .where(ContractProcessingJob.id == job_id)
            )
            contract_id = result.scalar_one_or_none()
            if contract_id:
                tracker.update_progress(
                    str(contract_id), stage, message or "",
                )
        except Exception:
            pass  # SSE is best-effort

    async def complete_job(
        self,
        job_id: uuid.UUID,
        details: dict | None = None,
    ) -> None:
        """Mark a job as completed."""
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(ContractProcessingJob)
            .where(ContractProcessingJob.id == job_id)
            .values(
                status=ProcessingJobStatus.COMPLETED.value,
                stage="completed",
                progress_percent=100,
                message="Processing complete",
                completed_at=now,
                updated_at=now,
                details=details,
            )
        )
        logger.info(f"Completed job {job_id}")

    async def fail_job(
        self,
        job_id: uuid.UUID,
        error: str,
    ) -> None:
        """Mark a job as failed. Re-queues if retries remain."""
        result = await self.db.execute(
            select(ContractProcessingJob).where(ContractProcessingJob.id == job_id)
        )
        job = result.scalar_one_or_none()
        if not job:
            return

        job.retry_count += 1
        job.error = error[:2000]
        job.updated_at = datetime.now(timezone.utc)

        if job.retry_count < job.max_retries:
            # Re-queue for retry
            job.status = ProcessingJobStatus.QUEUED.value
            job.stage = None
            job.progress_percent = 0
            job.message = f"Retrying ({job.retry_count}/{job.max_retries})"
            job.started_at = None
            logger.warning(
                f"Job {job_id} failed (attempt {job.retry_count}), re-queued: {error[:100]}"
            )
        else:
            # Max retries exhausted
            job.status = ProcessingJobStatus.FAILED.value
            job.completed_at = datetime.now(timezone.utc)
            job.message = f"Failed after {job.max_retries} attempts"
            logger.error(f"Job {job_id} permanently failed: {error[:200]}")

        await self.db.flush()

    async def detect_stuck_jobs(
        self,
        timeout_minutes: int = 30,
    ) -> int:
        """Find and re-queue jobs stuck in processing state."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

        result = await self.db.execute(
            select(ContractProcessingJob).where(
                ContractProcessingJob.status == ProcessingJobStatus.PROCESSING.value,
                ContractProcessingJob.started_at < cutoff,
            )
        )
        stuck_jobs = result.scalars().all()

        for job in stuck_jobs:
            job.retry_count += 1
            if job.retry_count < job.max_retries:
                job.status = ProcessingJobStatus.QUEUED.value
                job.stage = None
                job.progress_percent = 0
                job.message = f"Re-queued after stuck detection (attempt {job.retry_count})"
                job.started_at = None
            else:
                job.status = ProcessingJobStatus.STUCK.value
                job.message = "Stuck: max retries exhausted"
                job.completed_at = datetime.now(timezone.utc)
            job.updated_at = datetime.now(timezone.utc)

        if stuck_jobs:
            await self.db.flush()
            logger.warning(f"Detected {len(stuck_jobs)} stuck processing jobs")

        return len(stuck_jobs)

    async def get_batch_progress(
        self,
        batch_id: str,
    ) -> dict:
        """Get aggregate processing status for a batch."""
        result = await self.db.execute(
            select(ContractProcessingJob)
            .where(ContractProcessingJob.batch_id == batch_id)
            .order_by(ContractProcessingJob.created_at)
        )
        jobs = result.scalars().all()

        if not jobs:
            return {"batch_id": batch_id, "total": 0, "jobs": []}

        status_counts = {}
        job_details = []
        for job in jobs:
            status_counts[job.status] = status_counts.get(job.status, 0) + 1
            job_details.append({
                "contract_id": str(job.contract_id),
                "status": job.status,
                "stage": job.stage,
                "progress_percent": job.progress_percent,
                "message": job.message,
                "error": job.error,
                "retry_count": job.retry_count,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            })

        total = len(jobs)
        completed = status_counts.get(ProcessingJobStatus.COMPLETED.value, 0)
        failed = status_counts.get(ProcessingJobStatus.FAILED.value, 0)
        overall_progress = sum(j.progress_percent for j in jobs) // total if total else 0

        return {
            "batch_id": batch_id,
            "total": total,
            "completed": completed,
            "failed": failed,
            "processing": status_counts.get(ProcessingJobStatus.PROCESSING.value, 0),
            "queued": status_counts.get(ProcessingJobStatus.QUEUED.value, 0),
            "stuck": status_counts.get(ProcessingJobStatus.STUCK.value, 0),
            "overall_progress": overall_progress,
            "all_done": completed + failed == total,
            "jobs": job_details,
        }

    async def get_job_by_contract(
        self,
        contract_id: str,
    ) -> ContractProcessingJob | None:
        """Get the most recent processing job for a contract."""
        result = await self.db.execute(
            select(ContractProcessingJob)
            .where(ContractProcessingJob.contract_id == uuid.UUID(contract_id))
            .order_by(ContractProcessingJob.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_queue_stats(self) -> dict:
        """Get overall queue statistics."""
        result = await self.db.execute(
            select(
                ContractProcessingJob.status,
                func.count(ContractProcessingJob.id),
            )
            .group_by(ContractProcessingJob.status)
        )
        counts = {row[0]: row[1] for row in result.all()}
        return {
            "queued": counts.get(ProcessingJobStatus.QUEUED.value, 0),
            "processing": counts.get(ProcessingJobStatus.PROCESSING.value, 0),
            "completed": counts.get(ProcessingJobStatus.COMPLETED.value, 0),
            "failed": counts.get(ProcessingJobStatus.FAILED.value, 0),
            "stuck": counts.get(ProcessingJobStatus.STUCK.value, 0),
        }
