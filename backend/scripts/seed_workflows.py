#!/usr/bin/env python3
"""Seed initial workflows, notification templates, and integration configs."""

import asyncio
import sys
from pathlib import Path
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import async_session_maker
from app.models.event import EventType
from app.models.workflow import (
    WorkflowDefinition,
    WorkflowStep,
    ActionType,
)
from app.models.notification import (
    NotificationTemplate,
    NotificationChannel,
    RecipientType,
)
from app.models.integration import (
    IntegrationConfig,
    IntegrationSystem,
    IntegrationStatus,
)


# Workflow definitions
WORKFLOWS = [
    {
        "name": "SLA Breach Response",
        "description": "Handles SLA breach events: calculates service credits, gets approval, notifies vendor, creates SNOW incident",
        "event_type": EventType.sla_breach,
        "is_default": True,
        "steps": [
            {
                "name": "Calculate Service Credit",
                "step_order": 1,
                "action_type": ActionType.calculate_service_credit,
                "action_config": {
                    "formula": "breach_percentage * contract_value * credit_rate",
                    "credit_rate": 0.01,
                },
                "requires_approval": False,
            },
            {
                "name": "Request Approval for Credit",
                "step_order": 2,
                "action_type": ActionType.create_approval_request,
                "action_config": {
                    "title_template": "Service Credit Approval: {{ contract_name }}",
                    "description_template": "SLA breach detected. Proposed credit: ${{ credit_amount }}",
                },
                "requires_approval": True,
                "approval_timeout_hours": 24,
            },
            {
                "name": "Notify Vendor",
                "step_order": 3,
                "action_type": ActionType.send_email,
                "action_config": {
                    "template": "sla_breach_vendor",
                    "recipient_type": "vendor_contact",
                },
                "requires_approval": False,
            },
            {
                "name": "Create ServiceNow Incident",
                "step_order": 4,
                "action_type": ActionType.create_snow_incident,
                "action_config": {
                    "urgency": "2",
                    "impact": "2",
                    "category": "Contract SLA",
                    "short_description_template": "SLA Breach: {{ sla_name }} for {{ contract_name }}",
                },
                "requires_approval": False,
            },
            {
                "name": "Update Salesforce Account",
                "step_order": 5,
                "action_type": ActionType.update_sfdc_account,
                "action_config": {
                    "fields": {
                        "Contract_Health__c": "At Risk",
                        "Last_SLA_Breach_Date__c": "{{ today }}",
                    },
                },
                "requires_approval": False,
                "is_optional": True,
            },
        ],
    },
    {
        "name": "SLA Warning Alert",
        "description": "Sends warning when SLA is approaching breach threshold",
        "event_type": EventType.sla_warning,
        "is_default": True,
        "steps": [
            {
                "name": "Notify Contract Owner",
                "step_order": 1,
                "action_type": ActionType.send_email,
                "action_config": {
                    "template": "sla_warning_owner",
                    "recipient_type": "contract_owner",
                },
                "requires_approval": False,
            },
        ],
    },
    {
        "name": "Renewal Approaching",
        "description": "Handles upcoming contract renewals",
        "event_type": EventType.renewal_approaching,
        "is_default": True,
        "steps": [
            {
                "name": "Notify Contract Owner",
                "step_order": 1,
                "action_type": ActionType.send_email,
                "action_config": {
                    "template": "renewal_approaching",
                    "recipient_type": "contract_owner",
                },
                "requires_approval": False,
            },
            {
                "name": "Create Salesforce Task",
                "step_order": 2,
                "action_type": ActionType.create_sfdc_task,
                "action_config": {
                    "subject_template": "Review Renewal: {{ contract_name }}",
                    "due_date_offset_days": 14,
                    "priority": "High",
                },
                "requires_approval": False,
            },
        ],
    },
    {
        "name": "Milestone Overdue",
        "description": "Escalates overdue milestones",
        "event_type": EventType.milestone_overdue,
        "is_default": True,
        "steps": [
            {
                "name": "Notify Contract Owner",
                "step_order": 1,
                "action_type": ActionType.send_email,
                "action_config": {
                    "template": "milestone_overdue",
                    "recipient_type": "contract_owner",
                },
                "requires_approval": False,
            },
            {
                "name": "Create ServiceNow Incident",
                "step_order": 2,
                "action_type": ActionType.create_snow_incident,
                "action_config": {
                    "urgency": "3",
                    "impact": "3",
                    "category": "Contract Milestone",
                    "short_description_template": "Overdue Milestone: {{ milestone_name }}",
                },
                "requires_approval": False,
            },
        ],
    },
    {
        "name": "Obligation Due Soon",
        "description": "Reminds about upcoming obligation deadlines",
        "event_type": EventType.obligation_due,
        "is_default": True,
        "steps": [
            {
                "name": "Send Reminder",
                "step_order": 1,
                "action_type": ActionType.send_email,
                "action_config": {
                    "template": "obligation_reminder",
                    "recipient_type": "contract_owner",
                },
                "requires_approval": False,
            },
        ],
    },
]


# Notification templates
NOTIFICATION_TEMPLATES = [
    {
        "name": "sla_breach_vendor",
        "description": "Notifies vendor of SLA breach",
        "event_type": EventType.sla_breach,
        "channel": NotificationChannel.email,
        "subject_template": "[Action Required] SLA Breach Notice: {{ contract_name }}",
        "body_template": """Dear {{ vendor_name }},

We are writing to formally notify you of a Service Level Agreement (SLA) breach under our contract {{ contract_name }}.

**SLA Details:**
- SLA Name: {{ sla_name }}
- Target: {{ target_value }}{{ unit }}
- Actual: {{ actual_value }}{{ unit }}
- Measurement Period: {{ period_start }} to {{ period_end }}

**Impact:**
- Deviation: {{ deviation_percent }}% below target
- Service Credit Due: ${{ credit_amount }}

Per Section {{ sla_section }} of our agreement, this breach triggers the following remedies:
{{ remedy_description }}

Please acknowledge receipt of this notice and provide your remediation plan within 5 business days.

Best regards,
{{ sender_name }}
Contract Management Team
""",
        "is_html": False,
        "default_recipient_type": RecipientType.vendor_contact,
    },
    {
        "name": "sla_warning_owner",
        "description": "Warns contract owner about SLA approaching breach",
        "event_type": EventType.sla_warning,
        "channel": NotificationChannel.email,
        "subject_template": "[Warning] SLA At Risk: {{ contract_name }}",
        "body_template": """Hi {{ owner_name }},

This is an automated alert that the following SLA is approaching breach threshold:

**Contract:** {{ contract_name }}
**SLA:** {{ sla_name }}
**Current Performance:** {{ actual_value }}{{ unit }}
**Target:** {{ target_value }}{{ unit }}
**Warning Threshold:** {{ warning_threshold }}{{ unit }}

**Recommendation:** Monitor closely and consider proactive vendor outreach.

View contract details: {{ contract_url }}

Best regards,
Contract Intelligence System
""",
        "is_html": False,
        "default_recipient_type": RecipientType.contract_owner,
    },
    {
        "name": "renewal_approaching",
        "description": "Notification for upcoming contract renewal",
        "event_type": EventType.renewal_approaching,
        "channel": NotificationChannel.email,
        "subject_template": "[Action Required] Contract Renewal: {{ contract_name }} - {{ days_until_expiry }} days",
        "body_template": """Hi {{ owner_name }},

The following contract is approaching its renewal date:

**Contract:** {{ contract_name }}
**Counterparty:** {{ counterparty }}
**Expiration Date:** {{ expiration_date }}
**Days Until Expiry:** {{ days_until_expiry }}
**Auto-Renewal:** {{ auto_renewal_status }}

{% if auto_renewal_status == 'Yes' %}
**Notice Deadline:** {{ notice_deadline }}
If you wish to terminate or renegotiate, action must be taken by this date.
{% endif %}

**Contract Value:** ${{ contract_value }}

**Recommended Actions:**
1. Review contract performance and vendor relationship
2. Evaluate market alternatives
3. Prepare negotiation strategy if renewing
4. Submit renewal decision by {{ decision_deadline }}

View contract details: {{ contract_url }}

Best regards,
Contract Intelligence System
""",
        "is_html": False,
        "default_recipient_type": RecipientType.contract_owner,
    },
    {
        "name": "milestone_overdue",
        "description": "Alert for overdue milestone",
        "event_type": EventType.milestone_overdue,
        "channel": NotificationChannel.email,
        "subject_template": "[Overdue] Contract Milestone: {{ milestone_name }}",
        "body_template": """Hi {{ owner_name }},

The following contract milestone is now overdue:

**Contract:** {{ contract_name }}
**Milestone:** {{ milestone_name }}
**Due Date:** {{ due_date }}
**Days Overdue:** {{ days_overdue }}
**Responsible Party:** {{ responsible_party }}

**Description:**
{{ milestone_description }}

Please take immediate action to address this overdue milestone.

View contract details: {{ contract_url }}

Best regards,
Contract Intelligence System
""",
        "is_html": False,
        "default_recipient_type": RecipientType.contract_owner,
    },
    {
        "name": "obligation_reminder",
        "description": "Reminder for upcoming obligation deadline",
        "event_type": EventType.obligation_due,
        "channel": NotificationChannel.email,
        "subject_template": "[Reminder] Obligation Due: {{ obligation_description | truncate(50) }}",
        "body_template": """Hi {{ owner_name }},

This is a reminder that the following obligation is due soon:

**Contract:** {{ contract_name }}
**Obligation:** {{ obligation_description }}
**Due Date:** {{ due_date }}
**Days Remaining:** {{ days_remaining }}
**Category:** {{ obligation_category }}
**Owner:** {{ obligation_owner }}

Please ensure this obligation is completed on time.

View contract details: {{ contract_url }}

Best regards,
Contract Intelligence System
""",
        "is_html": False,
        "default_recipient_type": RecipientType.contract_owner,
    },
    {
        "name": "approval_request",
        "description": "Request for approval of an action",
        "event_type": None,
        "channel": NotificationChannel.email,
        "subject_template": "[Approval Required] {{ approval_title }}",
        "body_template": """Hi {{ approver_name }},

Your approval is required for the following action:

**Request:** {{ approval_title }}
**Contract:** {{ contract_name }}
**Requested By:** {{ requester_name }}
**Expires:** {{ expires_at }}

**Details:**
{{ approval_description }}

{% if has_financial_impact %}
**Financial Impact:** ${{ financial_amount }}
{% endif %}

**Actions:**
- Approve: {{ approve_url }}
- Reject: {{ reject_url }}
- View Details: {{ details_url }}

This request will expire in {{ hours_remaining }} hours.

Best regards,
Contract Intelligence System
""",
        "is_html": False,
        "default_recipient_type": RecipientType.approver,
    },
    {
        "name": "action_failed",
        "description": "Notification when an action fails after retries",
        "event_type": None,
        "channel": NotificationChannel.email,
        "subject_template": "[Alert] Action Failed: {{ action_type }}",
        "body_template": """Hi {{ admin_name }},

An automated action has failed after {{ max_attempts }} attempts:

**Action Type:** {{ action_type }}
**Event:** {{ event_title }}
**Contract:** {{ contract_name }}
**Workflow:** {{ workflow_name }}

**Error Details:**
{{ error_message }}

**Last Attempt:** {{ last_attempt_at }}
**Total Attempts:** {{ attempts }}

Please investigate and take manual action if necessary.

Event ID: {{ event_id }}
Action Execution ID: {{ action_execution_id }}

Best regards,
Contract Intelligence System
""",
        "is_html": False,
        "default_recipient_type": RecipientType.escalation_contact,
    },
]


# Integration configs (placeholders - credentials to be added)
INTEGRATION_CONFIGS = [
    {
        "system": IntegrationSystem.servicenow,
        "name": "ServiceNow Production",
        "description": "ServiceNow instance for incident management",
        "base_url": "https://your-instance.service-now.com",
        "auth_type": "basic",
        "config": {
            "api_version": "v2",
            "assignment_group": "Contract Management",
            "caller_id": "contract_intelligence_system",
        },
        "is_default": True,
    },
    {
        "system": IntegrationSystem.salesforce,
        "name": "Salesforce Production",
        "description": "Salesforce CRM for account and opportunity management",
        "base_url": "https://your-domain.my.salesforce.com",
        "auth_type": "oauth2",
        "config": {
            "api_version": "v58.0",
            "sandbox": False,
        },
        "is_default": True,
    },
    {
        "system": IntegrationSystem.sendgrid,
        "name": "SendGrid Email",
        "description": "SendGrid for transactional emails",
        "base_url": "https://api.sendgrid.com",
        "auth_type": "api_key",
        "config": {
            "from_email": "contracts@yourdomain.com",
            "from_name": "Contract Intelligence",
        },
        "is_default": True,
    },
]


async def seed_workflows():
    """Seed workflows, templates, and integration configs."""
    async with async_session_maker() as db:
        from sqlalchemy import select, func

        # Check if already seeded
        result = await db.execute(select(func.count(WorkflowDefinition.id)))
        count = result.scalar()

        if count > 0:
            print(f"Workflows already seeded ({count} found). Skipping.")
            return

        print("Seeding workflows, templates, and integrations...")

        # Create workflows
        for wf_data in WORKFLOWS:
            steps_data = wf_data.pop("steps")
            workflow = WorkflowDefinition(**wf_data)
            db.add(workflow)
            await db.flush()

            for step_data in steps_data:
                step = WorkflowStep(workflow_id=workflow.id, **step_data)
                db.add(step)

            print(f"  ✓ Workflow: {wf_data['name']} ({len(steps_data)} steps)")

        # Create notification templates
        for tmpl_data in NOTIFICATION_TEMPLATES:
            template = NotificationTemplate(**tmpl_data)
            db.add(template)
            print(f"  ✓ Template: {tmpl_data['name']}")

        # Create integration configs
        for int_data in INTEGRATION_CONFIGS:
            integration = IntegrationConfig(**int_data)
            db.add(integration)
            print(f"  ✓ Integration: {int_data['name']}")

        await db.commit()
        print("\nSeeding complete!")
        print(f"  - {len(WORKFLOWS)} workflows")
        print(f"  - {len(NOTIFICATION_TEMPLATES)} notification templates")
        print(f"  - {len(INTEGRATION_CONFIGS)} integration configs")


if __name__ == "__main__":
    asyncio.run(seed_workflows())
