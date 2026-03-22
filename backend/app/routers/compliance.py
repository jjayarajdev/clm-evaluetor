"""API endpoints for Industry-Aware Compliance Module.

Provides:
- Compliance rule management (CRUD)
- Compliance gap listing, resolution, and waiving
- Regulatory obligation tracking
- Compliance dashboard and summaries
- Industry detection
- Compliance checks
"""

from datetime import datetime, date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_db, get_current_user, get_current_tenant_id
from app.models.user import User
from app.models.contract import Contract
from app.models.compliance_rule import IndustryComplianceRule
from app.models.compliance_gap import ComplianceGap
from app.models.regulatory_obligation import RegulatoryObligation
from app.models.industry import (
    Industry,
    ComplianceDocumentType,
    ComplianceGapSeverity,
    ComplianceGapStatus,
    REGULATED_INDUSTRIES,
)
from app.schemas.compliance import (
    ComplianceRuleCreate,
    ComplianceRuleUpdate,
    ComplianceRuleResponse,
    ComplianceRuleSummary,
    ComplianceGapResponse,
    ComplianceGapSummary,
    ComplianceGapResolve,
    ComplianceGapWaive,
    ComplianceGapUpdateStatus,
    RegulatoryObligationResponse,
    RegulatoryObligationSummary,
    RegulatoryObligationUpdateStatus,
    IndustryDetectionResponse,
    IndustrySignalResponse,
    ComplianceCheckResponse,
    ComplianceDashboardSummary,
    IndustryComplianceSummary,
    ContractComplianceSummary,
    MatchingDocumentResponse,
    SuggestMatchingDocumentsResponse,
)
from app.services.industry_detector import IndustryDetector
from app.services.compliance_gap_detector import ComplianceGapDetector
from app.services.compliance_alert_service import ComplianceAlertService, create_compliance_alerts_for_gaps

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


# ============ Compliance Rules Endpoints ============

@router.get("/rules", response_model=list[ComplianceRuleSummary])
async def list_compliance_rules(
    industry: Optional[str] = None,
    contract_type: Optional[str] = None,
    active_only: bool = Query(default=True),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """List compliance rules with optional filters."""
    query = select(IndustryComplianceRule).where(
        IndustryComplianceRule.tenant_id == tenant_id
    )

    if active_only:
        query = query.where(IndustryComplianceRule.is_active == True)

    if industry:
        try:
            industry_enum = Industry(industry)
            query = query.where(IndustryComplianceRule.industry == industry_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid industry: {industry}"
            )

    if contract_type:
        query = query.where(IndustryComplianceRule.primary_contract_type == contract_type)

    query = query.order_by(
        IndustryComplianceRule.industry,
        IndustryComplianceRule.primary_contract_type,
    ).offset(offset).limit(limit)

    result = await db.execute(query)
    rules = result.scalars().all()

    return [
        ComplianceRuleSummary(
            id=str(r.id),
            industry=r.industry.value,
            primary_contract_type=r.primary_contract_type.value,
            required_document_type=r.required_document_type.value,
            rule_name=r.rule_name,
            severity_if_missing=r.severity_if_missing.value,
            is_required=r.is_required,
            is_active=r.is_active,
        )
        for r in rules
    ]


@router.get("/rules/{rule_id}", response_model=ComplianceRuleResponse)
async def get_compliance_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Get compliance rule details."""
    result = await db.execute(
        select(IndustryComplianceRule)
        .where(IndustryComplianceRule.id == rule_id)
        .where(IndustryComplianceRule.tenant_id == tenant_id)
    )
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    return ComplianceRuleResponse(
        id=str(rule.id),
        tenant_id=str(rule.tenant_id),
        industry=rule.industry.value,
        primary_contract_type=rule.primary_contract_type.value,
        required_document_type=rule.required_document_type.value,
        is_required=rule.is_required,
        condition_description=rule.condition_description,
        severity_if_missing=rule.severity_if_missing.value,
        regulatory_reference=rule.regulatory_reference,
        rule_name=rule.rule_name,
        rule_description=rule.rule_description,
        is_active=rule.is_active,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.post("/rules", response_model=ComplianceRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_compliance_rule(
    rule_data: ComplianceRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Create a new compliance rule."""
    from app.models.contract import ContractType

    try:
        industry_enum = Industry(rule_data.industry)
        contract_type_enum = ContractType(rule_data.primary_contract_type)
        doc_type_enum = ComplianceDocumentType(rule_data.required_document_type)
        severity_enum = ComplianceGapSeverity(rule_data.severity_if_missing)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid enum value: {e}")

    rule = IndustryComplianceRule(
        tenant_id=tenant_id,
        industry=industry_enum,
        primary_contract_type=contract_type_enum,
        required_document_type=doc_type_enum,
        is_required=rule_data.is_required,
        condition_description=rule_data.condition_description,
        severity_if_missing=severity_enum,
        regulatory_reference=rule_data.regulatory_reference,
        rule_name=rule_data.rule_name,
        rule_description=rule_data.rule_description,
        is_active=rule_data.is_active,
    )

    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    return ComplianceRuleResponse(
        id=str(rule.id),
        tenant_id=str(rule.tenant_id),
        industry=rule.industry.value,
        primary_contract_type=rule.primary_contract_type.value,
        required_document_type=rule.required_document_type.value,
        is_required=rule.is_required,
        condition_description=rule.condition_description,
        severity_if_missing=rule.severity_if_missing.value,
        regulatory_reference=rule.regulatory_reference,
        rule_name=rule.rule_name,
        rule_description=rule.rule_description,
        is_active=rule.is_active,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.patch("/rules/{rule_id}", response_model=ComplianceRuleResponse)
async def update_compliance_rule(
    rule_id: UUID,
    rule_data: ComplianceRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Update a compliance rule."""
    result = await db.execute(
        select(IndustryComplianceRule)
        .where(IndustryComplianceRule.id == rule_id)
        .where(IndustryComplianceRule.tenant_id == tenant_id)
    )
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Update fields
    if rule_data.is_required is not None:
        rule.is_required = rule_data.is_required
    if rule_data.condition_description is not None:
        rule.condition_description = rule_data.condition_description
    if rule_data.severity_if_missing is not None:
        rule.severity_if_missing = ComplianceGapSeverity(rule_data.severity_if_missing)
    if rule_data.regulatory_reference is not None:
        rule.regulatory_reference = rule_data.regulatory_reference
    if rule_data.rule_name is not None:
        rule.rule_name = rule_data.rule_name
    if rule_data.rule_description is not None:
        rule.rule_description = rule_data.rule_description
    if rule_data.is_active is not None:
        rule.is_active = rule_data.is_active

    await db.commit()
    await db.refresh(rule)

    return ComplianceRuleResponse(
        id=str(rule.id),
        tenant_id=str(rule.tenant_id),
        industry=rule.industry.value,
        primary_contract_type=rule.primary_contract_type.value,
        required_document_type=rule.required_document_type.value,
        is_required=rule.is_required,
        condition_description=rule.condition_description,
        severity_if_missing=rule.severity_if_missing.value,
        regulatory_reference=rule.regulatory_reference,
        rule_name=rule.rule_name,
        rule_description=rule.rule_description,
        is_active=rule.is_active,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_compliance_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Delete a compliance rule."""
    result = await db.execute(
        select(IndustryComplianceRule)
        .where(IndustryComplianceRule.id == rule_id)
        .where(IndustryComplianceRule.tenant_id == tenant_id)
    )
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    await db.delete(rule)
    await db.commit()


# ============ Compliance Gaps Endpoints ============

@router.get("/gaps", response_model=list[ComplianceGapSummary])
async def list_compliance_gaps(
    contract_id: Optional[UUID] = None,
    severity: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    open_only: bool = Query(default=True),
    overdue_only: bool = Query(default=False),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """List compliance gaps with filters."""
    query = (
        select(ComplianceGap)
        .join(Contract, ComplianceGap.contract_id == Contract.id)
        .where(Contract.tenant_id == tenant_id)
    )

    if contract_id:
        query = query.where(ComplianceGap.contract_id == contract_id)

    if severity:
        try:
            severity_enum = ComplianceGapSeverity(severity)
            query = query.where(ComplianceGap.severity == severity_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")

    if status_filter:
        try:
            status_enum = ComplianceGapStatus(status_filter)
            query = query.where(ComplianceGap.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status_filter}")
    elif open_only:
        query = query.where(ComplianceGap.status.in_([
            ComplianceGapStatus.OPEN,
            ComplianceGapStatus.IN_PROGRESS,
            ComplianceGapStatus.PENDING_REVIEW,
        ]))

    if overdue_only:
        query = query.where(
            and_(
                ComplianceGap.resolution_due_date != None,
                ComplianceGap.resolution_due_date < date.today(),
                ComplianceGap.status.in_([
                    ComplianceGapStatus.OPEN,
                    ComplianceGapStatus.IN_PROGRESS,
                ]),
            )
        )

    query = query.order_by(
        ComplianceGap.severity.desc(),
        ComplianceGap.resolution_due_date.asc().nullslast(),
    ).offset(offset).limit(limit)

    result = await db.execute(query)
    gaps = result.scalars().all()

    return [
        ComplianceGapSummary(
            id=str(g.id),
            contract_id=str(g.contract_id),
            missing_document_type=g.missing_document_type.value,
            gap_description=g.gap_description,
            severity=g.severity.value,
            status=g.status.value,
            resolution_due_date=g.resolution_due_date,
            is_overdue=g.is_overdue,
        )
        for g in gaps
    ]


@router.get("/gaps/{gap_id}", response_model=ComplianceGapResponse)
async def get_compliance_gap(
    gap_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Get compliance gap details."""
    result = await db.execute(
        select(ComplianceGap)
        .join(Contract, ComplianceGap.contract_id == Contract.id)
        .where(ComplianceGap.id == gap_id)
        .where(Contract.tenant_id == tenant_id)
    )
    gap = result.scalar_one_or_none()

    if not gap:
        raise HTTPException(status_code=404, detail="Gap not found")

    return ComplianceGapResponse(
        id=str(gap.id),
        contract_id=str(gap.contract_id),
        rule_id=str(gap.rule_id) if gap.rule_id else None,
        missing_document_type=gap.missing_document_type.value,
        gap_description=gap.gap_description,
        regulatory_reference=gap.regulatory_reference,
        severity=gap.severity.value,
        status=gap.status.value,
        resolution_due_date=gap.resolution_due_date,
        resolved_at=gap.resolved_at,
        resolved_by=str(gap.resolved_by) if gap.resolved_by else None,
        resolution_notes=gap.resolution_notes,
        linked_document_id=str(gap.linked_document_id) if gap.linked_document_id else None,
        detection_confidence=gap.detection_confidence,
        detection_reasoning=gap.detection_reasoning,
        detected_at=gap.detected_at,
        waiver_reason=gap.waiver_reason,
        waiver_approved_by=str(gap.waiver_approved_by) if gap.waiver_approved_by else None,
        waiver_approved_at=gap.waiver_approved_at,
        created_at=gap.created_at,
        updated_at=gap.updated_at,
        is_overdue=gap.is_overdue,
        days_until_due=gap.days_until_due,
    )


@router.post("/gaps/{gap_id}/resolve")
async def resolve_compliance_gap(
    gap_id: UUID,
    resolve_data: ComplianceGapResolve,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Resolve a compliance gap by linking a document."""
    detector = ComplianceGapDetector(db, tenant_id)

    try:
        gap = await detector.resolve_gap(
            gap_id=gap_id,
            linked_document_id=UUID(resolve_data.linked_document_id),
            resolved_by=current_user.id,
            notes=resolve_data.resolution_notes,
        )
        await db.commit()

        return {
            "success": True,
            "gap_id": str(gap.id),
            "status": gap.status.value,
            "resolved_at": gap.resolved_at.isoformat(),
            "linked_document_id": str(gap.linked_document_id),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/gaps/{gap_id}/waive")
async def waive_compliance_gap(
    gap_id: UUID,
    waive_data: ComplianceGapWaive,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Waive a compliance requirement."""
    detector = ComplianceGapDetector(db, tenant_id)

    try:
        gap = await detector.waive_gap(
            gap_id=gap_id,
            waiver_reason=waive_data.waiver_reason,
            approved_by=current_user.id,
        )
        await db.commit()

        return {
            "success": True,
            "gap_id": str(gap.id),
            "status": gap.status.value,
            "waiver_approved_at": gap.waiver_approved_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/gaps/{gap_id}/status")
async def update_gap_status(
    gap_id: UUID,
    status_data: ComplianceGapUpdateStatus,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Update gap status."""
    result = await db.execute(
        select(ComplianceGap)
        .join(Contract, ComplianceGap.contract_id == Contract.id)
        .where(ComplianceGap.id == gap_id)
        .where(Contract.tenant_id == tenant_id)
    )
    gap = result.scalar_one_or_none()

    if not gap:
        raise HTTPException(status_code=404, detail="Gap not found")

    gap.status = ComplianceGapStatus(status_data.status)
    if status_data.notes:
        gap.resolution_notes = status_data.notes

    await db.commit()

    return {
        "success": True,
        "gap_id": str(gap.id),
        "status": gap.status.value,
    }


@router.get("/gaps/{gap_id}/suggestions", response_model=SuggestMatchingDocumentsResponse)
async def suggest_matching_documents(
    gap_id: UUID,
    limit: int = Query(default=5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Get document suggestions that could resolve a gap."""
    # Get the gap
    result = await db.execute(
        select(ComplianceGap)
        .join(Contract, ComplianceGap.contract_id == Contract.id)
        .where(ComplianceGap.id == gap_id)
        .where(Contract.tenant_id == tenant_id)
        .options(selectinload(ComplianceGap.contract))
    )
    gap = result.scalar_one_or_none()

    if not gap:
        raise HTTPException(status_code=404, detail="Gap not found")

    # Find matching documents
    detector = ComplianceGapDetector(db, tenant_id)
    matches = await detector.find_matching_documents(
        contract=gap.contract,
        required_doc_type=gap.missing_document_type,
        limit=limit,
    )

    return SuggestMatchingDocumentsResponse(
        gap_id=str(gap.id),
        missing_document_type=gap.missing_document_type.value,
        suggestions=[
            MatchingDocumentResponse(
                contract_id=str(m.contract.id),
                filename=m.contract.filename,
                counterparty=m.contract.counterparty,
                contract_type=m.contract.contract_type.value if m.contract.contract_type else None,
                match_score=m.match_score,
                match_reason=m.match_reason,
                effective_date=m.contract.effective_date,
                expiration_date=m.contract.expiration_date,
            )
            for m in matches
        ],
    )


# ============ Regulatory Obligations Endpoints ============

@router.get("/obligations", response_model=list[RegulatoryObligationSummary])
async def list_regulatory_obligations(
    contract_id: Optional[UUID] = None,
    regulation_type: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    needs_attention: bool = Query(default=False),
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """List regulatory obligations with filters."""
    from app.models.obligation import RAGStatus

    query = (
        select(RegulatoryObligation)
        .join(Contract)
        .where(Contract.tenant_id == tenant_id)
    )

    if contract_id:
        query = query.where(RegulatoryObligation.contract_id == contract_id)

    if regulation_type:
        query = query.where(RegulatoryObligation.regulation_type == regulation_type)

    if status_filter:
        query = query.where(RegulatoryObligation.compliance_status == status_filter)

    if needs_attention:
        query = query.where(RegulatoryObligation.compliance_status.in_([
            RAGStatus.AMBER,
            RAGStatus.RED,
        ]))

    query = query.order_by(
        RegulatoryObligation.next_due_date.asc().nullslast(),
        RegulatoryObligation.compliance_status.desc(),
    ).offset(offset).limit(limit)

    result = await db.execute(query)
    obligations = result.scalars().all()

    return [
        RegulatoryObligationSummary(
            id=str(o.id),
            contract_id=str(o.contract_id),
            regulation_type=o.regulation_type.value,
            obligation_category=o.obligation_category.value,
            title=o.title,
            compliance_status=o.compliance_status.value,
            next_due_date=o.next_due_date,
            is_overdue=o.is_overdue,
        )
        for o in obligations
    ]


@router.get("/obligations/{obligation_id}", response_model=RegulatoryObligationResponse)
async def get_regulatory_obligation(
    obligation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Get regulatory obligation details."""
    result = await db.execute(
        select(RegulatoryObligation)
        .join(Contract)
        .where(RegulatoryObligation.id == obligation_id)
        .where(Contract.tenant_id == tenant_id)
    )
    obl = result.scalar_one_or_none()

    if not obl:
        raise HTTPException(status_code=404, detail="Obligation not found")

    return RegulatoryObligationResponse(
        id=str(obl.id),
        contract_id=str(obl.contract_id),
        industry=obl.industry.value,
        regulation_type=obl.regulation_type.value,
        regulation_reference=obl.regulation_reference,
        obligation_category=obl.obligation_category.value,
        title=obl.title,
        description=obl.description,
        source_text=obl.source_text,
        source_section=obl.source_section,
        responsible_party=obl.responsible_party,
        frequency=obl.frequency,
        next_due_date=obl.next_due_date,
        last_completed_date=obl.last_completed_date,
        compliance_status=obl.compliance_status.value,
        last_compliance_check=obl.last_compliance_check,
        compliance_notes=obl.compliance_notes,
        compliance_evidence=obl.compliance_evidence,
        extraction_confidence=obl.extraction_confidence,
        created_at=obl.created_at,
        updated_at=obl.updated_at,
        is_overdue=obl.is_overdue,
        needs_attention=obl.needs_attention,
    )


@router.patch("/obligations/{obligation_id}/status")
async def update_obligation_status(
    obligation_id: UUID,
    status_data: RegulatoryObligationUpdateStatus,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Update regulatory obligation compliance status."""
    from app.models.obligation import RAGStatus

    result = await db.execute(
        select(RegulatoryObligation)
        .join(Contract)
        .where(RegulatoryObligation.id == obligation_id)
        .where(Contract.tenant_id == tenant_id)
    )
    obl = result.scalar_one_or_none()

    if not obl:
        raise HTTPException(status_code=404, detail="Obligation not found")

    obl.compliance_status = RAGStatus(status_data.compliance_status)
    obl.last_compliance_check = datetime.utcnow()

    if status_data.compliance_notes is not None:
        obl.compliance_notes = status_data.compliance_notes
    if status_data.compliance_evidence is not None:
        obl.compliance_evidence = status_data.compliance_evidence
    if status_data.next_due_date is not None:
        obl.next_due_date = status_data.next_due_date
    if status_data.last_completed_date is not None:
        obl.last_completed_date = status_data.last_completed_date

    await db.commit()

    return {
        "success": True,
        "obligation_id": str(obl.id),
        "compliance_status": obl.compliance_status.value,
    }


# ============ Compliance Check Endpoints ============

@router.post("/check/{contract_id}", response_model=ComplianceCheckResponse)
async def check_contract_compliance(
    contract_id: UUID,
    industry: Optional[str] = None,
    create_gaps: bool = Query(default=True),
    create_alerts: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Run compliance check on a contract."""
    # Get contract
    result = await db.execute(
        select(Contract)
        .where(Contract.id == contract_id)
        .where(Contract.tenant_id == tenant_id)
    )
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # Parse industry if provided
    industry_enum = None
    if industry:
        try:
            industry_enum = Industry(industry)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid industry: {industry}")

    # Run compliance check
    detector = ComplianceGapDetector(db, tenant_id)
    check_result = await detector.check_compliance(
        contract=contract,
        industry=industry_enum,
        create_gaps=create_gaps,
    )

    # Update contract compliance fields
    contract.detected_industry = check_result.industry
    contract.industry_confidence = check_result.industry_confidence
    contract.compliance_score = check_result.compliance_score
    contract.last_compliance_check = datetime.utcnow()

    # Create alerts for critical/high gaps
    if create_alerts and check_result.gaps_found:
        await create_compliance_alerts_for_gaps(
            db, contract_id, check_result.gaps_found
        )

    await db.commit()

    return ComplianceCheckResponse(
        contract_id=str(contract_id),
        industry=check_result.industry.value,
        industry_confidence=check_result.industry_confidence,
        compliance_score=check_result.compliance_score,
        total_rules_checked=check_result.total_rules_checked,
        rules_satisfied=check_result.rules_satisfied,
        gaps_found=[
            ComplianceGapSummary(
                id=str(g.id),
                contract_id=str(g.contract_id),
                missing_document_type=g.missing_document_type.value,
                gap_description=g.gap_description,
                severity=g.severity.value,
                status=g.status.value,
                resolution_due_date=g.resolution_due_date,
                is_overdue=g.is_overdue,
            )
            for g in check_result.gaps_found
        ],
    )


@router.post("/detect-industry/{contract_id}", response_model=IndustryDetectionResponse)
async def detect_contract_industry(
    contract_id: UUID,
    counterparty_industry: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Detect industry for a contract."""
    # Get contract
    result = await db.execute(
        select(Contract)
        .where(Contract.id == contract_id)
        .where(Contract.tenant_id == tenant_id)
    )
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    # Parse counterparty industry if provided
    cp_industry = None
    if counterparty_industry:
        try:
            cp_industry = Industry(counterparty_industry)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid counterparty industry: {counterparty_industry}"
            )

    # Detect industry
    detector = IndustryDetector(db)
    detection = await detector.detect_industry(contract, cp_industry)

    # Update contract
    contract.detected_industry = detection.industry
    contract.industry_confidence = detection.confidence
    await db.commit()

    return IndustryDetectionResponse(
        contract_id=str(contract_id),
        detected_industry=detection.industry.value,
        confidence=detection.confidence,
        alternative_industries=[
            (ind.value, score) for ind, score in detection.alternative_industries
        ],
        signals=[
            IndustrySignalResponse(
                industry=s.industry.value,
                signal_type=s.signal_type,
                match=s.match,
                weight=s.weight,
                score=s.score,
            )
            for s in detection.signals
        ],
        reasoning=detection.reasoning,
        is_confident=detection.is_confident,
        needs_review=detection.needs_review,
    )


# ============ Dashboard Endpoints ============

@router.get("/dashboard", response_model=ComplianceDashboardSummary)
async def get_compliance_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Get compliance dashboard summary."""
    from app.models.obligation import RAGStatus

    # Total contracts
    contract_count_result = await db.execute(
        select(func.count(Contract.id))
        .where(Contract.tenant_id == tenant_id)
    )
    total_contracts = contract_count_result.scalar() or 0

    # Contracts by industry
    industry_result = await db.execute(
        select(Contract.detected_industry, func.count(Contract.id))
        .where(Contract.tenant_id == tenant_id)
        .where(Contract.detected_industry != None)
        .group_by(Contract.detected_industry)
    )
    contracts_by_industry = {
        row[0].value if row[0] else "unknown": row[1]
        for row in industry_result.fetchall()
    }

    # Total gaps
    gap_count_result = await db.execute(
        select(func.count(ComplianceGap.id))
        .join(Contract, ComplianceGap.contract_id == Contract.id)
        .where(Contract.tenant_id == tenant_id)
    )
    total_gaps = gap_count_result.scalar() or 0

    # Gaps by severity
    severity_result = await db.execute(
        select(ComplianceGap.severity, func.count(ComplianceGap.id))
        .join(Contract, ComplianceGap.contract_id == Contract.id)
        .where(Contract.tenant_id == tenant_id)
        .group_by(ComplianceGap.severity)
    )
    gaps_by_severity = {
        row[0].value: row[1] for row in severity_result.fetchall()
    }

    # Gaps by status
    status_result = await db.execute(
        select(ComplianceGap.status, func.count(ComplianceGap.id))
        .join(Contract, ComplianceGap.contract_id == Contract.id)
        .where(Contract.tenant_id == tenant_id)
        .group_by(ComplianceGap.status)
    )
    gaps_by_status = {
        row[0].value: row[1] for row in status_result.fetchall()
    }

    # Overdue gaps
    overdue_result = await db.execute(
        select(func.count(ComplianceGap.id))
        .join(Contract, ComplianceGap.contract_id == Contract.id)
        .where(Contract.tenant_id == tenant_id)
        .where(ComplianceGap.resolution_due_date != None)
        .where(ComplianceGap.resolution_due_date < date.today())
        .where(ComplianceGap.status.in_([
            ComplianceGapStatus.OPEN,
            ComplianceGapStatus.IN_PROGRESS,
        ]))
    )
    overdue_gaps = overdue_result.scalar() or 0

    # Average compliance score
    avg_score_result = await db.execute(
        select(func.avg(Contract.compliance_score))
        .where(Contract.tenant_id == tenant_id)
        .where(Contract.compliance_score != None)
    )
    average_compliance_score = float(avg_score_result.scalar() or 0)

    # Critical gaps count
    critical_gaps = gaps_by_severity.get("critical", 0)

    # Regulatory obligations
    obl_count_result = await db.execute(
        select(func.count(RegulatoryObligation.id))
        .join(Contract)
        .where(Contract.tenant_id == tenant_id)
    )
    regulatory_obligations_count = obl_count_result.scalar() or 0

    # Obligations needing attention
    obl_attention_result = await db.execute(
        select(func.count(RegulatoryObligation.id))
        .join(Contract)
        .where(Contract.tenant_id == tenant_id)
        .where(RegulatoryObligation.compliance_status.in_([
            RAGStatus.AMBER,
            RAGStatus.RED,
        ]))
    )
    obligations_needing_attention = obl_attention_result.scalar() or 0

    return ComplianceDashboardSummary(
        total_contracts=total_contracts,
        contracts_by_industry=contracts_by_industry,
        total_gaps=total_gaps,
        gaps_by_severity=gaps_by_severity,
        gaps_by_status=gaps_by_status,
        overdue_gaps=overdue_gaps,
        average_compliance_score=average_compliance_score,
        critical_gaps_count=critical_gaps,
        regulatory_obligations_count=regulatory_obligations_count,
        obligations_needing_attention=obligations_needing_attention,
    )


@router.get("/by-industry", response_model=list[IndustryComplianceSummary])
async def get_compliance_by_industry(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Get compliance summary by industry."""
    # Get contracts grouped by industry
    query = (
        select(
            Contract.detected_industry,
            func.count(Contract.id).label("contract_count"),
            func.avg(Contract.compliance_score).label("avg_score"),
        )
        .where(Contract.tenant_id == tenant_id)
        .where(Contract.detected_industry != None)
        .group_by(Contract.detected_industry)
    )

    result = await db.execute(query)
    industry_stats = result.fetchall()

    summaries = []
    for row in industry_stats:
        industry = row[0]
        contract_count = row[1]
        avg_score = float(row[2]) if row[2] else 0

        # Get gap counts for this industry
        gap_query = (
            select(ComplianceGap.severity, ComplianceGap.status, func.count(ComplianceGap.id))
            .join(Contract, ComplianceGap.contract_id == Contract.id)
            .where(Contract.tenant_id == tenant_id)
            .where(Contract.detected_industry == industry)
            .group_by(ComplianceGap.severity, ComplianceGap.status)
        )
        gap_result = await db.execute(gap_query)
        gap_rows = gap_result.fetchall()

        total_gaps = sum(r[2] for r in gap_rows)
        critical_gaps = sum(
            r[2] for r in gap_rows
            if r[0] == ComplianceGapSeverity.CRITICAL
        )
        high_gaps = sum(
            r[2] for r in gap_rows
            if r[0] == ComplianceGapSeverity.HIGH
        )
        open_gaps = sum(
            r[2] for r in gap_rows
            if r[1] in [ComplianceGapStatus.OPEN, ComplianceGapStatus.IN_PROGRESS]
        )
        resolved_gaps = sum(
            r[2] for r in gap_rows
            if r[1] == ComplianceGapStatus.RESOLVED
        )

        summaries.append(IndustryComplianceSummary(
            industry=industry.value,
            contract_count=contract_count,
            average_compliance_score=avg_score,
            total_gaps=total_gaps,
            critical_gaps=critical_gaps,
            high_gaps=high_gaps,
            open_gaps=open_gaps,
            resolved_gaps=resolved_gaps,
        ))

    return summaries


@router.get("/contracts", response_model=list[ContractComplianceSummary])
async def list_contracts_compliance(
    industry: Optional[str] = None,
    has_gaps: bool = Query(default=False),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """List contracts with their compliance summaries."""
    query = (
        select(
            Contract,
            func.count(ComplianceGap.id).filter(
                ComplianceGap.status.in_([
                    ComplianceGapStatus.OPEN,
                    ComplianceGapStatus.IN_PROGRESS,
                ])
            ).label("open_gaps_count"),
            func.count(ComplianceGap.id).filter(
                ComplianceGap.severity == ComplianceGapSeverity.CRITICAL
            ).label("critical_gaps_count"),
            func.count(RegulatoryObligation.id).label("regulatory_count"),
        )
        .outerjoin(ComplianceGap, ComplianceGap.contract_id == Contract.id)
        .outerjoin(RegulatoryObligation, RegulatoryObligation.contract_id == Contract.id)
        .where(Contract.tenant_id == tenant_id)
        .group_by(Contract.id)
    )

    if industry:
        try:
            industry_enum = Industry(industry)
            query = query.where(Contract.detected_industry == industry_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid industry: {industry}")

    if has_gaps:
        query = query.having(func.count(ComplianceGap.id) > 0)

    query = query.order_by(
        Contract.compliance_score.asc().nullslast(),
        Contract.created_at.desc(),
    ).offset(offset).limit(limit)

    result = await db.execute(query)
    rows = result.fetchall()

    return [
        ContractComplianceSummary(
            contract_id=str(row[0].id),
            filename=row[0].filename,
            counterparty=row[0].counterparty,
            detected_industry=row[0].detected_industry.value if row[0].detected_industry else None,
            industry_confidence=row[0].industry_confidence,
            compliance_score=row[0].compliance_score,
            last_compliance_check=row[0].last_compliance_check,
            open_gaps_count=row[1] or 0,
            critical_gaps_count=row[2] or 0,
            regulatory_obligations_count=row[3] or 0,
        )
        for row in rows
    ]
