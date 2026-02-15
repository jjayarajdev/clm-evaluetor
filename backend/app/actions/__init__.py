"""Action handlers for workflow execution.

Each action type has a corresponding handler that executes
the actual work (sending emails, creating tickets, etc.).
"""

from app.actions.handlers import (
    handle_send_email,
    handle_create_snow_incident,
    handle_update_sfdc_account,
    handle_create_sfdc_task,
    handle_calculate_service_credit,
    handle_calculate_penalty,
    handle_update_contract_status,
    handle_create_approval_request,
    handle_escalate,
    handle_webhook,
)

__all__ = [
    "handle_send_email",
    "handle_create_snow_incident",
    "handle_update_sfdc_account",
    "handle_create_sfdc_task",
    "handle_calculate_service_credit",
    "handle_calculate_penalty",
    "handle_update_contract_status",
    "handle_create_approval_request",
    "handle_escalate",
    "handle_webhook",
]
