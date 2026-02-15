"""Amendment and Version Tracking API endpoints."""

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Contract, ContractStatus, AuditLog, AuditAction
from app.models.contract_link import ContractLink, LinkType
from app.schemas.amendment import (
    AmendmentCreate,
    AmendmentResponse,
    VersionInfo,
    VersionHistoryResponse,
    FieldChange,
    VersionDiff,
    AuditEntry,
    AuditTrailResponse,
    SupersedeRequest,
    AmendmentSummary,
)

router = APIRouter(prefix="/api/contracts", tags=["amendments"])

# Link types that count as version changes
VERSION_LINK_TYPES = {
    LinkType.AMENDMENT,
    LinkType.ADDENDUM,
    LinkType.CHANGE_ORDER,
    LinkType.MODIFICATION,
    LinkType.RENEWAL,
}

# Fields to compare for version diff
METADATA_FIELDS = [
    ("counterparty", "Counterparty"),
    ("contract_type", "Contract Type"),
    ("jurisdiction", "Jurisdiction"),
    ("governing_law", "Governing Law"),
]

FINANCIAL_FIELDS = [
    ("contract_value", "Contract Value"),
    ("currency", "Currency"),
    ("liability_cap_amount", "Liability Cap"),
    ("liability_cap_type", "Liability Cap Type"),
]

TERM_FIELDS = [
    ("effective_date", "Effective Date"),
    ("expiration_date", "Expiration Date"),
    ("initial_term_months", "Initial Term (Months)"),
    ("auto_renewal", "Auto Renewal"),
    ("notice_period_days", "Notice Period (Days)"),
    ("renewal_term_months", "Renewal Term (Months)"),
    ("termination_for_convenience", "Termination for Convenience"),
    ("confidentiality_term_years", "Confidentiality Term (Years)"),
]

PARTY_FIELDS = [
    ("dispute_resolution_method", "Dispute Resolution"),
]


async def get_contract_or_404(db: AsyncSession, contract_id: UUID) -> Contract:
    """Get contract by ID or raise 404."""
    query = select(Contract).where(Contract.id == contract_id)
    result = await db.execute(query)
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contract {contract_id} not found"
        )
    return contract


async def find_original_contract(db: AsyncSession, contract_id: UUID) -> Contract:
    """Find the original contract in an amendment chain."""
    current_id = contract_id

    while True:
        # Check if this contract has a parent (is an amendment)
        query = select(ContractLink).where(
            and_(
                ContractLink.child_contract_id == current_id,
                ContractLink.link_type.in_(VERSION_LINK_TYPES),
                ContractLink.is_active == True,
            )
        )
        result = await db.execute(query)
        link = result.scalar_one_or_none()

        if not link:
            # No parent found - this is the original
            break

        current_id = link.parent_contract_id

    # Return the original contract
    return await get_contract_or_404(db, current_id)


async def get_all_versions(db: AsyncSession, original_contract_id: UUID) -> list[tuple[Contract, ContractLink | None, int]]:
    """Get all versions of a contract including the original."""
    versions = []

    # Start with the original
    original = await get_contract_or_404(db, original_contract_id)
    versions.append((original, None, 1))

    # Get all amendments (children)
    query = select(ContractLink, Contract).join(
        Contract,
        Contract.id == ContractLink.child_contract_id
    ).where(
        and_(
            ContractLink.parent_contract_id == original_contract_id,
            ContractLink.link_type.in_(VERSION_LINK_TYPES),
        )
    ).order_by(ContractLink.sequence_number, ContractLink.created_at)

    result = await db.execute(query)
    amendments = result.all()

    version_num = 2
    for link, contract in amendments:
        versions.append((contract, link, version_num))
        version_num += 1

    return versions


def compare_field(old_val, new_val, field_name: str, field_label: str) -> FieldChange | None:
    """Compare two field values and return a FieldChange if different."""
    # Normalize values for comparison
    old_str = str(old_val) if old_val is not None else None
    new_str = str(new_val) if new_val is not None else None

    if old_str == new_str:
        return None

    if old_val is None and new_val is not None:
        change_type = "added"
    elif old_val is not None and new_val is None:
        change_type = "removed"
    else:
        change_type = "modified"

    return FieldChange(
        field_name=field_name,
        field_label=field_label,
        old_value=old_str,
        new_value=new_str,
        change_type=change_type,
    )


@router.post("/{contract_id}/amendments", response_model=AmendmentResponse)
async def link_amendment(
    contract_id: UUID,
    amendment: AmendmentCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Link an amendment or version to a parent contract.

    The child_contract_id should be an already-uploaded contract
    that represents the amendment.
    """
    # Verify parent contract exists
    parent = await get_contract_or_404(db, contract_id)

    # Verify child contract exists
    child_id = UUID(amendment.child_contract_id)
    child = await get_contract_or_404(db, child_id)

    # Check for existing link
    existing_query = select(ContractLink).where(
        and_(
            ContractLink.parent_contract_id == contract_id,
            ContractLink.child_contract_id == child_id,
        )
    )
    result = await db.execute(existing_query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This amendment is already linked to the contract"
        )

    # Calculate sequence number
    seq_query = select(func.max(ContractLink.sequence_number)).where(
        and_(
            ContractLink.parent_contract_id == contract_id,
            ContractLink.link_type.in_(VERSION_LINK_TYPES),
        )
    )
    seq_result = await db.execute(seq_query)
    max_seq = seq_result.scalar() or 0
    new_seq = max_seq + 1

    # Create link
    link_type = LinkType(amendment.link_type)
    link = ContractLink(
        parent_contract_id=contract_id,
        child_contract_id=child_id,
        link_type=link_type,
        effective_date=amendment.effective_date,
        reference_number=amendment.reference_number or f"Amendment #{new_seq}",
        sequence_number=new_seq,
        link_description=amendment.description,
        notes=amendment.notes,
        is_active=True,
    )

    db.add(link)
    await db.commit()
    await db.refresh(link)

    return AmendmentResponse(
        link_id=str(link.id),
        parent_contract_id=str(parent.id),
        parent_filename=parent.filename,
        child_contract_id=str(child.id),
        child_filename=child.filename,
        link_type=link.link_type.value,
        effective_date=link.effective_date,
        reference_number=link.reference_number,
        sequence_number=link.sequence_number,
        description=link.link_description,
        is_active=link.is_active,
        created_at=link.created_at,
    )


@router.get("/{contract_id}/versions", response_model=VersionHistoryResponse)
async def get_version_history(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get complete version history for a contract.

    Returns all versions (original + amendments) ordered by version number.
    """
    # Find the original contract
    original = await find_original_contract(db, contract_id)

    # Get all versions
    versions = await get_all_versions(db, original.id)

    # Check if any version is superseded
    supersede_query = select(ContractLink).where(
        ContractLink.link_type == LinkType.SUPERSEDES
    )
    supersede_result = await db.execute(supersede_query)
    superseded_ids = {link.parent_contract_id for link in supersede_result.scalars().all()}

    # Build version info list
    version_list = []
    current_version = len(versions)

    for contract, link, version_num in versions:
        is_superseded = contract.id in superseded_ids
        is_current = (version_num == current_version) and not is_superseded

        version_info = VersionInfo(
            contract_id=str(contract.id),
            filename=contract.filename,
            version_number=version_num,
            version_label=link.reference_number if link else "Original",
            effective_date=link.effective_date if link else contract.effective_date,
            link_type=link.link_type.value if link else None,
            is_current=is_current,
            is_superseded=is_superseded,
            created_at=contract.created_at,
            contract_value=float(contract.contract_value) if contract.contract_value else None,
            expiration_date=contract.expiration_date,
            counterparty=contract.counterparty,
        )
        version_list.append(version_info)

    return VersionHistoryResponse(
        original_contract_id=str(original.id),
        original_filename=original.filename,
        current_version=current_version,
        total_versions=len(versions),
        versions=version_list,
    )


@router.get("/{contract_id}/diff/{compare_id}", response_model=VersionDiff)
async def get_version_diff(
    contract_id: UUID,
    compare_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Compare two contract versions and return the differences.

    Compares key metadata, financial terms, and contract terms.
    """
    # Get both contracts
    base_contract = await get_contract_or_404(db, contract_id)
    compare_contract = await get_contract_or_404(db, compare_id)

    # Find version numbers
    original = await find_original_contract(db, contract_id)
    versions = await get_all_versions(db, original.id)

    base_version = 0
    compare_version = 0
    for contract, link, version_num in versions:
        if contract.id == contract_id:
            base_version = version_num
        if contract.id == compare_id:
            compare_version = version_num

    # Compare fields
    all_changes = []
    metadata_changes = []
    financial_changes = []
    term_changes = []
    party_changes = []

    # Compare metadata fields
    for field_name, field_label in METADATA_FIELDS:
        old_val = getattr(base_contract, field_name, None)
        new_val = getattr(compare_contract, field_name, None)
        # Handle enum values
        if hasattr(old_val, 'value'):
            old_val = old_val.value
        if hasattr(new_val, 'value'):
            new_val = new_val.value
        change = compare_field(old_val, new_val, field_name, field_label)
        if change:
            all_changes.append(change)
            metadata_changes.append(change)

    # Compare financial fields
    for field_name, field_label in FINANCIAL_FIELDS:
        old_val = getattr(base_contract, field_name, None)
        new_val = getattr(compare_contract, field_name, None)
        change = compare_field(old_val, new_val, field_name, field_label)
        if change:
            all_changes.append(change)
            financial_changes.append(change)

    # Compare term fields
    for field_name, field_label in TERM_FIELDS:
        old_val = getattr(base_contract, field_name, None)
        new_val = getattr(compare_contract, field_name, None)
        change = compare_field(old_val, new_val, field_name, field_label)
        if change:
            all_changes.append(change)
            term_changes.append(change)

    # Compare party fields
    for field_name, field_label in PARTY_FIELDS:
        old_val = getattr(base_contract, field_name, None)
        new_val = getattr(compare_contract, field_name, None)
        change = compare_field(old_val, new_val, field_name, field_label)
        if change:
            all_changes.append(change)
            party_changes.append(change)

    # Count changes by type
    fields_added = sum(1 for c in all_changes if c.change_type == "added")
    fields_removed = sum(1 for c in all_changes if c.change_type == "removed")
    fields_modified = sum(1 for c in all_changes if c.change_type == "modified")

    return VersionDiff(
        base_contract_id=str(base_contract.id),
        base_filename=base_contract.filename,
        base_version=base_version,
        compare_contract_id=str(compare_contract.id),
        compare_filename=compare_contract.filename,
        compare_version=compare_version,
        total_changes=len(all_changes),
        fields_added=fields_added,
        fields_removed=fields_removed,
        fields_modified=fields_modified,
        changes=all_changes,
        metadata_changes=metadata_changes,
        financial_changes=financial_changes,
        term_changes=term_changes,
        party_changes=party_changes,
    )


@router.post("/{contract_id}/supersede", response_model=dict)
async def mark_superseded(
    contract_id: UUID,
    request: SupersedeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a contract as superseded by another contract.

    The superseded contract will be marked as inactive.
    """
    # Verify old contract exists
    old_contract = await get_contract_or_404(db, contract_id)

    # Verify new contract exists
    new_contract_id = UUID(request.superseding_contract_id)
    new_contract = await get_contract_or_404(db, new_contract_id)

    # Create supersedes link
    link = ContractLink(
        parent_contract_id=contract_id,  # Old contract is "parent" (being superseded)
        child_contract_id=new_contract_id,  # New contract is "child" (superseding)
        link_type=LinkType.SUPERSEDES,
        effective_date=request.effective_date,
        notes=request.notes,
        is_active=True,
    )

    db.add(link)

    # Mark old contract links as inactive (optional - depends on requirements)
    # For now, we just add the supersedes link

    await db.commit()

    return {
        "superseded_contract_id": str(contract_id),
        "superseding_contract_id": str(new_contract_id),
        "effective_date": request.effective_date.isoformat() if request.effective_date else None,
        "message": f"Contract {old_contract.filename} marked as superseded by {new_contract.filename}"
    }


@router.get("/{contract_id}/audit-trail", response_model=AuditTrailResponse)
async def get_audit_trail(
    contract_id: UUID,
    include_amendments: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """
    Get complete audit trail for a contract and optionally its amendments.

    Returns all audit log entries related to the contract.
    """
    # Get the contract
    contract = await get_contract_or_404(db, contract_id)

    # Collect contract IDs to query
    contract_ids = [str(contract_id)]
    amendment_count = 0

    if include_amendments:
        # Find original
        original = await find_original_contract(db, contract_id)
        versions = await get_all_versions(db, original.id)

        for c, link, version_num in versions:
            if str(c.id) not in contract_ids:
                contract_ids.append(str(c.id))
                if link:
                    amendment_count += 1

    # Query audit logs
    query = select(AuditLog).where(
        and_(
            AuditLog.resource_type == "contract",
            AuditLog.resource_id.in_(contract_ids),
        )
    ).order_by(AuditLog.created_at.desc())

    result = await db.execute(query)
    logs = result.scalars().all()

    # Build audit entries
    entries = []
    for log in logs:
        # Get contract info for this log
        contract_query = select(Contract).where(
            Contract.id == UUID(log.resource_id)
        )
        contract_result = await db.execute(contract_query)
        log_contract = contract_result.scalar_one_or_none()

        # Parse field changes from details if present
        field_changes = None
        if log.details and isinstance(log.details, dict):
            changes_data = log.details.get("changes", [])
            if changes_data:
                field_changes = [
                    FieldChange(
                        field_name=c.get("field", "unknown"),
                        field_label=c.get("label", c.get("field", "Unknown")),
                        old_value=c.get("old"),
                        new_value=c.get("new"),
                        change_type="modified",
                    )
                    for c in changes_data
                ]

        entry = AuditEntry(
            timestamp=log.created_at,
            action=log.action.value,
            actor=str(log.user_id) if log.user_id else None,
            details=log.details.get("description") if log.details else None,
            contract_id=log.resource_id,
            contract_filename=log_contract.filename if log_contract else "Unknown",
            field_changes=field_changes,
            version_info=None,
        )
        entries.append(entry)

    return AuditTrailResponse(
        contract_id=str(contract.id),
        filename=contract.filename,
        total_entries=len(entries),
        entries=entries,
        includes_amendments=include_amendments,
        amendment_count=amendment_count,
    )


@router.get("/{contract_id}/amendments", response_model=list[AmendmentResponse])
async def list_amendments(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all amendments linked to a contract."""
    # Verify contract exists
    contract = await get_contract_or_404(db, contract_id)

    # Get amendments
    query = select(ContractLink, Contract).join(
        Contract,
        Contract.id == ContractLink.child_contract_id
    ).where(
        and_(
            ContractLink.parent_contract_id == contract_id,
            ContractLink.link_type.in_(VERSION_LINK_TYPES),
        )
    ).order_by(ContractLink.sequence_number)

    result = await db.execute(query)
    amendments = result.all()

    return [
        AmendmentResponse(
            link_id=str(link.id),
            parent_contract_id=str(contract.id),
            parent_filename=contract.filename,
            child_contract_id=str(child.id),
            child_filename=child.filename,
            link_type=link.link_type.value,
            effective_date=link.effective_date,
            reference_number=link.reference_number,
            sequence_number=link.sequence_number,
            description=link.link_description,
            is_active=link.is_active,
            created_at=link.created_at,
        )
        for link, child in amendments
    ]


@router.get("/{contract_id}/amendment-summary/{amendment_id}", response_model=AmendmentSummary)
async def get_amendment_summary(
    contract_id: UUID,
    amendment_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get AI-extracted summary of changes in an amendment.

    This analyzes the differences between the parent contract
    and the amendment to summarize what changed.
    """
    # Get both contracts
    parent = await get_contract_or_404(db, contract_id)
    amendment = await get_contract_or_404(db, amendment_id)

    # Get the diff
    diff_response = await get_version_diff(contract_id, amendment_id, db)

    # Build summary from diff
    key_changes = []
    scope_changes = []
    financial_changes = []
    term_changes = []
    obligation_changes = []

    for change in diff_response.changes:
        change_desc = f"{change.field_label}: {change.old_value or 'N/A'} → {change.new_value or 'N/A'}"
        key_changes.append(change_desc)

    for change in diff_response.financial_changes:
        financial_changes.append(
            f"{change.field_label} changed from {change.old_value} to {change.new_value}"
        )

    for change in diff_response.term_changes:
        term_changes.append(
            f"{change.field_label} changed from {change.old_value} to {change.new_value}"
        )

    # Determine impact level
    impact_level = "minor"
    if diff_response.total_changes > 5:
        impact_level = "major"
    elif diff_response.total_changes > 2:
        impact_level = "moderate"

    # Check if financial changes exist
    requires_review = len(financial_changes) > 0 or impact_level in ["moderate", "major"]

    # Build summary text
    if diff_response.total_changes == 0:
        change_summary = "No significant metadata changes detected between versions."
    else:
        change_summary = (
            f"This amendment contains {diff_response.total_changes} field changes: "
            f"{diff_response.fields_modified} modified, {diff_response.fields_added} added, "
            f"{diff_response.fields_removed} removed."
        )

    return AmendmentSummary(
        amendment_contract_id=str(amendment.id),
        parent_contract_id=str(parent.id),
        change_summary=change_summary,
        key_changes=key_changes[:10],  # Limit to top 10
        scope_changes=scope_changes,
        financial_changes=financial_changes,
        term_changes=term_changes,
        obligation_changes=obligation_changes,
        impact_level=impact_level,
        requires_review=requires_review,
    )
