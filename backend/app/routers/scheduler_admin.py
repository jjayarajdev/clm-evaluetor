"""Scheduler Admin router for managing scheduled jobs."""

from fastapi import APIRouter, HTTPException

from app.core.deps import AdminUser
from app.models.scheduler import SchedulerJob, SchedulerJobHistory
from app.schemas.scheduler import (
    SchedulerJobHistoryListResponse,
    SchedulerJobHistoryResponse,
    SchedulerJobListResponse,
    SchedulerJobResponse,
    SchedulerJobUpdate,
    SchedulerRunResponse,
    SchedulerStatusResponse,
)
from app.services.scheduler_service import get_scheduler

router = APIRouter(prefix="/api/admin/scheduler", tags=["Scheduler Admin"])


# ============================================================================
# Helper Functions
# ============================================================================


def job_to_response(job: SchedulerJob) -> SchedulerJobResponse:
    """Convert SchedulerJob model to response schema."""
    return SchedulerJobResponse(
        id=str(job.id),
        job_name=job.job_name,
        job_type=job.job_type,
        description=job.description,
        interval_seconds=job.interval_seconds,
        is_enabled=job.is_enabled,
        last_run_at=job.last_run_at,
        next_run_at=job.next_run_at,
        last_run_status=job.last_run_status.value if job.last_run_status else None,
        last_run_duration_ms=job.last_run_duration_ms,
        last_run_error=job.last_run_error,
        total_runs=job.total_runs,
        successful_runs=job.successful_runs,
        failed_runs=job.failed_runs,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def history_to_response(history: SchedulerJobHistory) -> SchedulerJobHistoryResponse:
    """Convert SchedulerJobHistory model to response schema."""
    return SchedulerJobHistoryResponse(
        id=str(history.id),
        job_id=str(history.job_id),
        started_at=history.started_at,
        completed_at=history.completed_at,
        duration_ms=history.duration_ms,
        status=history.status.value if history.status else "running",
        error_message=history.error_message,
        items_processed=history.items_processed,
        run_metadata=history.run_metadata,
    )


# ============================================================================
# Scheduler Status Endpoints
# ============================================================================


@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status(
    admin: AdminUser,
):
    """Get overall scheduler status.

    Requires admin role.
    """
    scheduler = await get_scheduler()
    status = await scheduler.get_status()
    return SchedulerStatusResponse(
        is_running=status["is_running"],
        started_at=status["started_at"],
        total_jobs=status["total_jobs"],
        enabled_jobs=status["enabled_jobs"],
        disabled_jobs=status["disabled_jobs"],
        jobs_running=status["jobs_running"],
        next_job_run=status["next_job_run"],
        next_job_name=status["next_job_name"],
    )


# ============================================================================
# Job Management Endpoints
# ============================================================================


@router.get("/jobs", response_model=SchedulerJobListResponse)
async def list_scheduler_jobs(
    admin: AdminUser,
):
    """List all scheduled jobs.

    Requires admin role.
    """
    scheduler = await get_scheduler()
    jobs = await scheduler.get_jobs()
    return SchedulerJobListResponse(
        items=[job_to_response(j) for j in jobs],
        total=len(jobs),
    )


@router.get("/jobs/{job_name}", response_model=SchedulerJobResponse)
async def get_scheduler_job(
    job_name: str,
    admin: AdminUser,
):
    """Get a specific scheduled job by name.

    Requires admin role.
    """
    scheduler = await get_scheduler()
    job = await scheduler.get_job_by_name(job_name)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_name}' not found")
    return job_to_response(job)


@router.patch("/jobs/{job_name}", response_model=SchedulerJobResponse)
async def update_scheduler_job(
    job_name: str,
    data: SchedulerJobUpdate,
    admin: AdminUser,
):
    """Update a scheduled job's configuration.

    Requires admin role. Can update interval, enabled status, and description.
    """
    scheduler = await get_scheduler()
    job = await scheduler.update_job(job_name, data.model_dump(exclude_unset=True))
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_name}' not found")
    return job_to_response(job)


@router.post("/jobs/{job_name}/run", response_model=SchedulerRunResponse)
async def trigger_job_run(
    job_name: str,
    admin: AdminUser,
):
    """Manually trigger a job to run immediately.

    Requires admin role.
    """
    scheduler = await get_scheduler()
    success, message, execution_id = await scheduler.trigger_job(job_name)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return SchedulerRunResponse(
        job_name=job_name,
        triggered=True,
        message=message,
        execution_id=execution_id,
    )


@router.get("/jobs/{job_name}/history", response_model=SchedulerJobHistoryListResponse)
async def get_job_history(
    job_name: str,
    admin: AdminUser,
    limit: int = 50,
):
    """Get execution history for a job.

    Requires admin role.
    """
    scheduler = await get_scheduler()
    history = await scheduler.get_job_history(job_name, limit=limit)
    return SchedulerJobHistoryListResponse(
        items=[history_to_response(h) for h in history],
        total=len(history),
    )


# ============================================================================
# Scheduler Control Endpoints
# ============================================================================


@router.post("/start", response_model=dict)
async def start_scheduler(
    admin: AdminUser,
):
    """Start the scheduler if not already running.

    Requires admin role.
    """
    scheduler = await get_scheduler()
    if scheduler.is_running:
        return {"status": "already_running", "message": "Scheduler is already running"}

    await scheduler.start()
    return {"status": "started", "message": "Scheduler started successfully"}


@router.post("/stop", response_model=dict)
async def stop_scheduler(
    admin: AdminUser,
):
    """Stop the scheduler.

    Requires admin role.
    """
    scheduler = await get_scheduler()
    if not scheduler.is_running:
        return {"status": "already_stopped", "message": "Scheduler is not running"}

    await scheduler.stop()
    return {"status": "stopped", "message": "Scheduler stopped successfully"}
