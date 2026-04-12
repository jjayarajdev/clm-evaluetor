"""Email integration service.

Supports SendGrid API and SMTP for sending notifications.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from uuid import UUID

from app.integrations.base import BaseIntegrationClient
from app.models.integration import IntegrationConfig

logger = logging.getLogger(__name__)


class SendGridClient(BaseIntegrationClient):
    """Client for SendGrid email API."""

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get SendGrid API key authentication."""
        credentials = self.config.credentials or {}
        api_key = credentials.get("api_key", "")

        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def health_check(self) -> bool:
        """Check SendGrid API accessibility."""
        # SendGrid doesn't have a dedicated health endpoint
        # We just verify we can make authenticated requests
        try:
            response = await self.request(
                method="GET",
                endpoint="/v3/user/profile",
                operation="health_check",
            )
            return not response.get("error", False)
        except Exception as e:
            logger.error(f"SendGrid health check failed: {e}")
            return False

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        to_name: str = "",
        is_html: bool = False,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        action_execution_id: Optional[UUID] = None,
    ) -> dict:
        """Send an email via SendGrid.

        Args:
            to_email: Recipient email address.
            subject: Email subject.
            body: Email body (text or HTML).
            to_name: Recipient name.
            is_html: Whether body is HTML.
            from_email: Sender email (uses config default if not provided).
            from_name: Sender name.
            reply_to: Reply-to address.
            action_execution_id: Optional linked action execution.

        Returns:
            Send result with message ID.
        """
        config = self.config.config or {}

        # Get sender info
        sender_email = from_email or config.get("from_email", "noreply@example.com")
        sender_name = from_name or config.get("from_name", "Contract Intelligence")

        # Build SendGrid payload
        payload = {
            "personalizations": [
                {
                    "to": [{"email": to_email, "name": to_name}],
                    "subject": subject,
                }
            ],
            "from": {"email": sender_email, "name": sender_name},
            "content": [
                {
                    "type": "text/html" if is_html else "text/plain",
                    "value": body,
                }
            ],
        }

        if reply_to:
            payload["reply_to"] = {"email": reply_to}

        response = await self.request(
            method="POST",
            endpoint="/v3/mail/send",
            operation="send_email",
            action_execution_id=action_execution_id,
            json=payload,
        )

        # SendGrid returns 202 with no body on success
        if response.get("error"):
            raise ValueError(f"Failed to send email: {response.get('message')}")

        return {
            "status": "sent",
            "to": to_email,
            "subject": subject,
        }


class SMTPClient:
    """Simple SMTP client for email sending.

    Used as fallback when SendGrid is not configured.
    """

    def __init__(self, config: IntegrationConfig):
        """Initialize SMTP client.

        Args:
            config: Integration configuration with SMTP settings.
        """
        self.config = config
        self.credentials = config.credentials or {}
        self.settings = config.config or {}

    @property
    def host(self) -> str:
        return self.credentials.get("host", "localhost")

    @property
    def port(self) -> int:
        return int(self.credentials.get("port", 587))

    @property
    def username(self) -> Optional[str]:
        return self.credentials.get("username")

    @property
    def password(self) -> Optional[str]:
        return self.credentials.get("password")

    @property
    def use_tls(self) -> bool:
        return self.credentials.get("use_tls", True)

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        to_name: str = "",
        is_html: bool = False,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
    ) -> dict:
        """Send email via SMTP.

        Args:
            to_email: Recipient email.
            subject: Email subject.
            body: Email body.
            to_name: Recipient name.
            is_html: Whether body is HTML.
            from_email: Sender email.
            from_name: Sender name.

        Returns:
            Send result.
        """
        sender_email = from_email or self.settings.get("from_email", "noreply@example.com")
        sender_name = from_name or self.settings.get("from_name", "Contract Intelligence")

        # Build message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{sender_name} <{sender_email}>"
        msg["To"] = f"{to_name} <{to_email}>" if to_name else to_email

        # Add body
        content_type = "html" if is_html else "plain"
        msg.attach(MIMEText(body, content_type))

        try:
            # Connect to SMTP server
            if self.use_tls:
                server = smtplib.SMTP(self.host, self.port)
                server.starttls()
            else:
                server = smtplib.SMTP(self.host, self.port)

            # Authenticate if credentials provided
            if self.username and self.password:
                server.login(self.username, self.password)

            # Send email
            server.sendmail(sender_email, [to_email], msg.as_string())
            server.quit()

            logger.info(f"Email sent to {to_email}: {subject}")

            return {
                "status": "sent",
                "to": to_email,
                "subject": subject,
            }

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise


class EmailService:
    """High-level email service.

    Abstracts over SendGrid and SMTP implementations.
    """

    def __init__(self, db):
        """Initialize email service.

        Args:
            db: Database session for loading config.
        """
        self.db = db
        self._client = None

    async def _get_client(self):
        """Get or create email client.

        Priority order: AWS SES > SendGrid > SMTP > mock fallback.
        Only considers non-demo configs first; falls back to demo if nothing else.
        """
        if self._client:
            return self._client

        from sqlalchemy import select
        from app.models.integration import IntegrationConfig, IntegrationSystem

        # Try AWS SES first (preferred for production)
        result = await self.db.execute(
            select(IntegrationConfig)
            .where(
                IntegrationConfig.system == IntegrationSystem.aws_ses,
                IntegrationConfig.is_active == True,
                IntegrationConfig.is_demo == False,
            )
            .limit(1)
        )
        config = result.scalar_one_or_none()

        if config:
            from app.integrations.ses import SESClient
            self._client = SESClient(config)
            return self._client

        # Try SendGrid
        result = await self.db.execute(
            select(IntegrationConfig)
            .where(
                IntegrationConfig.system == IntegrationSystem.sendgrid,
                IntegrationConfig.is_active == True,
            )
            .limit(1)
        )
        config = result.scalar_one_or_none()

        if config and not config.is_demo:
            self._client = SendGridClient(config, self.db)
            return self._client

        # Fall back to SMTP
        result = await self.db.execute(
            select(IntegrationConfig)
            .where(
                IntegrationConfig.system == IntegrationSystem.smtp,
                IntegrationConfig.is_active == True,
            )
            .limit(1)
        )
        config = result.scalar_one_or_none()

        if config:
            self._client = SMTPClient(config)
            return self._client

        # No real email configured, use mock
        logger.warning("No email service configured, using mock")
        return None

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        **kwargs,
    ) -> dict:
        """Send an email.

        Args:
            to_email: Recipient email.
            subject: Email subject.
            body: Email body.
            **kwargs: Additional options.

        Returns:
            Send result.
        """
        client = await self._get_client()

        if client is None:
            # Mock send
            logger.info(f"[MOCK EMAIL] To: {to_email}, Subject: {subject}")
            return {
                "status": "sent",
                "to": to_email,
                "subject": subject,
                "mock": True,
            }

        from app.integrations.ses import SESClient

        if isinstance(client, SESClient):
            return await client.send_email(to_email, subject, body, **kwargs)
        elif isinstance(client, SendGridClient):
            async with client:
                return await client.send_email(to_email, subject, body, **kwargs)
        else:
            return client.send_email(to_email, subject, body, **kwargs)
