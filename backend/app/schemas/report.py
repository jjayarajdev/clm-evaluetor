"""Pydantic schemas for Compliance Reporting."""

from datetime import date, datetime
from pydantic import BaseModel, Field
from typing import Literal


class ReportDateRange(BaseModel):
    """Date range for report generation."""

    start_date: date
    end_date: date


class ObligationReportItem(BaseModel):
    """Obligation item in compliance report."""

    obligation_id: str
    contract_id: str
    contract_filename: str
    counterparty: str | None

    title: str
    category: str | None
    owner: str | None
    due_date: date | None
    completed_date: date | None

    status: str
    rag_status: str | None
    was_on_time: bool | None


class SLAReportItem(BaseModel):
    """SLA item in compliance report."""

    sla_id: str
    contract_id: str
    contract_filename: str
    counterparty: str | None

    sla_name: str
    metric_type: str
    target_value: float
    actual_value: float | None
    compliance_rate: float | None

    is_compliant: bool
    breaches_in_period: int
    penalties_in_period: float


class ComplianceReportSummary(BaseModel):
    """Summary section of compliance report."""

    report_period_start: date
    report_period_end: date
    generated_at: datetime

    # Obligation summary
    total_obligations: int
    obligations_completed: int
    obligations_overdue: int
    obligations_on_time: int
    obligation_compliance_rate: float

    # SLA summary
    total_slas: int
    slas_compliant: int
    slas_breached: int
    sla_compliance_rate: float
    total_penalties: float

    # Overall
    overall_compliance_rate: float
    contracts_reviewed: int
    high_risk_contracts: int


class ComplianceReportResponse(BaseModel):
    """Full compliance report response."""

    summary: ComplianceReportSummary

    # Detailed data
    obligations: list[ObligationReportItem]
    slas: list[SLAReportItem]

    # By contract breakdown
    by_contract: dict[str, dict]  # contract_id -> {obligation_rate, sla_rate, total}

    # By category breakdown
    by_category: dict[str, dict]  # category -> {total, completed, compliance_rate}


class TrendDataPoint(BaseModel):
    """A single data point in trend analysis."""

    period_start: date
    period_end: date
    period_label: str  # e.g., "Week 1", "Jan 2026"

    obligation_compliance_rate: float
    sla_compliance_rate: float
    overall_compliance_rate: float

    obligations_completed: int
    obligations_overdue: int
    sla_breaches: int
    penalties: float


class ComplianceTrendResponse(BaseModel):
    """Compliance trend analysis response."""

    trend_type: Literal["weekly", "monthly"]
    data_points: list[TrendDataPoint]

    # Trend direction
    obligation_trend: Literal["improving", "stable", "declining"]
    sla_trend: Literal["improving", "stable", "declining"]
    overall_trend: Literal["improving", "stable", "declining"]

    # Change percentages
    obligation_change_pct: float
    sla_change_pct: float
    overall_change_pct: float


class ScheduledReportConfig(BaseModel):
    """Configuration for a scheduled report."""

    name: str = Field(..., max_length=100)
    frequency: Literal["daily", "weekly", "monthly"]
    report_type: Literal["compliance", "sla", "obligations", "vendor"]
    recipients: list[str]  # Email addresses
    include_csv: bool = True
    include_charts: bool = False
    filters: dict | None = None  # Optional filters


class ScheduledReportResponse(BaseModel):
    """Response for scheduled report."""

    id: str
    name: str
    frequency: str
    report_type: str
    recipients: list[str]
    next_run: datetime
    last_run: datetime | None
    is_active: bool
    created_at: datetime


class ExportRequest(BaseModel):
    """Request for report export."""

    format: Literal["csv", "excel"] = "csv"
    start_date: date
    end_date: date
    include_obligations: bool = True
    include_slas: bool = True
    include_summary: bool = True
