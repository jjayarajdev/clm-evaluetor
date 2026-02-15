"""Notification Service - Sends notifications through various channels.

Handles:
- Template rendering with Jinja2
- Email sending via configured provider
- Notification logging and tracking
- Retry logic for failed notifications
"""

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from jinja2 import Environment, BaseLoader, TemplateError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.event import Event
from app.models.notification import (
    NotificationChannel,
    NotificationLog,
    NotificationStatus,
    NotificationTemplate,
    RecipientType,
)
from app.models.user import User

logger = logging.getLogger(__name__)


class TemplateRenderer:
    """Renders notification templates using Jinja2."""

    def __init__(self):
        """Initialize Jinja2 environment."""
        self.env = Environment(
            loader=BaseLoader(),
            autoescape=True,
        )
        # Add custom filters
        self.env.filters["truncate"] = self._truncate
        self.env.filters["currency"] = self._format_currency
        self.env.filters["date"] = self._format_date

    def render(self, template_str: str, context: dict) -> str:
        """Render a template string with context.

        Args:
            template_str: Jinja2 template string.
            context: Variables to substitute.

        Returns:
            Rendered string.
        """
        try:
            template = self.env.from_string(template_str)
            return template.render(**context)
        except TemplateError as e:
            logger.error(f"Template render error: {e}")
            # Return original with basic substitution as fallback
            result = template_str
            for key, value in context.items():
                result = result.replace("{{ " + key + " }}", str(value) if value else "")
                result = result.replace("{{" + key + "}}", str(value) if value else "")
            return result

    @staticmethod
    def _truncate(value: str, length: int = 50) -> str:
        """Truncate string to length."""
        if len(value) <= length:
            return value
        return value[:length - 3] + "..."

    @staticmethod
    def _format_currency(value: float) -> str:
        """Format number as currency."""
        return f"${value:,.2f}"

    @staticmethod
    def _format_date(value: datetime, fmt: str = "%Y-%m-%d") -> str:
        """Format datetime."""
        if isinstance(value, datetime):
            return value.strftime(fmt)
        return str(value)


class NotificationService:
    """High-level service for sending notifications."""

    def __init__(self, db: AsyncSession):
        """Initialize notification service.

        Args:
            db: Database session.
        """
        self.db = db
        self.renderer = TemplateRenderer()

    async def send_notification(
        self,
        template_name: str,
        recipient_email: str,
        context: dict,
        recipient_name: str = "",
        recipient_type: Optional[RecipientType] = None,
        event_id: Optional[UUID] = None,
        action_execution_id: Optional[UUID] = None,
        channel: NotificationChannel = NotificationChannel.email,
    ) -> NotificationLog:
        """Send a notification using a template.

        Args:
            template_name: Name of the template to use.
            recipient_email: Recipient email address.
            context: Template context variables.
            recipient_name: Recipient display name.
            recipient_type: Type of recipient.
            event_id: Related event ID.
            action_execution_id: Related action execution ID.
            channel: Notification channel.

        Returns:
            NotificationLog record.
        """
        # Get template
        template = await self._get_template(template_name)

        if template:
            subject = self.renderer.render(template.subject_template, context)
            body = self.renderer.render(template.body_template, context)
            is_html = template.is_html
            recipient_type = recipient_type or template.default_recipient_type
        else:
            # Fallback to basic notification
            subject = context.get("subject", "Notification")
            body = context.get("body", "You have a new notification.")
            is_html = False

        # Create log entry
        notification = NotificationLog(
            template_id=template.id if template else None,
            event_id=event_id,
            action_execution_id=action_execution_id,
            channel=channel,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            recipient_type=recipient_type,
            subject=subject,
            body=body,
            variables_used=context,
            status=NotificationStatus.pending,
        )
        self.db.add(notification)
        await self.db.flush()

        # Send the notification
        try:
            await self._send(notification, is_html)
            notification.status = NotificationStatus.sent
            notification.sent_at = datetime.utcnow()
            logger.info(f"Notification sent to {recipient_email}: {subject}")
        except Exception as e:
            notification.status = NotificationStatus.failed
            notification.error_message = str(e)[:500]
            notification.attempts += 1
            notification.last_attempt_at = datetime.utcnow()
            logger.error(f"Failed to send notification: {e}")

        await self.db.commit()
        return notification

    async def send_event_notification(
        self,
        event: Event,
        template_name: str,
        recipient_email: str,
        recipient_name: str = "",
        additional_context: Optional[dict] = None,
    ) -> NotificationLog:
        """Send notification for an event.

        Builds context from event and related entities.

        Args:
            event: The event to notify about.
            template_name: Template name.
            recipient_email: Recipient email.
            recipient_name: Recipient name.
            additional_context: Extra context variables.

        Returns:
            NotificationLog record.
        """
        # Build context from event
        context = await self._build_event_context(event)

        if additional_context:
            context.update(additional_context)

        return await self.send_notification(
            template_name=template_name,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            context=context,
            event_id=event.id,
        )

    async def send_approval_request_notification(
        self,
        approval_request,
        approver: User,
        approve_url: str = "",
        reject_url: str = "",
    ) -> NotificationLog:
        """Send notification for approval request.

        Args:
            approval_request: The ApprovalRequest object.
            approver: The user who needs to approve.
            approve_url: URL to approve.
            reject_url: URL to reject.

        Returns:
            NotificationLog record.
        """
        # Calculate hours remaining
        hours_remaining = 24
        if approval_request.expires_at:
            delta = approval_request.expires_at - datetime.utcnow()
            hours_remaining = max(0, int(delta.total_seconds() / 3600))

        context = {
            "approval_title": approval_request.title,
            "approval_description": approval_request.description or "",
            "approver_name": approver.full_name or approver.email,
            "expires_at": approval_request.expires_at.strftime("%Y-%m-%d %H:%M") if approval_request.expires_at else "N/A",
            "hours_remaining": hours_remaining,
            "approve_url": approve_url,
            "reject_url": reject_url,
            "details_url": f"/approvals/{approval_request.id}",
            "has_financial_impact": False,
            "financial_amount": 0,
        }

        # Add context data from approval request
        if approval_request.context_data:
            context.update(approval_request.context_data)
            if "calculated_credit_amount" in approval_request.context_data:
                context["has_financial_impact"] = True
                context["financial_amount"] = approval_request.context_data["calculated_credit_amount"]

        return await self.send_notification(
            template_name="approval_request",
            recipient_email=approver.email,
            recipient_name=approver.full_name or "",
            context=context,
            recipient_type=RecipientType.approver,
            action_execution_id=approval_request.action_execution_id,
        )

    async def send_failure_notification(
        self,
        event: Event,
        action_execution,
        admin_email: str,
    ) -> NotificationLog:
        """Send notification when action fails after retries.

        Args:
            event: The related event.
            action_execution: The failed action execution.
            admin_email: Admin email to notify.

        Returns:
            NotificationLog record.
        """
        context = {
            "admin_name": "Administrator",
            "action_type": action_execution.action_type.value,
            "event_title": event.title,
            "contract_name": "",
            "workflow_name": "",
            "error_message": action_execution.error_message or "Unknown error",
            "last_attempt_at": action_execution.completed_at.strftime("%Y-%m-%d %H:%M") if action_execution.completed_at else "N/A",
            "attempts": action_execution.attempts,
            "max_attempts": action_execution.max_attempts,
            "event_id": str(event.id),
            "action_execution_id": str(action_execution.id),
        }

        # Get workflow name if available
        if action_execution.workflow_step:
            step = action_execution.workflow_step
            if step.workflow:
                context["workflow_name"] = step.workflow.name

        return await self.send_notification(
            template_name="action_failed",
            recipient_email=admin_email,
            context=context,
            recipient_type=RecipientType.escalation_contact,
            event_id=event.id,
            action_execution_id=action_execution.id,
        )

    async def retry_failed_notifications(self, max_retries: int = 3) -> int:
        """Retry failed notifications.

        Args:
            max_retries: Maximum retry attempts.

        Returns:
            Number of notifications retried.
        """
        query = select(NotificationLog).where(
            NotificationLog.status == NotificationStatus.failed,
            NotificationLog.attempts < max_retries,
        )

        result = await self.db.execute(query)
        failed = result.scalars().all()

        retried = 0
        for notification in failed:
            try:
                await self._send(notification, is_html=False)
                notification.status = NotificationStatus.sent
                notification.sent_at = datetime.utcnow()
                retried += 1
            except Exception as e:
                notification.attempts += 1
                notification.last_attempt_at = datetime.utcnow()
                notification.error_message = str(e)[:500]

        await self.db.commit()
        return retried

    async def _get_template(self, name: str) -> Optional[NotificationTemplate]:
        """Get template by name."""
        result = await self.db.execute(
            select(NotificationTemplate)
            .where(NotificationTemplate.name == name)
        )
        return result.scalar_one_or_none()

    async def _build_event_context(self, event: Event) -> dict:
        """Build context dict from event."""
        context = {
            "event_type": event.event_type.value,
            "event_title": event.title,
            "event_description": event.description or "",
            "severity": event.severity.value,
            "detected_at": event.detected_at,
            "today": datetime.utcnow().strftime("%Y-%m-%d"),
        }

        # Add event details
        if event.details:
            context.update(event.details)

        # Get contract info
        if event.contract_id:
            result = await self.db.execute(
                select(Contract).where(Contract.id == event.contract_id)
            )
            contract = result.scalar_one_or_none()
            if contract:
                context["contract_name"] = contract.filename
                context["counterparty"] = contract.counterparty or ""
                context["contract_url"] = f"/contracts/{contract.id}"
                if contract.total_value:
                    context["contract_value"] = float(contract.total_value)

        return context

    async def _send(self, notification: NotificationLog, is_html: bool = False) -> None:
        """Actually send the notification.

        Args:
            notification: The notification to send.
            is_html: Whether body is HTML.
        """
        if notification.channel == NotificationChannel.email:
            await self._send_email(notification, is_html)
        elif notification.channel == NotificationChannel.slack:
            await self._send_slack(notification)
        elif notification.channel == NotificationChannel.webhook:
            await self._send_webhook(notification)
        else:
            logger.warning(f"Unsupported channel: {notification.channel}")

    async def _send_email(self, notification: NotificationLog, is_html: bool) -> None:
        """Send email notification."""
        from app.integrations.email import EmailService

        email_service = EmailService(self.db)
        await email_service.send_email(
            to_email=notification.recipient_email,
            subject=notification.subject,
            body=notification.body,
            to_name=notification.recipient_name or "",
            is_html=is_html,
        )

    async def _send_slack(self, notification: NotificationLog) -> None:
        """Send Slack notification (placeholder)."""
        logger.info(f"[SLACK] Would send to channel: {notification.subject}")
        # TODO: Implement Slack integration

    async def _send_webhook(self, notification: NotificationLog) -> None:
        """Send webhook notification (placeholder)."""
        logger.info(f"[WEBHOOK] Would POST: {notification.subject}")
        # TODO: Implement webhook integration


async def get_notification_service(db: AsyncSession) -> NotificationService:
    """Factory function for notification service."""
    return NotificationService(db)
