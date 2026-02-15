"""Pydantic schemas for Scheduler management."""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal


# ============================================================================
# Scheduler Job Schemas
# ============================================================================


class SchedulerJobResponse(BaseModel):
    """Response model for a scheduler job."""

    id: str
    job_name: str
    job_type: str
    description: str | None
    interval_seconds: int
    is_enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_run_status: Literal["success", "failed", "running", "skipped"] | None
    last_run_duration_ms: int | None
    last_run_error: str | None
    total_runs: int
    successful_runs: int
    failed_runs: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SchedulerJobUpdate(BaseModel):
    """Request to update a scheduler job."""

    interval_seconds: int | None = Field(None, ge=60, description="Interval in seconds (min 60)")
    is_enabled: bool | None = Field(None, description="Enable or disable the job")
    description: str | None = Field(None, max_length=2000)


class SchedulerJobListResponse(BaseModel):
    """Response model for list of scheduler jobs."""

    items: list[SchedulerJobResponse]
    total: int


# ============================================================================
# Scheduler Job History Schemas
# ============================================================================


class SchedulerJobHistoryResponse(BaseModel):
    """Response model for a job execution history entry."""

    id: str
    job_id: str
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    status: Literal["success", "failed", "running", "skipped"]
    error_message: str | None
    items_processed: int | None
    run_metadata: dict | None

    class Config:
        from_attributes = True


class SchedulerJobHistoryListResponse(BaseModel):
    """Response model for list of job history entries."""

    items: list[SchedulerJobHistoryResponse]
    total: int


# ============================================================================
# Scheduler Status Schemas
# ============================================================================


class SchedulerStatusResponse(BaseModel):
    """Response model for overall scheduler status."""

    is_running: bool
    started_at: datetime | None
    total_jobs: int
    enabled_jobs: int
    disabled_jobs: int
    jobs_running: int
    next_job_run: datetime | None
    next_job_name: str | None


class SchedulerRunResponse(BaseModel):
    """Response model for a manual job trigger."""

    job_name: str
    triggered: bool
    message: str
    execution_id: str | None = None
