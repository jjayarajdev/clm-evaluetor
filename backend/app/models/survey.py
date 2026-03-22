"""Survey models for multi-party satisfaction surveys (Evaluetor features)."""

import enum
import uuid
from datetime import datetime, date

from sqlalchemy import Column, DateTime, Date, String, Text, Enum, Boolean, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM
from sqlalchemy.orm import relationship as sa_relationship

from app.database import Base


class SurveyFrequency(str, enum.Enum):
    """How often surveys should be sent."""
    ONE_TIME = "one_time"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"


class QuestionType(str, enum.Enum):
    """Type of survey question."""
    RATING = "rating"  # 1-10 scale
    RATING_5 = "rating_5"  # 1-5 stars
    MULTIPLE_CHOICE = "multiple_choice"
    SINGLE_CHOICE = "single_choice"
    TEXT = "text"
    TEXT_LONG = "text_long"
    YES_NO = "yes_no"
    NPS = "nps"  # Net Promoter Score (0-10)


class SurveyTemplate(Base):
    """Template for satisfaction surveys."""

    __tablename__ = "survey_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Template info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    frequency = Column(
        PG_ENUM(*[e.value for e in SurveyFrequency], name='surveyfrequency', create_type=False),
        nullable=False, default=SurveyFrequency.QUARTERLY.value
    )

    # Configuration
    introduction_text = Column(Text, nullable=True)  # Text shown at start
    closing_text = Column(Text, nullable=True)  # Thank you text
    allow_anonymous = Column(Boolean, default=False, nullable=False)
    require_all_questions = Column(Boolean, default=True, nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    version = Column(Integer, default=1, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    questions = sa_relationship("SurveyQuestion", back_populates="template", lazy="dynamic", order_by="SurveyQuestion.sequence")
    instances = sa_relationship("SurveyInstance", back_populates="template", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<SurveyTemplate {self.id}: {self.name}>"


class SurveyQuestion(Base):
    """Question within a survey template."""

    __tablename__ = "survey_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    template_id = Column(UUID(as_uuid=True), ForeignKey("survey_templates.id"), nullable=False)

    # Question content
    text = Column(Text, nullable=False)
    help_text = Column(Text, nullable=True)
    question_type = Column(
        PG_ENUM(*[e.value for e in QuestionType], name='questiontype', create_type=False),
        nullable=False, default=QuestionType.RATING.value
    )

    # For multiple choice questions
    options = Column(JSON, nullable=True)  # List of option strings

    # For rating questions
    rating_min_label = Column(String(100), nullable=True)  # e.g., "Poor"
    rating_max_label = Column(String(100), nullable=True)  # e.g., "Excellent"

    # Optional link to KPI
    kpi_id = Column(UUID(as_uuid=True), ForeignKey("kpis.id"), nullable=True)

    # Ordering and validation
    sequence = Column(Integer, nullable=False, default=0)
    is_required = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    template = sa_relationship("SurveyTemplate", back_populates="questions")
    kpi = sa_relationship("KPI")

    def __repr__(self) -> str:
        return f"<SurveyQuestion {self.id}: {self.text[:30]}>"


class SurveyStatus(str, enum.Enum):
    """Status of a survey instance."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENT = "sent"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class SurveyInstance(Base):
    """Instance of a survey sent to a relationship."""

    __tablename__ = "survey_instances"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    template_id = Column(UUID(as_uuid=True), ForeignKey("survey_templates.id"), nullable=False)
    relationship_id = Column(UUID(as_uuid=True), ForeignKey("business_relationships.id"), nullable=False)

    # Period and timing
    period = Column(String(20), nullable=False)  # e.g., "2024-Q1"
    status = Column(
        PG_ENUM(*[e.value for e in SurveyStatus], name='surveystatus', create_type=False),
        nullable=False, default=SurveyStatus.DRAFT.value
    )

    # Scheduling
    scheduled_send_date = Column(Date, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    due_date = Column(Date, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Recipients
    target_respondent_count = Column(Integer, nullable=True)
    actual_respondent_count = Column(Integer, default=0, nullable=False)

    # Notes
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    template = sa_relationship("SurveyTemplate", back_populates="instances")
    relationship = sa_relationship("BusinessRelationship", back_populates="survey_instances")
    responses = sa_relationship("SurveyResponse", back_populates="survey_instance", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<SurveyInstance {self.id}: {self.period}>"

    @property
    def response_rate(self) -> float:
        """Calculate response rate as percentage."""
        if not self.target_respondent_count or self.target_respondent_count == 0:
            return 0.0
        return (self.actual_respondent_count / self.target_respondent_count) * 100


class SurveyResponse(Base):
    """Response to a survey from a respondent."""

    __tablename__ = "survey_responses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    survey_instance_id = Column(UUID(as_uuid=True), ForeignKey("survey_instances.id"), nullable=False)

    # Respondent info
    respondent_email = Column(String(255), nullable=True)
    respondent_name = Column(String(255), nullable=True)
    respondent_org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    is_anonymous = Column(Boolean, default=False, nullable=False)

    # Response data
    answers = Column(JSON, nullable=False)  # {question_id: answer_value}
    completion_time_seconds = Column(Integer, nullable=True)

    # Status
    is_complete = Column(Boolean, default=False, nullable=False)
    submitted_at = Column(DateTime, nullable=True)

    # Access tracking
    access_token = Column(String(100), nullable=True, unique=True)
    first_accessed_at = Column(DateTime, nullable=True)
    last_accessed_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    survey_instance = sa_relationship("SurveyInstance", back_populates="responses")
    respondent_org = sa_relationship("Organization")

    def __repr__(self) -> str:
        return f"<SurveyResponse {self.id}: {self.respondent_email or 'anonymous'}>"
