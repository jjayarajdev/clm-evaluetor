"""ServiceNow SLA mapping model for linking SNOW SLA definitions to platform SLAs."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class SnowSLAMapping(Base, TimestampMixin):
    """Maps a ServiceNow SLA definition to a platform ContractSLA.

    Each record represents a discovered SLA from ServiceNow and tracks
    its mapping status to platform SLAs (pending, mapped, ignored, error).
    """

    __tablename__ = "snow_sla_mappings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Tenant association
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )

    # Link to the ServiceNow integration config
    integration_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("integration_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ServiceNow SLA definition identifiers
    snow_sys_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    snow_sla_name: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    snow_metric_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    snow_target: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # Platform SLA link (nullable until mapped)
    platform_sla_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contract_slas.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Mapping status: pending, mapped, ignored, error
    mapping_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )

    # Sync tracking
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    sync_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    integration_config: Mapped["IntegrationConfig"] = relationship(
        "IntegrationConfig",
        lazy="selectin",
    )
    platform_sla: Mapped[Optional["ContractSLA"]] = relationship(
        "ContractSLA",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "integration_config_id", "snow_sys_id",
            name="uq_snow_sla_mapping_config_sysid",
        ),
    )

    def __repr__(self) -> str:
        return f"<SnowSLAMapping {self.snow_sla_name} [{self.mapping_status}]>"
