"""Relationship Performance Status History model for tracking status changes over time."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM
from sqlalchemy.orm import relationship as sa_relationship

from app.database import Base


class PerformanceStatus(str, enum.Enum):
    """Performance status classification for a business relationship."""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    CONCERNING = "concerning"
    POOR = "poor"
    CRITICAL = "critical"


class RelationshipStatusHistory(Base):
    """Historical record of relationship performance status changes.

    Tracks how a business relationship's performance status evolves over time,
    including the composite score, what triggered the change, and who recorded it.
    """

    __tablename__ = "relationship_status_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Tenant (multi-tenancy)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)

    # Which relationship
    relationship_id = Column(UUID(as_uuid=True), ForeignKey("business_relationships.id"), nullable=False, index=True)

    # Status values
    status = Column(
        PG_ENUM('excellent', 'good', 'acceptable', 'concerning', 'poor', 'critical', name='performancestatus', create_type=False),
        nullable=False
    )
    previous_status = Column(
        PG_ENUM('excellent', 'good', 'acceptable', 'concerning', 'poor', 'critical', name='performancestatus', create_type=False),
        nullable=True
    )

    # Composite score (0-100)
    overall_score = Column(Numeric(5, 2), nullable=True)

    # Period identifier (e.g., "2024-Q1")
    period = Column(String(20), nullable=False)

    # When this status was recorded
    recorded_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Who recorded it
    recorded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Notes / context
    notes = Column(Text, nullable=True)

    # What triggered this entry (e.g., "kpi_evaluation_cycle", "manual", "health_score_recalc")
    trigger = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    relationship = sa_relationship("BusinessRelationship", back_populates="status_history")
    recorded_by_user = sa_relationship("User")

    def __repr__(self) -> str:
        return f"<RelationshipStatusHistory {self.relationship_id}: {self.status} ({self.period})>"
