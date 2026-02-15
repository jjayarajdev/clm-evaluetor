"""KPI and Perception Scoring models for relationship governance (Evaluetor features)."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Column, DateTime, String, Text, Boolean, ForeignKey, Numeric, Integer
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM
from sqlalchemy.orm import relationship as sa_relationship

from app.database import Base


class KPIMeasurementType(str, enum.Enum):
    """Type of KPI measurement."""
    PERCENTAGE = "percentage"
    NUMBER = "number"
    CURRENCY = "currency"
    TIME_HOURS = "time_hours"
    TIME_DAYS = "time_days"
    RATING = "rating"  # 1-10 scale
    BOOLEAN = "boolean"


class KPICategory(str, enum.Enum):
    """Category of KPI."""
    SERVICE_DELIVERY = "service_delivery"
    QUALITY = "quality"
    TIMELINESS = "timeliness"
    COMMUNICATION = "communication"
    INNOVATION = "innovation"
    COST_EFFICIENCY = "cost_efficiency"
    COMPLIANCE = "compliance"
    SATISFACTION = "satisfaction"
    OTHER = "other"


class KPI(Base):
    """Key Performance Indicator for a business relationship.

    Tracks both contracted targets and perception scores from
    internal and external stakeholders.
    """

    __tablename__ = "kpis"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    relationship_id = Column(UUID(as_uuid=True), ForeignKey("business_relationships.id"), nullable=False)

    # KPI definition
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=True)  # Short code for reference
    description = Column(Text, nullable=True)
    category = Column(
        PG_ENUM('service_delivery', 'quality', 'timeliness', 'communication', 'innovation', 'cost_efficiency', 'compliance', 'satisfaction', 'other', name='kpicategory', create_type=False),
        nullable=False,
        default='other'
    )
    measurement_type = Column(
        PG_ENUM('percentage', 'number', 'currency', 'time_hours', 'time_days', 'rating', 'boolean', name='kpimeasurementtype', create_type=False),
        nullable=False,
        default='rating'
    )

    # Target values
    target_value = Column(Numeric(12, 2), nullable=True)
    minimum_value = Column(Numeric(12, 2), nullable=True)
    threshold_amber = Column(Numeric(12, 2), nullable=True)  # Warn if below
    threshold_red = Column(Numeric(12, 2), nullable=True)  # Critical if below

    # Weighting for composite scores
    weight = Column(Numeric(5, 2), nullable=True, default=1.0)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_perception_based = Column(Boolean, default=True, nullable=False)  # Uses perception scoring

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    relationship = sa_relationship("BusinessRelationship", back_populates="kpis")
    perception_scores = sa_relationship("PerceptionScore", back_populates="kpi", lazy="dynamic")
    perception_gaps = sa_relationship("PerceptionGap", back_populates="kpi", lazy="dynamic")
    improvement_points = sa_relationship("ImprovementPoint", back_populates="kpi", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<KPI {self.code or self.id}: {self.name}>"


class PerceptionScore(Base):
    """Perception score submitted for a KPI.

    Captures both internal (our view) and external (client/vendor view)
    perception of KPI performance for gap analysis.
    """

    __tablename__ = "perception_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    kpi_id = Column(UUID(as_uuid=True), ForeignKey("kpis.id"), nullable=False)

    # Who submitted the score
    scorer_org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    scored_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Score details
    score = Column(Numeric(5, 2), nullable=False)  # 1-10 rating typically
    period = Column(String(20), nullable=False)  # e.g., "2024-Q1", "2024-01"
    comments = Column(Text, nullable=True)

    # Is this internal or external perception?
    is_internal = Column(Boolean, nullable=False, default=True)

    # Timestamps
    scored_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    kpi = sa_relationship("KPI", back_populates="perception_scores")
    scorer_org = sa_relationship("Organization")
    scored_by = sa_relationship("User")

    def __repr__(self) -> str:
        return f"<PerceptionScore {self.kpi_id}: {self.score} ({self.period})>"


class GapSeverity(str, enum.Enum):
    """Severity classification of perception gaps."""
    MINOR = "minor"  # Gap < 1 point
    MODERATE = "moderate"  # Gap 1-2 points
    SIGNIFICANT = "significant"  # Gap 2-3 points
    CRITICAL = "critical"  # Gap > 3 points


class PerceptionGap(Base):
    """Calculated gap between internal and external perception scores.

    Core Evaluetor feature: identifying where internal and external
    perceptions diverge, enabling focused improvement efforts.
    """

    __tablename__ = "perception_gaps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    kpi_id = Column(UUID(as_uuid=True), ForeignKey("kpis.id"), nullable=False)

    # Period
    period = Column(String(20), nullable=False)  # e.g., "2024-Q1"

    # Scores
    internal_score = Column(Numeric(5, 2), nullable=True)
    external_score = Column(Numeric(5, 2), nullable=True)
    gap = Column(Numeric(5, 2), nullable=True)  # internal - external

    # Analysis
    gap_severity = Column(
        PG_ENUM('minor', 'moderate', 'significant', 'critical', name='gapseverity', create_type=False),
        nullable=True
    )
    requires_action = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True)

    # Timestamps
    calculated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    kpi = sa_relationship("KPI", back_populates="perception_gaps")
    improvement_points = sa_relationship("ImprovementPoint", back_populates="gap", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<PerceptionGap {self.kpi_id}: {self.gap} ({self.period})>"

    @classmethod
    def calculate_severity(cls, gap: Decimal) -> str:
        """Calculate gap severity based on gap value."""
        abs_gap = abs(gap) if gap else 0
        if abs_gap < 1:
            return "minor"
        elif abs_gap < 2:
            return "moderate"
        elif abs_gap < 3:
            return "significant"
        else:
            return "critical"
