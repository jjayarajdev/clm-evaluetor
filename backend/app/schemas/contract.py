"""Pydantic schemas for contracts."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.models.contract import ContractStatus, ContractType, RiskLevel


class ContractUploadResponse(BaseModel):
    """Response for single file upload."""

    id: str
    filename: str
    status: str
    message: str


class BatchUploadResponse(BaseModel):
    """Response for batch file upload."""

    batch_id: str
    total_files: int
    accepted: int
    rejected: int
    files: list[ContractUploadResponse]


class UploadStatusResponse(BaseModel):
    """Response for upload status check."""

    batch_id: str
    total: int
    pending: int
    processing: int
    completed: int
    failed: int
    contracts: list["ContractSummary"]


class ContractSummary(BaseModel):
    """Brief contract summary for lists."""

    id: str
    filename: str
    contract_type: str | None
    counterparty: str | None
    status: str
    risk_level: str | None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class ContractResponse(BaseModel):
    """Full contract response."""

    id: str
    filename: str
    file_path: str
    file_size: int | None
    mime_type: str | None

    # Extracted metadata
    contract_type: str | None
    counterparty: str | None
    effective_date: date | None
    expiration_date: date | None
    contract_value: Decimal | None
    currency: str | None
    jurisdiction: str | None

    # Risk
    risk_score: int | None
    risk_level: str | None

    # Renewal
    auto_renewal: bool | None
    notice_period_days: int | None
    renewal_term_months: int | None

    # Status
    status: str
    processing_error: str | None

    # Schema extraction
    schema_id: str | None = None
    schema_data: dict[str, Any] | None = None

    # Relationships
    uploaded_by: str
    clause_count: int = 0
    obligation_count: int = 0

    # Timestamps
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContractListResponse(BaseModel):
    """Paginated contract list response."""

    contracts: list[ContractSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class ContractFilter(BaseModel):
    """Contract filter options."""

    contract_type: ContractType | None = None
    counterparty: str | None = None
    risk_level: RiskLevel | None = None
    status: ContractStatus | None = None
    expiration_before: date | None = None
    expiration_after: date | None = None
    search: str | None = None


# Update forward references
UploadStatusResponse.model_rebuild()
