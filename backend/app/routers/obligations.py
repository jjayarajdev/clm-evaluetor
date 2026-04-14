"""Obligations router for compliance workflow management."""

import uuid as uuid_mod
from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, CurrentTenantId
from app.database import get_db
from app.models.obligation import (
    Obligation,
    ObligationStatus,
    RAGStatus,
    ObligationOwner,
    ObligationCategory,
)
from app.models.contract import Contract
from app.schemas.obligation import (
    ObligationStatusUpdate,
    ObligationRAGUpdate,
    ObligationOwnerUpdate,
    ObligationEvidenceUpload,
    ObligationResponse,
    ComplianceRatesResponse,
    ComplianceRatesByContract,
    ComplianceRatesByOwner,
    ComplianceRatesByCategory,
)

router = APIRouter(prefix="/api/obligations", tags=["Obligations"])


def apply_tenant_filter(query, tenant_id):
    """Apply tenant filter to an Obligation query through its parent Contract."""
    if tenant_id is not None:
        # Filter by joining with Contract and checking tenant_id
        return query.join(Contract, Obligation.contract_id == Contract.id).where(Contract.tenant_id == tenant_id)
    return query


def obligation_to_response(obl: Obligation) -> ObligationResponse:
    """Convert Obligation model to response schema."""
    return ObligationResponse(
        id=str(obl.id),
        contract_id=str(obl.contract_id),
        description=obl.description,
        obligation_type=obl.obligation_type.value if obl.obligation_type else "other",
        status=obl.status.value if obl.status else "pending",
        rag_status=obl.rag_status.value if obl.rag_status else None,
        owner_type=obl.owner_type.value if obl.owner_type else None,
        category=obl.category.value if obl.category else None,
        frequency=obl.frequency.value if obl.frequency else None,
        deadline=obl.deadline,
        deadline_type=obl.deadline_type.value if obl.deadline_type else None,
        obligated_party=obl.obligated_party,
        beneficiary_party=obl.beneficiary_party,
        is_critical=obl.is_critical,
        priority=obl.priority,
        compliance_notes=obl.compliance_notes,
        compliance_evidence=obl.compliance_evidence,
        last_compliance_date=obl.last_compliance_date,
        next_compliance_due=obl.next_compliance_due,
        section_reference=obl.section_reference,
        source_text=obl.source_text,
        consequence_of_breach=obl.consequence_of_breach,
        created_at=obl.created_at,
        updated_at=obl.updated_at,
    )


@router.get("/{obligation_id}", response_model=ObligationResponse)
async def get_obligation(
    obligation_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ObligationResponse:
    """Get a single obligation by ID."""
    query = select(Obligation).where(Obligation.id == uuid_mod.UUID(obligation_id))
    query = apply_tenant_filter(query, tenant_id)
    result = await db.execute(query)
    obligation = result.scalar_one_or_none()

    if not obligation:
        raise HTTPException(status_code=404, detail="Obligation not found")

    return obligation_to_response(obligation)


@router.put("/{obligation_id}/status", response_model=ObligationResponse)
async def update_obligation_status(
    obligation_id: str,
    update: ObligationStatusUpdate,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ObligationResponse:
    """Update the status of an obligation."""
    query = select(Obligation).where(Obligation.id == uuid_mod.UUID(obligation_id))
    query = apply_tenant_filter(query, tenant_id)
    result = await db.execute(query)
    obligation = result.scalar_one_or_none()

    if not obligation:
        raise HTTPException(status_code=404, detail="Obligation not found")

    # Update status
    obligation.status = ObligationStatus(update.status)

    # Add notes if provided
    if update.notes:
        existing_notes = obligation.compliance_notes or ""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_note = f"[{timestamp}] Status changed to {update.status}: {update.notes}"
        obligation.compliance_notes = f"{existing_notes}\n{new_note}".strip()

    # Auto-update RAG status based on status
    if update.status == "completed":
        obligation.rag_status = RAGStatus.GREEN
        obligation.last_compliance_date = date.today()
    elif update.status == "overdue":
        obligation.rag_status = RAGStatus.RED

    obligation.updated_at = datetime.now()
    await db.commit()
    await db.refresh(obligation)

    # Invalidate dashboard caches affected by obligation status changes
    try:
        from app.services.metric_snapshot_service import invalidate_dashboard_cache
        contract = await db.get(Contract, obligation.contract_id)
        if contract:
            await invalidate_dashboard_cache(
                db, contract.tenant_id,
                dashboard_types=["admin", "legal", "obligations", "portfolio"],
            )
    except Exception:
        pass  # Cache invalidation is best-effort

    return obligation_to_response(obligation)


@router.put("/{obligation_id}/rag", response_model=ObligationResponse)
async def update_obligation_rag(
    obligation_id: str,
    update: ObligationRAGUpdate,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ObligationResponse:
    """Update the RAG status of an obligation with compliance notes."""
    query = select(Obligation).where(Obligation.id == uuid_mod.UUID(obligation_id))
    query = apply_tenant_filter(query, tenant_id)
    result = await db.execute(query)
    obligation = result.scalar_one_or_none()

    if not obligation:
        raise HTTPException(status_code=404, detail="Obligation not found")

    # Update RAG status
    obligation.rag_status = RAGStatus(update.rag_status)

    # Update compliance tracking fields
    if update.compliance_notes is not None:
        obligation.compliance_notes = update.compliance_notes

    if update.last_compliance_date is not None:
        obligation.last_compliance_date = update.last_compliance_date

    if update.next_compliance_due is not None:
        obligation.next_compliance_due = update.next_compliance_due

    obligation.last_compliance_check = datetime.now()
    obligation.updated_at = datetime.now()

    await db.commit()
    await db.refresh(obligation)

    return obligation_to_response(obligation)


@router.put("/{obligation_id}/owner", response_model=ObligationResponse)
async def update_obligation_owner(
    obligation_id: str,
    update: ObligationOwnerUpdate,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ObligationResponse:
    """Assign an owner to an obligation."""
    query = select(Obligation).where(Obligation.id == uuid_mod.UUID(obligation_id))
    query = apply_tenant_filter(query, tenant_id)
    result = await db.execute(query)
    obligation = result.scalar_one_or_none()

    if not obligation:
        raise HTTPException(status_code=404, detail="Obligation not found")

    # Update owner fields
    obligation.owner_type = ObligationOwner(update.owner_type)

    if update.obligated_party is not None:
        obligation.obligated_party = update.obligated_party

    if update.priority is not None:
        obligation.priority = update.priority

    if update.is_critical is not None:
        obligation.is_critical = update.is_critical

    obligation.updated_at = datetime.now()

    await db.commit()
    await db.refresh(obligation)

    return obligation_to_response(obligation)


# --- General Obligation Update Schema ---

class ObligationGeneralUpdate(BaseModel):
    description: str | None = None
    deadline: date | None = None
    deadline_type: str | None = None
    obligation_type: str | None = None
    obligated_party: str | None = None
    beneficiary_party: str | None = None
    consequence_of_breach: str | None = None
    source_text: str | None = None
    section_reference: str | None = None
    is_critical: bool | None = None
    priority: int | None = None  # 1-5


@router.patch("/{obligation_id}", response_model=ObligationResponse)
async def update_obligation(
    obligation_id: str,
    update: ObligationGeneralUpdate,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ObligationResponse:
    """General update for obligation fields."""
    from app.models.obligation import ObligationType, DeadlineType

    query = select(Obligation).where(Obligation.id == uuid_mod.UUID(obligation_id))
    query = apply_tenant_filter(query, tenant_id)
    result = await db.execute(query)
    obligation = result.scalar_one_or_none()

    if not obligation:
        raise HTTPException(status_code=404, detail="Obligation not found")

    # Apply only non-None fields
    if update.description is not None:
        obligation.description = update.description
    if update.deadline is not None:
        obligation.deadline = update.deadline
    if update.deadline_type is not None:
        obligation.deadline_type = DeadlineType(update.deadline_type)
    if update.obligation_type is not None:
        obligation.obligation_type = ObligationType(update.obligation_type)
    if update.obligated_party is not None:
        obligation.obligated_party = update.obligated_party
    if update.beneficiary_party is not None:
        obligation.beneficiary_party = update.beneficiary_party
    if update.consequence_of_breach is not None:
        obligation.consequence_of_breach = update.consequence_of_breach
    if update.source_text is not None:
        obligation.source_text = update.source_text
    if update.section_reference is not None:
        obligation.section_reference = update.section_reference
    if update.is_critical is not None:
        obligation.is_critical = update.is_critical
    if update.priority is not None:
        obligation.priority = update.priority

    obligation.updated_at = datetime.now()
    await db.commit()
    await db.refresh(obligation)

    return obligation_to_response(obligation)


@router.post("/{obligation_id}/evidence", response_model=ObligationResponse)
async def upload_obligation_evidence(
    obligation_id: str,
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    evidence_description: str = Form(...),
    evidence_date: date | None = Form(None),
    file: UploadFile | None = File(None),
) -> ObligationResponse:
    """Upload compliance evidence for an obligation."""
    query = select(Obligation).where(Obligation.id == uuid_mod.UUID(obligation_id))
    query = apply_tenant_filter(query, tenant_id)
    result = await db.execute(query)
    obligation = result.scalar_one_or_none()

    if not obligation:
        raise HTTPException(status_code=404, detail="Obligation not found")

    # Build evidence record
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    evidence_record = f"[{timestamp}] {evidence_description}"

    if file:
        # Save file to storage
        import os
        storage_dir = "storage/evidence"
        os.makedirs(storage_dir, exist_ok=True)

        file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
        safe_filename = f"{obligation_id}_{timestamp.replace(':', '-').replace(' ', '_')}{file_ext}"
        file_path = os.path.join(storage_dir, safe_filename)

        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        evidence_record += f" [File: {safe_filename}]"

    # Append to existing evidence
    existing_evidence = obligation.compliance_evidence or ""
    obligation.compliance_evidence = f"{existing_evidence}\n{evidence_record}".strip()

    if evidence_date:
        obligation.last_compliance_date = evidence_date

    obligation.last_compliance_check = datetime.now()
    obligation.updated_at = datetime.now()

    await db.commit()
    await db.refresh(obligation)

    return obligation_to_response(obligation)


@router.get("/compliance/rates", response_model=ComplianceRatesResponse)
async def get_compliance_rates(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    contract_id: str | None = None,
) -> ComplianceRatesResponse:
    """Get compliance rates across obligations.

    Optionally filter by contract_id.
    """
    today = date.today()
    seven_days = today + timedelta(days=7)

    # Base query with tenant filter
    base_query = select(Obligation)
    base_query = apply_tenant_filter(base_query, tenant_id)
    if contract_id:
        base_query = base_query.where(Obligation.contract_id == uuid_mod.UUID(contract_id))

    # Get all obligations
    result = await db.execute(base_query)
    obligations = result.scalars().all()

    # Calculate totals
    total = len(obligations)
    if total == 0:
        return ComplianceRatesResponse(
            total_obligations=0,
            overall_compliance_rate=0.0,
            by_status={},
            by_rag={},
            by_owner=[],
            by_category=[],
            contracts=[],
            overdue_count=0,
            critical_overdue=0,
            upcoming_7_days=0,
        )

    # Count by status
    by_status: dict[str, int] = {}
    by_rag: dict[str, int] = {}
    by_owner: dict[str, dict] = {}
    by_category: dict[str, dict] = {}
    by_contract: dict[str, dict] = {}

    overdue_count = 0
    critical_overdue = 0
    upcoming_7_days = 0
    completed = 0

    for obl in obligations:
        # Status counts
        status_val = obl.status.value if obl.status else "pending"
        by_status[status_val] = by_status.get(status_val, 0) + 1

        if status_val == "completed":
            completed += 1
        elif status_val == "overdue":
            overdue_count += 1
            if obl.is_critical:
                critical_overdue += 1

        # RAG counts
        rag_val = obl.rag_status.value if obl.rag_status else "not_assessed"
        by_rag[rag_val] = by_rag.get(rag_val, 0) + 1

        # Owner grouping
        owner_val = obl.owner_type.value if obl.owner_type else "unspecified"
        if owner_val not in by_owner:
            by_owner[owner_val] = {"total": 0, "completed": 0, "overdue": 0}
        by_owner[owner_val]["total"] += 1
        if status_val == "completed":
            by_owner[owner_val]["completed"] += 1
        elif status_val == "overdue":
            by_owner[owner_val]["overdue"] += 1

        # Category grouping
        cat_val = obl.category.value if obl.category else "other"
        if cat_val not in by_category:
            by_category[cat_val] = {"total": 0, "completed": 0, "overdue": 0}
        by_category[cat_val]["total"] += 1
        if status_val == "completed":
            by_category[cat_val]["completed"] += 1
        elif status_val == "overdue":
            by_category[cat_val]["overdue"] += 1

        # Contract grouping
        contract_key = str(obl.contract_id)
        if contract_key not in by_contract:
            by_contract[contract_key] = {
                "total": 0, "completed": 0, "in_progress": 0,
                "overdue": 0, "pending": 0,
                "rag_green": 0, "rag_amber": 0, "rag_red": 0,
            }
        by_contract[contract_key]["total"] += 1
        by_contract[contract_key][status_val] = by_contract[contract_key].get(status_val, 0) + 1

        if rag_val == "green":
            by_contract[contract_key]["rag_green"] += 1
        elif rag_val == "amber":
            by_contract[contract_key]["rag_amber"] += 1
        elif rag_val == "red":
            by_contract[contract_key]["rag_red"] += 1

        # Upcoming deadlines
        if obl.deadline and today <= obl.deadline <= seven_days:
            upcoming_7_days += 1

    # Calculate compliance rate
    overall_compliance_rate = (completed / total * 100) if total > 0 else 0.0

    # Build owner response
    owner_list = [
        ComplianceRatesByOwner(
            owner_type=owner,
            total_obligations=data["total"],
            completed=data["completed"],
            overdue=data["overdue"],
            compliance_rate=(data["completed"] / data["total"] * 100) if data["total"] > 0 else 0.0,
        )
        for owner, data in by_owner.items()
    ]

    # Build category response
    category_list = [
        ComplianceRatesByCategory(
            category=cat,
            total_obligations=data["total"],
            completed=data["completed"],
            overdue=data["overdue"],
            compliance_rate=(data["completed"] / data["total"] * 100) if data["total"] > 0 else 0.0,
        )
        for cat, data in by_category.items()
    ]

    # Get contract filenames
    contract_ids = list(by_contract.keys())
    contract_names: dict[str, str] = {}
    if contract_ids:
        contract_result = await db.execute(
            select(Contract.id, Contract.filename)
            .where(Contract.id.in_([uuid_mod.UUID(cid) for cid in contract_ids]))
        )
        for cid, fname in contract_result.all():
            contract_names[str(cid)] = fname

    # Build contract response
    contract_list = [
        ComplianceRatesByContract(
            contract_id=cid,
            contract_filename=contract_names.get(cid, "Unknown"),
            total_obligations=data["total"],
            completed=data.get("completed", 0),
            in_progress=data.get("in_progress", 0),
            overdue=data.get("overdue", 0),
            pending=data.get("pending", 0),
            compliance_rate=(data.get("completed", 0) / data["total"] * 100) if data["total"] > 0 else 0.0,
            rag_green=data.get("rag_green", 0),
            rag_amber=data.get("rag_amber", 0),
            rag_red=data.get("rag_red", 0),
        )
        for cid, data in by_contract.items()
    ]

    return ComplianceRatesResponse(
        total_obligations=total,
        overall_compliance_rate=round(overall_compliance_rate, 2),
        by_status=by_status,
        by_rag=by_rag,
        by_owner=owner_list,
        by_category=category_list,
        contracts=contract_list,
        overdue_count=overdue_count,
        critical_overdue=critical_overdue,
        upcoming_7_days=upcoming_7_days,
    )


@router.get("/")
async def list_obligations(
    current_user: CurrentUser,
    tenant_id: CurrentTenantId,
    db: Annotated[AsyncSession, Depends(get_db)],
    contract_id: str | None = None,
    status: str | None = None,
    rag_status: str | None = None,
    owner_type: str | None = None,
    category: str | None = None,
    is_critical: bool | None = None,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
):
    """List obligations with optional filters and pagination."""
    query = select(Obligation)
    query = apply_tenant_filter(query, tenant_id)

    if contract_id:
        query = query.where(Obligation.contract_id == uuid_mod.UUID(contract_id))

    if status:
        query = query.where(Obligation.status == ObligationStatus(status))

    if rag_status:
        query = query.where(Obligation.rag_status == RAGStatus(rag_status))

    if owner_type:
        query = query.where(Obligation.owner_type == ObligationOwner(owner_type))

    if category:
        query = query.where(Obligation.category == ObligationCategory(category))

    if is_critical is not None:
        query = query.where(Obligation.is_critical == is_critical)

    # Count total before pagination
    from sqlalchemy import func as sa_func
    count_query = select(sa_func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Apply ordering and pagination
    offset = (page - 1) * page_size
    query = query.order_by(
        Obligation.deadline.asc().nulls_last(),
        Obligation.priority.asc().nulls_last(),
    ).offset(offset).limit(page_size)

    result = await db.execute(query)
    obligations = result.scalars().all()

    import math
    return {
        "items": [obligation_to_response(obl) for obl in obligations],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if page_size > 0 else 0,
    }
