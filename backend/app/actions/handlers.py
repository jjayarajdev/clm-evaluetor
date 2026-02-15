"""Action Handlers - Execute workflow actions.

Each handler implements a specific action type that can be used in workflows.
Handlers receive an ActionExecution and return a result dictionary.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.event import Event
from app.models.notification import NotificationLog, NotificationStatus
from app.models.workflow import ActionExecution

logger = logging.getLogger(__name__)


async def handle_send_email(execution: ActionExecution) -> dict:
    """Send an email notification.

    Config:
        template: Template name to use.
        recipient_type: Type of recipient (vendor_contact, contract_owner, etc.)
        recipient_email: Optional override email address.

    Returns:
        Result with notification_id and status.
    """
    config = execution.action_config or {}
    logger.info(f"Sending email with template: {config.get('template')}")

    # Get event details for context
    from app.database import async_session_maker
    async with async_session_maker() as db:
        event = await db.execute(
            select(Event).where(Event.id == execution.event_id)
        )
        event = event.scalar_one_or_none()

        if not event:
            raise ValueError(f"Event {execution.event_id} not found")

        # Get contract for context
        contract = await db.execute(
            select(Contract).where(Contract.id == event.contract_id)
        )
        contract = contract.scalar_one_or_none()

        # Determine recipient
        recipient_email = config.get("recipient_email")
        recipient_type = config.get("recipient_type", "contract_owner")

        if not recipient_email and contract:
            # Get from contract metadata or use placeholder
            recipient_email = _get_recipient_email(contract, recipient_type)

        if not recipient_email:
            recipient_email = "admin@example.com"  # Fallback

        # Build email content using template
        template_name = config.get("template", "generic")
        subject, body = await _render_email_template(
            template_name,
            event=event,
            contract=contract,
        )

        # Create notification log
        notification = NotificationLog(
            event_id=event.id,
            action_execution_id=execution.id,
            channel="email",
            recipient_email=recipient_email,
            recipient_type=recipient_type,
            subject=subject,
            body=body,
            status=NotificationStatus.pending,
        )
        db.add(notification)

        # In a real implementation, this would call the email service
        # For now, simulate success
        notification.status = NotificationStatus.sent
        notification.sent_at = datetime.utcnow()

        await db.commit()

        logger.info(f"Email sent to {recipient_email}: {subject}")

        return {
            "notification_id": str(notification.id),
            "recipient": recipient_email,
            "subject": subject,
            "status": "sent",
        }


async def handle_create_snow_incident(execution: ActionExecution) -> dict:
    """Create a ServiceNow incident.

    Config:
        urgency: Incident urgency (1=high, 2=medium, 3=low).
        impact: Incident impact (1=high, 2=medium, 3=low).
        category: Incident category.
        short_description_template: Template for short description.

    Returns:
        Result with incident number and sys_id.
    """
    config = execution.action_config or {}
    logger.info(f"Creating ServiceNow incident")

    # Get event context
    from app.database import async_session_maker
    async with async_session_maker() as db:
        event = await db.execute(
            select(Event).where(Event.id == execution.event_id)
        )
        event = event.scalar_one_or_none()

        if not event:
            raise ValueError(f"Event {execution.event_id} not found")

        # Build incident data
        short_description = _render_template(
            config.get("short_description_template", "Contract Event: {{ event_type }}"),
            event=event,
        )

        incident_data = {
            "urgency": config.get("urgency", "2"),
            "impact": config.get("impact", "2"),
            "category": config.get("category", "Contract Management"),
            "short_description": short_description,
            "description": event.description or "",
            "caller_id": "contract_intelligence_system",
        }

        # In a real implementation, call ServiceNow API
        # For now, simulate success with mock incident number
        import random
        incident_number = f"INC{random.randint(1000000, 9999999)}"
        sys_id = f"mock-{execution.id}"

        # Store external ID
        execution.external_id = incident_number

        logger.info(f"Created ServiceNow incident: {incident_number}")

        return {
            "incident_number": incident_number,
            "sys_id": sys_id,
            "short_description": short_description,
            "status": "created",
        }


async def handle_update_sfdc_account(execution: ActionExecution) -> dict:
    """Update a Salesforce account record.

    Config:
        fields: Dictionary of field names to values.
        account_id: Optional specific account ID.

    Returns:
        Result with account ID and updated fields.
    """
    config = execution.action_config or {}
    logger.info(f"Updating Salesforce account")

    fields = config.get("fields", {})

    # Get event context
    from app.database import async_session_maker
    async with async_session_maker() as db:
        event = await db.execute(
            select(Event).where(Event.id == execution.event_id)
        )
        event = event.scalar_one_or_none()

        # Render field values with template data
        rendered_fields = {}
        for field_name, value in fields.items():
            if isinstance(value, str) and "{{" in value:
                rendered_fields[field_name] = _render_template(value, event=event)
            else:
                rendered_fields[field_name] = value

        # In a real implementation, call Salesforce API
        # For now, simulate success
        account_id = config.get("account_id", "mock-account-001")

        logger.info(f"Updated Salesforce account {account_id}: {rendered_fields}")

        return {
            "account_id": account_id,
            "updated_fields": rendered_fields,
            "status": "updated",
        }


async def handle_create_sfdc_task(execution: ActionExecution) -> dict:
    """Create a Salesforce task.

    Config:
        subject_template: Template for task subject.
        due_date_offset_days: Days from today for due date.
        priority: Task priority.
        owner_id: Optional task owner ID.

    Returns:
        Result with task ID.
    """
    config = execution.action_config or {}
    logger.info(f"Creating Salesforce task")

    # Get event context
    from app.database import async_session_maker
    async with async_session_maker() as db:
        event = await db.execute(
            select(Event).where(Event.id == execution.event_id)
        )
        event = event.scalar_one_or_none()

        subject = _render_template(
            config.get("subject_template", "Follow up: {{ event_type }}"),
            event=event,
        )

        due_offset = config.get("due_date_offset_days", 7)
        from datetime import timedelta
        due_date = datetime.utcnow() + timedelta(days=due_offset)

        task_data = {
            "subject": subject,
            "priority": config.get("priority", "Normal"),
            "due_date": due_date.date().isoformat(),
            "status": "Not Started",
        }

        # In a real implementation, call Salesforce API
        # For now, simulate success
        import random
        task_id = f"00T{random.randint(1000000, 9999999)}"

        logger.info(f"Created Salesforce task: {task_id}")

        return {
            "task_id": task_id,
            "subject": subject,
            "due_date": due_date.date().isoformat(),
            "status": "created",
        }


async def handle_calculate_service_credit(execution: ActionExecution) -> dict:
    """Calculate service credit for an SLA breach.

    Config:
        formula: Credit calculation formula.
        credit_rate: Rate to apply.
        max_credit: Maximum credit cap.

    Returns:
        Result with calculated credit amount.
    """
    config = execution.action_config or {}
    logger.info(f"Calculating service credit")

    # Get event context
    from app.database import async_session_maker
    async with async_session_maker() as db:
        event = await db.execute(
            select(Event).where(Event.id == execution.event_id)
        )
        event = event.scalar_one_or_none()

        if not event or not event.details:
            raise ValueError("Event details required for credit calculation")

        details = event.details

        # Extract values for calculation
        deviation_percent = abs(details.get("deviation_percent", 0))
        contract_value = details.get("contract_value", 0)
        credit_rate = config.get("credit_rate", 0.01)
        max_credit = config.get("max_credit")

        # Simple credit formula: deviation% * contract_value * credit_rate
        credit_amount = (deviation_percent / 100) * contract_value * credit_rate

        if max_credit and credit_amount > max_credit:
            credit_amount = max_credit

        credit_amount = round(credit_amount, 2)

        logger.info(f"Calculated service credit: ${credit_amount}")

        # Store in event details for downstream steps
        event.details["calculated_credit_amount"] = credit_amount
        await db.commit()

        return {
            "credit_amount": credit_amount,
            "deviation_percent": deviation_percent,
            "credit_rate": credit_rate,
            "formula": config.get("formula", "default"),
            "status": "calculated",
        }


async def handle_calculate_penalty(execution: ActionExecution) -> dict:
    """Calculate penalty for contract violation.

    Config:
        penalty_type: Type of penalty (fixed, percentage, tiered).
        base_amount: Base penalty amount or rate.

    Returns:
        Result with penalty amount.
    """
    config = execution.action_config or {}
    logger.info(f"Calculating penalty")

    penalty_type = config.get("penalty_type", "percentage")
    base_amount = config.get("base_amount", 0)

    # Get event context
    from app.database import async_session_maker
    async with async_session_maker() as db:
        event = await db.execute(
            select(Event).where(Event.id == execution.event_id)
        )
        event = event.scalar_one_or_none()

        details = event.details if event else {}

        if penalty_type == "fixed":
            penalty = base_amount
        elif penalty_type == "percentage":
            contract_value = details.get("contract_value", 0)
            penalty = contract_value * (base_amount / 100)
        else:
            penalty = base_amount

        penalty = round(penalty, 2)

        logger.info(f"Calculated penalty: ${penalty}")

        return {
            "penalty_amount": penalty,
            "penalty_type": penalty_type,
            "status": "calculated",
        }


async def handle_update_contract_status(execution: ActionExecution) -> dict:
    """Update contract status in the system.

    Config:
        new_status: Target contract status.
        notes: Optional status change notes.

    Returns:
        Result with old and new status.
    """
    config = execution.action_config or {}
    logger.info(f"Updating contract status")

    new_status = config.get("new_status")
    if not new_status:
        raise ValueError("new_status is required")

    from app.database import async_session_maker
    from app.models.contract import ContractStatus

    async with async_session_maker() as db:
        event = await db.execute(
            select(Event).where(Event.id == execution.event_id)
        )
        event = event.scalar_one_or_none()

        if not event:
            raise ValueError("Event not found")

        contract = await db.execute(
            select(Contract).where(Contract.id == event.contract_id)
        )
        contract = contract.scalar_one_or_none()

        if not contract:
            raise ValueError("Contract not found")

        old_status = contract.status.value if contract.status else None
        contract.status = ContractStatus(new_status)

        await db.commit()

        logger.info(f"Updated contract status: {old_status} -> {new_status}")

        return {
            "contract_id": str(contract.id),
            "old_status": old_status,
            "new_status": new_status,
            "status": "updated",
        }


async def handle_create_approval_request(execution: ActionExecution) -> dict:
    """Create an approval request.

    This is handled by the orchestrator, this handler is for custom approvals.

    Returns:
        Result indicating approval request created.
    """
    logger.info(f"Creating custom approval request")

    # The orchestrator handles approval creation for workflow steps
    # This handler is for custom approval scenarios

    return {
        "status": "approval_created",
        "message": "Approval request created by orchestrator",
    }


async def handle_escalate(execution: ActionExecution) -> dict:
    """Escalate an event to higher priority handling.

    Config:
        escalation_level: Level to escalate to.
        notification_template: Template for escalation notification.

    Returns:
        Result with escalation details.
    """
    config = execution.action_config or {}
    logger.info(f"Escalating event")

    escalation_level = config.get("escalation_level", 1)

    # Get event and increase severity
    from app.database import async_session_maker
    from app.models.event import EventSeverity

    async with async_session_maker() as db:
        event = await db.execute(
            select(Event).where(Event.id == execution.event_id)
        )
        event = event.scalar_one_or_none()

        if event:
            # Increase severity
            if event.severity == EventSeverity.info:
                event.severity = EventSeverity.warning
            elif event.severity == EventSeverity.warning:
                event.severity = EventSeverity.critical

            await db.commit()

        logger.info(f"Escalated to level {escalation_level}")

        return {
            "escalation_level": escalation_level,
            "new_severity": event.severity.value if event else None,
            "status": "escalated",
        }


async def handle_webhook(execution: ActionExecution) -> dict:
    """Call an external webhook.

    Config:
        url: Webhook URL.
        method: HTTP method (default: POST).
        headers: Optional headers.
        payload_template: Template for payload.

    Returns:
        Result with response status.
    """
    config = execution.action_config or {}
    logger.info(f"Calling webhook: {config.get('url')}")

    url = config.get("url")
    if not url:
        raise ValueError("Webhook URL is required")

    method = config.get("method", "POST")

    # In a real implementation, make HTTP request
    # For now, simulate success

    logger.info(f"Webhook called: {method} {url}")

    return {
        "url": url,
        "method": method,
        "response_code": 200,
        "status": "success",
    }


# Helper functions

def _get_recipient_email(contract: Contract, recipient_type: str) -> Optional[str]:
    """Get recipient email based on type."""
    # In a real implementation, look up from contract parties
    # For now, return placeholder
    email_map = {
        "contract_owner": "owner@example.com",
        "vendor_contact": "vendor@example.com",
        "escalation_contact": "escalation@example.com",
    }
    return email_map.get(recipient_type)


async def _render_email_template(
    template_name: str,
    event: Optional[Event] = None,
    contract: Optional[Contract] = None,
) -> tuple[str, str]:
    """Render email subject and body from template.

    Returns:
        Tuple of (subject, body).
    """
    # Get template from database
    from app.database import async_session_maker
    from app.models.notification import NotificationTemplate

    async with async_session_maker() as db:
        result = await db.execute(
            select(NotificationTemplate).where(NotificationTemplate.name == template_name)
        )
        template = result.scalar_one_or_none()

        if not template:
            # Use defaults
            subject = f"Contract Event: {event.event_type.value if event else 'Unknown'}"
            body = event.description if event else "No details available."
            return subject, body

        # Build context
        context = {}
        if event:
            context["event_type"] = event.event_type.value
            context["event_title"] = event.title
            context["event_description"] = event.description
            if event.details:
                context.update(event.details)
        if contract:
            context["contract_name"] = contract.filename
            context["counterparty"] = contract.counterparty

        # Render templates
        subject = _render_template(template.subject_template, **context)
        body = _render_template(template.body_template, **context)

        return subject, body


def _render_template(template: str, **context) -> str:
    """Simple template rendering.

    Replaces {{ variable }} patterns with context values.
    """
    result = template
    for key, value in context.items():
        placeholder = "{{ " + key + " }}"
        if placeholder in result:
            result = result.replace(placeholder, str(value) if value else "")

        # Also try without spaces
        placeholder = "{{" + key + "}}"
        if placeholder in result:
            result = result.replace(placeholder, str(value) if value else "")

    return result
