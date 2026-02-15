"""Salesforce integration client.

Updates Accounts and creates Tasks in Salesforce.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional
from uuid import UUID

from app.integrations.base import BaseIntegrationClient
from app.models.integration import IntegrationConfig

logger = logging.getLogger(__name__)


class SalesforceClient(BaseIntegrationClient):
    """Client for Salesforce REST API.

    Supports:
    - Account updates
    - Task creation
    - Health checks
    """

    def __init__(self, config: IntegrationConfig, db):
        super().__init__(config, db)
        self._access_token: Optional[str] = None
        self._instance_url: Optional[str] = None

    @property
    def api_version(self) -> str:
        """Get Salesforce API version."""
        config = self.config.config or {}
        return config.get("api_version", "v58.0")

    async def _get_auth_headers(self) -> dict[str, str]:
        """Get OAuth2 authentication headers."""
        if not self._access_token:
            await self._authenticate()

        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    async def _authenticate(self) -> None:
        """Authenticate with Salesforce OAuth2.

        In production, this would handle the OAuth2 flow.
        For now, uses credentials from config.
        """
        credentials = self.config.credentials or {}

        if "access_token" in credentials:
            # Use stored token
            self._access_token = credentials["access_token"]
            self._instance_url = credentials.get("instance_url", self.base_url)
        else:
            # Would implement OAuth2 password grant or JWT flow
            logger.warning("Salesforce OAuth2 not fully implemented, using mock token")
            self._access_token = "mock-access-token"
            self._instance_url = self.base_url

    async def health_check(self) -> bool:
        """Check Salesforce connectivity."""
        try:
            response = await self.request(
                method="GET",
                endpoint=f"/services/data/{self.api_version}/limits",
                operation="health_check",
            )
            return not response.get("error", False)
        except Exception as e:
            logger.error(f"Salesforce health check failed: {e}")
            return False

    async def update_account(
        self,
        account_id: str,
        action_execution_id: Optional[UUID] = None,
        **fields,
    ) -> dict:
        """Update a Salesforce Account.

        Args:
            account_id: Salesforce Account ID.
            action_execution_id: Optional linked action execution.
            **fields: Fields to update on the Account.

        Returns:
            Update result.
        """
        response = await self.request(
            method="PATCH",
            endpoint=f"/services/data/{self.api_version}/sobjects/Account/{account_id}",
            operation="update_account",
            action_execution_id=action_execution_id,
            json=fields,
        )

        if response.get("error"):
            raise ValueError(f"Failed to update account: {response.get('message')}")

        return {
            "account_id": account_id,
            "updated_fields": list(fields.keys()),
            "status": "updated",
        }

    async def get_account(self, account_id: str) -> Optional[dict]:
        """Get Account details.

        Args:
            account_id: Salesforce Account ID.

        Returns:
            Account data or None.
        """
        response = await self.request(
            method="GET",
            endpoint=f"/services/data/{self.api_version}/sobjects/Account/{account_id}",
            operation="get_account",
        )

        if response.get("error"):
            return None

        return response

    async def find_account_by_name(self, name: str) -> Optional[dict]:
        """Find Account by name.

        Args:
            name: Account name to search for.

        Returns:
            Account data or None.
        """
        query = f"SELECT Id, Name, Contract_Health__c FROM Account WHERE Name = '{name}'"
        response = await self.request(
            method="GET",
            endpoint=f"/services/data/{self.api_version}/query?q={query}",
            operation="find_account",
        )

        if response.get("error") or not response.get("records"):
            return None

        return response["records"][0]

    async def create_task(
        self,
        subject: str,
        what_id: Optional[str] = None,
        who_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        due_date: Optional[date] = None,
        priority: str = "Normal",
        status: str = "Not Started",
        description: str = "",
        action_execution_id: Optional[UUID] = None,
    ) -> dict:
        """Create a Task in Salesforce.

        Args:
            subject: Task subject.
            what_id: Related record ID (Account, Opportunity, etc.).
            who_id: Contact or Lead ID.
            owner_id: Task owner ID.
            due_date: Task due date.
            priority: High, Normal, or Low.
            status: Not Started, In Progress, Completed, etc.
            description: Task description.
            action_execution_id: Optional linked action execution.

        Returns:
            Created task details.
        """
        payload = {
            "Subject": subject,
            "Priority": priority,
            "Status": status,
        }

        if what_id:
            payload["WhatId"] = what_id
        if who_id:
            payload["WhoId"] = who_id
        if owner_id:
            payload["OwnerId"] = owner_id
        if due_date:
            payload["ActivityDate"] = due_date.isoformat()
        if description:
            payload["Description"] = description

        response = await self.request(
            method="POST",
            endpoint=f"/services/data/{self.api_version}/sobjects/Task",
            operation="create_task",
            action_execution_id=action_execution_id,
            json=payload,
        )

        if response.get("error"):
            raise ValueError(f"Failed to create task: {response.get('message')}")

        return {
            "task_id": response.get("id"),
            "subject": subject,
            "due_date": due_date.isoformat() if due_date else None,
            "status": "created",
        }

    async def update_task(
        self,
        task_id: str,
        action_execution_id: Optional[UUID] = None,
        **fields,
    ) -> dict:
        """Update a Task.

        Args:
            task_id: Salesforce Task ID.
            action_execution_id: Optional linked action execution.
            **fields: Fields to update.

        Returns:
            Update result.
        """
        response = await self.request(
            method="PATCH",
            endpoint=f"/services/data/{self.api_version}/sobjects/Task/{task_id}",
            operation="update_task",
            action_execution_id=action_execution_id,
            json=fields,
        )

        if response.get("error"):
            raise ValueError(f"Failed to update task: {response.get('message')}")

        return {
            "task_id": task_id,
            "updated_fields": list(fields.keys()),
            "status": "updated",
        }

    async def complete_task(
        self,
        task_id: str,
        action_execution_id: Optional[UUID] = None,
    ) -> dict:
        """Mark a Task as completed.

        Args:
            task_id: Salesforce Task ID.
            action_execution_id: Optional linked action execution.

        Returns:
            Update result.
        """
        return await self.update_task(
            task_id=task_id,
            action_execution_id=action_execution_id,
            Status="Completed",
        )

    async def create_contract_review_task(
        self,
        account_id: str,
        contract_name: str,
        review_type: str = "Renewal",
        due_days: int = 14,
        action_execution_id: Optional[UUID] = None,
    ) -> dict:
        """Create a contract review task.

        Convenience method for common contract-related tasks.

        Args:
            account_id: Account ID.
            contract_name: Contract name for subject.
            review_type: Type of review (Renewal, Performance, etc.).
            due_days: Days until due.
            action_execution_id: Optional linked action execution.

        Returns:
            Created task details.
        """
        due_date = datetime.utcnow().date() + timedelta(days=due_days)

        return await self.create_task(
            subject=f"{review_type} Review: {contract_name}",
            what_id=account_id,
            due_date=due_date,
            priority="High",
            description=f"Review contract '{contract_name}' for upcoming {review_type.lower()}. "
                       f"Take necessary action before due date.",
            action_execution_id=action_execution_id,
        )
