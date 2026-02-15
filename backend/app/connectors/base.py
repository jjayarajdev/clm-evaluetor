"""Base Connector Framework.

Provides abstract base class and registry for external system connectors.
Designed to allow easy swapping between stub and real implementations.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ConnectorType(str, Enum):
    """Types of external connectors."""

    ITSM = "itsm"  # IT Service Management (ServiceNow, Jira Service Desk)
    PROJECT = "project"  # Project Management (Jira, MS Project)
    ERP = "erp"  # Enterprise Resource Planning (SAP, Oracle)
    CRM = "crm"  # Customer Relationship Management (Salesforce)
    FX = "fx"  # Foreign Exchange Rates
    HR = "hr"  # Human Resources


class DataQuality(str, Enum):
    """Quality/confidence of retrieved data."""

    HIGH = "high"  # Direct from source, recent
    MEDIUM = "medium"  # Derived or slightly stale
    LOW = "low"  # Estimated or old
    SIMULATED = "simulated"  # Stub/demo data


@dataclass
class ConnectorResult:
    """Result from a connector query."""

    success: bool
    data: Any = None
    error: str | None = None
    quality: DataQuality = DataQuality.HIGH
    retrieved_at: datetime = field(default_factory=datetime.utcnow)
    source: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class SLAActualValue:
    """Actual SLA performance value from external system."""

    sla_reference: str  # Maps to section_reference in ContractSLA
    sla_name: str
    actual_value: Decimal
    target_value: Decimal | None = None
    measurement_period_start: date | None = None
    measurement_period_end: date | None = None
    is_compliant: bool | None = None
    deviation_percentage: Decimal | None = None
    source_system: str = ""
    source_ticket_id: str | None = None
    notes: str | None = None


@dataclass
class MilestoneStatus:
    """Status of a project milestone."""

    milestone_id: str
    milestone_name: str
    planned_date: date
    actual_date: date | None = None
    status: str = "pending"  # pending, in_progress, completed, delayed, at_risk
    days_variance: int = 0  # Negative = early, Positive = late
    completion_percentage: int = 0
    dependencies: list[str] = field(default_factory=list)
    notes: str | None = None


@dataclass
class FXRate:
    """Foreign exchange rate."""

    base_currency: str
    target_currency: str
    rate: Decimal
    rate_date: date
    source: str = ""


class ConnectorBase(ABC):
    """Abstract base class for external connectors."""

    connector_type: ConnectorType
    connector_name: str
    is_stub: bool = False

    def __init__(self, config: dict | None = None):
        """Initialize connector with optional configuration.

        Args:
            config: Configuration dictionary (API keys, endpoints, etc.)
        """
        self.config = config or {}
        self._connected = False

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to external system.

        Returns:
            True if connection successful.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to external system."""
        pass

    @abstractmethod
    async def health_check(self) -> ConnectorResult:
        """Check if connector is healthy and responsive.

        Returns:
            ConnectorResult with health status.
        """
        pass

    @property
    def is_connected(self) -> bool:
        """Check if connector is currently connected."""
        return self._connected


class ITSMConnector(ConnectorBase):
    """Base class for IT Service Management connectors."""

    connector_type = ConnectorType.ITSM

    @abstractmethod
    async def get_sla_actuals(
        self,
        sla_references: list[str],
        start_date: date,
        end_date: date,
    ) -> ConnectorResult:
        """Get actual SLA performance values.

        Args:
            sla_references: List of SLA section references to query.
            start_date: Start of measurement period.
            end_date: End of measurement period.

        Returns:
            ConnectorResult with list of SLAActualValue.
        """
        pass

    @abstractmethod
    async def get_incident_metrics(
        self,
        start_date: date,
        end_date: date,
    ) -> ConnectorResult:
        """Get incident management metrics.

        Args:
            start_date: Start date.
            end_date: End date.

        Returns:
            ConnectorResult with incident metrics.
        """
        pass


class ProjectConnector(ConnectorBase):
    """Base class for Project Management connectors."""

    connector_type = ConnectorType.PROJECT

    @abstractmethod
    async def get_milestone_status(
        self,
        project_id: str | None = None,
        milestone_ids: list[str] | None = None,
    ) -> ConnectorResult:
        """Get status of project milestones.

        Args:
            project_id: Optional project ID to filter.
            milestone_ids: Optional list of specific milestones.

        Returns:
            ConnectorResult with list of MilestoneStatus.
        """
        pass


class FXConnector(ConnectorBase):
    """Base class for FX Rate connectors."""

    connector_type = ConnectorType.FX

    @abstractmethod
    async def get_rate(
        self,
        base_currency: str,
        target_currency: str,
        rate_date: date | None = None,
    ) -> ConnectorResult:
        """Get exchange rate.

        Args:
            base_currency: Base currency code (e.g., "USD").
            target_currency: Target currency code (e.g., "EUR").
            rate_date: Date for rate (None = today).

        Returns:
            ConnectorResult with FXRate.
        """
        pass

    @abstractmethod
    async def get_rates_history(
        self,
        base_currency: str,
        target_currency: str,
        start_date: date,
        end_date: date,
    ) -> ConnectorResult:
        """Get historical exchange rates.

        Args:
            base_currency: Base currency code.
            target_currency: Target currency code.
            start_date: Start date.
            end_date: End date.

        Returns:
            ConnectorResult with list of FXRate.
        """
        pass


class ConnectorRegistry:
    """Registry for managing connector instances."""

    _instance: "ConnectorRegistry | None" = None
    _connectors: dict[str, ConnectorBase]

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connectors = {}
        return cls._instance

    def register(self, name: str, connector: ConnectorBase) -> None:
        """Register a connector instance.

        Args:
            name: Unique name for the connector.
            connector: Connector instance.
        """
        self._connectors[name] = connector
        logger.info(f"Registered connector: {name} ({connector.connector_type.value})")

    def get(self, name: str) -> ConnectorBase | None:
        """Get a registered connector.

        Args:
            name: Connector name.

        Returns:
            Connector instance or None.
        """
        return self._connectors.get(name)

    def get_by_type(self, connector_type: ConnectorType) -> list[ConnectorBase]:
        """Get all connectors of a specific type.

        Args:
            connector_type: Type to filter by.

        Returns:
            List of matching connectors.
        """
        return [c for c in self._connectors.values() if c.connector_type == connector_type]

    def list_connectors(self) -> dict[str, dict]:
        """List all registered connectors with their status.

        Returns:
            Dictionary of connector info.
        """
        return {
            name: {
                "type": c.connector_type.value,
                "name": c.connector_name,
                "is_stub": c.is_stub,
                "connected": c.is_connected,
            }
            for name, c in self._connectors.items()
        }


def get_connector_registry() -> ConnectorRegistry:
    """Get the singleton connector registry."""
    return ConnectorRegistry()
