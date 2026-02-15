"""External system integrations.

Provides clients for:
- ServiceNow (incident management)
- Salesforce (account and task management)
- Email (SendGrid and SMTP)
"""

from app.integrations.base import BaseIntegrationClient, MockIntegrationClient
from app.integrations.servicenow import ServiceNowClient
from app.integrations.salesforce import SalesforceClient
from app.integrations.email import SendGridClient, SMTPClient, EmailService

__all__ = [
    "BaseIntegrationClient",
    "MockIntegrationClient",
    "ServiceNowClient",
    "SalesforceClient",
    "SendGridClient",
    "SMTPClient",
    "EmailService",
]
