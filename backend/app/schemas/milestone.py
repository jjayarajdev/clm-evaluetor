"""Pydantic schemas for Milestone Health Dashboard."""

from datetime import date, datetime
from pydantic import BaseModel, Field
from typing import Literal


class MilestoneItem(BaseModel):
    """A single milestone (obligation-based)."""

    milestone_id: str
    contract_id: str
    contract_filename: str
    counterparty: str | None

    # Milestone details
    title: str
    description: str | None
    category: str | None
    owner: str | None

    # Dates
    due_date: date | None
    completed_date: date | None

    # Status
    status: str  # pending, in_progress, completed, overdue, waived
    rag_status: str | None  # green, amber, red, not_assessed
    is_at_risk: bool  # Approaching deadline with no progress

    # Time info
    days_until_due: int | None
    days_overdue: int | None

    # Grouping
    time_bucket: Literal["overdue", "this_week", "next_week", "this_month", "future"]


class MilestonesByStatus(BaseModel):
    """Milestones grouped by status."""

    pending: int
    in_progress: int
    completed: int
    overdue: int
    waived: int


class MilestonesByTimeBucket(BaseModel):
    """Milestones grouped by time bucket."""

    overdue: list[MilestoneItem]
    this_week: list[MilestoneItem]
    next_week: list[MilestoneItem]
    this_month: list[MilestoneItem]
    future: list[MilestoneItem]


class MilestoneHealthResponse(BaseModel):
    """Response for milestone health dashboard."""

    as_of_date: date
    total_milestones: int

    # Counts by status
    by_status: MilestonesByStatus

    # At-risk detection
    at_risk_count: int
    at_risk_milestones: list[MilestoneItem]

    # Grouped by time
    by_time_bucket: MilestonesByTimeBucket

    # Compliance metrics
    completion_rate: float  # completed / (completed + overdue)
    on_track_rate: float  # (completed + in_progress) / total


class AtRiskContractItem(BaseModel):
    """A contract that is at risk based on milestone/obligation status."""

    contract_id: str
    filename: str
    counterparty: str | None
    contract_type: str | None
    contract_value: float | None

    # Risk indicators
    risk_score: int  # 0-100
    risk_level: str  # low, medium, high, critical
    risk_factors: list[str]

    # Milestone stats
    total_milestones: int
    overdue_milestones: int
    at_risk_milestones: int
    completion_rate: float

    # SLA stats
    sla_compliance_rate: float | None
    active_breaches: int

    # Recommended action
    recommended_action: str


class AtRiskContractsResponse(BaseModel):
    """Response for at-risk contracts endpoint."""

    total_at_risk: int
    critical_count: int
    high_count: int
    total_value_at_risk: float
    contracts: list[AtRiskContractItem]


class PortfolioComplianceMetrics(BaseModel):
    """Portfolio-level compliance metrics."""

    as_of_date: date

    # Overall metrics
    total_contracts: int
    total_obligations: int
    total_slas: int

    # Compliance rates
    obligation_compliance_rate: float
    sla_compliance_rate: float
    overall_compliance_rate: float  # Weighted average

    # Status breakdown
    obligations_by_status: dict[str, int]
    obligations_by_rag: dict[str, int]

    # At-risk summary
    contracts_at_risk: int
    obligations_at_risk: int
    slas_breached: int

    # Trends (if available)
    compliance_trend: Literal["improving", "stable", "declining"] | None
    previous_compliance_rate: float | None


class MilestoneOwnerAssignment(BaseModel):
    """Request to assign milestone owner."""

    owner: str = Field(..., max_length=100)
    notes: str | None = Field(None, max_length=500)
