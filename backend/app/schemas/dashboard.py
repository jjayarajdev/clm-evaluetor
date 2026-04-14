"""Dashboard response schemas.

Pydantic models for all dashboard API responses.
Extracted from routers/dashboard.py to enable service layer separation.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


# ============== Contract Summary ==============


class ContractSummaryCard(BaseModel):
    """Summary card for a single contract."""

    id: str
    filename: str
    contract_type: str | None
    counterparty: str | None
    status: str
    risk_level: str | None
    risk_score: int | None
    clause_count: int
    obligation_count: int
    expiration_date: date | None
    days_until_expiration: int | None


class ContractsSummaryResponse(BaseModel):
    """Summary of all contracts for dashboard."""

    contracts: list[ContractSummaryCard]
    total_contracts: int
    by_status: dict[str, int]
    by_risk: dict[str, int]
    expiring_soon: int  # contracts expiring in 30 days


# ============== Admin Dashboard ==============


class ContractStats(BaseModel):
    """Contract statistics by category."""

    by_type: dict[str, int]
    by_status: dict[str, int]
    total: int


class UserStats(BaseModel):
    """User statistics."""

    by_role: dict[str, int]
    active: int
    inactive: int
    total: int


class ActivityMetrics(BaseModel):
    """Activity metrics over time."""

    queries_7d: int
    queries_30d: int
    uploads_7d: int
    uploads_30d: int


class IngestionStatus(BaseModel):
    """Document ingestion queue status."""

    pending: int
    processing: int
    completed: int
    failed: int


class AdminDashboardResponse(BaseModel):
    """Admin dashboard data."""

    contract_stats: ContractStats
    user_stats: UserStats
    activity: ActivityMetrics
    ingestion: IngestionStatus
    recent_failures: list[dict[str, Any]]


# ============== Legal Dashboard ==============


class RiskOverview(BaseModel):
    """Risk distribution overview."""

    by_level: dict[str, int]
    high_risk_contracts: list[dict[str, Any]]


class ExpirationItem(BaseModel):
    """Contract expiration item."""

    contract_id: str
    filename: str
    counterparty: str | None
    expiration_date: date
    days_remaining: int


class ExpirationTimeline(BaseModel):
    """Expiration timeline."""

    next_30_days: list[ExpirationItem]
    next_60_days: list[ExpirationItem]
    next_90_days: list[ExpirationItem]


class HighRiskClause(BaseModel):
    """High risk clause item."""

    clause_id: str
    contract_id: str
    contract_filename: str
    clause_type: str
    risk_level: str
    excerpt: str


class LegalDashboardResponse(BaseModel):
    """Legal dashboard data."""

    risk_overview: RiskOverview
    expiration_timeline: ExpirationTimeline
    high_risk_clauses: list[HighRiskClause]
    recent_activity: list[dict[str, Any]]


# ============== Procurement Dashboard ==============


class SpendCommitment(BaseModel):
    """Spend commitment by vendor."""

    counterparty: str
    total_value: Decimal
    contract_count: int
    currency: str | None


class VendorObligation(BaseModel):
    """Upcoming vendor obligation."""

    obligation_id: str
    contract_id: str
    contract_filename: str
    counterparty: str | None
    description: str
    deadline: date | None
    days_remaining: int | None
    status: str


class AutoRenewalRisk(BaseModel):
    """Auto-renewal risk item."""

    contract_id: str
    filename: str
    counterparty: str | None
    expiration_date: date | None
    notice_period_days: int | None
    notice_deadline: date | None
    days_until_notice: int | None
    urgency: str


class ProcurementDashboardResponse(BaseModel):
    """Procurement dashboard data."""

    spend_commitments: list[SpendCommitment]
    upcoming_obligations: list[VendorObligation]
    auto_renewal_risks: list[AutoRenewalRisk]
    vendor_summary: dict[str, int]


# ============== Contract Intelligence ==============


class ClauseBreakdown(BaseModel):
    """Clause type breakdown."""

    clause_type: str
    count: int
    high_risk_count: int


class ObligationItem(BaseModel):
    """Single obligation item."""

    id: str
    description: str
    obligation_type: str
    obligated_party: str | None
    beneficiary_party: str | None
    deadline: date | None
    status: str
    source_text: str | None = None


class ObligationsMatrix(BaseModel):
    """Obligations grouped by party."""

    provider_obligations: list[ObligationItem]
    client_obligations: list[ObligationItem]
    total_count: int


class ContractKeyTerms(BaseModel):
    """Key contract terms."""

    contract_type: str | None
    counterparty: str | None
    effective_date: date | None
    expiration_date: date | None
    contract_value: float | None
    currency: str | None
    jurisdiction: str | None
    notice_period_days: int | None
    auto_renewal: bool | None


class RiskSummary(BaseModel):
    """Risk summary for contract."""

    risk_level: str | None
    risk_score: int | None
    high_risk_clauses: list[dict]


class ContractIntelligenceResponse(BaseModel):
    """Comprehensive contract intelligence data."""

    contract_id: str
    filename: str
    key_terms: ContractKeyTerms
    clause_breakdown: list[ClauseBreakdown]
    obligations_matrix: ObligationsMatrix
    risk_summary: RiskSummary
    extraction_status: dict[str, int]


# ============== Obligations Summary ==============


class ObligationsByType(BaseModel):
    """Obligations grouped by type."""

    obligation_type: str
    count: int
    by_party: dict[str, int]


class ObligationsSummaryResponse(BaseModel):
    """Summary of all obligations across contracts."""

    by_type: list[ObligationsByType]
    by_status: dict[str, int]
    by_party: dict[str, int]
    total: int


# ============== Clauses Summary ==============


class ClauseByType(BaseModel):
    """Clause count by type."""

    clause_type: str
    count: int
    high_risk_count: int


class ClausesSummaryResponse(BaseModel):
    """Summary of all clauses across contracts."""

    by_type: list[ClauseByType]
    total: int
    classified: int
    high_risk_total: int


# ============== Clauses Drill-Down ==============


class ClauseDetail(BaseModel):
    """Detailed clause info for drill-down."""

    id: str
    contract_id: str
    contract_filename: str
    counterparty: str | None
    clause_type: str
    text: str
    risk_level: str | None
    page_number: int | None
    section_number: str | None


class ClausesByTypeResponse(BaseModel):
    """Response for clauses filtered by type."""

    clause_type: str
    clauses: list[ClauseDetail]
    total: int
    high_risk_count: int


# ============== Clause Detail ==============


class ClauseFullDetail(BaseModel):
    """Full clause details for detail page."""

    id: str
    contract_id: str
    contract_filename: str
    contract_type: str | None
    counterparty: str | None
    clause_type: str
    text: str  # Full text, not truncated
    risk_level: str | None
    risk_reason: str | None
    page_number: int | None
    section_number: str | None
    # Related clauses in the same contract
    related_clauses: list[dict[str, Any]]


# ============== Obligations Drill-Down ==============


class ObligationDetail(BaseModel):
    """Detailed obligation info for drill-down."""

    id: str
    contract_id: str
    contract_filename: str
    counterparty: str | None
    description: str
    obligation_type: str
    obligated_party: str | None
    beneficiary_party: str | None
    deadline: date | None
    status: str
    source_clause_text: str | None


class ObligationsByTypeResponse(BaseModel):
    """Response for obligations filtered by type."""

    obligation_type: str
    obligations: list[ObligationDetail]
    total: int
    by_party: dict[str, int]
    by_status: dict[str, int]


# ============== Single Obligation Detail ==============


class ObligationFullDetail(BaseModel):
    """Full obligation details for the detail page."""

    id: str
    contract_id: str
    contract_filename: str
    counterparty: str | None
    contract_type: str | None

    # Obligation info
    description: str
    obligation_type: str
    obligated_party: str | None
    beneficiary_party: str | None
    deadline: date | None
    deadline_type: str | None
    recurrence_pattern: str | None
    relative_deadline_text: str | None
    status: str
    consequence_of_breach: str | None
    trigger_condition: str | None
    source_text: str | None  # Direct source from obligation

    # Source clause info (if linked to a clause)
    clause_id: str | None
    clause_type: str | None
    clause_text: str | None
    clause_page_number: int | None
    clause_section_number: str | None
    clause_risk_level: str | None


# ============== Contract Cockpit ==============


class CockpitParty(BaseModel):
    """Party information for cockpit."""

    legal_name: str
    role: str
    short_name: str | None
    entity_type: str | None
    jurisdiction: str | None
    is_primary: bool


class CockpitKeyDate(BaseModel):
    """Key date for cockpit timeline."""

    event_name: str
    event_type: str
    event_date: date
    days_until: int
    action_required: str | None
    alert_days_before: int | None
    urgency: str  # OVERDUE, IMMEDIATE, SOON, UPCOMING, FUTURE


class CockpitFinancial(BaseModel):
    """Financial term for cockpit."""

    fee_type: str
    description: str | None
    amount: float | None
    currency: str | None
    frequency: str | None
    payment_terms: str | None
    is_penalty: bool


class CockpitLiability(BaseModel):
    """Liability term for cockpit."""

    cap_type: str | None
    cap_amount: float | None
    cap_currency: str | None
    description: str | None
    is_mutual: bool
    indemnifying_party: str | None
    insurance_required: bool


class CockpitObligation(BaseModel):
    """Obligation for cockpit matrix."""

    id: str
    description: str
    owner: str  # provider, client, mutual
    category: str | None
    frequency: str | None
    deadline: date | None
    status: str
    rag_status: str
    is_critical: bool
    priority: int | None


class CockpitClauseIndicators(BaseModel):
    """Clause presence indicators for cockpit risk view."""

    # Grouped by category
    confidentiality_ip: dict[str, bool | None]
    liability_indemnity: dict[str, bool | None]
    termination_renewal: dict[str, bool | None]
    compliance_regulatory: dict[str, bool | None]
    business_restrictions: dict[str, bool | None]
    operational: dict[str, bool | None]
    payment: dict[str, bool | None]

    coverage_stats: dict[str, list[str] | float]  # present, absent, unknown lists and coverage_percentage


class CockpitLinkedContract(BaseModel):
    """Linked contract for relationship view."""

    contract_id: str
    filename: str
    link_type: str
    direction: str  # parent, child
    effective_date: date | None
    reference_number: str | None
    is_active: bool


class CockpitRiskSummary(BaseModel):
    """Risk summary for cockpit."""

    overall_risk_level: str | None
    risk_score: int | None
    high_risk_clause_count: int
    overdue_obligations: int
    expiring_soon: bool
    missing_critical_clauses: list[str]
    risk_factors: list[str]


class ContractCockpitResponse(BaseModel):
    """Comprehensive contract cockpit dashboard response."""

    # Contract identity
    contract_id: str
    filename: str
    contract_type: str | None
    status: str

    # Key metadata
    counterparty: str | None
    effective_date: date | None
    expiration_date: date | None
    days_until_expiration: int | None
    contract_value: float | None
    currency: str | None
    governing_law: str | None
    jurisdiction: str | None

    # Renewal info
    auto_renewal: bool | None
    notice_period_days: int | None
    notice_deadline: date | None

    # Parties
    parties: list[CockpitParty]

    # Timeline
    key_dates: list[CockpitKeyDate]

    # Financials
    total_contract_value: float | None
    financials: list[CockpitFinancial]
    penalties: list[CockpitFinancial]

    # Liabilities
    liabilities: list[CockpitLiability]
    primary_liability_cap: CockpitLiability | None

    # Obligations matrix
    provider_obligations: list[CockpitObligation]
    client_obligations: list[CockpitObligation]
    mutual_obligations: list[CockpitObligation]
    obligation_stats: dict[str, int]  # by status, by rag_status

    # Clause indicators (risk view)
    clause_indicators: CockpitClauseIndicators | None

    # Linked contracts
    parent_contracts: list[CockpitLinkedContract]
    child_contracts: list[CockpitLinkedContract]

    # Risk summary
    risk_summary: CockpitRiskSummary

    # Schema data (raw)
    has_schema_data: bool
    schema_id: str | None


# ============== Obligations & Compliance ==============


class ComplianceObligationItem(BaseModel):
    """Single obligation for compliance tracking."""

    id: str
    contract_id: str
    contract_filename: str
    counterparty: str | None
    description: str
    owner: str
    category: str | None
    frequency: str | None
    deadline: date | None
    days_until_deadline: int | None
    status: str
    rag_status: str
    is_critical: bool
    priority: int | None
    last_compliance_date: date | None
    next_compliance_due: date | None


class RAGStatusSummary(BaseModel):
    """RAG status summary across all obligations."""

    green: int
    amber: int
    red: int
    not_assessed: int
    total: int
    compliance_rate: float  # Percentage of green


class ComplianceByCategory(BaseModel):
    """Compliance stats grouped by category."""

    category: str
    total: int
    green: int
    amber: int
    red: int
    not_assessed: int
    compliance_rate: float


class ComplianceByOwner(BaseModel):
    """Compliance stats grouped by owner."""

    owner: str
    total: int
    green: int
    amber: int
    red: int
    overdue: int


class ComplianceCalendarItem(BaseModel):
    """Item for compliance calendar view."""

    date: date
    obligation_count: int
    obligations: list[ComplianceObligationItem]


class ObligationsComplianceResponse(BaseModel):
    """Obligations & Compliance Dashboard response."""

    # Summary stats
    rag_summary: RAGStatusSummary
    status_summary: dict[str, int]  # pending, in_progress, completed, overdue, waived

    # Critical items
    overdue_obligations: list[ComplianceObligationItem]
    critical_upcoming: list[ComplianceObligationItem]  # Critical within 7 days

    # Breakdown views
    by_category: list[ComplianceByCategory]
    by_owner: list[ComplianceByOwner]
    by_frequency: dict[str, int]

    # Calendar view (next 30 days)
    calendar: list[ComplianceCalendarItem]

    # Contract exposure
    contracts_with_red: int
    contracts_with_amber: int
    top_risk_contracts: list[dict[str, Any]]


# ============== Portfolio Dashboard ==============


class PortfolioContractSummary(BaseModel):
    """Contract summary for portfolio view."""

    contract_id: str
    filename: str
    contract_type: str | None
    counterparty: str | None
    status: str
    risk_level: str | None
    contract_value: float | None
    currency: str | None
    effective_date: date | None
    expiration_date: date | None
    days_until_expiration: int | None
    obligation_count: int
    red_obligations: int
    has_auto_renewal: bool


class PortfolioValueMetrics(BaseModel):
    """Portfolio value metrics."""

    total_value: float
    by_currency: dict[str, float]
    by_type: dict[str, float]
    by_counterparty: dict[str, float]
    average_contract_value: float
    contracts_with_value: int


class PortfolioRiskMetrics(BaseModel):
    """Portfolio risk metrics."""

    by_risk_level: dict[str, int]
    high_risk_count: int
    critical_count: int
    contracts_expiring_30d: int
    contracts_expiring_90d: int
    auto_renewal_count: int
    missing_key_clauses: int


class PortfolioObligationMetrics(BaseModel):
    """Portfolio obligation metrics."""

    total_obligations: int
    by_owner: dict[str, int]
    by_status: dict[str, int]
    by_rag: dict[str, int]
    overdue_count: int
    compliance_rate: float


class PortfolioClauseMetrics(BaseModel):
    """Portfolio clause coverage metrics."""

    contracts_with_indicators: int
    average_clause_coverage: float
    missing_critical_by_clause: dict[str, int]  # clause_name -> count of contracts missing


class CounterpartyExposure(BaseModel):
    """Exposure to a single counterparty."""

    counterparty: str
    contract_count: int
    total_value: float
    currency: str | None
    risk_score: float  # Weighted average
    expiring_soon: int
    red_obligations: int


class PortfolioDashboardResponse(BaseModel):
    """Portfolio Dashboard response."""

    # Overview
    total_contracts: int
    contracts_by_status: dict[str, int]
    contracts_by_type: dict[str, int]

    # Value metrics
    value_metrics: PortfolioValueMetrics

    # Risk metrics
    risk_metrics: PortfolioRiskMetrics

    # Obligation metrics
    obligation_metrics: PortfolioObligationMetrics

    # Clause coverage
    clause_metrics: PortfolioClauseMetrics

    # Counterparty exposure
    top_counterparties: list[CounterpartyExposure]

    # Timeline
    expiring_contracts: list[PortfolioContractSummary]
    recently_added: list[PortfolioContractSummary]

    # Alerts
    alerts: list[dict[str, Any]]


# ============== Definitions ==============


class DefinitionItem(BaseModel):
    """Single definition for display."""

    id: str
    term: str
    definition_text: str
    category: str | None
    section_reference: str | None
    page_number: int | None
    cross_references: list[str]


class DefinitionsSummary(BaseModel):
    """Summary of definitions for a contract."""

    contract_id: str
    contract_filename: str
    definitions: list[DefinitionItem]
    total: int
    by_category: dict[str, int]


class DefinitionsByCategory(BaseModel):
    """Definitions grouped by category across all contracts."""

    category: str
    definitions: list[dict[str, Any]]
    total: int


# ============== Financials ==============


class FinancialItem(BaseModel):
    """Single financial item for display."""

    id: str
    fee_type: str
    fee_description: str | None
    fee_amount: float | None
    currency: str
    quantity: int | None
    unit_price: float | None
    payment_terms: str | None
    payment_terms_days: int | None
    invoicing_frequency: str | None
    is_penalty: bool
    penalty_type: str | None
    penalty_trigger: str | None
    penalty_amount: float | None
    penalty_percentage: float | None
    section_reference: str | None


class FinancialsResponse(BaseModel):
    """Financials summary for a contract."""

    financials: list[FinancialItem]
    total_value: float
    currency: str
    by_fee_type: dict[str, int]
    penalties: list[FinancialItem]
    total_penalties: float


# ============== Process Steps ==============


class ProcessStepItem(BaseModel):
    """Single process step for display."""

    id: str
    step_number: int
    step_name: str
    step_type: str
    description: str | None
    responsible_party: str | None
    duration_days: int | None
    sla_days: int | None
    dependencies: list[str]
    deliverables: list[str]
    status: str
    source_text: str | None


class ProcessResponse(BaseModel):
    """Process steps summary for a contract."""

    contract_id: str
    steps: list[ProcessStepItem]
    total_steps: int
    estimated_duration_days: int
    by_responsible_party: dict[str, int]
    sla_items: int


# ============== Preamble ==============


class PartyDetailItem(BaseModel):
    """Single party detail for display."""

    id: str
    party_name: str
    party_role: str | None
    party_short_name: str | None
    legal_form: str | None
    jurisdiction_of_incorporation: str | None
    address: str | None
    party_order: int


class PreambleResponse(BaseModel):
    """Preamble data for a contract."""

    contract_id: str
    document_title: str | None
    effective_date_text: str | None
    background_summary: str | None
    recitals_text: str | None
    parties: list[PartyDetailItem]
    has_preamble: bool


# ============== Exhibits ==============


class FeeItemResponse(BaseModel):
    """Single fee item for display."""

    id: str
    item_name: str
    item_description: str | None
    quantity: int | None
    unit_price: float | None
    total_price: float | None
    currency: str
    item_order: int


class ExhibitItem(BaseModel):
    """Single exhibit/schedule for display."""

    id: str
    exhibit_identifier: str
    exhibit_type: str
    title: str | None
    description: str | None
    page_number: int | None
    source_text: str | None
    fee_items: list[FeeItemResponse]
    total_fee_value: float | None


class ExhibitsResponse(BaseModel):
    """Exhibits summary for a contract."""

    contract_id: str
    exhibits: list[ExhibitItem]
    total_exhibits: int
    by_type: dict[str, int]
    total_fee_value: float
    has_pricing_exhibits: bool


# ============== Insights ==============


class InsightItem(BaseModel):
    """Single insight item."""
    title: str
    description: str
    action: str
    action_label: str
    variant: str  # info, warning, success


class InsightsResponse(BaseModel):
    """AI Insights response."""
    insights: list[InsightItem]


# ============== Activity ==============


class ActivityItem(BaseModel):
    """Single activity item."""
    icon: str
    title: str
    subtitle: str
    time: str
    color: str


class ActivityResponse(BaseModel):
    """Recent activity response."""
    activities: list[ActivityItem]
