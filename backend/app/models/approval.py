"""Approval models for human-in-the-loop workflows."""

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


class ApprovalStatus(str, enum.Enum):
    """Status of an approval request."""

    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"
    escalated = "escalated"
    delegated = "delegated"


class Approver(Base, TimestampMixin):
    """Defines who can approve actions for a workflow.

    Approvers can be assigned to specific workflows. Primary approvers
    are notified first, with the ability to delegate or escalate.
    """

    __tablename__ = "approvers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # Approver settings
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    can_delegate: Mapped[bool] = mapped_column(Boolean, default=True)
    approval_order: Mapped[int] = mapped_column(Integer, default=1)
    # If approval_order > 1, this approver is notified after previous approvers

    # Notification preferences
    notify_email: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_slack: Mapped[bool] = mapped_column(Boolean, default=False)

    # Availability
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    out_of_office: Mapped[bool] = mapped_column(Boolean, default=False)
    delegate_to: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    workflow: Mapped["WorkflowDefinition"] = relationship(
        "WorkflowDefinition", back_populates="approvers"
    )
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    delegate_user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[delegate_to]
    )

    def __repr__(self) -> str:
        return f"<Approver {self.user_id} for workflow {self.workflow_id}>"


class ApprovalRequest(Base, TimestampMixin):
    """A request for human approval of an action.

    Created when a workflow step requires approval. The approver
    can approve, reject, or delegate the request.
    """

    __tablename__ = "approval_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    action_execution_id: Mapped[UUID] = mapped_column(
        ForeignKey("action_executions.id", ondelete="CASCADE"), nullable=False
    )

    # Request details
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    context_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Additional context for decision
    # Example: {"service_credit_amount": 4500, "sla_breach_details": {...}}

    # Assigned approver
    approver_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    original_approver_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )  # If delegated

    # Status tracking
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus), default=ApprovalStatus.pending
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Decision details
    decision_notes: Mapped[Optional[str]] = mapped_column(Text)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Notification tracking
    notification_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    notification_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    reminder_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reminder_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    # Relationships
    action_execution: Mapped["ActionExecution"] = relationship(
        "ActionExecution", back_populates="approval_request"
    )
    approver: Mapped["User"] = relationship("User", foreign_keys=[approver_id])
    original_approver: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[original_approver_id]
    )

    def __repr__(self) -> str:
        return f"<ApprovalRequest {self.id} [{self.status.value}]>"

    @property
    def is_expired(self) -> bool:
        """Check if this request has expired."""
        if self.expires_at and self.status == ApprovalStatus.pending:
            return datetime.utcnow() > self.expires_at
        return False

    @property
    def is_actionable(self) -> bool:
        """Check if this request can still be acted upon."""
        return self.status == ApprovalStatus.pending and not self.is_expired

    @property
    def time_to_decision_seconds(self) -> Optional[float]:
        """Calculate time from request to decision."""
        if self.decided_at:
            return (self.decided_at - self.requested_at).total_seconds()
        return None
