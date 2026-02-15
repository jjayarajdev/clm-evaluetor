"""Improvement Point models for relationship governance (Evaluetor features)."""

import enum
import uuid
from datetime import datetime, date

from sqlalchemy import Column, DateTime, Date, String, Text, Enum, Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship as sa_relationship

from app.database import Base


class ImprovementPriority(str, enum.Enum):
    """Priority level for improvement points."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ImprovementStatus(str, enum.Enum):
    """Status of an improvement point."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ImprovementSource(str, enum.Enum):
    """How the improvement point was identified."""
    PERCEPTION_GAP = "perception_gap"
    SLA_BREACH = "sla_breach"
    REVIEW_MEETING = "review_meeting"
    CUSTOMER_FEEDBACK = "customer_feedback"
    INTERNAL_AUDIT = "internal_audit"
    MANUAL = "manual"


class ImprovementPoint(Base):
    """Improvement point for addressing gaps or issues in a relationship.

    Core Evaluetor feature: tracking improvement initiatives tied to
    KPI gaps, with action items and progress tracking.
    """

    __tablename__ = "improvement_points"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    relationship_id = Column(UUID(as_uuid=True), ForeignKey("business_relationships.id"), nullable=False)

    # Optional links to KPI/Gap that triggered this improvement
    kpi_id = Column(UUID(as_uuid=True), ForeignKey("kpis.id"), nullable=True)
    gap_id = Column(UUID(as_uuid=True), ForeignKey("perception_gaps.id"), nullable=True)

    # Improvement details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source = Column(Enum(ImprovementSource), nullable=False, default=ImprovementSource.MANUAL)
    priority = Column(Enum(ImprovementPriority), nullable=False, default=ImprovementPriority.MEDIUM)
    status = Column(Enum(ImprovementStatus), nullable=False, default=ImprovementStatus.OPEN)

    # Assignment
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    assigned_org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)

    # Timeline
    due_date = Column(Date, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Impact tracking
    target_outcome = Column(Text, nullable=True)  # What we expect to achieve
    actual_outcome = Column(Text, nullable=True)  # What was actually achieved
    impact_score = Column(Integer, nullable=True)  # 1-10 impact rating

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    relationship = sa_relationship("BusinessRelationship", back_populates="improvement_points")
    kpi = sa_relationship("KPI", back_populates="improvement_points")
    gap = sa_relationship("PerceptionGap", back_populates="improvement_points")
    owner = sa_relationship("User", foreign_keys=[owner_id])
    assigned_org = sa_relationship("Organization")
    actions = sa_relationship("ImprovementAction", back_populates="improvement_point", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<ImprovementPoint {self.id}: {self.title[:30]}>"

    @property
    def progress_percentage(self) -> int:
        """Calculate progress based on completed actions."""
        total = self.actions.count()
        if total == 0:
            return 0
        completed = self.actions.filter(
            ImprovementAction.status == ActionStatus.COMPLETED
        ).count()
        return int((completed / total) * 100)


class ActionStatus(str, enum.Enum):
    """Status of an improvement action."""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class ImprovementAction(Base):
    """Action item within an improvement point."""

    __tablename__ = "improvement_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    improvement_id = Column(UUID(as_uuid=True), ForeignKey("improvement_points.id"), nullable=False)

    # Action details
    description = Column(Text, nullable=False)
    status = Column(Enum(ActionStatus), nullable=False, default=ActionStatus.TODO)
    sequence = Column(Integer, nullable=True)  # Order of execution

    # Assignment
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    # Timeline
    due_date = Column(Date, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Notes
    notes = Column(Text, nullable=True)
    blocker_reason = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    improvement_point = sa_relationship("ImprovementPoint", back_populates="actions")
    owner = sa_relationship("User")

    def __repr__(self) -> str:
        return f"<ImprovementAction {self.id}: {self.description[:30]}>"
