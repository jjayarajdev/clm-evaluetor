"""Workflow Orchestrator - Executes workflows for detected events.

This service takes pending events and executes their associated workflows,
managing step sequencing, approvals, retries, and action execution.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.approval import ApprovalRequest, ApprovalStatus
from app.models.event import Event, EventStatus
from app.models.user import User
from app.models.workflow import (
    ActionExecution,
    ActionType,
    ExecutionStatus,
    WorkflowDefinition,
    WorkflowStep,
)

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    """Orchestrates workflow execution for contract events.

    Manages the lifecycle of event processing:
    1. Picks up pending events
    2. Executes workflow steps in order
    3. Handles approval checkpoints
    4. Manages retries and failures
    5. Tracks execution state
    """

    def __init__(self, db: AsyncSession):
        """Initialize with database session."""
        self.db = db
        self._action_handlers: dict = {}

    def register_action_handler(self, action_type: ActionType, handler):
        """Register a handler for an action type.

        Args:
            action_type: The ActionType enum value.
            handler: Async function that executes the action.
        """
        self._action_handlers[action_type] = handler
        logger.info(f"Registered handler for action type: {action_type.value}")

    async def process_pending_events(self, limit: int = 10) -> int:
        """Process pending events that have workflows assigned.

        Args:
            limit: Maximum number of events to process in this batch.

        Returns:
            Number of events processed.
        """
        logger.info(f"Processing up to {limit} pending events")

        # Find pending events with workflows
        query = (
            select(Event)
            .where(
                and_(
                    Event.status == EventStatus.pending,
                    Event.workflow_id.isnot(None),
                )
            )
            .options(selectinload(Event.workflow))
            .limit(limit)
        )

        result = await self.db.execute(query)
        events = result.scalars().all()

        processed = 0
        for event in events:
            try:
                await self._start_event_processing(event)
                processed += 1
            except Exception as e:
                logger.error(f"Error processing event {event.id}: {e}")
                event.status = EventStatus.failed
                event.error_message = str(e)
                await self.db.commit()

        return processed

    async def continue_in_progress_events(self, limit: int = 10) -> int:
        """Continue processing events that are in progress.

        Picks up events that are processing/awaiting_approval/executing
        and advances them to the next step.

        Args:
            limit: Maximum events to process.

        Returns:
            Number of events advanced.
        """
        logger.info("Continuing in-progress events")

        query = (
            select(Event)
            .where(
                Event.status.in_([
                    EventStatus.processing,
                    EventStatus.executing,
                ])
            )
            .options(
                selectinload(Event.workflow).selectinload(WorkflowDefinition.steps),
                selectinload(Event.action_executions),
            )
            .limit(limit)
        )

        result = await self.db.execute(query)
        events = result.scalars().all()

        advanced = 0
        for event in events:
            try:
                if await self._advance_event(event):
                    advanced += 1
            except Exception as e:
                logger.error(f"Error advancing event {event.id}: {e}")

        return advanced

    async def check_pending_approvals(self) -> int:
        """Check and process pending approval requests.

        Handles expired approvals and processes approved/rejected requests.

        Returns:
            Number of approvals processed.
        """
        logger.info("Checking pending approvals")

        # Find pending approvals
        query = (
            select(ApprovalRequest)
            .where(ApprovalRequest.status == ApprovalStatus.pending)
            .options(selectinload(ApprovalRequest.action_execution))
        )

        result = await self.db.execute(query)
        approvals = result.scalars().all()

        processed = 0
        for approval in approvals:
            # Check if expired
            if approval.is_expired:
                await self._handle_expired_approval(approval)
                processed += 1
            # Approved/rejected requests are handled by the API endpoint

        await self.db.commit()
        return processed

    async def _start_event_processing(self, event: Event) -> None:
        """Start processing a new event.

        Creates action executions for all workflow steps.

        Args:
            event: The event to process.
        """
        logger.info(f"Starting workflow for event {event.id} ({event.event_type.value})")

        # Update event status
        event.status = EventStatus.processing
        event.started_at = datetime.utcnow()

        # Get workflow steps
        workflow = event.workflow
        if not workflow:
            raise ValueError(f"Event {event.id} has no workflow assigned")

        steps_query = (
            select(WorkflowStep)
            .where(WorkflowStep.workflow_id == workflow.id)
            .order_by(WorkflowStep.step_order)
        )
        result = await self.db.execute(steps_query)
        steps = result.scalars().all()

        if not steps:
            logger.warning(f"Workflow {workflow.id} has no steps")
            event.status = EventStatus.completed
            event.completed_at = datetime.utcnow()
            await self.db.commit()
            return

        # Create action executions for each step
        for step in steps:
            execution = ActionExecution(
                event_id=event.id,
                workflow_step_id=step.id,
                action_type=step.action_type,
                action_config=step.action_config,
                status=ExecutionStatus.pending,
                max_attempts=step.max_retries or 3,
            )
            self.db.add(execution)

        await self.db.commit()

        # Start first step
        await self._advance_event(event)

    async def _advance_event(self, event: Event) -> bool:
        """Advance event to the next workflow step.

        Args:
            event: The event to advance.

        Returns:
            True if advanced, False if workflow complete or blocked.
        """
        # Get all action executions for this event, ordered by step order
        query = (
            select(ActionExecution)
            .join(WorkflowStep, ActionExecution.workflow_step_id == WorkflowStep.id)
            .where(ActionExecution.event_id == event.id)
            .order_by(WorkflowStep.step_order)
            .options(selectinload(ActionExecution.workflow_step))
        )

        result = await self.db.execute(query)
        executions = result.scalars().all()

        # Find next pending execution
        for execution in executions:
            if execution.status == ExecutionStatus.pending:
                # Check if this step requires approval
                step = execution.workflow_step
                if step and step.requires_approval:
                    await self._create_approval_request(execution)
                    return True
                else:
                    # Execute the action
                    await self._execute_action(execution)
                    return True

            elif execution.status == ExecutionStatus.pending_approval:
                # Still waiting for approval
                event.status = EventStatus.awaiting_approval
                await self.db.commit()
                return False

            elif execution.status in (
                ExecutionStatus.executing,
                ExecutionStatus.approved,
            ):
                # Action is in progress
                event.status = EventStatus.executing
                await self.db.commit()
                return False

            elif execution.status == ExecutionStatus.failed:
                # Check if we should continue on failure
                step = execution.workflow_step
                if step and step.continue_on_failure:
                    continue
                else:
                    # Workflow failed
                    event.status = EventStatus.failed
                    event.error_message = f"Step '{step.name if step else 'unknown'}' failed: {execution.error_message}"
                    event.completed_at = datetime.utcnow()
                    await self.db.commit()
                    return False

            elif execution.status == ExecutionStatus.rejected:
                # Approval was rejected, workflow stops
                event.status = EventStatus.cancelled
                event.error_message = "Workflow cancelled: approval rejected"
                event.completed_at = datetime.utcnow()
                await self.db.commit()
                return False

        # All steps completed
        event.status = EventStatus.completed
        event.completed_at = datetime.utcnow()
        await self.db.commit()
        logger.info(f"Event {event.id} workflow completed successfully")
        return False

    async def _execute_action(self, execution: ActionExecution) -> None:
        """Execute a single action.

        Args:
            execution: The action execution record.
        """
        action_type = execution.action_type
        logger.info(f"Executing action {action_type.value} for execution {execution.id}")

        execution.status = ExecutionStatus.executing
        execution.started_at = datetime.utcnow()
        execution.attempts += 1
        await self.db.commit()

        handler = self._action_handlers.get(action_type)
        if not handler:
            logger.warning(f"No handler registered for action type: {action_type.value}")
            execution.status = ExecutionStatus.skipped
            execution.error_message = f"No handler for action type: {action_type.value}"
            execution.completed_at = datetime.utcnow()
            await self.db.commit()
            return

        try:
            # Execute the handler
            result = await handler(execution)

            # Success
            execution.status = ExecutionStatus.completed
            execution.result = result
            execution.completed_at = datetime.utcnow()
            logger.info(f"Action {action_type.value} completed successfully")

        except Exception as e:
            logger.error(f"Action {action_type.value} failed: {e}")
            execution.error_message = str(e)

            if execution.attempts >= execution.max_attempts:
                execution.status = ExecutionStatus.failed
                execution.completed_at = datetime.utcnow()
            else:
                # Schedule retry
                execution.status = ExecutionStatus.pending
                execution.scheduled_at = datetime.utcnow() + timedelta(seconds=60)

        await self.db.commit()

    async def _create_approval_request(self, execution: ActionExecution) -> None:
        """Create an approval request for an action.

        Args:
            execution: The action execution requiring approval.
        """
        step = execution.workflow_step
        if not step:
            raise ValueError("Execution has no associated workflow step")

        logger.info(f"Creating approval request for action {execution.id}")

        execution.status = ExecutionStatus.pending_approval
        await self.db.flush()

        # Get event for context
        event_query = select(Event).where(Event.id == execution.event_id)
        event_result = await self.db.execute(event_query)
        event = event_result.scalar_one()

        # Find an approver (get first active user with admin role for now)
        # In production, this would use the Approver model
        approver_query = (
            select(User)
            .where(User.is_active == True)
            .limit(1)
        )
        approver_result = await self.db.execute(approver_query)
        approver = approver_result.scalar_one_or_none()

        if not approver:
            logger.error("No approver found, skipping approval")
            execution.status = ExecutionStatus.approved
            await self.db.commit()
            return

        # Calculate expiration
        timeout_hours = step.approval_timeout_hours or 24
        expires_at = datetime.utcnow() + timedelta(hours=timeout_hours)

        # Build title and description from config
        config = step.action_config or {}
        title = config.get("title_template", f"Approval Required: {step.name}")
        description = config.get("description_template", step.description or "")

        # Create approval request
        approval = ApprovalRequest(
            action_execution_id=execution.id,
            title=title,
            description=description,
            context_data=event.details,
            approver_id=approver.id,
            expires_at=expires_at,
            status=ApprovalStatus.pending,
        )
        self.db.add(approval)

        await self.db.commit()
        logger.info(f"Created approval request {approval.id} for approver {approver.email}")

    async def _handle_expired_approval(self, approval: ApprovalRequest) -> None:
        """Handle an expired approval request.

        Args:
            approval: The expired approval request.
        """
        logger.info(f"Handling expired approval {approval.id}")

        approval.status = ApprovalStatus.expired

        # Get the associated execution
        execution = approval.action_execution
        if execution:
            step_query = (
                select(WorkflowStep)
                .where(WorkflowStep.id == execution.workflow_step_id)
            )
            step_result = await self.db.execute(step_query)
            step = step_result.scalar_one_or_none()

            if step and step.auto_approve_after_timeout:
                # Auto-approve
                logger.info(f"Auto-approving expired request {approval.id}")
                execution.status = ExecutionStatus.approved
            else:
                # Mark as failed
                execution.status = ExecutionStatus.failed
                execution.error_message = "Approval request expired"
                execution.completed_at = datetime.utcnow()

        await self.db.commit()

    async def approve_request(
        self,
        approval_id: UUID,
        approver_id: UUID,
        notes: Optional[str] = None
    ) -> bool:
        """Approve an approval request.

        Args:
            approval_id: The approval request ID.
            approver_id: The user approving.
            notes: Optional approval notes.

        Returns:
            True if approved successfully.
        """
        query = (
            select(ApprovalRequest)
            .where(ApprovalRequest.id == approval_id)
            .options(selectinload(ApprovalRequest.action_execution))
        )

        result = await self.db.execute(query)
        approval = result.scalar_one_or_none()

        if not approval:
            return False

        if not approval.is_actionable:
            logger.warning(f"Approval {approval_id} is not actionable")
            return False

        approval.status = ApprovalStatus.approved
        approval.decided_at = datetime.utcnow()
        approval.decision_notes = notes

        # Update execution status
        if approval.action_execution:
            approval.action_execution.status = ExecutionStatus.approved

        await self.db.commit()
        logger.info(f"Approval {approval_id} approved by {approver_id}")
        return True

    async def reject_request(
        self,
        approval_id: UUID,
        approver_id: UUID,
        reason: str
    ) -> bool:
        """Reject an approval request.

        Args:
            approval_id: The approval request ID.
            approver_id: The user rejecting.
            reason: Rejection reason.

        Returns:
            True if rejected successfully.
        """
        query = (
            select(ApprovalRequest)
            .where(ApprovalRequest.id == approval_id)
            .options(selectinload(ApprovalRequest.action_execution))
        )

        result = await self.db.execute(query)
        approval = result.scalar_one_or_none()

        if not approval:
            return False

        if not approval.is_actionable:
            return False

        approval.status = ApprovalStatus.rejected
        approval.decided_at = datetime.utcnow()
        approval.rejection_reason = reason

        # Update execution status
        if approval.action_execution:
            approval.action_execution.status = ExecutionStatus.rejected
            approval.action_execution.completed_at = datetime.utcnow()

        await self.db.commit()
        logger.info(f"Approval {approval_id} rejected by {approver_id}")
        return True
