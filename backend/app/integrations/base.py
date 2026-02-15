"""Base integration client with common functionality.

All external integration clients inherit from this base class.
Provides common features like logging, retry, health checks.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import IntegrationConfig, IntegrationLog, IntegrationStatus

logger = logging.getLogger(__name__)


class BaseIntegrationClient(ABC):
    """Abstract base class for integration clients.

    Provides common functionality for all external system integrations:
    - Authentication management
    - Request logging
    - Error handling and retry
    - Health monitoring
    """

    def __init__(
        self,
        config: IntegrationConfig,
        db: AsyncSession,
    ):
        """Initialize the client.

        Args:
            config: Integration configuration from database.
            db: Database session for logging.
        """
        self.config = config
        self.db = db
        self.base_url = config.base_url.rstrip("/")
        self._http_client: Optional[httpx.AsyncClient] = None

    @property
    def system_name(self) -> str:
        """Return the integration system name."""
        return self.config.system.value

    async def __aenter__(self):
        """Async context manager entry."""
        self._http_client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._http_client:
            await self._http_client.aclose()

    @abstractmethod
    async def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for requests.

        Subclasses must implement based on auth type.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the integration is healthy.

        Returns:
            True if healthy, False otherwise.
        """
        pass

    async def request(
        self,
        method: str,
        endpoint: str,
        operation: str,
        action_execution_id: Optional[UUID] = None,
        **kwargs,
    ) -> dict:
        """Make an authenticated request to the external system.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            endpoint: API endpoint (appended to base_url).
            operation: Description of the operation for logging.
            action_execution_id: Optional linked action execution.
            **kwargs: Additional httpx request arguments.

        Returns:
            Response JSON or error dict.
        """
        if not self._http_client:
            raise RuntimeError("Client not initialized. Use async with statement.")

        # Start timing
        started_at = datetime.utcnow()

        # Create log entry
        log = IntegrationLog(
            integration_id=self.config.id,
            action_execution_id=action_execution_id,
            operation=operation,
            method=method.upper(),
            endpoint=endpoint,
            request_payload=self._sanitize_payload(kwargs.get("json", kwargs.get("data"))),
            started_at=started_at,
        )
        self.db.add(log)
        await self.db.flush()

        try:
            # Get auth headers
            headers = await self._get_auth_headers()
            if "headers" in kwargs:
                headers.update(kwargs.pop("headers"))

            # Make request
            response = await self._http_client.request(
                method=method,
                url=endpoint,
                headers=headers,
                **kwargs,
            )

            # Log response
            completed_at = datetime.utcnow()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            log.status_code = response.status_code
            log.completed_at = completed_at
            log.duration_ms = duration_ms

            if response.is_success:
                log.is_success = True
                response_json = response.json() if response.content else {}
                log.response_payload = self._sanitize_payload(response_json)

                # Extract external ID if present
                log.external_id = self._extract_external_id(response_json)

                # Update integration stats
                await self._update_stats(success=True)

                await self.db.commit()
                return response_json
            else:
                log.is_success = False
                log.error_message = f"HTTP {response.status_code}: {response.text[:500]}"

                await self._update_stats(success=False)
                await self.db.commit()

                return {
                    "error": True,
                    "status_code": response.status_code,
                    "message": response.text[:500],
                }

        except httpx.TimeoutException as e:
            log.is_success = False
            log.error_message = f"Timeout: {str(e)}"
            log.completed_at = datetime.utcnow()
            await self._update_stats(success=False)
            await self.db.commit()
            raise

        except httpx.RequestError as e:
            log.is_success = False
            log.error_message = f"Request error: {str(e)}"
            log.completed_at = datetime.utcnow()
            await self._update_stats(success=False)
            await self.db.commit()
            raise

        except Exception as e:
            log.is_success = False
            log.error_message = str(e)[:500]
            log.completed_at = datetime.utcnow()
            await self._update_stats(success=False)
            await self.db.commit()
            raise

    async def _update_stats(self, success: bool) -> None:
        """Update integration statistics."""
        self.config.total_requests += 1
        if not success:
            self.config.failed_requests += 1
        self.config.last_used_at = datetime.utcnow()

    def _sanitize_payload(self, payload: Any) -> Optional[dict]:
        """Remove sensitive data from payload for logging."""
        if payload is None:
            return None

        if isinstance(payload, dict):
            sanitized = {}
            sensitive_keys = {"password", "secret", "token", "api_key", "authorization", "credential"}

            for key, value in payload.items():
                key_lower = key.lower()
                if any(s in key_lower for s in sensitive_keys):
                    sanitized[key] = "***REDACTED***"
                elif isinstance(value, dict):
                    sanitized[key] = self._sanitize_payload(value)
                else:
                    sanitized[key] = value

            return sanitized

        return {"raw": str(payload)[:1000]}

    def _extract_external_id(self, response: dict) -> Optional[str]:
        """Extract external ID from response.

        Subclasses can override for specific ID extraction.
        """
        # Common patterns
        for key in ["sys_id", "id", "number", "Id", "ID"]:
            if key in response:
                return str(response[key])

        # Nested result
        if "result" in response and isinstance(response["result"], dict):
            for key in ["sys_id", "id", "number"]:
                if key in response["result"]:
                    return str(response["result"][key])

        return None


class MockIntegrationClient(BaseIntegrationClient):
    """Mock integration client for testing.

    Returns simulated responses without making real API calls.
    """

    def __init__(self, config: IntegrationConfig, db: AsyncSession):
        super().__init__(config, db)
        self._mock_responses: dict = {}

    async def _get_auth_headers(self) -> dict[str, str]:
        return {"Authorization": "Bearer mock-token"}

    async def health_check(self) -> bool:
        return True

    def set_mock_response(self, operation: str, response: dict) -> None:
        """Set a mock response for an operation."""
        self._mock_responses[operation] = response

    async def request(
        self,
        method: str,
        endpoint: str,
        operation: str,
        action_execution_id: Optional[UUID] = None,
        **kwargs,
    ) -> dict:
        """Return mock response instead of making real request."""
        logger.info(f"[MOCK] {method} {endpoint} - {operation}")

        if operation in self._mock_responses:
            return self._mock_responses[operation]

        # Default mock response based on operation
        import random
        if "create" in operation.lower():
            return {
                "sys_id": f"mock-{random.randint(1000000, 9999999)}",
                "number": f"MOCK{random.randint(1000000, 9999999)}",
                "status": "created",
            }
        elif "update" in operation.lower():
            return {
                "sys_id": "mock-updated",
                "status": "updated",
            }
        else:
            return {"status": "success"}
