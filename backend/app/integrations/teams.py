"""Microsoft Teams integration via Power Automate workflows.

Sends notifications to Teams channels using Power Automate HTTP triggers.
Supports Adaptive Card format for rich, interactive notifications.
"""

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import httpx

from app.integrations.base import BaseIntegrationClient
from app.models.integration import IntegrationConfig

logger = logging.getLogger(__name__)


class TeamsClient(BaseIntegrationClient):
    """Client for Microsoft Teams via Power Automate.

    Uses Power Automate workflow URLs (HTTP triggers) to post messages
    to Teams channels. Supports Adaptive Card format for rich notifications.

    Configuration:
        base_url: The Power Automate workflow URL
        config: {
            "default_channel": "General",  # For logging/display purposes
            "include_action_buttons": true  # Whether to include action buttons
        }
    """

    def __init__(self, config: IntegrationConfig, db):
        super().__init__(config, db)

    async def _get_auth_headers(self) -> dict[str, str]:
        """Power Automate URLs include authentication in the URL itself."""
        return {
            "Content-Type": "application/json",
        }

    async def health_check(self) -> bool:
        """Check if Power Automate workflow is accessible.

        Note: Power Automate doesn't have a separate health endpoint,
        so we just verify the URL is reachable.
        """
        try:
            # Send a minimal test payload
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.base_url,
                    json={"type": "health_check", "message": "CLM connectivity test"},
                    headers=await self._get_auth_headers(),
                )
                # Power Automate returns 202 Accepted for async workflows
                return response.status_code in (200, 202)
        except Exception as e:
            logger.error(f"Teams health check failed: {e}")
            return False

    async def send_notification(
        self,
        title: str,
        message: str,
        severity: str = "info",
        details: Optional[dict[str, Any]] = None,
        action_url: Optional[str] = None,
        action_title: str = "View Details",
        action_execution_id: Optional[UUID] = None,
    ) -> dict:
        """Send a notification to Teams channel.

        Args:
            title: Notification title.
            message: Main message body.
            severity: info, warning, error, or success.
            details: Additional key-value details to display.
            action_url: URL for the action button.
            action_title: Text for the action button.
            action_execution_id: Optional linked action execution.

        Returns:
            Result with status.
        """
        # Build Adaptive Card
        card = self._build_adaptive_card(
            title=title,
            message=message,
            severity=severity,
            details=details,
            action_url=action_url,
            action_title=action_title,
        )

        # Power Automate expects the card in a specific format
        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card,
                }
            ],
        }

        response = await self.request(
            method="POST",
            endpoint="",  # URL is the base_url itself
            operation="send_notification",
            action_execution_id=action_execution_id,
            json=payload,
        )

        return {
            "status": "sent" if not response.get("error") else "failed",
            "title": title,
            "severity": severity,
        }

    def _build_adaptive_card(
        self,
        title: str,
        message: str,
        severity: str = "info",
        details: Optional[dict[str, Any]] = None,
        action_url: Optional[str] = None,
        action_title: str = "View Details",
    ) -> dict:
        """Build an Adaptive Card for Teams.

        Args:
            title: Card title.
            message: Main message.
            severity: Determines accent color.
            details: Key-value pairs to display.
            action_url: URL for action button.
            action_title: Action button text.

        Returns:
            Adaptive Card JSON structure.
        """
        # Severity to color mapping
        severity_colors = {
            "info": "accent",
            "success": "good",
            "warning": "warning",
            "error": "attention",
        }
        color = severity_colors.get(severity, "accent")

        # Severity to emoji mapping for visual clarity
        severity_icons = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "🚨",
        }
        icon = severity_icons.get(severity, "ℹ️")

        # Build card body
        body = [
            {
                "type": "TextBlock",
                "size": "Large",
                "weight": "Bolder",
                "text": f"{icon} {title}",
                "wrap": True,
            },
            {
                "type": "TextBlock",
                "text": message,
                "wrap": True,
            },
        ]

        # Add details as FactSet if provided
        if details:
            facts = [
                {"title": str(k), "value": str(v)}
                for k, v in details.items()
                if v is not None
            ]
            if facts:
                body.append(
                    {
                        "type": "FactSet",
                        "facts": facts,
                    }
                )

        # Add timestamp
        body.append(
            {
                "type": "TextBlock",
                "text": f"Sent at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                "size": "Small",
                "isSubtle": True,
            }
        )

        # Build card
        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": body,
        }

        # Add action button if URL provided
        config = self.config.config or {}
        if action_url and config.get("include_action_buttons", True):
            card["actions"] = [
                {
                    "type": "Action.OpenUrl",
                    "title": action_title,
                    "url": action_url,
                }
            ]

        return card

    # Convenience methods for common CLM notifications

    async def notify_contract_renewal(
        self,
        contract_name: str,
        counterparty: str,
        renewal_date: str,
        days_until_renewal: int,
        contract_id: str,
        base_app_url: str = "",
        action_execution_id: Optional[UUID] = None,
    ) -> dict:
        """Send contract renewal notification.

        Args:
            contract_name: Name of the contract.
            counterparty: Counterparty name.
            renewal_date: Date of renewal.
            days_until_renewal: Days until renewal.
            contract_id: Contract ID for action URL.
            base_app_url: Base URL of CLM application.
            action_execution_id: Optional linked action execution.

        Returns:
            Notification result.
        """
        severity = "warning" if days_until_renewal <= 30 else "info"
        if days_until_renewal <= 7:
            severity = "error"

        return await self.send_notification(
            title="Contract Renewal Approaching",
            message=f"Contract '{contract_name}' with {counterparty} is due for renewal.",
            severity=severity,
            details={
                "Contract": contract_name,
                "Counterparty": counterparty,
                "Renewal Date": renewal_date,
                "Days Remaining": str(days_until_renewal),
            },
            action_url=f"{base_app_url}/contracts/{contract_id}" if base_app_url else None,
            action_title="View Contract",
            action_execution_id=action_execution_id,
        )

    async def notify_sla_breach(
        self,
        sla_name: str,
        contract_name: str,
        target_value: float,
        actual_value: float,
        deviation_percent: float,
        contract_id: str,
        base_app_url: str = "",
        action_execution_id: Optional[UUID] = None,
    ) -> dict:
        """Send SLA breach notification.

        Args:
            sla_name: Name of the SLA metric.
            contract_name: Associated contract name.
            target_value: Expected SLA value.
            actual_value: Actual measured value.
            deviation_percent: Percentage deviation from target.
            contract_id: Contract ID for action URL.
            base_app_url: Base URL of CLM application.
            action_execution_id: Optional linked action execution.

        Returns:
            Notification result.
        """
        return await self.send_notification(
            title="SLA Breach Detected",
            message=f"SLA '{sla_name}' has breached its target on contract '{contract_name}'.",
            severity="error",
            details={
                "SLA Metric": sla_name,
                "Contract": contract_name,
                "Target": f"{target_value}",
                "Actual": f"{actual_value}",
                "Deviation": f"{deviation_percent:.1f}%",
            },
            action_url=f"{base_app_url}/contracts/{contract_id}/sla" if base_app_url else None,
            action_title="View SLA Details",
            action_execution_id=action_execution_id,
        )

    async def notify_perception_gap(
        self,
        kpi_name: str,
        relationship_name: str,
        internal_score: float,
        external_score: float,
        gap: float,
        severity_level: str,
        relationship_id: str,
        base_app_url: str = "",
        action_execution_id: Optional[UUID] = None,
    ) -> dict:
        """Send perception gap notification.

        Args:
            kpi_name: Name of the KPI.
            relationship_name: Business relationship name.
            internal_score: Internal stakeholder score.
            external_score: External stakeholder score.
            gap: Calculated perception gap.
            severity_level: low, medium, high, critical.
            relationship_id: Relationship ID for action URL.
            base_app_url: Base URL of CLM application.
            action_execution_id: Optional linked action execution.

        Returns:
            Notification result.
        """
        severity_map = {
            "low": "info",
            "medium": "warning",
            "high": "error",
            "critical": "error",
        }

        return await self.send_notification(
            title="Perception Gap Identified",
            message=f"A {severity_level} perception gap has been detected for KPI '{kpi_name}' "
                    f"in relationship '{relationship_name}'.",
            severity=severity_map.get(severity_level, "warning"),
            details={
                "KPI": kpi_name,
                "Relationship": relationship_name,
                "Internal Score": f"{internal_score:.1f}",
                "External Score": f"{external_score:.1f}",
                "Gap": f"{gap:.1f}",
                "Severity": severity_level.upper(),
            },
            action_url=f"{base_app_url}/relationships/{relationship_id}/kpis" if base_app_url else None,
            action_title="View KPI Details",
            action_execution_id=action_execution_id,
        )

    async def notify_improvement_assigned(
        self,
        improvement_title: str,
        assigned_to: str,
        due_date: Optional[str],
        priority: str,
        relationship_name: str,
        improvement_id: str,
        base_app_url: str = "",
        action_execution_id: Optional[UUID] = None,
    ) -> dict:
        """Send improvement point assignment notification.

        Args:
            improvement_title: Title of the improvement.
            assigned_to: Name of assignee.
            due_date: Due date if set.
            priority: low, medium, high, critical.
            relationship_name: Associated relationship.
            improvement_id: Improvement ID for action URL.
            base_app_url: Base URL of CLM application.
            action_execution_id: Optional linked action execution.

        Returns:
            Notification result.
        """
        severity_map = {
            "low": "info",
            "medium": "info",
            "high": "warning",
            "critical": "error",
        }

        details = {
            "Improvement": improvement_title,
            "Assigned To": assigned_to,
            "Priority": priority.upper(),
            "Relationship": relationship_name,
        }
        if due_date:
            details["Due Date"] = due_date

        return await self.send_notification(
            title="Improvement Point Assigned",
            message=f"You have been assigned an improvement point: '{improvement_title}'.",
            severity=severity_map.get(priority, "info"),
            details=details,
            action_url=f"{base_app_url}/improvements/{improvement_id}" if base_app_url else None,
            action_title="View Improvement",
            action_execution_id=action_execution_id,
        )

    async def notify_contract_risk(
        self,
        contract_name: str,
        risk_level: str,
        risk_score: float,
        top_risks: list[str],
        contract_id: str,
        base_app_url: str = "",
        action_execution_id: Optional[UUID] = None,
    ) -> dict:
        """Send contract risk alert notification.

        Args:
            contract_name: Name of the contract.
            risk_level: low, medium, high, critical.
            risk_score: Numeric risk score.
            top_risks: List of top risk factors.
            contract_id: Contract ID for action URL.
            base_app_url: Base URL of CLM application.
            action_execution_id: Optional linked action execution.

        Returns:
            Notification result.
        """
        severity_map = {
            "low": "info",
            "medium": "warning",
            "high": "error",
            "critical": "error",
        }

        return await self.send_notification(
            title="Contract Risk Alert",
            message=f"Contract '{contract_name}' has been flagged with {risk_level} risk.",
            severity=severity_map.get(risk_level, "warning"),
            details={
                "Contract": contract_name,
                "Risk Level": risk_level.upper(),
                "Risk Score": f"{risk_score:.0f}/100",
                "Top Risks": ", ".join(top_risks[:3]) if top_risks else "N/A",
            },
            action_url=f"{base_app_url}/contracts/{contract_id}/risk" if base_app_url else None,
            action_title="View Risk Analysis",
            action_execution_id=action_execution_id,
        )

    async def notify_survey_response(
        self,
        survey_name: str,
        respondent_name: str,
        relationship_name: str,
        overall_score: Optional[float],
        survey_id: str,
        base_app_url: str = "",
        action_execution_id: Optional[UUID] = None,
    ) -> dict:
        """Send survey response notification.

        Args:
            survey_name: Name of the survey.
            respondent_name: Name of respondent.
            relationship_name: Associated relationship.
            overall_score: Average response score if available.
            survey_id: Survey instance ID for action URL.
            base_app_url: Base URL of CLM application.
            action_execution_id: Optional linked action execution.

        Returns:
            Notification result.
        """
        details = {
            "Survey": survey_name,
            "Respondent": respondent_name,
            "Relationship": relationship_name,
        }
        if overall_score is not None:
            details["Score"] = f"{overall_score:.1f}/5"

        return await self.send_notification(
            title="New Survey Response",
            message=f"{respondent_name} has completed the survey '{survey_name}'.",
            severity="success",
            details=details,
            action_url=f"{base_app_url}/surveys/{survey_id}/responses" if base_app_url else None,
            action_title="View Response",
            action_execution_id=action_execution_id,
        )
