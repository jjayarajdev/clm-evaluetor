"""Pydantic schemas for Vendor Performance Scoring."""

from datetime import date, datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Literal


class CounterpartyType(str, Enum):
    """Type of counterparty relationship."""
    VENDOR = "vendor"      # You buy from them
    CLIENT = "client"      # You deliver to them
    UNKNOWN = "unknown"    # Not determined


class VendorScoringConfig(BaseModel):
    """Resolved vendor scoring rules (default -> tenant -> BU overrides).

    Server truth for score weights and risk banding, so the UI never hardcodes
    thresholds like 80/60.
    """

    obligation_weight: float
    sla_weight: float
    responsiveness_weight: float  # reserved — signal not measured yet
    issue_rate_weight: float      # reserved — signal not measured yet
    # score >= low -> low risk, >= medium -> medium, >= high -> high, else critical
    low_threshold: float
    medium_threshold: float
    high_threshold: float
    # vendor is "at risk" when composite score < this
    at_risk_threshold: float


class VendorScoreBreakdown(BaseModel):
    """Breakdown of how vendor score is calculated."""

    # None when there is no real signal (obligations not tracked / SLAs not measured)
    obligation_compliance_score: float | None  # 0-100, weight: 40%
    obligation_compliance_weight: float = 0.40

    sla_compliance_score: float | None  # 0-100, weight: 30%
    sla_compliance_weight: float = 0.30

    responsiveness_score: float | None = None  # not yet captured
    responsiveness_weight: float = 0.20

    issue_rate_score: float | None = None  # not yet captured
    issue_rate_weight: float = 0.10

    weighted_total: float | None  # Final composite score; None = unrated


class VendorContractSummary(BaseModel):
    """Summary of a vendor's contracts."""

    total_contracts: int
    active_contracts: int
    expired_contracts: int
    total_value: float
    annual_spend: float | None
    contract_types: dict[str, int]  # type -> count
    earliest_contract: date | None
    latest_expiration: date | None


class VendorObligationSummary(BaseModel):
    """Summary of vendor's obligation compliance."""

    total_obligations: int
    completed_obligations: int
    overdue_obligations: int
    compliance_rate: float | None  # 0-100; None when nothing is assessable yet
    by_status: dict[str, int]
    by_rag: dict[str, int]
    critical_overdue: int


class VendorSLASummary(BaseModel):
    """Summary of vendor's SLA compliance."""

    total_slas: int
    active_slas: int
    compliance_rate: float | None  # 0-100; None when no SLA has been measured
    total_breaches: int
    critical_breaches: int
    total_penalties: float
    by_metric_type: dict[str, dict]  # metric -> {total, compliant, compliance_rate}


class VendorListItem(BaseModel):
    """Vendor item for list view."""

    vendor_name: str
    normalized_name: str  # Lowercase, trimmed for matching
    tenant_name: str | None = None  # Owning tenant (populated for super-admin)
    party_type: CounterpartyType = CounterpartyType.UNKNOWN  # vendor or client
    performance_score: float | None  # 0-100 composite score; None = unrated
    risk_level: Literal["low", "medium", "high", "critical", "unrated"]
    is_at_risk: bool  # score below the configured at_risk_threshold

    # Quick stats
    contract_count: int
    total_exposure: float
    sla_compliance_rate: float | None
    obligation_compliance_rate: float | None
    active_breaches: int

    last_updated: datetime


class VendorListResponse(BaseModel):
    """Response for vendor list endpoint."""

    total_vendors: int
    at_risk_count: int
    total_exposure: float
    vendors: list[VendorListItem]
    # Additive: resolved scoring config used to compute the scores above.
    scoring: VendorScoringConfig | None = None


class VendorPerformanceDetail(BaseModel):
    """Detailed vendor performance profile."""

    vendor_name: str
    normalized_name: str

    # Overall score
    performance_score: float | None
    risk_level: Literal["low", "medium", "high", "critical", "unrated"]
    is_at_risk: bool
    score_breakdown: VendorScoreBreakdown

    # Summaries
    contracts: VendorContractSummary
    obligations: VendorObligationSummary
    slas: VendorSLASummary

    # Trend (if historical data available)
    score_trend: Literal["improving", "stable", "declining"] | None
    previous_score: float | None

    # Recommendations
    risk_factors: list[str]
    recommended_actions: list[str]

    last_updated: datetime


class VendorCompareItem(BaseModel):
    """Vendor data for comparison."""

    vendor_name: str
    performance_score: float | None
    obligation_compliance: float | None
    sla_compliance: float | None
    total_exposure: float
    contract_count: int
    active_breaches: int
    risk_level: str


class VendorCompareResponse(BaseModel):
    """Response for vendor comparison."""

    vendors: list[VendorCompareItem]
    comparison_date: datetime

    # Best/worst for each metric
    best_overall: str
    worst_overall: str
    best_sla_compliance: str
    best_obligation_compliance: str
    highest_exposure: str


class AtRiskVendor(BaseModel):
    """Vendor whose score is below the configured at-risk threshold."""

    vendor_name: str
    performance_score: float | None
    risk_level: str

    # Key issues
    primary_issues: list[str]
    contracts_affected: int
    exposure_at_risk: float

    # Metrics driving the low score
    obligation_compliance: float | None
    sla_compliance: float | None
    active_breaches: int
    overdue_obligations: int

    recommended_action: str


class AtRiskVendorsResponse(BaseModel):
    """Response for at-risk vendors endpoint."""

    total_at_risk: int
    total_exposure_at_risk: float
    critical_count: int
    high_count: int
    vendors: list[AtRiskVendor]


class VendorScorecard(BaseModel):
    """Vendor scorecard for procurement dashboard."""

    vendor_name: str
    score: float | None
    grade: Literal["A", "B", "C", "D", "F", "N/A"]  # A: 90+, B: 80-89, C: 70-79, D: 60-69, F: <60

    # Key metrics
    contracts: int
    exposure: float
    sla_compliance: float
    obligation_compliance: float

    # Flags
    is_strategic: bool  # High value vendor
    is_at_risk: bool
    needs_review: bool
