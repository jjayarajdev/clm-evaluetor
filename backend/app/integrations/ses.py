"""AWS SES email integration.

Uses boto3 to send transactional emails via Amazon Simple Email Service.
Supports IAM credentials (access key + secret) or instance role authentication.
"""

import logging
from typing import Optional
from uuid import UUID

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.models.integration import IntegrationConfig

logger = logging.getLogger(__name__)


class SESClient:
    """Client for AWS Simple Email Service.

    Unlike SendGrid/SMTP, SES uses the boto3 SDK directly rather than
    HTTP requests through BaseIntegrationClient. This avoids fighting
    the AWS Signature V4 auth pattern through generic HTTP headers.
    """

    def __init__(self, config: IntegrationConfig):
        """Initialize SES client from IntegrationConfig.

        Args:
            config: IntegrationConfig with credentials and config JSONB fields.
                credentials: {"aws_access_key_id": "...", "aws_secret_access_key": "...", "region": "us-east-1"}
                config: {"from_email": "noreply@example.com", "from_name": "Evaluetor CLM", "configuration_set": null}
        """
        self.config = config
        self._credentials = config.credentials or {}
        self._settings = config.config or {}
        self._client = None

    @property
    def region(self) -> str:
        return self._credentials.get("region", "us-east-1")

    @property
    def from_email(self) -> str:
        return self._settings.get("from_email", "noreply@evaluetor.com")

    @property
    def from_name(self) -> str:
        return self._settings.get("from_name", "Evaluetor CLM")

    @property
    def configuration_set(self) -> Optional[str]:
        return self._settings.get("configuration_set")

    def _get_client(self):
        """Lazily create boto3 SES client."""
        if self._client:
            return self._client

        kwargs = {"region_name": self.region}

        # Use explicit credentials if provided, otherwise fall back to
        # instance role / environment variables / AWS config file
        access_key = self._credentials.get("aws_access_key_id")
        secret_key = self._credentials.get("aws_secret_access_key")
        if access_key and secret_key and not access_key.startswith("***"):
            kwargs["aws_access_key_id"] = access_key
            kwargs["aws_secret_access_key"] = secret_key

        self._client = boto3.client("ses", **kwargs)
        return self._client

    async def health_check(self) -> bool:
        """Verify SES is accessible by checking send quota."""
        try:
            client = self._get_client()
            response = client.get_send_quota()
            max_24hr = response.get("Max24HourSend", 0)
            logger.info(f"SES health OK — 24h quota: {max_24hr}")
            return True
        except (BotoCoreError, ClientError) as e:
            logger.error(f"SES health check failed: {e}")
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
        """Send an email via AWS SES.

        Args:
            to_email: Recipient email address.
            subject: Email subject.
            body: Email body (text or HTML).
            to_name: Recipient display name.
            is_html: Whether body is HTML.
            from_email: Sender email override.
            from_name: Sender name override.
            reply_to: Reply-to address.
            action_execution_id: Optional linked action execution.

        Returns:
            Dict with status and SES message ID.
        """
        client = self._get_client()

        sender_email = from_email or self.from_email
        sender_name = from_name or self.from_name
        source = f"{sender_name} <{sender_email}>"

        destination = {"ToAddresses": [to_email]}

        body_content = {}
        if is_html:
            body_content["Html"] = {"Charset": "UTF-8", "Data": body}
        else:
            body_content["Text"] = {"Charset": "UTF-8", "Data": body}

        message = {
            "Subject": {"Charset": "UTF-8", "Data": subject},
            "Body": body_content,
        }

        kwargs = {
            "Source": source,
            "Destination": destination,
            "Message": message,
        }

        if reply_to:
            kwargs["ReplyToAddresses"] = [reply_to]

        if self.configuration_set:
            kwargs["ConfigurationSetName"] = self.configuration_set

        try:
            response = client.send_email(**kwargs)
            message_id = response.get("MessageId", "")
            logger.info(f"SES email sent to {to_email}: {subject} (MessageId: {message_id})")
            return {
                "status": "sent",
                "to": to_email,
                "subject": subject,
                "message_id": message_id,
            }
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_msg = e.response["Error"]["Message"]
            logger.error(f"SES send failed ({error_code}): {error_msg}")
            raise ValueError(f"SES error ({error_code}): {error_msg}")
        except BotoCoreError as e:
            logger.error(f"SES send failed: {e}")
            raise ValueError(f"SES error: {e}")
