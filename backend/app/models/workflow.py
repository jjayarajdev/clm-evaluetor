"""Workflow definition models for orchestrating actions."""

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin
from app.models.event import EventType


class ActionType(str, enum.Enum):
    """Types of actions that can be executed."""

    send_email = "send_email"
    send_slack = "send_slack"
    create_snow_incident = "create_snow_incident"
    update_snow_incident = "update_snow_incident"
    update_sfdc_account = "update_sfdc_account"
    create_sfdc_task = "create_sfdc_task"
    calculate_service_credit = "calculate_service_credit"
    calculate_penalty = "calculate_penalty"
    update_contract_status = "update_contract_status"
    update_obligation_status = "update_obligation_status"
    create_approval_request = "create_approval_request"
    escalate = "escalate"
    webhook = "webhook"
    custom = "custom"


class ExecutionStatus(str, enum.Enum):
    """Status of action execution."""

    pending = "pending"
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"
    executing = "executing"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"
    cancelled = "cancelled"


class WorkflowDefinition(Base, TimestampMixin):
    """Defines a workflow for handling specific event types.

    A workflow is a sequence of steps that execute when an event
    of the specified type is detected. Workflows can be enabled/disabled
    and have multiple versions.
    """

    __tablename__ = "workflow_definitions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Workflow identification
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)

    # Versioning
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    # Execution settings
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, default=60)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=3600)  # 1 hour

    # Conditions for triggering (optional filters)
    trigger_conditions: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Example: {"severity": ["critical", "warning"], "contract_type": ["msa"]}

    # Relationships
    steps: Mapped[list["WorkflowStep"]] = relationship(
        "WorkflowStep",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowStep.step_order"
    )
    approvers: Mapped[list["Approver"]] = relationship(
        "Approver", back_populates="workflow", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<WorkflowDefinition {self.name} v{self.version}>"


class WorkflowStep(Base, TimestampMixin):
    """A single step in a workflow.

    Steps are executed in order (by step_order). Each step can have
    multiple actions that execute in parallel within that step.
    Steps can require approval before execution.
    """

    __tablename__ = "workflow_steps"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False
    )

    # Step identification
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)

    # Action configuration
    action_type: Mapped[ActionType] = mapped_column(Enum(ActionType), nullable=False)
    action_config: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Example for email: {"template": "sla_breach", "recipients": ["vendor"]}
    # Example for SNOW: {"urgency": "high", "impact": "medium"}

    # Approval settings
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_timeout_hours: Mapped[int] = mapped_column(Integer, default=24)
    auto_approve_after_timeout: Mapped[bool] = mapped_column(Boolean, default=False)

    # Execution settings
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)
    continue_on_failure: Mapped[bool] = mapped_column(Boolean, default=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    # Conditional execution
    condition: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Example: {"previous_step": "approved", "severity": "critical"}

    # Relationships
    workflow: Mapped[WorkflowDefinition] = relationship(
        "WorkflowDefinition", back_populates="steps"
    )

    def __repr__(self) -> str:
        return f"<WorkflowStep {self.step_order}: {self.name}>"


class ActionExecution(Base, TimestampMixin):
    """Tracks the execution of an action for an event.

    Each time an action is executed (or attempted), a record is created
    to track the status, result, and any errors.
    """

    __tablename__ = "action_executions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    workflow_step_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="SET NULL"), nullable=True
    )

    # Action details
    action_type: Mapped[ActionType] = mapped_column(Enum(ActionType), nullable=False)
    action_config: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Status tracking
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus), default=ExecutionStatus.pending
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)

    # Timing
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Results
    result: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Example: {"service_credit": 4500, "calculation_breakdown": {...}}
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    external_id: Mapped[Optional[str]] = mapped_column(String(200))
    # Example: ServiceNow incident ID "INC0012345"

    # Langfuse tracing
    trace_id: Mapped[Optional[str]] = mapped_column(String(100))

    # Relationships
    event: Mapped["Event"] = relationship("Event", back_populates="action_executions")
    approval_request: Mapped[Optional["ApprovalRequest"]] = relationship(
        "ApprovalRequest", back_populates="action_execution", uselist=False
    )

    def __repr__(self) -> str:
        return f"<ActionExecution {self.action_type.value} [{self.status.value}]>"

    @property
    def can_retry(self) -> bool:
        """Check if this action can be retried."""
        return (
            self.status == ExecutionStatus.failed
            and self.attempts < self.max_attempts
        )

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate execution duration."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
