"""Master Data models for SLA and Milestone configurations."""

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class SLAMasterData(Base, UUIDMixin, TimestampMixin):
    """Master data configuration for SLAs.

    This replaces the hardcoded SLA_CONFIGURATIONS in servicenow_stub.py.
    Provides database-backed SLA reference data that can be managed via admin UI.
    """

    __tablename__ = "sla_master_data"

    # SLA identification
    reference_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )  # e.g., "12.1", "2.1.1"

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Target and threshold values
    target_value: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
    )  # e.g., 0.54, 0.99

    minimum_value: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
    )  # Floor/breach threshold

    typical_performance: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
    )  # Expected typical performance

    volatility: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4),
        nullable=True,
    )  # Expected variance

    # Categorization
    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )  # e.g., "Critical Service Levels", "Key Measurements"

    service_tower: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )  # e.g., "Desktop Services", "Network Services"

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    __table_args__ = (
        Index("ix_sla_master_category_tower", "category", "service_tower"),
    )

    def __repr__(self) -> str:
        return f"<SLAMasterData {self.reference_code}: {self.name}>"

    def to_config_dict(self) -> dict:
        """Convert to dict format compatible with connector stubs."""
        return {
            "name": self.name,
            "target": self.target_value,
            "minimum": self.minimum_value,
            "typical_performance": self.typical_performance,
            "volatility": self.volatility,
        }


class MilestoneMasterData(Base, UUIDMixin, TimestampMixin):
    """Master data configuration for project milestones.

    This replaces the hardcoded MILESTONE_CONFIGURATIONS in milestone_stub.py.
    Provides database-backed milestone reference data that can be managed via admin UI.
    """

    __tablename__ = "milestone_master_data"

    # Milestone identification
    milestone_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )  # e.g., "MS-2.1", "MS-4.3"

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Timeline
    baseline_days_from_start: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )  # Days from project start

    # Dependencies (list of milestone codes)
    dependencies: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )  # e.g., ["MS-2.1", "MS-3.1"]

    # Financial
    credit_at_risk: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )  # Service credit at risk for this milestone

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<MilestoneMasterData {self.milestone_code}: {self.name}>"

    def to_config_dict(self) -> dict:
        """Convert to dict format compatible with connector stubs."""
        return {
            "name": self.name,
            "description": self.description,
            "baseline_days_from_start": self.baseline_days_from_start,
            "dependencies": self.dependencies or [],
            "credit_at_risk": self.credit_at_risk,
        }
