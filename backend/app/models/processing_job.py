"""Contract processing job queue model for persistent, reliable processing."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class ProcessingJobStatus(str, enum.Enum):
    """Status of a contract processing job."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    STUCK = "stuck"


class ContractProcessingJob(Base, UUIDMixin, TimestampMixin):
    """Persistent job queue entry for contract processing.

    Replaces fire-and-forget BackgroundTasks with a DB-backed queue
    that survives restarts and supports retry/progress tracking.
    """

    __tablename__ = "contract_processing_jobs"

    # References
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )

    # Batch grouping
    batch_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    # File info (denormalized for worker access without joining)
    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    # Job status
    status: Mapped[str] = mapped_column(
        PG_ENUM(
            *[s.value for s in ProcessingJobStatus],
            name="processingjobstatus",
            create_type=False,
        ),
        nullable=False,
        default=ProcessingJobStatus.QUEUED.value,
    )

    # Progress tracking
    stage: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    progress_percent: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Error handling
    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )

    # Priority (higher = processed first)
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Arbitrary details (counterparty found, clause count, etc.)
    details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    __table_args__ = (
        # Queue polling index: find next queued job efficiently
        Index(
            "ix_processing_jobs_queue",
            "status", "priority", "created_at",
        ),
        # Batch status lookups
        Index(
            "ix_processing_jobs_batch_status",
            "batch_id", "status",
        ),
    )

    def __repr__(self) -> str:
        return f"<ProcessingJob {self.contract_id} [{self.status}] {self.progress_percent}%>"
