"""Taxonomy discovery service.

After AI extraction, compares discovered items against the effective
industry profile + overrides. The resolution chain is:
  1. Contract's BU has its own profile → use BU profile + BU overrides
  2. Fall back to tenant profile + tenant overrides
  3. No profile at all → skip discovery

Items not in the known taxonomy are created as TaxonomySuggestion
records for admin review.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business_unit import BusinessUnit
from app.models.clause import Clause
from app.models.contract import Contract
from app.models.industry_profile import IndustryProfile
from app.models.sla import ContractSLA
from app.models.taxonomy_suggestion import SuggestionStatus, TaxonomySuggestion
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


async def _resolve_effective_config(
    db: AsyncSession,
    contract: Contract,
    tenant: Tenant,
) -> tuple[dict, uuid.UUID | None]:
    """Resolve the effective industry config for a contract.

    Returns (merged_config, business_unit_id).
    Resolution: Contract BU profile → Tenant profile → empty.
    """
    bu_id = contract.business_unit_id
    if bu_id:
        bu_result = await db.execute(
            select(BusinessUnit).where(BusinessUnit.id == bu_id)
        )
        bu = bu_result.scalar_one_or_none()
        if bu and bu.industry_profile_id:
            logger.info(
                f"[TAXONOMY] Using BU-level profile '{bu.effective_profile_name}' "
                f"for contract {contract.id} (BU: {bu.name})"
            )
            return bu.get_industry_config(), bu_id

    # Fall back to tenant config
    return tenant.get_industry_config(), bu_id


async def discover_taxonomy_suggestions(
    db: AsyncSession,
    contract_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> int:
    """Compare extracted items against effective taxonomy and create suggestions.

    Called after deep analysis completes. Resolves the effective profile
    (BU-level or tenant-level), then checks extracted clauses,
    the contract type, and SLA metrics against it.
    Returns the number of new suggestions created.
    """
    # Load tenant + profile
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        return 0

    # Load contract
    contract_result = await db.execute(
        select(Contract).where(Contract.id == contract_id)
    )
    contract = contract_result.scalar_one_or_none()
    if not contract:
        return 0

    # Resolve effective config (BU profile → tenant profile)
    merged_config, bu_id = await _resolve_effective_config(db, contract, tenant)
    if not merged_config.get("industry"):
        # No profile assigned at any level — skip discovery
        return 0

    # Get existing pending/approved suggestions to avoid duplicates
    existing_result = await db.execute(
        select(TaxonomySuggestion.category, TaxonomySuggestion.code).where(
            TaxonomySuggestion.tenant_id == tenant_id,
            TaxonomySuggestion.status.in_([
                SuggestionStatus.PENDING.value,
                SuggestionStatus.APPROVED.value,
                SuggestionStatus.MODIFIED.value,
            ]),
        )
    )
    existing_keys = {(row[0], row[1]) for row in existing_result.fetchall()}

    suggestions_created = 0

    # Determine the BU ID for suggestion association
    # Only set if the BU has its own profile (BU-level taxonomy)
    suggestion_bu_id = None
    if bu_id:
        bu_result2 = await db.execute(
            select(BusinessUnit.industry_profile_id).where(BusinessUnit.id == bu_id)
        )
        row = bu_result2.first()
        if row and row[0]:
            suggestion_bu_id = bu_id

    # --- 1. Contract type ---
    suggestions_created += await _check_contract_type(
        db, contract, merged_config, existing_keys, tenant_id, suggestion_bu_id,
    )

    # --- 2. Clause types ---
    suggestions_created += await _check_clause_types(
        db, contract_id, merged_config, existing_keys, tenant_id, suggestion_bu_id,
    )

    # --- 3. SLA metrics ---
    suggestions_created += await _check_sla_metrics(
        db, contract_id, merged_config, existing_keys, tenant_id, suggestion_bu_id,
    )

    if suggestions_created > 0:
        logger.info(
            f"[TAXONOMY] Created {suggestions_created} suggestions for "
            f"contract {contract_id} (tenant {tenant_id}, BU {suggestion_bu_id})"
        )

    return suggestions_created


async def _check_contract_type(
    db: AsyncSession,
    contract: Contract,
    merged_config: dict,
    existing_keys: set,
    tenant_id: uuid.UUID,
    business_unit_id: uuid.UUID | None = None,
) -> int:
    """Check if the contract type is in the tenant's taxonomy."""
    if not contract.contract_type:
        return 0

    known_codes = {
        ct.get("code", "").lower()
        for ct in merged_config.get("contract_types", [])
    }
    ct_code = contract.contract_type.lower().strip()

    if ct_code in known_codes:
        return 0
    if ("contract_types", ct_code) in existing_keys:
        return 0

    suggestion = TaxonomySuggestion(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        contract_id=contract.id,
        business_unit_id=business_unit_id,
        category="contract_types",
        code=ct_code,
        label=_humanize(ct_code),
        details={"description": f"Discovered from contract: {contract.filename}"},
        source_agent="metadata_extraction",
        confidence=0.8,
        source_text=f"Contract classified as: {contract.contract_type}",
        status=SuggestionStatus.PENDING.value,
    )
    db.add(suggestion)
    existing_keys.add(("contract_types", ct_code))
    return 1


async def _check_clause_types(
    db: AsyncSession,
    contract_id: uuid.UUID,
    merged_config: dict,
    existing_keys: set,
    tenant_id: uuid.UUID,
    business_unit_id: uuid.UUID | None = None,
) -> int:
    """Check extracted clause types against the tenant's clause taxonomy."""
    clause_result = await db.execute(
        select(Clause.clause_type, Clause.text, Clause.confidence_score)
        .where(Clause.contract_id == contract_id)
    )
    clauses = clause_result.fetchall()
    if not clauses:
        return 0

    known_codes = {
        ct.get("code", "").lower()
        for ct in merged_config.get("clause_types", [])
    }

    # Collect unique clause types found
    found_types: dict[str, tuple[str, float]] = {}
    for clause_type, text, confidence in clauses:
        if clause_type:
            code = clause_type.value if hasattr(clause_type, "value") else str(clause_type)
            code = code.lower().strip()
            if code not in found_types or (confidence or 0) > found_types[code][1]:
                found_types[code] = (text[:200] if text else "", confidence or 0)

    count = 0
    for code, (source_text, confidence) in found_types.items():
        if code in known_codes or code == "other":
            continue
        if ("clause_types", code) in existing_keys:
            continue

        suggestion = TaxonomySuggestion(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            contract_id=contract_id,
            business_unit_id=business_unit_id,
            category="clause_types",
            code=code,
            label=_humanize(code),
            details={"category": _infer_clause_category(code)},
            source_agent="clause_extraction",
            confidence=confidence,
            source_text=source_text,
            status=SuggestionStatus.PENDING.value,
        )
        db.add(suggestion)
        existing_keys.add(("clause_types", code))
        count += 1

    return count


async def _check_sla_metrics(
    db: AsyncSession,
    contract_id: uuid.UUID,
    merged_config: dict,
    existing_keys: set,
    tenant_id: uuid.UUID,
    business_unit_id: uuid.UUID | None = None,
) -> int:
    """Check extracted SLA metric types against the tenant's SLA taxonomy."""
    sla_result = await db.execute(
        select(
            ContractSLA.metric_type,
            ContractSLA.sla_name,
            ContractSLA.metric_unit,
        ).where(ContractSLA.contract_id == contract_id)
    )
    slas = sla_result.fetchall()
    if not slas:
        return 0

    known_codes = {
        sm.get("code", "").lower()
        for sm in merged_config.get("sla_metrics", [])
    }

    found_types: dict[str, tuple[str, str | None]] = {}
    for metric_type, sla_name, metric_unit in slas:
        if metric_type:
            code = metric_type.value if hasattr(metric_type, "value") else str(metric_type)
            code = code.lower().strip()
            if code not in found_types:
                found_types[code] = (sla_name or code, metric_unit)

    count = 0
    for code, (name, unit) in found_types.items():
        if code in known_codes or code == "custom":
            continue
        if ("sla_metrics", code) in existing_keys:
            continue

        unit_str = unit.value if hasattr(unit, "value") else str(unit) if unit else None
        suggestion = TaxonomySuggestion(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            contract_id=contract_id,
            business_unit_id=business_unit_id,
            category="sla_metrics",
            code=code,
            label=_humanize(code),
            details={
                "unit": unit_str,
                "direction": "higher_is_better" if "uptime" in code or "rate" in code else "lower_is_better",
            },
            source_agent="sla_extraction",
            confidence=0.7,
            source_text=f"SLA: {name}",
            status=SuggestionStatus.PENDING.value,
        )
        db.add(suggestion)
        existing_keys.add(("sla_metrics", code))
        count += 1

    return count


def _humanize(code: str) -> str:
    """Convert snake_case code to Title Case label."""
    return code.replace("_", " ").title()


def _infer_clause_category(code: str) -> str:
    """Guess a clause category from the code."""
    risk_terms = {"indemnification", "liability", "warranty", "force_majeure", "risk", "penalty", "late_payment"}
    compliance_terms = {"data_protection", "governing_law", "compliance", "export", "govt", "regulatory"}
    commercial_terms = {"payment", "pricing", "fee", "cost", "financial"}
    operational_terms = {"service", "support", "transition", "change", "deliverable", "acceptance", "scope"}

    for term in risk_terms:
        if term in code:
            return "risk"
    for term in compliance_terms:
        if term in code:
            return "compliance"
    for term in commercial_terms:
        if term in code:
            return "commercial"
    for term in operational_terms:
        if term in code:
            return "operational"
    return "general"
