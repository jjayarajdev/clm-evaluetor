"""ServiceNow integration client.

Creates and updates incidents in ServiceNow.
"""

import base64
import logging
from typing import Optional
from uuid import UUID

from app.integrations.base import BaseIntegrationClient
from app.models.integration import IntegrationConfig

logger = logging.getLogger(__name__)


class ServiceNowClient(BaseIntegrationClient):
    """Client for ServiceNow REST API.

    Supports:
    - Incident creation and updates
    - User lookup
    - Health checks
    """

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers based on auth type."""
        credentials = self.config.credentials or {}
        auth_type = self.config.auth_type

        if auth_type == "basic":
            username = credentials.get("username", "")
            password = credentials.get("password", "")
            token = base64.b64encode(f"{username}:{password}".encode()).decode()
            return {
                "Authorization": f"Basic {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

        elif auth_type == "oauth2":
            # Would need to implement OAuth2 token refresh
            access_token = credentials.get("access_token", "")
            return {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

        else:
            return {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

    async def health_check(self) -> bool:
        """Check ServiceNow connectivity."""
        try:
            response = await self.request(
                method="GET",
                endpoint="/api/now/table/sys_user?sysparm_limit=1",
                operation="health_check",
            )
            return not response.get("error", False)
        except Exception as e:
            logger.error(f"ServiceNow health check failed: {e}")
            return False

    async def create_incident(
        self,
        short_description: str,
        description: str = "",
        urgency: str = "2",
        impact: str = "2",
        category: str = "",
        caller_id: str = "",
        assignment_group: str = "",
        action_execution_id: Optional[UUID] = None,
        **extra_fields,
    ) -> dict:
        """Create a new incident in ServiceNow.

        Args:
            short_description: Brief description of the incident.
            description: Detailed description.
            urgency: 1=High, 2=Medium, 3=Low.
            impact: 1=High, 2=Medium, 3=Low.
            category: Incident category.
            caller_id: User ID or sys_id of caller.
            assignment_group: Group to assign the incident to.
            action_execution_id: Optional linked action execution.
            **extra_fields: Additional incident fields.

        Returns:
            Response with incident number and sys_id.
        """
        config = self.config.config or {}

        # Build incident payload
        payload = {
            "short_description": short_description,
            "description": description,
            "urgency": urgency,
            "impact": impact,
            "state": "1",  # New
        }

        if category:
            payload["category"] = category
        if caller_id:
            payload["caller_id"] = caller_id
        elif config.get("caller_id"):
            payload["caller_id"] = config["caller_id"]

        if assignment_group:
            payload["assignment_group"] = assignment_group
        elif config.get("assignment_group"):
            payload["assignment_group"] = config["assignment_group"]

        # Add extra fields
        payload.update(extra_fields)

        response = await self.request(
            method="POST",
            endpoint="/api/now/table/incident",
            operation="create_incident",
            action_execution_id=action_execution_id,
            json=payload,
        )

        if response.get("error"):
            raise ValueError(f"Failed to create incident: {response.get('message')}")

        result = response.get("result", response)
        return {
            "incident_number": result.get("number"),
            "sys_id": result.get("sys_id"),
            "state": result.get("state"),
            "link": f"{self.base_url}/nav_to.do?uri=incident.do?sys_id={result.get('sys_id')}",
        }

    async def update_incident(
        self,
        sys_id: str,
        action_execution_id: Optional[UUID] = None,
        **fields,
    ) -> dict:
        """Update an existing incident.

        Args:
            sys_id: The sys_id of the incident to update.
            action_execution_id: Optional linked action execution.
            **fields: Fields to update.

        Returns:
            Updated incident data.
        """
        response = await self.request(
            method="PATCH",
            endpoint=f"/api/now/table/incident/{sys_id}",
            operation="update_incident",
            action_execution_id=action_execution_id,
            json=fields,
        )

        if response.get("error"):
            raise ValueError(f"Failed to update incident: {response.get('message')}")

        result = response.get("result", response)
        return {
            "sys_id": result.get("sys_id"),
            "number": result.get("number"),
            "state": result.get("state"),
        }

    async def get_incident(
        self,
        incident_number: Optional[str] = None,
        sys_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Get incident details.

        Args:
            incident_number: Incident number (e.g., INC0012345).
            sys_id: Incident sys_id.

        Returns:
            Incident data or None.
        """
        if sys_id:
            endpoint = f"/api/now/table/incident/{sys_id}"
        elif incident_number:
            endpoint = f"/api/now/table/incident?number={incident_number}"
        else:
            raise ValueError("Either incident_number or sys_id required")

        response = await self.request(
            method="GET",
            endpoint=endpoint,
            operation="get_incident",
        )

        if response.get("error"):
            return None

        result = response.get("result", response)
        if isinstance(result, list):
            return result[0] if result else None
        return result

    async def add_work_note(
        self,
        sys_id: str,
        work_notes: str,
        action_execution_id: Optional[UUID] = None,
    ) -> dict:
        """Add a work note to an incident.

        Args:
            sys_id: Incident sys_id.
            work_notes: Note text to add.
            action_execution_id: Optional linked action execution.

        Returns:
            Update result.
        """
        return await self.update_incident(
            sys_id=sys_id,
            action_execution_id=action_execution_id,
            work_notes=work_notes,
        )

    async def resolve_incident(
        self,
        sys_id: str,
        close_notes: str,
        close_code: str = "Solved (Permanently)",
        action_execution_id: Optional[UUID] = None,
    ) -> dict:
        """Resolve an incident.

        Args:
            sys_id: Incident sys_id.
            close_notes: Resolution notes.
            close_code: Resolution code.
            action_execution_id: Optional linked action execution.

        Returns:
            Update result.
        """
        return await self.update_incident(
            sys_id=sys_id,
            action_execution_id=action_execution_id,
            state="6",  # Resolved
            close_code=close_code,
            close_notes=close_notes,
        )
