"""Pydantic schemas for Contract Document endpoints."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field


# ===== Document Signature Schemas =====

class DocumentSignatureCreate(BaseModel):
    """Schema for adding a signature record to a document."""
    signer_name: str = Field(..., max_length=255)
    signer_title: Optional[str] = Field(None, max_length=255)
    signer_organization: Optional[str] = Field(None, max_length=255)
    signer_email: Optional[str] = Field(None, max_length=255)
    signed_date: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    signature_type: str = Field("electronic", description="One of: wet_ink, digital, electronic, stamp")
    signature_status: str = Field("pending", description="One of: pending, signed, declined, expired")
    notes: Optional[str] = None


class DocumentSignatureUpdate(BaseModel):
    """Schema for updating a signature record."""
    signer_name: Optional[str] = Field(None, max_length=255)
    signer_title: Optional[str] = Field(None, max_length=255)
    signer_organization: Optional[str] = Field(None, max_length=255)
    signer_email: Optional[str] = Field(None, max_length=255)
    signed_date: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    signature_type: Optional[str] = Field(None, description="One of: wet_ink, digital, electronic, stamp")
    signature_status: Optional[str] = Field(None, description="One of: pending, signed, declined, expired")
    notes: Optional[str] = None


class DocumentSignatureResponse(BaseModel):
    """Response schema for a document signature."""
    id: UUID
    document_id: UUID
    signer_name: str
    signer_title: Optional[str] = None
    signer_organization: Optional[str] = None
    signer_email: Optional[str] = None
    signed_date: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    signature_type: str
    signature_status: str
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Document Section Schemas =====

class DocumentSectionCreate(BaseModel):
    """Schema for adding a section to a document."""
    parent_section_id: Optional[UUID] = None
    section_number: Optional[str] = Field(None, max_length=50)
    title: str = Field(..., max_length=500)
    content_summary: Optional[str] = None
    page_start: Optional[int] = Field(None, ge=1)
    page_end: Optional[int] = Field(None, ge=1)
    order_index: int = 0


class DocumentSectionResponse(BaseModel):
    """Response schema for a document section."""
    id: UUID
    document_id: UUID
    parent_section_id: Optional[UUID] = None
    section_number: Optional[str] = None
    title: str
    content_summary: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    order_index: int
    created_at: datetime
    sub_sections: List["DocumentSectionResponse"] = []

    class Config:
        from_attributes = True


# ===== Contract Document Schemas =====

class ContractDocumentCreate(BaseModel):
    """Schema for adding a document to a contract."""
    document_type: str = Field(
        "other",
        description="One of: main_agreement, amendment, addendum, schedule, exhibit, statement_of_work, side_letter, appendix, certificate, other",
    )
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    language: str = Field("en", max_length=10)
    version: Optional[str] = Field(None, max_length=20)
    file_path: Optional[str] = Field(None, max_length=500)
    file_size: Optional[int] = Field(None, ge=0)
    mime_type: Optional[str] = Field(None, max_length=100)


class ContractDocumentUpdate(BaseModel):
    """Schema for updating a contract document."""
    document_type: Optional[str] = Field(
        None,
        description="One of: main_agreement, amendment, addendum, schedule, exhibit, statement_of_work, side_letter, appendix, certificate, other",
    )
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    language: Optional[str] = Field(None, max_length=10)
    version: Optional[str] = Field(None, max_length=20)
    file_path: Optional[str] = Field(None, max_length=500)
    file_size: Optional[int] = Field(None, ge=0)
    mime_type: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class ContractDocumentResponse(BaseModel):
    """Response schema for a contract document."""
    id: UUID
    tenant_id: UUID
    contract_id: UUID
    document_type: str
    title: str
    description: Optional[str] = None
    language: str
    version: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    upload_date: datetime
    is_active: bool
    created_at: datetime
    updated_at: datetime
    signatures: List[DocumentSignatureResponse] = []
    sections: List[DocumentSectionResponse] = []

    class Config:
        from_attributes = True


class ContractDocumentListResponse(BaseModel):
    """Paginated list of contract documents."""
    items: List[ContractDocumentResponse]
    total: int
    page: int
    page_size: int
    pages: int


# Rebuild models for forward reference resolution
DocumentSectionResponse.model_rebuild()
