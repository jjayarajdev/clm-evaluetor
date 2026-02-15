"""Project task tracking model for development progress."""

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class TaskStatus(str, enum.Enum):
    """Status of a project task."""

    not_started = "not_started"
    in_progress = "in_progress"
    blocked = "blocked"
    completed = "completed"
    cancelled = "cancelled"


class TaskPriority(str, enum.Enum):
    """Priority level of a task."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ProjectPhase(Base, TimestampMixin):
    """A phase in the project plan."""

    __tablename__ = "project_phases"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    phase_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    estimated_days: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.not_started
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    tasks: Mapped[list["ProjectTask"]] = relationship(
        "ProjectTask", back_populates="phase", cascade="all, delete-orphan"
    )

    @property
    def progress_percent(self) -> float:
        """Calculate completion percentage based on tasks."""
        if not self.tasks:
            return 0.0
        completed = sum(1 for t in self.tasks if t.status == TaskStatus.completed)
        return (completed / len(self.tasks)) * 100


class ProjectTask(Base, TimestampMixin):
    """A task in the project plan."""

    __tablename__ = "project_tasks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    phase_id: Mapped[UUID] = mapped_column(ForeignKey("project_phases.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g., "1.1", "2.3"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.not_started
    )
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority), default=TaskPriority.medium
    )

    # Dependencies (comma-separated task IDs)
    dependencies: Mapped[Optional[str]] = mapped_column(String(500))

    # Tracking
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # What was created/modified
    files_created: Mapped[Optional[str]] = mapped_column(Text)  # JSON list of files
    files_modified: Mapped[Optional[str]] = mapped_column(Text)  # JSON list of files

    # Relationships
    phase: Mapped[ProjectPhase] = relationship("ProjectPhase", back_populates="tasks")

    def __repr__(self) -> str:
        return f"<ProjectTask {self.task_id}: {self.name}>"


class ProjectNote(Base, TimestampMixin):
    """Notes and decisions made during the project."""

    __tablename__ = "project_notes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    task_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("project_tasks.id"))
    category: Mapped[str] = mapped_column(String(50))  # decision, blocker, learning, etc.
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationship
    task: Mapped[Optional[ProjectTask]] = relationship("ProjectTask")
