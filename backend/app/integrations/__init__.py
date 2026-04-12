"""External system integrations.

Provides clients for:
- ServiceNow (incident management)
- Salesforce (account and task management)
- Email (SendGrid, AWS SES, and SMTP)
- Microsoft Teams (notifications via Power Automate)
"""

from app.integrations.base import BaseIntegrationClient, MockIntegrationClient
from app.integrations.servicenow import ServiceNowClient
from app.integrations.salesforce import SalesforceClient
from app.integrations.email import SendGridClient, SMTPClient, EmailService
from app.integrations.ses import SESClient
from app.integrations.teams import TeamsClient

__all__ = [
    "BaseIntegrationClient",
    "MockIntegrationClient",
    "ServiceNowClient",
    "SalesforceClient",
    "SendGridClient",
    "SMTPClient",
    "SESClient",
    "EmailService",
    "TeamsClient",
]
