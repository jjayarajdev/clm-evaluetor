"""Scheduler models for job tracking and execution history."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class SchedulerJobStatus(str, enum.Enum):
    """Status of a scheduler job run."""

    SUCCESS = "success"
    FAILED = "failed"
    RUNNING = "running"
    SKIPPED = "skipped"


class SchedulerJob(Base, UUIDMixin, TimestampMixin):
    """Configuration and status for scheduled jobs.

    Tracks scheduled background jobs like SLA comparison runs.
    """

    __tablename__ = "scheduler_jobs"

    # Job identification
    job_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )  # e.g., "sla_comparison", "milestone_check"

    job_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # e.g., "comparison", "sync", "cleanup"

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Schedule configuration
    interval_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=900,  # 15 minutes
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    # Execution tracking
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    last_run_status: Mapped[SchedulerJobStatus | None] = mapped_column(
        Enum(SchedulerJobStatus, name='schedulerjobstatus', create_type=False,
             values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )

    last_run_duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    last_run_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Statistics
    total_runs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    successful_runs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    failed_runs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Relationships
    history: Mapped[list["SchedulerJobHistory"]] = relationship(
        "SchedulerJobHistory",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="desc(SchedulerJobHistory.started_at)",
    )

    def __repr__(self) -> str:
        status = "enabled" if self.is_enabled else "disabled"
        return f"<SchedulerJob {self.job_name} ({status})>"


class SchedulerJobHistory(Base, UUIDMixin):
    """Detailed history of scheduler job executions."""

    __tablename__ = "scheduler_job_history"

    # Relationship to job
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scheduler_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job: Mapped["SchedulerJob"] = relationship(
        "SchedulerJob",
        back_populates="history",
    )

    # Execution timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Status
    status: Mapped[SchedulerJobStatus] = mapped_column(
        Enum(SchedulerJobStatus, name='schedulerjobstatus', create_type=False,
             values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Results
    items_processed: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    run_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Created timestamp (no updated_at needed for history)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_job_history_job_started", "job_id", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<SchedulerJobHistory {self.status.value} @ {self.started_at}>"
