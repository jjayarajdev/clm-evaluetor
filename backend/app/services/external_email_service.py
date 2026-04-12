"""Email service for external portal notifications.

Sends branded emails to external users for:
- Contract sharing invitations
- Dashboard access invitations
- Score submission confirmations
- SLA breach alerts
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import (
    NotificationChannel,
    NotificationLog,
    NotificationStatus,
    RecipientType,
)
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


# ── HTML Email Templates ────────────────────────────────────────────

PORTAL_INVITE_SUBJECT = "You've been invited to view contracts on Evaluetor"

PORTAL_INVITE_BODY = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a1a1a; max-width: 600px; margin: 0 auto; padding: 20px;">
  <div style="border-bottom: 3px solid #7c3aed; padding-bottom: 16px; margin-bottom: 24px;">
    <h1 style="margin: 0; font-size: 24px; color: #7c3aed;">Evaluetor</h1>
    <p style="margin: 4px 0 0; color: #6b7280; font-size: 14px;">Contract Lifecycle Management</p>
  </div>

  <p>Hi {{ recipient_name }},</p>

  <p><strong>{{ inviter_name }}</strong> has shared {{ contract_count }} contract{{ 's' if contract_count != 1 else '' }} with you on Evaluetor.</p>

  {% if message %}
  <div style="background: #f5f3ff; border-left: 4px solid #7c3aed; padding: 12px 16px; margin: 16px 0; border-radius: 0 8px 8px 0;">
    <p style="margin: 0; font-style: italic; color: #4b5563;">{{ message }}</p>
  </div>
  {% endif %}

  <div style="text-align: center; margin: 32px 0;">
    <a href="{{ access_url }}"
       style="display: inline-block; background: #7c3aed; color: #ffffff; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">
      View Contracts
    </a>
  </div>

  <div style="background: #f9fafb; border-radius: 8px; padding: 16px; margin: 24px 0;">
    <p style="margin: 0 0 8px; font-weight: 600; font-size: 14px;">Access Details</p>
    <table style="font-size: 14px; color: #4b5563;">
      <tr><td style="padding: 2px 12px 2px 0;">Permissions:</td><td>{{ permissions }}</td></tr>
      {% if expires_at %}<tr><td style="padding: 2px 12px 2px 0;">Expires:</td><td>{{ expires_at }}</td></tr>{% endif %}
    </table>
  </div>

  <p style="color: #6b7280; font-size: 13px; margin-top: 32px;">
    This link is unique to you. Do not forward this email — the access token is tied to your account.
  </p>

  <div style="border-top: 1px solid #e5e7eb; margin-top: 32px; padding-top: 16px; color: #9ca3af; font-size: 12px;">
    Sent by Evaluetor CLM
  </div>
</body>
</html>"""


RESEND_INVITE_SUBJECT = "Your updated Evaluetor access link"

RESEND_INVITE_BODY = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1a1a1a; max-width: 600px; margin: 0 auto; padding: 20px;">
  <div style="border-bottom: 3px solid #7c3aed; padding-bottom: 16px; margin-bottom: 24px;">
    <h1 style="margin: 0; font-size: 24px; color: #7c3aed;">Evaluetor</h1>
    <p style="margin: 4px 0 0; color: #6b7280; font-size: 14px;">Contract Lifecycle Management</p>
  </div>

  <p>Hi {{ recipient_name }},</p>

  <p>A new access link has been generated for your Evaluetor contract portal.</p>

  <div style="text-align: center; margin: 32px 0;">
    <a href="{{ access_url }}"
       style="display: inline-block; background: #7c3aed; color: #ffffff; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px;">
      Access Portal
    </a>
  </div>

  {% if expires_at %}
  <p style="text-align: center; color: #6b7280; font-size: 14px;">This link expires on {{ expires_at }}.</p>
  {% endif %}

  <p style="color: #6b7280; font-size: 13px; margin-top: 32px;">
    Any previous access links have been replaced by this one.
  </p>

  <div style="border-top: 1px solid #e5e7eb; margin-top: 32px; padding-top: 16px; color: #9ca3af; font-size: 12px;">
    Sent by Evaluetor CLM
  </div>
</body>
</html>"""


# ── Service ─────────────────────────────────────────────────────────


class ExternalEmailService:
    """Sends branded emails to external portal users."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._notification_service = NotificationService(db)

    async def send_portal_invitation(
        self,
        recipient_email: str,
        recipient_name: str,
        inviter_name: str,
        access_url: str,
        contract_count: int = 1,
        message: Optional[str] = None,
        permissions: str = "View, Comment",
        expires_at: Optional[datetime] = None,
    ) -> dict:
        """Send contract portal invitation email.

        Args:
            recipient_email: External user's email.
            recipient_name: External user's display name.
            inviter_name: Internal user who created the invitation.
            access_url: Full URL with token for portal access.
            contract_count: Number of contracts shared.
            message: Optional personal message from inviter.
            permissions: Human-readable permission summary.
            expires_at: When the access expires.

        Returns:
            Dict with send status and notification log ID.
        """
        context = {
            "recipient_name": recipient_name or "there",
            "inviter_name": inviter_name,
            "access_url": access_url,
            "contract_count": contract_count,
            "message": message,
            "permissions": permissions,
            "expires_at": expires_at.strftime("%B %d, %Y") if expires_at else None,
        }

        return await self._send_external_email(
            template_name=None,  # Use inline template
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=PORTAL_INVITE_SUBJECT,
            body=PORTAL_INVITE_BODY,
            context=context,
        )

    async def send_resend_invitation(
        self,
        recipient_email: str,
        recipient_name: str,
        access_url: str,
        expires_at: Optional[datetime] = None,
    ) -> dict:
        """Send a refreshed access link email.

        Args:
            recipient_email: External user's email.
            recipient_name: External user's display name.
            access_url: New access URL.
            expires_at: When the new token expires.

        Returns:
            Dict with send status.
        """
        context = {
            "recipient_name": recipient_name or "there",
            "access_url": access_url,
            "expires_at": expires_at.strftime("%B %d, %Y") if expires_at else None,
        }

        return await self._send_external_email(
            template_name=None,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            subject=RESEND_INVITE_SUBJECT,
            body=RESEND_INVITE_BODY,
            context=context,
        )

    async def _send_external_email(
        self,
        template_name: Optional[str],
        recipient_email: str,
        recipient_name: str,
        subject: str,
        body: str,
        context: dict,
    ) -> dict:
        """Send an email using NotificationService with inline templates.

        Uses NotificationService for logging and delivery, but renders
        the Jinja2 template inline rather than loading from DB.
        """
        renderer = self._notification_service.renderer

        rendered_subject = renderer.render(subject, context)
        rendered_body = renderer.render(body, context)

        # Create notification log entry
        notification = NotificationLog(
            channel=NotificationChannel.email,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            recipient_type=RecipientType.external_user,
            subject=rendered_subject,
            body=rendered_body,
            variables_used=context,
            status=NotificationStatus.pending,
        )
        self.db.add(notification)
        await self.db.flush()

        # Send via EmailService
        try:
            from app.integrations.email import EmailService

            email_service = EmailService(self.db)
            result = await email_service.send_email(
                to_email=recipient_email,
                subject=rendered_subject,
                body=rendered_body,
                to_name=recipient_name,
                is_html=True,
            )

            notification.status = NotificationStatus.sent
            notification.sent_at = datetime.utcnow()
            if result.get("message_id"):
                notification.external_id = result["message_id"]

            logger.info(f"External email sent to {recipient_email}: {rendered_subject}")

            return {
                "email_sent": True,
                "to": recipient_email,
                "subject": rendered_subject,
                "mock": result.get("mock", False),
                "notification_id": str(notification.id),
            }

        except Exception as e:
            notification.status = NotificationStatus.failed
            notification.error_message = str(e)[:500]
            notification.attempts = 1
            notification.last_attempt_at = datetime.utcnow()

            logger.error(f"Failed to send external email to {recipient_email}: {e}")

            return {
                "email_sent": False,
                "to": recipient_email,
                "error": str(e)[:200],
                "notification_id": str(notification.id),
            }
