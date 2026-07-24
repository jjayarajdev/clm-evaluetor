"""Scheduler Service.

Manages background scheduled jobs like SLA comparisons.
Singleton pattern with auto-start on application startup.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Coroutine

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import async_session_maker
from app.models.scheduler import SchedulerJob, SchedulerJobHistory, SchedulerJobStatus
from app.services.sla_comparison import SLAComparisonEngine
from app.models.contract import Contract, ContractStatus

logger = logging.getLogger(__name__)


# Job execution function type
JobExecutor = Callable[[AsyncSession], Coroutine[Any, Any, dict]]


class SchedulerService:
    """Scheduler service for running background jobs.

    Singleton pattern - use get_scheduler() to get the instance.
    """

    _instance: "SchedulerService | None" = None
    _lock = asyncio.Lock()

    def __init__(self, session_maker: async_sessionmaker):
        self._session_maker = session_maker
        self._is_running = False
        self._started_at: datetime | None = None
        self._task: asyncio.Task | None = None
        self._job_executors: dict[str, JobExecutor] = {}

        # Register default job executors
        self._register_default_executors()

    @classmethod
    async def get_instance(
        cls,
        session_maker: async_sessionmaker | None = None,
    ) -> "SchedulerService":
        """Get or create the singleton instance.

        Args:
            session_maker: SQLAlchemy async session maker (required on first call).

        Returns:
            SchedulerService instance.
        """
        async with cls._lock:
            if cls._instance is None:
                if session_maker is None:
                    session_maker = async_session_maker
                cls._instance = cls(session_maker)
            return cls._instance

    def _register_default_executors(self) -> None:
        """Register default job executors."""
        self._job_executors["sla_comparison"] = self._execute_sla_comparison_job
        self._job_executors["auto_family_sync"] = self._execute_auto_family_sync_job

    def register_executor(self, job_name: str, executor: JobExecutor) -> None:
        """Register a job executor.

        Args:
            job_name: Name of the job.
            executor: Async function that executes the job.
        """
        self._job_executors[job_name] = executor

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._is_running

    @property
    def started_at(self) -> datetime | None:
        """Get scheduler start time."""
        return self._started_at

    async def start(self) -> None:
        """Start the scheduler background loop."""
        if self._is_running:
            logger.warning("Scheduler already running")
            return

        self._is_running = True
        self._started_at = datetime.now(timezone.utc)
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started")

        # Ensure default jobs exist
        await self._ensure_default_jobs()

    async def stop(self) -> None:
        """Stop the scheduler."""
        if not self._is_running:
            return

        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("Scheduler stopped")

    async def _ensure_default_jobs(self) -> None:
        """Ensure default scheduled jobs exist in database."""
        async with self._session_maker() as db:
            # Check for SLA comparison job
            result = await db.execute(
                select(SchedulerJob).where(SchedulerJob.job_name == "sla_comparison")
            )
            if not result.scalars().first():
                job = SchedulerJob(
                    job_name="sla_comparison",
                    job_type="comparison",
                    description="Compares contracted SLAs against actual performance values from external systems",
                    interval_seconds=900,  # 15 minutes
                    is_enabled=True,
                    next_run_at=datetime.now(timezone.utc) + timedelta(seconds=60),  # First run in 1 minute
                )
                db.add(job)
                await db.commit()
                logger.info("Created default SLA comparison job")

            # Nightly auto_family group reconcile
            result = await db.execute(
                select(SchedulerJob).where(SchedulerJob.job_name == "auto_family_sync")
            )
            if not result.scalars().first():
                job = SchedulerJob(
                    job_name="auto_family_sync",
                    job_type="maintenance",
                    description="Reconciles auto_family contract groups with the contract link graph",
                    interval_seconds=86400,  # nightly
                    is_enabled=True,
                    next_run_at=datetime.now(timezone.utc) + timedelta(seconds=300),
                )
                db.add(job)
                await db.commit()
                logger.info("Created default auto_family sync job")

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        logger.info("Scheduler loop started")

        while self._is_running:
            try:
                await self._check_and_run_jobs()
                # Check every 10 seconds
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                await asyncio.sleep(30)  # Wait longer on error

        logger.info("Scheduler loop ended")

    async def _check_and_run_jobs(self) -> None:
        """Check for jobs that need to run and execute them."""
        now = datetime.now(timezone.utc)

        async with self._session_maker() as db:
            # Find jobs that are due to run
            result = await db.execute(
                select(SchedulerJob)
                .where(SchedulerJob.is_enabled == True)
                .where(SchedulerJob.next_run_at <= now)
                .where(
                    # Not currently running
                    (SchedulerJob.last_run_status != SchedulerJobStatus.RUNNING)
                    | (SchedulerJob.last_run_status.is_(None))
                )
            )
            jobs = result.scalars().all()

            for job in jobs:
                if job.job_name in self._job_executors:
                    # Run job in background task
                    asyncio.create_task(self._execute_job(job.id, job.job_name))
                else:
                    logger.warning(f"No executor registered for job: {job.job_name}")

    async def _execute_job(self, job_id: uuid.UUID, job_name: str) -> None:
        """Execute a scheduled job.

        Args:
            job_id: Job ID from database.
            job_name: Job name for executor lookup.
        """
        started_at = datetime.now(timezone.utc)
        history_id: uuid.UUID | None = None
        error_message: str | None = None
        items_processed: int | None = None
        metadata: dict | None = None

        async with self._session_maker() as db:
            try:
                # Mark job as running
                await db.execute(
                    update(SchedulerJob)
                    .where(SchedulerJob.id == job_id)
                    .values(
                        last_run_status=SchedulerJobStatus.RUNNING,
                        last_run_at=started_at,
                    )
                )

                # Create history entry
                history = SchedulerJobHistory(
                    job_id=job_id,
                    started_at=started_at,
                    status=SchedulerJobStatus.RUNNING,
                    created_at=started_at,
                )
                db.add(history)
                await db.flush()
                history_id = history.id
                await db.commit()

                # Execute the job
                logger.info(f"Executing job: {job_name}")
                executor = self._job_executors[job_name]
                result = await executor(db)

                items_processed = result.get("items_processed", 0)
                metadata = result.get("metadata")

                # Mark as success
                status = SchedulerJobStatus.SUCCESS

            except Exception as e:
                logger.error(f"Job {job_name} failed: {e}", exc_info=True)
                error_message = str(e)
                status = SchedulerJobStatus.FAILED

            finally:
                # Calculate duration
                completed_at = datetime.now(timezone.utc)
                duration_ms = int((completed_at - started_at).total_seconds() * 1000)

                # Get job to calculate next run time
                result = await db.execute(
                    select(SchedulerJob).where(SchedulerJob.id == job_id)
                )
                job = result.scalars().first()
                next_run_at = completed_at + timedelta(seconds=job.interval_seconds if job else 900)

                # Update job status
                await db.execute(
                    update(SchedulerJob)
                    .where(SchedulerJob.id == job_id)
                    .values(
                        last_run_status=status,
                        last_run_duration_ms=duration_ms,
                        last_run_error=error_message,
                        next_run_at=next_run_at,
                        total_runs=SchedulerJob.total_runs + 1,
                        successful_runs=(
                            SchedulerJob.successful_runs + 1
                            if status == SchedulerJobStatus.SUCCESS
                            else SchedulerJob.successful_runs
                        ),
                        failed_runs=(
                            SchedulerJob.failed_runs + 1
                            if status == SchedulerJobStatus.FAILED
                            else SchedulerJob.failed_runs
                        ),
                    )
                )

                # Update history entry
                if history_id:
                    await db.execute(
                        update(SchedulerJobHistory)
                        .where(SchedulerJobHistory.id == history_id)
                        .values(
                            completed_at=completed_at,
                            duration_ms=duration_ms,
                            status=status,
                            error_message=error_message,
                            items_processed=items_processed,
                            run_metadata=metadata,
                        )
                    )

                await db.commit()

                logger.info(
                    f"Job {job_name} completed with status {status.value} "
                    f"in {duration_ms}ms. Next run: {next_run_at}"
                )

    async def _execute_auto_family_sync_job(self, db: AsyncSession) -> dict:
        """Nightly reconcile of auto_family contract groups for all tenants."""
        from app.models.tenant import Tenant
        from app.services.family_enrichment import enrich_from_family
        from app.services.group_sync import (
            detect_missing_references,
            sync_auto_family_groups,
        )
        from app.services.reference_resolver import resolve_declared_references

        tenant_ids = (await db.execute(select(Tenant.id))).scalars().all()
        touched = 0
        findings_changed = 0
        links_resolved = 0
        enriched = 0
        errors = []
        for tid in tenant_ids:
            try:
                from app.services.framework_linker import (
                    link_by_counterparty_master,
                    link_change_orders,
                )

                n_links, _ = await resolve_declared_references(db, tid)
                n_links += await link_by_counterparty_master(db, tid)
                n_links += await link_change_orders(db, tid)
                links_resolved += n_links
                touched += await sync_auto_family_groups(db, tid)
                enriched += await enrich_from_family(db, tid)
                findings_changed += await detect_missing_references(db, tid)
                await db.commit()
            except Exception as e:
                errors.append(f"{tid}: {e}")
                await db.rollback()
        return {
            "tenants": len(tenant_ids),
            "groups_touched": touched,
            "links_resolved": links_resolved,
            "enriched": enriched,
            "findings_changed": findings_changed,
            "errors": errors,
        }

    async def _execute_sla_comparison_job(self, db: AsyncSession) -> dict:
        """Execute SLA comparison for all active contracts.

        Args:
            db: Database session.

        Returns:
            Dict with execution results.
        """
        from datetime import date

        # Get all active contracts with SLAs
        result = await db.execute(
            select(Contract)
            .where(Contract.status == ContractStatus.COMPLETED)
        )
        contracts = result.scalars().all()

        total_contracts = 0
        total_slas = 0
        total_breaches = 0
        errors = []

        # Calculate date range (current month)
        today = date.today()
        start_date = today.replace(day=1)
        end_date = today

        engine = SLAComparisonEngine(db)

        for contract in contracts:
            try:
                summary = await engine.compare_contract_slas(
                    contract.id,
                    start_date,
                    end_date,
                    store_results=True,
                )
                total_contracts += 1
                total_slas += summary.total_slas
                total_breaches += summary.breach_count
            except Exception as e:
                errors.append(f"Contract {contract.id}: {str(e)}")
                logger.error(f"SLA comparison failed for contract {contract.id}: {e}")

        await db.commit()

        return {
            "items_processed": total_contracts,
            "metadata": {
                "contracts_processed": total_contracts,
                "total_slas_compared": total_slas,
                "total_breaches_found": total_breaches,
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "errors": errors if errors else None,
            },
        }

    async def trigger_job(self, job_name: str) -> tuple[bool, str, str | None]:
        """Manually trigger a job to run immediately.

        Args:
            job_name: Name of the job to trigger.

        Returns:
            Tuple of (success, message, execution_id).
        """
        async with self._session_maker() as db:
            # Find the job
            result = await db.execute(
                select(SchedulerJob).where(SchedulerJob.job_name == job_name)
            )
            job = result.scalars().first()

            if not job:
                return False, f"Job '{job_name}' not found", None

            if job.last_run_status == SchedulerJobStatus.RUNNING:
                return False, f"Job '{job_name}' is already running", None

            if job_name not in self._job_executors:
                return False, f"No executor registered for job '{job_name}'", None

            # Trigger the job in background
            execution_id = str(uuid.uuid4())
            asyncio.create_task(self._execute_job(job.id, job_name))

            return True, f"Job '{job_name}' triggered successfully", execution_id

    async def get_status(self) -> dict:
        """Get scheduler status.

        Returns:
            Dict with scheduler status info.
        """
        async with self._session_maker() as db:
            # Get job counts
            result = await db.execute(select(SchedulerJob))
            jobs = result.scalars().all()

            total_jobs = len(jobs)
            enabled_jobs = sum(1 for j in jobs if j.is_enabled)
            disabled_jobs = total_jobs - enabled_jobs
            jobs_running = sum(1 for j in jobs if j.last_run_status == SchedulerJobStatus.RUNNING)

            # Find next job to run
            next_job = min(
                (j for j in jobs if j.is_enabled and j.next_run_at),
                key=lambda j: j.next_run_at,
                default=None,
            )

            return {
                "is_running": self._is_running,
                "started_at": self._started_at.isoformat() if self._started_at else None,
                "total_jobs": total_jobs,
                "enabled_jobs": enabled_jobs,
                "disabled_jobs": disabled_jobs,
                "jobs_running": jobs_running,
                "next_job_run": next_job.next_run_at.isoformat() if next_job and next_job.next_run_at else None,
                "next_job_name": next_job.job_name if next_job else None,
            }

    async def get_jobs(self) -> list[SchedulerJob]:
        """Get all scheduled jobs.

        Returns:
            List of SchedulerJob models.
        """
        async with self._session_maker() as db:
            result = await db.execute(
                select(SchedulerJob).order_by(SchedulerJob.job_name)
            )
            return list(result.scalars().all())

    async def get_job_by_name(self, job_name: str) -> SchedulerJob | None:
        """Get a job by name.

        Args:
            job_name: Job name.

        Returns:
            SchedulerJob or None.
        """
        async with self._session_maker() as db:
            result = await db.execute(
                select(SchedulerJob).where(SchedulerJob.job_name == job_name)
            )
            return result.scalars().first()

    async def update_job(self, job_name: str, data: dict) -> SchedulerJob | None:
        """Update a job's configuration.

        Args:
            job_name: Job name.
            data: Fields to update.

        Returns:
            Updated SchedulerJob or None if not found.
        """
        async with self._session_maker() as db:
            result = await db.execute(
                select(SchedulerJob).where(SchedulerJob.job_name == job_name)
            )
            job = result.scalars().first()

            if not job:
                return None

            for key, value in data.items():
                if hasattr(job, key) and value is not None:
                    setattr(job, key, value)

            # Recalculate next_run_at if interval changed
            if "interval_seconds" in data and data["interval_seconds"]:
                job.next_run_at = datetime.now(timezone.utc) + timedelta(seconds=data["interval_seconds"])

            await db.commit()
            await db.refresh(job)
            return job

    async def get_job_history(
        self,
        job_name: str,
        limit: int = 50,
    ) -> list[SchedulerJobHistory]:
        """Get execution history for a job.

        Args:
            job_name: Job name.
            limit: Maximum number of records to return.

        Returns:
            List of SchedulerJobHistory records.
        """
        async with self._session_maker() as db:
            # Get job ID first
            result = await db.execute(
                select(SchedulerJob.id).where(SchedulerJob.job_name == job_name)
            )
            job_id = result.scalar()

            if not job_id:
                return []

            result = await db.execute(
                select(SchedulerJobHistory)
                .where(SchedulerJobHistory.job_id == job_id)
                .order_by(SchedulerJobHistory.started_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())


# Module-level convenience function
_scheduler: SchedulerService | None = None


async def get_scheduler() -> SchedulerService:
    """Get the scheduler service instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = await SchedulerService.get_instance()
    return _scheduler


async def start_scheduler() -> None:
    """Start the scheduler (convenience function for main.py)."""
    scheduler = await get_scheduler()
    await scheduler.start()


async def stop_scheduler() -> None:
    """Stop the scheduler (convenience function for main.py)."""
    global _scheduler
    if _scheduler:
        await _scheduler.stop()
        _scheduler = None
