"""Pydantic schemas for Renewal Management."""

from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from typing import Literal


class RenewalStatusUpdate(BaseModel):
    """Update renewal decision status."""

    renewal_status: Literal[
        "pending_review", "approved", "declined",
        "auto_renewed", "expired", "renegotiating"
    ]
    decision_notes: str | None = Field(None, max_length=2000)
    decided_by: str | None = Field(None, max_length=100)
    new_expiration_date: date | None = None  # If renewed, the new expiration


class ContractRenewalInfo(BaseModel):
    """Renewal information for a single contract."""

    contract_id: str
    filename: str
    counterparty: str | None
    contract_type: str | None
    contract_value: float | None

    # Dates
    effective_date: date | None
    expiration_date: date | None
    notice_deadline: date | None

    # Renewal terms
    auto_renewal: bool | None
    notice_period_days: int | None
    renewal_term_months: int | None

    # Calculated fields
    days_until_expiration: int | None
    days_until_notice_deadline: int | None
    is_past_notice_deadline: bool
    renewal_window: str  # "expired", "critical", "30_days", "60_days", "90_days", "beyond_90"

    # Status
    renewal_status: str | None
    risk_level: str | None

    # SLA compliance (if available)
    sla_compliance_rate: float | None
    active_sla_breaches: int


class RenewalCalendarResponse(BaseModel):
    """Response for renewal calendar view."""

    as_of_date: date
    total_contracts: int

    # Grouped by urgency
    expired: list[ContractRenewalInfo]
    critical: list[ContractRenewalInfo]  # Past notice deadline
    within_30_days: list[ContractRenewalInfo]
    within_60_days: list[ContractRenewalInfo]
    within_90_days: list[ContractRenewalInfo]

    # Summary stats
    total_value_at_risk: float
    auto_renewal_count: int
    requires_action_count: int


class AtRiskContract(BaseModel):
    """Contract that is at risk of unfavorable renewal."""

    contract_id: str
    filename: str
    counterparty: str | None
    contract_value: float | None

    expiration_date: date | None
    notice_deadline: date | None
    days_past_notice: int

    auto_renewal: bool | None
    risk_level: str | None

    # Risk factors
    risk_factors: list[str]
    recommended_action: str


class AtRiskResponse(BaseModel):
    """Response for at-risk contracts endpoint."""

    total_at_risk: int
    total_value_at_risk: float
    contracts: list[AtRiskContract]


class RenewalRecommendation(BaseModel):
    """AI-generated renewal recommendation."""

    contract_id: str
    filename: str
    counterparty: str | None

    recommendation: Literal["renew", "renegotiate", "terminate", "review_terms"]
    confidence_score: float  # 0-1

    # Factors considered
    factors: list[dict]  # {factor: str, impact: str, details: str}

    # Key metrics
    contract_value: float | None
    sla_compliance_rate: float | None
    total_penalties_paid: float
    obligation_compliance_rate: float | None

    # Suggested actions
    suggested_actions: list[str]
    negotiation_points: list[str] | None


class RenewalSummaryStats(BaseModel):
    """Summary statistics for renewal dashboard."""

    # Counts
    total_active_contracts: int
    expiring_30_days: int
    expiring_60_days: int
    expiring_90_days: int
    past_notice_deadline: int
    auto_renewing: int

    # Values
    total_value_expiring_90_days: float
    total_value_past_notice: float

    # Trends
    renewal_rate_last_12_months: float | None
    avg_renewal_increase_pct: float | None

    # By status
    by_renewal_status: dict[str, int]

    # By contract type
    by_contract_type: dict[str, dict]  # type -> {count, total_value}
