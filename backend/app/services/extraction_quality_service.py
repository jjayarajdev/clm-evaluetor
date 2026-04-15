"""Service layer for extraction quality golden set management.

Supports two tiers of golden set:
- Global/platform (tenant_id=NULL, is_global=True): Managed by super admin,
  visible to and benefits ALL tenants.
- Tenant-specific (tenant_id set, is_global=False): Managed by tenant admin,
  visible only to that tenant.

Tenant admins see both global + their own tenant entries.
Super admins see all entries across all tenants.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Contract, ContractStatus, Clause, Obligation, ContractSLA,
    GoldenSetContract, ExtractionVerification, VerificationStatus,
)


def _golden_set_filter(query, tenant_id: UUID | None, model=GoldenSetContract):
    """Apply golden set visibility filter.

    - Super admin (tenant_id=None): sees everything
    - Tenant admin: sees global entries (tenant_id IS NULL) + own tenant entries
    """
    if tenant_id is not None:
        return query.where(
            or_(model.tenant_id == tenant_id, model.tenant_id.is_(None))
        )
    return query


async def get_golden_set_overview(db: AsyncSession, tenant_id: UUID | None) -> dict:
    """Get aggregate extraction quality metrics for the golden set."""
    query = select(GoldenSetContract).options(selectinload(GoldenSetContract.contract))
    query = _golden_set_filter(query, tenant_id)
    result = await db.execute(query)
    golden_contracts = result.scalars().all()

    if not golden_contracts:
        return {
            "total_golden": 0,
            "total_global": 0,
            "total_tenant": 0,
            "verified": 0,
            "pending_review": 0,
            "avg_overall_score": None,
            "avg_metadata_score": None,
            "avg_clause_score": None,
            "avg_obligation_score": None,
            "avg_sla_score": None,
        }

    scores = [g.overall_score for g in golden_contracts if g.overall_score is not None]
    meta_scores = [g.metadata_score for g in golden_contracts if g.metadata_score is not None]
    clause_scores = [g.clause_score for g in golden_contracts if g.clause_score is not None]
    obl_scores = [g.obligation_score for g in golden_contracts if g.obligation_score is not None]
    sla_scores = [g.sla_score for g in golden_contracts if g.sla_score is not None]

    verified = sum(1 for g in golden_contracts if g.overall_score is not None)
    global_count = sum(1 for g in golden_contracts if g.is_global)

    return {
        "total_golden": len(golden_contracts),
        "total_global": global_count,
        "total_tenant": len(golden_contracts) - global_count,
        "verified": verified,
        "pending_review": len(golden_contracts) - verified,
        "avg_overall_score": round(sum(scores) / len(scores), 2) if scores else None,
        "avg_metadata_score": round(sum(meta_scores) / len(meta_scores), 2) if meta_scores else None,
        "avg_clause_score": round(sum(clause_scores) / len(clause_scores), 2) if clause_scores else None,
        "avg_obligation_score": round(sum(obl_scores) / len(obl_scores), 2) if obl_scores else None,
        "avg_sla_score": round(sum(sla_scores) / len(sla_scores), 2) if sla_scores else None,
    }


async def list_golden_set(db: AsyncSession, tenant_id: UUID | None) -> list[dict]:
    """List all contracts in the visible golden set with extraction stats."""
    query = select(GoldenSetContract).options(selectinload(GoldenSetContract.contract))
    query = _golden_set_filter(query, tenant_id)
    query = query.order_by(GoldenSetContract.is_global.desc(), GoldenSetContract.created_at.desc())
    result = await db.execute(query)
    golden_contracts = result.scalars().all()

    items = []
    for g in golden_contracts:
        contract = g.contract
        if not contract:
            continue

        # Get extraction counts
        clause_count = await db.scalar(
            select(func.count(Clause.id)).where(Clause.contract_id == contract.id)
        )
        obl_count = await db.scalar(
            select(func.count(Obligation.id)).where(Obligation.contract_id == contract.id)
        )
        sla_count = await db.scalar(
            select(func.count(ContractSLA.id)).where(ContractSLA.contract_id == contract.id)
        )

        # Get verification stats
        verif_result = await db.execute(
            select(
                ExtractionVerification.status,
                func.count(ExtractionVerification.id),
            )
            .where(ExtractionVerification.golden_set_id == g.id)
            .group_by(ExtractionVerification.status)
        )
        verif_stats = {row[0]: row[1] for row in verif_result.all()}

        # Metadata completeness
        meta_fields = ["contract_type", "counterparty", "effective_date",
                       "expiration_date", "contract_value", "jurisdiction"]
        meta_filled = sum(1 for f in meta_fields if getattr(contract, f, None) is not None)

        items.append({
            "id": str(g.id),
            "contract_id": str(contract.id),
            "filename": contract.filename,
            "contract_type": contract.contract_type.value if contract.contract_type else None,
            "counterparty": contract.counterparty,
            "status": contract.status.value if contract.status else None,
            "is_baseline": g.is_baseline,
            "is_global": g.is_global,
            "notes": g.notes,
            "added_at": g.created_at.isoformat() if g.created_at else None,
            "extraction": {
                "metadata_completeness": round(meta_filled / len(meta_fields) * 100),
                "clause_count": clause_count or 0,
                "obligation_count": obl_count or 0,
                "sla_count": sla_count or 0,
            },
            "verification": {
                "pending": verif_stats.get(VerificationStatus.PENDING.value, 0),
                "correct": verif_stats.get(VerificationStatus.CORRECT.value, 0),
                "incorrect": verif_stats.get(VerificationStatus.INCORRECT.value, 0),
                "partial": verif_stats.get(VerificationStatus.PARTIAL.value, 0),
            },
            "scores": {
                "metadata": g.metadata_score,
                "clause": g.clause_score,
                "obligation": g.obligation_score,
                "sla": g.sla_score,
                "overall": g.overall_score,
            },
        })

    return items


async def get_extraction_detail(
    db: AsyncSession, contract_id: UUID, tenant_id: UUID | None
) -> dict:
    """Get full extraction detail for a contract — metadata, clauses, obligations, SLAs."""
    # Verify contract access: super admin can see all, tenant admin filtered
    query = select(Contract).where(Contract.id == contract_id)
    if tenant_id is not None:
        query = query.where(Contract.tenant_id == tenant_id)
    result = await db.execute(query)
    contract = result.scalar_one_or_none()
    if not contract:
        return None

    # Check golden set membership (could be tenant-specific or global)
    gs_query = select(GoldenSetContract).where(
        GoldenSetContract.contract_id == contract_id
    )
    gs_query = _golden_set_filter(gs_query, tenant_id)
    gs_result = await db.execute(gs_query)
    golden = gs_result.scalar_one_or_none()

    # Get existing verifications
    verifications = {}
    manual_clauses = []
    manual_obligations = []
    manual_slas = []
    if golden:
        v_result = await db.execute(
            select(ExtractionVerification).where(
                ExtractionVerification.golden_set_id == golden.id
            )
        )
        for v in v_result.scalars().all():
            key = f"{v.entity_type}:{v.entity_id}"
            v_data = {
                "status": v.status,
                "corrected_value": v.corrected_value,
                "notes": v.notes,
                "verified_at": v.verified_at.isoformat() if v.verified_at else None,
            }
            verifications[key] = v_data

            # Collect manually-added items (entity_id starts with "manual_")
            if v.entity_id and v.entity_id.startswith("manual_"):
                corr = v.corrected_value or {}
                if v.entity_type == "clause":
                    manual_clauses.append({
                        "id": v.entity_id,
                        "clause_type": corr.get("clause_type"),
                        "text": corr.get("text"),
                        "section_number": corr.get("section_number"),
                        "page_number": corr.get("page_number"),
                        "risk_level": corr.get("risk_level"),
                        "confidence": None,
                        "is_manual": True,
                        "verification": v_data,
                    })
                elif v.entity_type == "obligation":
                    manual_obligations.append({
                        "id": v.entity_id,
                        "description": corr.get("description"),
                        "obligation_type": corr.get("obligation_type"),
                        "obligated_party": corr.get("obligated_party"),
                        "deadline_type": corr.get("deadline_type"),
                        "deadline": corr.get("deadline"),
                        "status": None,
                        "is_critical": corr.get("is_critical", False),
                        "is_manual": True,
                        "verification": v_data,
                    })
                elif v.entity_type == "sla":
                    manual_slas.append({
                        "id": v.entity_id,
                        "sla_name": corr.get("sla_name"),
                        "metric_type": corr.get("metric_type"),
                        "target_value": corr.get("target_value"),
                        "metric_unit": corr.get("metric_unit"),
                        "severity": corr.get("severity"),
                        "has_penalty": corr.get("has_penalty", False),
                        "penalty_value": corr.get("penalty_value"),
                        "is_manual": True,
                        "verification": v_data,
                    })

    # Metadata
    meta_fields = {
        "contract_type": contract.contract_type.value if contract.contract_type else None,
        "counterparty": contract.counterparty,
        "effective_date": contract.effective_date.isoformat() if contract.effective_date else None,
        "expiration_date": contract.expiration_date.isoformat() if contract.expiration_date else None,
        "contract_value": float(contract.contract_value) if contract.contract_value else None,
        "currency": contract.currency,
        "jurisdiction": contract.jurisdiction,
        "governing_law": contract.governing_law,
    }
    metadata = []
    for field, value in meta_fields.items():
        v_key = f"metadata_field:{field}"
        metadata.append({
            "field": field,
            "value": value,
            "verification": verifications.get(v_key),
        })

    # Clauses
    clause_result = await db.execute(
        select(Clause).where(Clause.contract_id == contract_id)
        .order_by(Clause.page_number, Clause.section_number)
    )
    clauses = []
    for c in clause_result.scalars().all():
        v_key = f"clause:{c.id}"
        clauses.append({
            "id": str(c.id),
            "clause_type": c.clause_type.value if c.clause_type else None,
            "text": c.text[:500] if c.text else None,
            "section_number": c.section_number,
            "page_number": c.page_number,
            "risk_level": c.risk_level.value if c.risk_level else None,
            "confidence": c.confidence_score,
            "verification": verifications.get(v_key),
        })

    # Obligations
    obl_result = await db.execute(
        select(Obligation).where(Obligation.contract_id == contract_id)
        .order_by(Obligation.created_at)
    )
    obligations = []
    for o in obl_result.scalars().all():
        v_key = f"obligation:{o.id}"
        obligations.append({
            "id": str(o.id),
            "description": o.description[:300] if o.description else None,
            "obligation_type": o.obligation_type.value if o.obligation_type else None,
            "obligated_party": o.obligated_party,
            "deadline_type": o.deadline_type.value if o.deadline_type else None,
            "deadline": o.deadline.isoformat() if o.deadline else None,
            "status": o.status.value if o.status else None,
            "is_critical": o.is_critical,
            "verification": verifications.get(v_key),
        })

    # SLAs
    sla_result = await db.execute(
        select(ContractSLA).where(ContractSLA.contract_id == contract_id)
        .order_by(ContractSLA.severity.desc())
    )
    slas = []
    for s in sla_result.scalars().all():
        v_key = f"sla:{s.id}"
        slas.append({
            "id": str(s.id),
            "sla_name": s.sla_name,
            "metric_type": s.metric_type.value if s.metric_type else None,
            "target_value": float(s.target_value) if s.target_value else None,
            "metric_unit": s.metric_unit.value if s.metric_unit else None,
            "severity": s.severity.value if s.severity else None,
            "has_penalty": s.has_penalty,
            "penalty_value": float(s.penalty_value) if s.penalty_value else None,
            "verification": verifications.get(v_key),
        })

    # Append manually-added items
    clauses.extend(manual_clauses)
    obligations.extend(manual_obligations)
    slas.extend(manual_slas)

    # Count only AI-extracted clauses for confidence average
    ai_clauses = [c for c in clauses if not c.get("is_manual")]

    return {
        "contract_id": str(contract.id),
        "filename": contract.filename,
        "contract_status": contract.status.value if contract.status else None,
        "is_golden": golden is not None,
        "is_global": golden.is_global if golden else False,
        "golden_set_id": str(golden.id) if golden else None,
        "metadata": metadata,
        "clauses": clauses,
        "obligations": obligations,
        "slas": slas,
        "summary": {
            "metadata_filled": sum(1 for m in metadata if m["value"] is not None),
            "metadata_total": len(metadata),
            "clause_count": len(clauses),
            "obligation_count": len(obligations),
            "sla_count": len(slas),
            "manual_count": len(manual_clauses) + len(manual_obligations) + len(manual_slas),
            "avg_clause_confidence": (
                round(sum(c["confidence"] for c in ai_clauses if c["confidence"]) /
                      max(1, sum(1 for c in ai_clauses if c["confidence"])), 2)
                if any(c["confidence"] for c in ai_clauses) else None
            ),
        },
    }


async def add_to_golden_set(
    db: AsyncSession,
    contract_id: UUID,
    tenant_id: UUID | None,
    user_id: UUID,
    notes: str | None = None,
    is_global: bool = False,
) -> GoldenSetContract:
    """Add a contract to the golden set.

    Args:
        tenant_id: None for super admin. When is_global=True, entry has tenant_id=NULL.
        is_global: If True, creates a platform-wide golden set entry (super admin only).
    """
    contract = await db.get(Contract, contract_id)
    if not contract:
        raise ValueError("Contract not found")

    if is_global:
        # Super admin adding to global golden set — contract can be from any tenant
        if tenant_id is not None:
            raise ValueError("Only super admin can add to global golden set")
        golden = GoldenSetContract(
            tenant_id=None,
            contract_id=contract_id,
            added_by=user_id,
            notes=notes,
            is_global=True,
        )
    else:
        # Tenant admin adding to their own golden set
        if tenant_id is None:
            raise ValueError("Super admin must specify tenant context or use is_global=True")
        if contract.tenant_id != tenant_id:
            raise ValueError("Contract not found or does not belong to this tenant")
        golden = GoldenSetContract(
            tenant_id=tenant_id,
            contract_id=contract_id,
            added_by=user_id,
            notes=notes,
            is_global=False,
        )

    db.add(golden)
    await db.flush()
    return golden


async def remove_from_golden_set(
    db: AsyncSession, contract_id: UUID, tenant_id: UUID | None,
    is_global: bool = False,
) -> bool:
    """Remove a contract from the golden set.

    Super admin can remove global entries. Tenant admin can only remove their own.
    """
    query = select(GoldenSetContract).where(
        GoldenSetContract.contract_id == contract_id
    )

    if is_global:
        # Removing a global entry — only super admin (tenant_id=None)
        if tenant_id is not None:
            raise ValueError("Only super admin can remove global golden set entries")
        query = query.where(GoldenSetContract.is_global.is_(True))
    elif tenant_id is not None:
        # Tenant admin: can only remove their own tenant entries
        query = query.where(GoldenSetContract.tenant_id == tenant_id)
    # else: super admin removing tenant-specific entry — find any matching

    result = await db.execute(query)
    golden = result.scalar_one_or_none()
    if golden:
        await db.delete(golden)
        return True
    return False


async def verify_extraction(
    db: AsyncSession,
    golden_set_id: UUID,
    entity_type: str,
    entity_id: str,
    status: str,
    user_id: UUID,
    corrected_value: dict | None = None,
    notes: str | None = None,
    tenant_id: UUID | None = None,
) -> ExtractionVerification:
    """Create or update a verification for an extracted item."""
    gs = await db.get(GoldenSetContract, golden_set_id)
    if not gs:
        raise ValueError("Golden set entry not found")

    # Security: tenant admin can verify their own + global entries
    if tenant_id is not None:
        if gs.tenant_id is not None and gs.tenant_id != tenant_id:
            raise ValueError("Golden set not found or does not belong to this tenant")
        # gs.tenant_id is None (global) — tenant admin CAN verify global entries
    # else: super admin — can verify anything

    # Check for existing verification
    query = select(ExtractionVerification).where(
        ExtractionVerification.golden_set_id == golden_set_id,
        ExtractionVerification.entity_type == entity_type,
        ExtractionVerification.entity_id == entity_id,
    )
    result = await db.execute(query)
    verification = result.scalar_one_or_none()

    if verification:
        verification.status = status
        verification.corrected_value = corrected_value
        verification.notes = notes
        verification.verified_by = user_id
        verification.verified_at = datetime.now(timezone.utc)
    else:
        verification = ExtractionVerification(
            golden_set_id=golden_set_id,
            entity_type=entity_type,
            entity_id=entity_id,
            status=status,
            corrected_value=corrected_value,
            notes=notes,
            verified_by=user_id,
            verified_at=datetime.now(timezone.utc),
        )
        db.add(verification)

    await db.flush()

    # Recompute golden set scores
    await _recompute_scores(db, golden_set_id)

    return verification


async def _recompute_scores(db: AsyncSession, golden_set_id: UUID) -> None:
    """Recompute quality scores for a golden set contract based on verifications."""
    result = await db.execute(
        select(ExtractionVerification).where(
            ExtractionVerification.golden_set_id == golden_set_id
        )
    )
    verifications = result.scalars().all()

    if not verifications:
        return

    scores_by_type = {}
    for v in verifications:
        etype = v.entity_type.split(":")[0] if ":" in v.entity_type else v.entity_type
        if etype not in scores_by_type:
            scores_by_type[etype] = {"correct": 0, "total": 0}
        if v.status != VerificationStatus.PENDING.value:
            scores_by_type[etype]["total"] += 1
            if v.status == VerificationStatus.CORRECT.value:
                scores_by_type[etype]["correct"] += 1
            elif v.status == VerificationStatus.PARTIAL.value:
                scores_by_type[etype]["correct"] += 0.5

    golden = await db.get(GoldenSetContract, golden_set_id)
    if not golden:
        return

    def _score(key):
        s = scores_by_type.get(key)
        if not s or s["total"] == 0:
            return None
        return round(s["correct"] / s["total"] * 100, 1)

    golden.metadata_score = _score("metadata_field")
    golden.clause_score = _score("clause")
    golden.obligation_score = _score("obligation")
    golden.sla_score = _score("sla")

    # Overall: weighted average of available scores
    weights = {"metadata_field": 0.2, "clause": 0.3, "obligation": 0.3, "sla": 0.2}
    weighted_sum = 0
    weight_total = 0
    for key, weight in weights.items():
        score = _score(key)
        if score is not None:
            weighted_sum += score * weight
            weight_total += weight
    golden.overall_score = round(weighted_sum / weight_total, 1) if weight_total > 0 else None
