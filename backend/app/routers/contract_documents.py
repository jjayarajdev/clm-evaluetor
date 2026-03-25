"""API endpoints for Contract Document management.

Manages documents within a contract package: main agreements, amendments,
addenda, schedules, exhibits, SOWs, etc. Includes signature tracking
and hierarchical section outlines.
"""

from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.deps import (
    CurrentTenantId,
    RequiredTenantId,
    get_current_user,
    require_role,
)
from app.models import User, Role
from app.models.contract import Contract
from app.models.contract_document import (
    ContractDocument,
    DocumentSignature,
    DocumentSection,
    DocumentType,
    SignatureType,
    SignatureStatus,
)
from app.schemas.contract_document import (
    ContractDocumentCreate,
    ContractDocumentUpdate,
    ContractDocumentResponse,
    ContractDocumentListResponse,
    DocumentSignatureCreate,
    DocumentSignatureUpdate,
    DocumentSignatureResponse,
    DocumentSectionCreate,
    DocumentSectionResponse,
)

router = APIRouter(
    prefix="/api/contracts/{contract_id}/documents",
    tags=["Contract Documents"],
)


# ===== Helpers =====

async def _get_contract_or_404(
    contract_id: UUID,
    tenant_id: UUID,
    db: AsyncSession,
) -> Contract:
    """Fetch a contract by ID within the tenant, or raise 404."""
    query = select(Contract).where(
        Contract.id == contract_id,
        Contract.tenant_id == tenant_id,
    )
    result = await db.execute(query)
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found",
        )
    return contract


async def _get_document_or_404(
    doc_id: UUID,
    contract_id: UUID,
    tenant_id: UUID,
    db: AsyncSession,
) -> ContractDocument:
    """Fetch a document by ID within the contract and tenant, or raise 404."""
    query = select(ContractDocument).where(
        ContractDocument.id == doc_id,
        ContractDocument.contract_id == contract_id,
        ContractDocument.tenant_id == tenant_id,
    )
    result = await db.execute(query)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return doc


def _validate_document_type(value: str) -> str:
    """Validate that a document_type string is a valid DocumentType value."""
    valid = {e.value for e in DocumentType}
    if value not in valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document_type '{value}'. Must be one of: {sorted(valid)}",
        )
    return value


def _validate_signature_type(value: str) -> str:
    """Validate that a signature_type string is a valid SignatureType value."""
    valid = {e.value for e in SignatureType}
    if value not in valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid signature_type '{value}'. Must be one of: {sorted(valid)}",
        )
    return value


def _validate_signature_status(value: str) -> str:
    """Validate that a signature_status string is a valid SignatureStatus value."""
    valid = {e.value for e in SignatureStatus}
    if value not in valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid signature_status '{value}'. Must be one of: {sorted(valid)}",
        )
    return value


# ===== Document Endpoints =====

@router.get("", response_model=ContractDocumentListResponse)
async def list_documents(
    contract_id: UUID,
    tenant_id: RequiredTenantId,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    document_type: Optional[str] = None,
    is_active: Optional[bool] = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List documents for a contract with optional filtering and pagination."""
    # Verify contract exists and belongs to tenant
    await _get_contract_or_404(contract_id, tenant_id, db)

    query = select(ContractDocument).where(
        ContractDocument.contract_id == contract_id,
        ContractDocument.tenant_id == tenant_id,
    )

    # Apply filters
    if document_type is not None:
        _validate_document_type(document_type)
        query = query.where(ContractDocument.document_type == document_type)

    if is_active is not None:
        query = query.where(ContractDocument.is_active == is_active)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(
        ContractDocument.upload_date.desc()
    )

    result = await db.execute(query)
    items = result.scalars().all()

    return ContractDocumentListResponse(
        items=[ContractDocumentResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


@router.post("", response_model=ContractDocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    contract_id: UUID,
    data: ContractDocumentCreate,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.LEGAL)),
):
    """Add a document to a contract. Requires ADMIN or LEGAL role."""
    # Verify contract exists and belongs to tenant
    await _get_contract_or_404(contract_id, tenant_id, db)

    # Validate enum value
    _validate_document_type(data.document_type)

    doc = ContractDocument(
        tenant_id=tenant_id,
        contract_id=contract_id,
        **data.model_dump(),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    return ContractDocumentResponse.model_validate(doc)


@router.get("/{doc_id}", response_model=ContractDocumentResponse)
async def get_document(
    contract_id: UUID,
    doc_id: UUID,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific document by ID."""
    doc = await _get_document_or_404(doc_id, contract_id, tenant_id, db)
    return ContractDocumentResponse.model_validate(doc)


@router.put("/{doc_id}", response_model=ContractDocumentResponse)
async def update_document(
    contract_id: UUID,
    doc_id: UUID,
    data: ContractDocumentUpdate,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.LEGAL)),
):
    """Update a document. Requires ADMIN or LEGAL role."""
    doc = await _get_document_or_404(doc_id, contract_id, tenant_id, db)

    update_data = data.model_dump(exclude_unset=True)

    # Validate document_type if being updated
    if "document_type" in update_data:
        _validate_document_type(update_data["document_type"])

    for field, value in update_data.items():
        setattr(doc, field, value)

    await db.commit()
    await db.refresh(doc)

    return ContractDocumentResponse.model_validate(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    contract_id: UUID,
    doc_id: UUID,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.LEGAL)),
):
    """Soft-delete a document (sets is_active = False). Requires ADMIN or LEGAL role."""
    doc = await _get_document_or_404(doc_id, contract_id, tenant_id, db)
    doc.is_active = False
    await db.commit()


# ===== Signature Endpoints =====

@router.get("/{doc_id}/signatures", response_model=list[DocumentSignatureResponse])
async def list_signatures(
    contract_id: UUID,
    doc_id: UUID,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all signatures for a document."""
    doc = await _get_document_or_404(doc_id, contract_id, tenant_id, db)

    query = select(DocumentSignature).where(
        DocumentSignature.document_id == doc.id,
    ).order_by(DocumentSignature.created_at)

    result = await db.execute(query)
    sigs = result.scalars().all()

    return [DocumentSignatureResponse.model_validate(s) for s in sigs]


@router.post(
    "/{doc_id}/signatures",
    response_model=DocumentSignatureResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_signature(
    contract_id: UUID,
    doc_id: UUID,
    data: DocumentSignatureCreate,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.LEGAL)),
):
    """Add a signature record to a document. Requires ADMIN or LEGAL role."""
    doc = await _get_document_or_404(doc_id, contract_id, tenant_id, db)

    _validate_signature_type(data.signature_type)
    _validate_signature_status(data.signature_status)

    sig = DocumentSignature(
        document_id=doc.id,
        **data.model_dump(),
    )
    db.add(sig)
    await db.commit()
    await db.refresh(sig)

    return DocumentSignatureResponse.model_validate(sig)


@router.put(
    "/{doc_id}/signatures/{sig_id}",
    response_model=DocumentSignatureResponse,
)
async def update_signature(
    contract_id: UUID,
    doc_id: UUID,
    sig_id: UUID,
    data: DocumentSignatureUpdate,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.LEGAL)),
):
    """Update a signature record (e.g., mark as signed). Requires ADMIN or LEGAL role."""
    # Verify document chain
    await _get_document_or_404(doc_id, contract_id, tenant_id, db)

    query = select(DocumentSignature).where(
        DocumentSignature.id == sig_id,
        DocumentSignature.document_id == doc_id,
    )
    result = await db.execute(query)
    sig = result.scalar_one_or_none()

    if not sig:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signature not found",
        )

    update_data = data.model_dump(exclude_unset=True)

    if "signature_type" in update_data:
        _validate_signature_type(update_data["signature_type"])
    if "signature_status" in update_data:
        _validate_signature_status(update_data["signature_status"])

    for field, value in update_data.items():
        setattr(sig, field, value)

    await db.commit()
    await db.refresh(sig)

    return DocumentSignatureResponse.model_validate(sig)


# ===== Section Endpoints =====

@router.get("/{doc_id}/sections", response_model=list[DocumentSectionResponse])
async def list_sections(
    contract_id: UUID,
    doc_id: UUID,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List sections for a document in hierarchical structure.

    Returns only top-level sections; sub-sections are nested within
    their parent via the sub_sections field.
    """
    doc = await _get_document_or_404(doc_id, contract_id, tenant_id, db)

    # Fetch only top-level sections (no parent)
    query = select(DocumentSection).where(
        DocumentSection.document_id == doc.id,
        DocumentSection.parent_section_id.is_(None),
    ).order_by(DocumentSection.order_index)

    result = await db.execute(query)
    sections = result.scalars().all()

    return [DocumentSectionResponse.model_validate(s) for s in sections]


@router.post(
    "/{doc_id}/sections",
    response_model=DocumentSectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_section(
    contract_id: UUID,
    doc_id: UUID,
    data: DocumentSectionCreate,
    tenant_id: RequiredTenantId,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.ADMIN, Role.LEGAL)),
):
    """Add a section to a document. Requires ADMIN or LEGAL role."""
    doc = await _get_document_or_404(doc_id, contract_id, tenant_id, db)

    # Validate parent_section_id if provided
    if data.parent_section_id:
        parent_query = select(DocumentSection).where(
            DocumentSection.id == data.parent_section_id,
            DocumentSection.document_id == doc.id,
        )
        parent = (await db.execute(parent_query)).scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent section not found in this document",
            )

    section = DocumentSection(
        document_id=doc.id,
        **data.model_dump(),
    )
    db.add(section)
    await db.commit()
    await db.refresh(section)

    return DocumentSectionResponse.model_validate(section)
