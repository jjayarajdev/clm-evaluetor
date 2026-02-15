"""Pydantic schemas for Amendment and Version Tracking."""

from datetime import date, datetime
from pydantic import BaseModel, Field
from typing import Literal


class AmendmentCreate(BaseModel):
    """Request to link an amendment to a parent contract."""

    child_contract_id: str  # The amendment contract ID
    link_type: Literal[
        "amendment", "addendum", "change_order",
        "modification", "renewal", "supersedes"
    ] = "amendment"
    effective_date: date | None = None
    reference_number: str | None = Field(None, max_length=100)  # e.g., "Amendment #3"
    description: str | None = Field(None, max_length=500)
    notes: str | None = None


class AmendmentResponse(BaseModel):
    """Response for an amendment/version link."""

    link_id: str
    parent_contract_id: str
    parent_filename: str
    child_contract_id: str
    child_filename: str
    link_type: str
    effective_date: date | None
    reference_number: str | None
    sequence_number: int | None
    description: str | None
    is_active: bool
    created_at: datetime


class VersionInfo(BaseModel):
    """Version information for a contract."""

    contract_id: str
    filename: str
    version_number: int  # Calculated from sequence
    version_label: str | None  # e.g., "Amendment #3" or "Original"
    effective_date: date | None
    link_type: str | None  # None for original
    is_current: bool
    is_superseded: bool
    created_at: datetime

    # Key metadata snapshot
    contract_value: float | None
    expiration_date: date | None
    counterparty: str | None


class VersionHistoryResponse(BaseModel):
    """Complete version history for a contract family."""

    original_contract_id: str
    original_filename: str
    current_version: int
    total_versions: int
    versions: list[VersionInfo]


class FieldChange(BaseModel):
    """A single field change between versions."""

    field_name: str
    field_label: str  # Human-readable label
    old_value: str | None
    new_value: str | None
    change_type: Literal["added", "removed", "modified"]


class VersionDiff(BaseModel):
    """Differences between two contract versions."""

    base_contract_id: str
    base_filename: str
    base_version: int

    compare_contract_id: str
    compare_filename: str
    compare_version: int

    # Summary
    total_changes: int
    fields_added: int
    fields_removed: int
    fields_modified: int

    # Detailed changes
    changes: list[FieldChange]

    # Change categories
    metadata_changes: list[FieldChange]
    financial_changes: list[FieldChange]
    term_changes: list[FieldChange]
    party_changes: list[FieldChange]


class AuditEntry(BaseModel):
    """A single audit trail entry."""

    timestamp: datetime
    action: str
    actor: str | None
    details: str | None
    contract_id: str
    contract_filename: str

    # Change details
    field_changes: list[FieldChange] | None
    version_info: str | None


class AuditTrailResponse(BaseModel):
    """Complete audit trail for a contract and its versions."""

    contract_id: str
    filename: str
    total_entries: int
    entries: list[AuditEntry]

    # Linked contracts included
    includes_amendments: bool
    amendment_count: int


class SupersedeRequest(BaseModel):
    """Request to mark a contract as superseded."""

    superseding_contract_id: str
    effective_date: date | None = None
    notes: str | None = None


class AmendmentSummary(BaseModel):
    """AI-extracted summary of what changed in an amendment."""

    amendment_contract_id: str
    parent_contract_id: str

    # Summary
    change_summary: str
    key_changes: list[str]

    # Categorized changes
    scope_changes: list[str]
    financial_changes: list[str]
    term_changes: list[str]
    obligation_changes: list[str]

    # Impact assessment
    impact_level: Literal["minor", "moderate", "major"]
    requires_review: bool
