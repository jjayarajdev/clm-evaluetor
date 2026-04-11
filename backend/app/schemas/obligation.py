"""Pydantic schemas for obligation management."""

from datetime import date, datetime
from pydantic import BaseModel, Field
from typing import Literal


class ObligationStatusUpdate(BaseModel):
    """Request to update obligation status."""

    status: Literal["pending", "in_progress", "completed", "overdue", "waived"]
    notes: str | None = Field(None, max_length=1000, description="Optional notes about the status change")


class ObligationRAGUpdate(BaseModel):
    """Request to update obligation RAG status."""

    rag_status: Literal["green", "amber", "red", "not_assessed"]
    compliance_notes: str | None = Field(None, max_length=2000, description="Notes about compliance status")
    last_compliance_date: date | None = Field(None, description="Date of last compliance check")
    next_compliance_due: date | None = Field(None, description="Next compliance due date")


class ObligationOwnerUpdate(BaseModel):
    """Request to assign obligation owner."""

    owner_type: Literal["provider", "client", "mutual", "third_party", "unspecified"]
    obligated_party: str | None = Field(None, max_length=255, description="Name of the obligated party")
    priority: int | None = Field(None, ge=1, le=5, description="Priority 1=highest, 5=lowest")
    is_critical: bool | None = Field(None, description="Mark as critical obligation")


class ObligationEvidenceUpload(BaseModel):
    """Request to add compliance evidence."""

    evidence_description: str = Field(..., max_length=500, description="Description of the evidence")
    file_path: str | None = Field(None, max_length=500, description="Path to uploaded evidence file")
    evidence_date: date | None = Field(None, description="Date the evidence was collected")


class ObligationResponse(BaseModel):
    """Response model for obligation details."""

    id: str
    contract_id: str
    description: str
    obligation_type: str
    status: str
    rag_status: str | None
    owner_type: str | None
    category: str | None
    frequency: str | None
    deadline: date | None
    deadline_type: str | None
    obligated_party: str | None
    beneficiary_party: str | None
    is_critical: bool | None
    priority: int | None
    compliance_notes: str | None
    compliance_evidence: str | None
    last_compliance_date: date | None
    next_compliance_due: date | None
    section_reference: str | None
    source_text: str | None = None
    consequence_of_breach: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ComplianceRatesByContract(BaseModel):
    """Compliance rates for a single contract."""

    contract_id: str
    contract_filename: str
    total_obligations: int
    completed: int
    in_progress: int
    overdue: int
    pending: int
    compliance_rate: float  # percentage 0-100
    rag_green: int
    rag_amber: int
    rag_red: int


class ComplianceRatesByOwner(BaseModel):
    """Compliance rates grouped by owner type."""

    owner_type: str
    total_obligations: int
    completed: int
    overdue: int
    compliance_rate: float


class ComplianceRatesByCategory(BaseModel):
    """Compliance rates grouped by category."""

    category: str
    total_obligations: int
    completed: int
    overdue: int
    compliance_rate: float


class ComplianceRatesResponse(BaseModel):
    """Overall compliance rates response."""

    total_obligations: int
    overall_compliance_rate: float
    by_status: dict[str, int]
    by_rag: dict[str, int]
    by_owner: list[ComplianceRatesByOwner]
    by_category: list[ComplianceRatesByCategory]
    contracts: list[ComplianceRatesByContract]
    overdue_count: int
    critical_overdue: int
    upcoming_7_days: int
