"""Pydantic schemas for SLA tracking."""

from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from typing import Literal


class SLACreate(BaseModel):
    """Request to create an SLA."""

    sla_name: str = Field(..., max_length=200)
    sla_description: str | None = Field(None, max_length=2000)
    metric_type: Literal[
        "uptime_percentage", "response_time", "resolution_time",
        "delivery_time", "throughput", "error_rate",
        "availability", "quality_score", "custom"
    ]
    metric_unit: Literal[
        "percentage", "hours", "minutes", "days",
        "business_days", "count", "score"
    ]
    target_value: Decimal
    target_operator: Literal[">=", "<=", "=", ">", "<"] = ">="
    warning_threshold: Decimal | None = None
    severity: Literal["critical", "high", "medium", "low"] = "medium"
    has_penalty: bool = False
    penalty_type: str | None = None
    penalty_value: Decimal | None = None
    penalty_description: str | None = None
    max_penalty_cap: Decimal | None = None
    measurement_period: str | None = None
    source_text: str | None = None
    source_clause_id: str | None = None


class SLAUpdate(BaseModel):
    """Request to update an SLA."""

    sla_name: str | None = Field(None, max_length=200)
    sla_description: str | None = Field(None, max_length=2000)
    metric_type: Literal[
        "uptime_percentage", "response_time", "resolution_time",
        "delivery_time", "throughput", "error_rate",
        "availability", "quality_score", "custom"
    ] | None = None
    metric_unit: Literal[
        "percentage", "hours", "minutes", "days",
        "business_days", "count", "score"
    ] | None = None
    target_value: Decimal | None = None
    target_operator: Literal[">=", "<=", "=", ">", "<"] | None = None
    warning_threshold: Decimal | None = None
    severity: Literal["critical", "high", "medium", "low"] | None = None
    has_penalty: bool | None = None
    penalty_type: str | None = None
    penalty_value: Decimal | None = None
    penalty_description: str | None = None
    max_penalty_cap: Decimal | None = None
    measurement_period: str | None = None
    is_active: bool | None = None


class SLAResponse(BaseModel):
    """Response model for SLA details."""

    id: str
    contract_id: str
    sla_name: str
    sla_description: str | None
    metric_type: str
    metric_unit: str
    target_value: float
    target_operator: str
    warning_threshold: float | None
    severity: str
    has_penalty: bool
    penalty_type: str | None
    penalty_value: float | None
    penalty_description: str | None
    max_penalty_cap: float | None
    measurement_period: str | None
    is_active: bool
    current_compliance_rate: float | None
    last_measured_at: datetime | None
    consecutive_breaches: int
    source_text: str | None
    master_data_id: str | None = None
    source: str = "manual"  # "ai_extracted", "from_library", "manual"
    master_data_name: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SLAPerformanceCreate(BaseModel):
    """Request to log SLA performance."""

    actual_value: Decimal
    measured_at: datetime | None = None  # Defaults to now
    measurement_period_start: date | None = None
    measurement_period_end: date | None = None
    notes: str | None = Field(None, max_length=1000)
    recorded_by: str | None = Field(None, max_length=100)


class SLAPerformanceResponse(BaseModel):
    """Response model for SLA performance record."""

    id: str
    sla_id: str
    actual_value: float
    measured_at: datetime
    measurement_period_start: date | None
    measurement_period_end: date | None
    is_compliant: bool
    deviation_percentage: float | None
    breach_severity: str | None
    penalty_applied: bool
    penalty_amount: float | None
    credit_issued: float | None
    notes: str | None
    recorded_by: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class SLAWithPerformance(SLAResponse):
    """SLA with recent performance history."""

    recent_performances: list[SLAPerformanceResponse]
    compliance_trend: str | None  # "improving", "declining", "stable"


class SLABreachItem(BaseModel):
    """A single SLA breach."""

    sla_id: str
    sla_name: str
    contract_id: str
    contract_filename: str
    metric_type: str
    target_value: float
    actual_value: float
    deviation_percentage: float
    breach_severity: str
    measured_at: datetime
    penalty_amount: float | None
    consecutive_breaches: int


class SLAComplianceByContract(BaseModel):
    """SLA compliance summary for a contract."""

    contract_id: str
    contract_filename: str
    total_slas: int
    compliant_slas: int
    breached_slas: int
    compliance_rate: float
    total_penalties: float
    active_breaches: int


class SLAComplianceResponse(BaseModel):
    """Overall SLA compliance response."""

    total_slas: int
    total_active: int
    overall_compliance_rate: float
    by_metric_type: dict[str, dict]  # metric_type -> {total, compliant, compliance_rate}
    by_severity: dict[str, dict]  # severity -> {total, compliant, compliance_rate}
    contracts: list[SLAComplianceByContract]
    total_breaches: int
    total_penalties_this_period: float
    critical_breaches: int


class SLABreachesResponse(BaseModel):
    """Current active breaches."""

    total_breaches: int
    critical: list[SLABreachItem]
    high: list[SLABreachItem]
    medium: list[SLABreachItem]
    low: list[SLABreachItem]
    total_penalty_exposure: float
