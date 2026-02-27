"""Pydantic schemas for Industry-Aware Compliance Module."""

from datetime import date, datetime
from pydantic import BaseModel, Field
from typing import Literal


# ============ Industry Enums as Literals ============

IndustryType = Literal[
    "pharmaceutical", "healthcare", "chemical", "manufacturing",
    "technology", "financial_services", "energy", "aerospace_defense",
    "food_beverage", "automotive", "telecommunications", "retail",
    "construction", "professional_services", "other"
]

ComplianceDocType = Literal[
    "quality_agreement", "pharmacovigilance_agreement", "technical_agreement",
    "safety_data_exchange_agreement", "baa", "dpa", "scc",
    "product_specifications", "quality_management_plan", "supplier_quality_agreement",
    "safety_data_sheet", "environmental_compliance_plan",
    "security_addendum", "soc2_report", "penetration_test_report",
    "outsourcing_agreement", "bcdr_plan",
    "insurance_certificate", "audit_report", "compliance_certification"
]

GapSeverityType = Literal["critical", "high", "medium", "low"]

GapStatusType = Literal[
    "open", "in_progress", "pending_review", "resolved", "waived", "not_applicable"
]

RegulationTypeStr = Literal[
    "fda", "hipaa", "epa", "osha", "sox", "finra", "sec", "ftc",
    "gdpr", "mdr", "ivdr", "reach",
    "gmp", "gcp", "glp", "iso_9001", "iso_13485", "iso_27001", "soc2", "pci_dss",
    "ich", "who", "other"
]

RegulatoryObligationCategoryType = Literal[
    "audit_rights", "change_control", "deviation_reporting", "corrective_action",
    "quality_review", "recall_response", "adverse_event_reporting", "safety_monitoring",
    "risk_assessment", "record_retention", "documentation_control", "batch_records",
    "validation_records", "training_requirements", "qualification_requirements",
    "regulatory_reporting", "periodic_reporting", "notification_requirements",
    "data_protection", "breach_notification", "data_retention",
    "environmental_compliance", "waste_management", "other"
]

ComplianceStatusType = Literal["green", "amber", "red", "not_assessed"]

ContractTypeStr = Literal[
    "nda", "msa", "sow", "amendment", "vendor_agreement", "employment_contract"
]


# ============ Compliance Rule Schemas ============

class ComplianceRuleCreate(BaseModel):
    """Request to create a compliance rule."""

    industry: IndustryType
    primary_contract_type: ContractTypeStr
    required_document_type: ComplianceDocType
    is_required: bool = True
    condition_description: str | None = Field(None, max_length=2000)
    severity_if_missing: GapSeverityType = "medium"
    regulatory_reference: str | None = Field(None, max_length=500)
    rule_name: str = Field(..., max_length=255)
    rule_description: str | None = Field(None, max_length=2000)
    is_active: bool = True


class ComplianceRuleUpdate(BaseModel):
    """Request to update a compliance rule."""

    is_required: bool | None = None
    condition_description: str | None = None
    severity_if_missing: GapSeverityType | None = None
    regulatory_reference: str | None = None
    rule_name: str | None = None
    rule_description: str | None = None
    is_active: bool | None = None


class ComplianceRuleResponse(BaseModel):
    """Response model for compliance rule."""

    id: str
    tenant_id: str
    industry: str
    primary_contract_type: str
    required_document_type: str
    is_required: bool
    condition_description: str | None
    severity_if_missing: str
    regulatory_reference: str | None
    rule_name: str
    rule_description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ComplianceRuleSummary(BaseModel):
    """Summary view of a compliance rule."""

    id: str
    industry: str
    primary_contract_type: str
    required_document_type: str
    rule_name: str
    severity_if_missing: str
    is_required: bool
    is_active: bool

    model_config = {"from_attributes": True}


# ============ Compliance Gap Schemas ============

class ComplianceGapResponse(BaseModel):
    """Response model for compliance gap."""

    id: str
    contract_id: str
    rule_id: str | None
    missing_document_type: str
    gap_description: str
    regulatory_reference: str | None
    severity: str
    status: str
    resolution_due_date: date | None
    resolved_at: datetime | None
    resolved_by: str | None
    resolution_notes: str | None
    linked_document_id: str | None
    detection_confidence: float
    detection_reasoning: str | None
    detected_at: datetime
    waiver_reason: str | None
    waiver_approved_by: str | None
    waiver_approved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    is_overdue: bool
    days_until_due: int | None

    model_config = {"from_attributes": True}


class ComplianceGapSummary(BaseModel):
    """Summary view of a compliance gap."""

    id: str
    contract_id: str
    missing_document_type: str
    gap_description: str
    severity: str
    status: str
    resolution_due_date: date | None
    is_overdue: bool

    model_config = {"from_attributes": True}


class ComplianceGapResolve(BaseModel):
    """Request to resolve a compliance gap."""

    linked_document_id: str = Field(..., description="ID of the document that resolves this gap")
    resolution_notes: str | None = Field(None, max_length=2000)


class ComplianceGapWaive(BaseModel):
    """Request to waive a compliance requirement."""

    waiver_reason: str = Field(..., min_length=10, max_length=2000)


class ComplianceGapUpdateStatus(BaseModel):
    """Request to update gap status."""

    status: GapStatusType
    notes: str | None = None


# ============ Regulatory Obligation Schemas ============

class RegulatoryObligationResponse(BaseModel):
    """Response model for regulatory obligation."""

    id: str
    contract_id: str
    industry: str
    regulation_type: str
    regulation_reference: str | None
    obligation_category: str
    title: str
    description: str
    source_text: str | None
    source_section: str | None
    responsible_party: str | None
    frequency: str | None
    next_due_date: date | None
    last_completed_date: date | None
    compliance_status: str
    last_compliance_check: datetime | None
    compliance_notes: str | None
    compliance_evidence: str | None
    extraction_confidence: float
    created_at: datetime
    updated_at: datetime
    is_overdue: bool
    needs_attention: bool

    model_config = {"from_attributes": True}


class RegulatoryObligationSummary(BaseModel):
    """Summary view of a regulatory obligation."""

    id: str
    contract_id: str
    regulation_type: str
    obligation_category: str
    title: str
    compliance_status: str
    next_due_date: date | None
    is_overdue: bool

    model_config = {"from_attributes": True}


class RegulatoryObligationUpdateStatus(BaseModel):
    """Request to update compliance status."""

    compliance_status: ComplianceStatusType
    compliance_notes: str | None = Field(None, max_length=2000)
    compliance_evidence: str | None = Field(None, max_length=2000)
    next_due_date: date | None = None
    last_completed_date: date | None = None


# ============ Industry Detection Schemas ============

class IndustryDetectionRequest(BaseModel):
    """Request to detect contract industry."""

    contract_id: str
    counterparty_industry: IndustryType | None = None


class IndustrySignalResponse(BaseModel):
    """A signal that contributed to industry detection."""

    industry: str
    signal_type: str
    match: str
    weight: float
    score: float


class IndustryDetectionResponse(BaseModel):
    """Response from industry detection."""

    contract_id: str
    detected_industry: str
    confidence: float
    alternative_industries: list[tuple[str, float]]
    signals: list[IndustrySignalResponse]
    reasoning: str
    is_confident: bool
    needs_review: bool


# ============ Compliance Check Schemas ============

class ComplianceCheckRequest(BaseModel):
    """Request to check contract compliance."""

    industry: IndustryType | None = None
    create_gaps: bool = True


class ComplianceCheckResponse(BaseModel):
    """Response from compliance check."""

    contract_id: str
    industry: str
    industry_confidence: float
    compliance_score: int
    total_rules_checked: int
    rules_satisfied: int
    gaps_found: list[ComplianceGapSummary]


# ============ Dashboard Schemas ============

class ComplianceDashboardSummary(BaseModel):
    """Summary statistics for compliance dashboard."""

    total_contracts: int
    contracts_by_industry: dict[str, int]
    total_gaps: int
    gaps_by_severity: dict[str, int]
    gaps_by_status: dict[str, int]
    overdue_gaps: int
    average_compliance_score: float
    critical_gaps_count: int
    regulatory_obligations_count: int
    obligations_needing_attention: int


class IndustryComplianceSummary(BaseModel):
    """Compliance summary for a specific industry."""

    industry: str
    contract_count: int
    average_compliance_score: float
    total_gaps: int
    critical_gaps: int
    high_gaps: int
    open_gaps: int
    resolved_gaps: int


class ContractComplianceSummary(BaseModel):
    """Compliance summary for a specific contract."""

    contract_id: str
    filename: str
    counterparty: str | None
    detected_industry: str | None
    industry_confidence: float | None
    compliance_score: int | None
    last_compliance_check: datetime | None
    open_gaps_count: int
    critical_gaps_count: int
    regulatory_obligations_count: int


# ============ Matching Document Schemas ============

class MatchingDocumentResponse(BaseModel):
    """A document that potentially resolves a compliance gap."""

    contract_id: str
    filename: str
    counterparty: str | None
    contract_type: str | None
    match_score: float
    match_reason: str
    effective_date: date | None
    expiration_date: date | None


class SuggestMatchingDocumentsRequest(BaseModel):
    """Request to find matching documents for a gap."""

    gap_id: str
    limit: int = Field(default=5, ge=1, le=20)


class SuggestMatchingDocumentsResponse(BaseModel):
    """Response with potential matching documents."""

    gap_id: str
    missing_document_type: str
    suggestions: list[MatchingDocumentResponse]
