"""Integration models for external systems (ServiceNow, Salesforce, etc.)."""

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class IntegrationSystem(str, enum.Enum):
    """Supported external systems."""

    servicenow = "servicenow"
    salesforce = "salesforce"
    sendgrid = "sendgrid"
    smtp = "smtp"
    slack = "slack"
    teams = "teams"
    webhook = "webhook"


class IntegrationStatus(str, enum.Enum):
    """Health status of an integration."""

    healthy = "healthy"
    degraded = "degraded"
    unhealthy = "unhealthy"
    unknown = "unknown"


class IntegrationConfig(Base, TimestampMixin):
    """Configuration for external system integrations.

    Stores connection details and credentials for external systems.
    Credentials should be encrypted at rest.
    """

    __tablename__ = "integration_configs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Tenant association (nullable for legacy/global configs)
    tenant_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("tenants.id"), nullable=True, index=True
    )

    # Integration identification
    system: Mapped[IntegrationSystem] = mapped_column(
        Enum(IntegrationSystem), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Connection details
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    # Example: "https://dev12345.service-now.com"

    # Authentication (encrypted in DB, decrypt at runtime)
    auth_type: Mapped[str] = mapped_column(String(50), default="oauth2")
    # Options: "oauth2", "basic", "api_key", "bearer"

    credentials: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Encrypted JSON with auth details
    # OAuth2: {"client_id": "...", "client_secret": "...", "token_url": "..."}
    # Basic: {"username": "...", "password": "..."}
    # API Key: {"api_key": "...", "header_name": "X-API-Key"}

    # Additional configuration
    config: Mapped[Optional[dict]] = mapped_column(JSONB)
    # System-specific settings
    # SNOW: {"api_version": "v2", "assignment_group": "..."}
    # SFDC: {"api_version": "v58.0", "sandbox": true}

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    # Only one default per system type
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    # True for auto-provisioned mock data; False for real integrations

    # Health monitoring
    health_status: Mapped[IntegrationStatus] = mapped_column(
        Enum(IntegrationStatus), default=IntegrationStatus.unknown
    )
    last_health_check: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    last_health_message: Mapped[Optional[str]] = mapped_column(Text)

    # Usage tracking
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    failed_requests: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<IntegrationConfig {self.system.value}: {self.name}>"

    @property
    def success_rate(self) -> float:
        """Calculate success rate of requests."""
        if self.total_requests == 0:
            return 100.0
        return ((self.total_requests - self.failed_requests) / self.total_requests) * 100


class IntegrationLog(Base, TimestampMixin):
    """Log of API calls to external systems.

    Every external API call is logged for debugging and auditing.
    """

    __tablename__ = "integration_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Related entities
    integration_id: Mapped[UUID] = mapped_column(
        ForeignKey("integration_configs.id", ondelete="CASCADE"), nullable=False
    )
    action_execution_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("action_executions.id", ondelete="SET NULL"), nullable=True
    )

    # Request details
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    # Example: "create_incident", "update_account", "send_email"

    method: Mapped[str] = mapped_column(String(10), nullable=False)
    # HTTP method: GET, POST, PUT, PATCH, DELETE

    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    # Example: "/api/now/table/incident"

    request_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Sanitized request body (no secrets)

    # Response details
    status_code: Mapped[Optional[int]] = mapped_column(Integer)
    response_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    # Sanitized response body

    # External reference
    external_id: Mapped[Optional[str]] = mapped_column(String(200))
    # ID of created/updated record in external system
    # Example: "INC0012345" for ServiceNow incident

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)

    # Status
    is_success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    integration: Mapped["IntegrationConfig"] = relationship("IntegrationConfig")

    def __repr__(self) -> str:
        status = "OK" if self.is_success else "FAIL"
        return f"<IntegrationLog {self.operation} [{status}]>"


class SLAMeasurement(Base, TimestampMixin):
    """Synthetic or imported SLA performance measurements.

    This table stores SLA performance data that can be:
    - Synthetically generated for testing
    - Imported from external monitoring systems
    - Manually entered
    """

    __tablename__ = "sla_measurements"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    sla_id: Mapped[UUID] = mapped_column(
        ForeignKey("contract_slas.id", ondelete="CASCADE"), nullable=False
    )

    # Measurement details
    measurement_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Values
    actual_value: Mapped[float] = mapped_column(nullable=False)
    target_value: Mapped[float] = mapped_column(nullable=False)

    # Calculated fields
    is_breach: Mapped[bool] = mapped_column(Boolean, default=False)
    deviation_percent: Mapped[Optional[float]] = mapped_column()
    # (target - actual) / target * 100

    # Source tracking
    source: Mapped[str] = mapped_column(String(50), default="synthetic")
    # Options: "synthetic", "servicenow", "manual", "api"
    source_reference: Mapped[Optional[str]] = mapped_column(String(200))
    # External reference ID if imported

    # Event generation
    event_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    event_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    sla: Mapped["ContractSLA"] = relationship("ContractSLA")

    def __repr__(self) -> str:
        status = "BREACH" if self.is_breach else "OK"
        return f"<SLAMeasurement {self.actual_value}/{self.target_value} [{status}]>"

    def calculate_deviation(self) -> float:
        """Calculate deviation percentage from target."""
        if self.target_value == 0:
            return 0.0
        return ((self.target_value - self.actual_value) / self.target_value) * 100
