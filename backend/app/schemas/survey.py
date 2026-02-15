"""Pydantic schemas for Survey endpoints."""

from datetime import datetime, date
from uuid import UUID
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, EmailStr

from app.models.survey import SurveyFrequency, SurveyStatus, QuestionType


# ===== Question Schemas =====

class QuestionBase(BaseModel):
    """Base question schema."""
    text: str = Field(..., min_length=1)
    help_text: Optional[str] = None
    question_type: QuestionType = QuestionType.RATING
    options: Optional[List[str]] = None  # For multiple choice
    rating_min_label: Optional[str] = Field(None, max_length=100)
    rating_max_label: Optional[str] = Field(None, max_length=100)
    kpi_id: Optional[UUID] = None
    sequence: int = 0
    is_required: bool = True


class QuestionCreate(QuestionBase):
    """Schema for creating a question."""
    pass


class QuestionUpdate(BaseModel):
    """Schema for updating a question."""
    text: Optional[str] = Field(None, min_length=1)
    help_text: Optional[str] = None
    question_type: Optional[QuestionType] = None
    options: Optional[List[str]] = None
    rating_min_label: Optional[str] = Field(None, max_length=100)
    rating_max_label: Optional[str] = Field(None, max_length=100)
    kpi_id: Optional[UUID] = None
    sequence: Optional[int] = None
    is_required: Optional[bool] = None
    is_active: Optional[bool] = None


class QuestionResponse(QuestionBase):
    """Schema for question response."""
    id: UUID
    template_id: UUID
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Template Schemas =====

class TemplateBase(BaseModel):
    """Base template schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    frequency: SurveyFrequency = SurveyFrequency.QUARTERLY
    introduction_text: Optional[str] = None
    closing_text: Optional[str] = None
    allow_anonymous: bool = False
    require_all_questions: bool = True


class TemplateCreate(TemplateBase):
    """Schema for creating a template."""
    questions: Optional[List[QuestionCreate]] = None


class TemplateUpdate(BaseModel):
    """Schema for updating a template."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    frequency: Optional[SurveyFrequency] = None
    introduction_text: Optional[str] = None
    closing_text: Optional[str] = None
    allow_anonymous: Optional[bool] = None
    require_all_questions: Optional[bool] = None
    is_active: Optional[bool] = None


class TemplateResponse(TemplateBase):
    """Schema for template response."""
    id: UUID
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime

    questions: Optional[List[QuestionResponse]] = None
    question_count: Optional[int] = None

    class Config:
        from_attributes = True


class TemplateListResponse(BaseModel):
    """Schema for template list."""
    items: List[TemplateResponse]
    total: int


# ===== Instance Schemas =====

class InstanceCreate(BaseModel):
    """Schema for creating a survey instance."""
    template_id: UUID
    relationship_id: UUID
    period: str = Field(..., min_length=1, max_length=20)
    scheduled_send_date: Optional[date] = None
    due_date: Optional[date] = None
    target_respondent_count: Optional[int] = None
    notes: Optional[str] = None


class InstanceUpdate(BaseModel):
    """Schema for updating a survey instance."""
    status: Optional[SurveyStatus] = None
    scheduled_send_date: Optional[date] = None
    due_date: Optional[date] = None
    target_respondent_count: Optional[int] = None
    notes: Optional[str] = None


class InstanceResponse(BaseModel):
    """Schema for instance response."""
    id: UUID
    template_id: UUID
    relationship_id: UUID
    period: str
    status: SurveyStatus
    scheduled_send_date: Optional[date] = None
    sent_at: Optional[datetime] = None
    due_date: Optional[date] = None
    closed_at: Optional[datetime] = None
    target_respondent_count: Optional[int] = None
    actual_respondent_count: int
    response_rate: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Populated from joins
    template_name: Optional[str] = None
    relationship_name: Optional[str] = None

    class Config:
        from_attributes = True


class InstanceListResponse(BaseModel):
    """Schema for instance list."""
    items: List[InstanceResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ===== Response Schemas =====

class SurveyAnswers(BaseModel):
    """Schema for survey answers."""
    answers: Dict[str, Any]  # {question_id: answer}


class ResponseCreate(BaseModel):
    """Schema for submitting a survey response."""
    answers: Dict[str, Any]  # {question_id: answer}
    respondent_name: Optional[str] = Field(None, max_length=255)
    respondent_email: Optional[EmailStr] = None
    is_anonymous: bool = False


class ResponseResponse(BaseModel):
    """Schema for survey response."""
    id: UUID
    survey_instance_id: UUID
    respondent_email: Optional[str] = None
    respondent_name: Optional[str] = None
    respondent_org_id: Optional[UUID] = None
    is_anonymous: bool
    answers: Dict[str, Any]
    completion_time_seconds: Optional[int] = None
    is_complete: bool
    submitted_at: Optional[datetime] = None
    created_at: datetime

    # Populated from join
    respondent_org_name: Optional[str] = None

    class Config:
        from_attributes = True


class ResponseListResponse(BaseModel):
    """Schema for response list."""
    items: List[ResponseResponse]
    total: int


# ===== Aggregation Schemas =====

class QuestionResults(BaseModel):
    """Results for a single question."""
    question_id: UUID
    question_text: str
    question_type: QuestionType
    response_count: int
    average_rating: Optional[float] = None  # For rating questions
    distribution: Optional[Dict[str, int]] = None  # For choice questions
    sample_responses: Optional[List[str]] = None  # For text questions


class SurveyResults(BaseModel):
    """Aggregated survey results."""
    instance_id: UUID
    period: str
    total_responses: int
    completion_rate: float
    questions: List[QuestionResults]


# ===== External Survey Schemas =====

class ExternalSurveyContext(BaseModel):
    """Context for external survey completion."""
    instance_id: UUID
    template_name: str
    relationship_name: Optional[str] = None
    organization_name: str
    period: str
    introduction_text: Optional[str] = None
    questions: List[QuestionResponse]
    allow_anonymous: bool
    due_date: Optional[date] = None
