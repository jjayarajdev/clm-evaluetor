"""Pydantic schemas for Post-Signing Dashboard."""

from datetime import date, datetime
from pydantic import BaseModel
from typing import Literal


class ObligationWidget(BaseModel):
    """Obligation compliance widget data."""

    total: int
    completed: int
    in_progress: int
    overdue: int
    at_risk: int
    compliance_rate: float | None = None  # None = not tracked (no completions/progress)

    # RAG breakdown
    green: int
    amber: int
    red: int

    # Recent items needing attention
    urgent_items: list[dict]  # Top 5 urgent


class SLAWidget(BaseModel):
    """SLA tracking widget data."""

    total_slas: int
    active_slas: int
    compliant: int
    breached: int
    compliance_rate: float | None = None  # None = not measured (no performance data)

    # Breaches
    critical_breaches: int
    total_penalties_mtd: float

    # Recent breaches
    recent_breaches: list[dict]  # Top 5


class RenewalWidget(BaseModel):
    """Renewal calendar widget data."""

    expiring_30_days: int
    expiring_60_days: int
    expiring_90_days: int
    past_notice_deadline: int
    total_value_at_risk: float

    # Upcoming renewals
    upcoming_renewals: list[dict]  # Top 5


class VendorWidget(BaseModel):
    """Vendor scorecard widget data."""

    total_vendors: int
    at_risk_vendors: int
    avg_performance_score: float | None  # None when no vendor is rated yet

    # Top and bottom performers
    top_performers: list[dict]  # Top 3
    bottom_performers: list[dict]  # Bottom 3


class MilestoneWidget(BaseModel):
    """Milestone health widget data."""

    total_milestones: int
    completed: int
    at_risk: int
    overdue: int
    completion_rate: float | None = None  # None = no milestones to measure

    # This week's milestones
    due_this_week: list[dict]


class ComplianceWidget(BaseModel):
    """Overall compliance widget data."""

    overall_compliance_rate: float | None = None  # None = nothing measured
    obligation_compliance_rate: float | None = None
    sla_compliance_rate: float | None = None

    trend: Literal["improving", "stable", "declining"] | None
    change_from_last_month: float | None

    contracts_at_risk: int
    high_priority_actions: int


class PostSigningDashboard(BaseModel):
    """Complete post-signing dashboard data."""

    generated_at: datetime
    as_of_date: date

    # Widgets
    obligations: ObligationWidget
    slas: SLAWidget
    renewals: RenewalWidget
    vendors: VendorWidget
    milestones: MilestoneWidget
    compliance: ComplianceWidget

    # Quick stats for header
    total_contracts: int
    total_value: float  # dominant-currency subtotal (never a cross-currency sum)
    total_value_currency: str = "USD"
    total_value_by_currency: dict[str, float] = {}
    valued_contracts: int = 0  # how many contracts actually have a recorded value
    contracts_needing_attention: int

    # Action items
    priority_actions: list[dict]  # Combined priority actions from all areas


class DashboardFilter(BaseModel):
    """Filters for dashboard data."""

    contract_type: str | None = None
    counterparty: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    risk_level: str | None = None
