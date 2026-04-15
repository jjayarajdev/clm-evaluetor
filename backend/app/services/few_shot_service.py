"""Few-shot example service for extraction quality improvement.

Queries both the global (platform-wide) golden set AND the tenant's own
golden set for verified extractions and returns formatted examples to
inject into agent prompts. Only uses items that have been explicitly
verified (CORRECT, or INCORRECT/PARTIAL with a corrected_value provided).

Supports both AI-extracted items (entity_id = UUID of DB record) and
manually-added items (entity_id starts with "manual_") where the admin
provided ground-truth data the AI missed entirely.
"""

import logging
from uuid import UUID

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_quality import (
    GoldenSetContract,
    ExtractionVerification,
)
from app.models.contract import Contract
from app.models.clause import Clause
from app.models.obligation import Obligation
from app.models.sla import ContractSLA

logger = logging.getLogger(__name__)

# Metadata fields we care about for few-shot examples
_META_FIELDS = [
    "contract_type", "counterparty", "effective_date", "expiration_date",
    "contract_value", "currency", "jurisdiction",
]


def _is_manual_entry(entity_id: str | None) -> bool:
    """Check if an entity_id represents a manually-added item."""
    return bool(entity_id and entity_id.startswith("manual_"))


async def get_few_shot_context(
    db: AsyncSession,
    tenant_id: UUID,
    entity_type: str,
    contract_type: str | None = None,
    limit: int = 3,
) -> str:
    """Return formatted few-shot examples from global + tenant golden sets.

    Args:
        db: Database session.
        tenant_id: Tenant UUID.
        entity_type: One of "metadata", "clause", "obligation", "sla".
        contract_type: Optional filter for contract type (e.g. "msa").
        limit: Max number of example contracts to use.

    Returns:
        Prompt-ready text block, or empty string if no examples.
    """
    try:
        if entity_type == "metadata":
            return await _metadata_examples(db, tenant_id, contract_type, limit)
        elif entity_type == "clause":
            return await _clause_examples(db, tenant_id, contract_type, limit)
        elif entity_type == "obligation":
            return await _obligation_examples(db, tenant_id, contract_type, limit)
        elif entity_type == "sla":
            return await _sla_examples(db, tenant_id, contract_type, limit)
    except Exception as e:
        logger.warning(f"Failed to build few-shot context ({entity_type}): {e}")
    return ""


# ── helpers ──────────────────────────────────────────────────────────

async def _golden_contract_ids(
    db: AsyncSession,
    tenant_id: UUID,
    contract_type: str | None,
    limit: int,
) -> list[tuple[UUID, UUID, str]]:
    """Return [(golden_set_id, contract_id, filename), ...] from global + tenant golden sets."""
    q = (
        select(
            GoldenSetContract.id,
            GoldenSetContract.contract_id,
            Contract.filename,
        )
        .join(Contract, GoldenSetContract.contract_id == Contract.id)
        .where(
            or_(
                GoldenSetContract.tenant_id == tenant_id,
                GoldenSetContract.tenant_id.is_(None),
            )
        )
        .order_by(GoldenSetContract.is_global.desc())
    )
    if contract_type:
        q = q.where(Contract.contract_type == contract_type)
    q = q.limit(limit)
    rows = (await db.execute(q)).all()
    return [(r[0], r[1], r[2] or "unknown") for r in rows]


async def _verifications_for(
    db: AsyncSession,
    gs_ids: list[UUID],
    entity_type_db: str,
) -> list[ExtractionVerification]:
    """Fetch verified items (CORRECT or with corrections)."""
    if not gs_ids:
        return []
    q = (
        select(ExtractionVerification)
        .where(
            and_(
                ExtractionVerification.golden_set_id.in_(gs_ids),
                ExtractionVerification.entity_type == entity_type_db,
                ExtractionVerification.status.in_(["correct", "incorrect", "partial"]),
            )
        )
    )
    return list((await db.execute(q)).scalars().all())


# ── metadata ─────────────────────────────────────────────────────────

async def _metadata_examples(
    db: AsyncSession,
    tenant_id: UUID,
    contract_type: str | None,
    limit: int,
) -> str:
    gc = await _golden_contract_ids(db, tenant_id, contract_type, limit)
    if not gc:
        return ""

    contract_ids = [cid for _, cid, _ in gc]
    gs_ids = [gsid for gsid, _, _ in gc]

    contracts = {}
    for cid in contract_ids:
        c = await db.get(Contract, cid)
        if c:
            contracts[cid] = c

    verifications = await _verifications_for(db, gs_ids, "metadata_field")
    gs_to_contract = {gsid: cid for gsid, cid, _ in gc}

    corrections: dict[UUID, dict[str, str]] = {}
    for v in verifications:
        cid = gs_to_contract.get(v.golden_set_id)
        if not cid:
            continue
        if v.status == "correct":
            continue
        if v.corrected_value and isinstance(v.corrected_value, dict):
            corrections.setdefault(cid, {})[v.entity_id] = str(
                v.corrected_value.get("value", "")
            )

    lines = [
        "REFERENCE EXAMPLES — correct metadata extracted from verified contracts:\n"
    ]
    for gsid, cid, fname in gc:
        c = contracts.get(cid)
        if not c:
            continue
        overrides = corrections.get(cid, {})
        fields = []
        for f in _META_FIELDS:
            val = overrides.get(f) if f in overrides else getattr(c, f, None)
            if val is not None:
                val_str = val.value if hasattr(val, "value") else str(val)
                fields.append(f"  {f}: {val_str}")
        if fields:
            lines.append(f"Example ({fname}):")
            lines.extend(fields)
            lines.append("")

    if len(lines) <= 1:
        return ""
    return "\n".join(lines)


# ── clauses ──────────────────────────────────────────────────────────

async def _clause_examples(
    db: AsyncSession,
    tenant_id: UUID,
    contract_type: str | None,
    limit: int,
) -> str:
    gc = await _golden_contract_ids(db, tenant_id, contract_type, limit)
    if not gc:
        return ""

    gs_ids = [gsid for gsid, _, _ in gc]
    verifications = await _verifications_for(db, gs_ids, "clause")
    if not verifications:
        return ""

    # Fetch original clauses for AI-extracted verifications
    clause_ids = set()
    for v in verifications:
        if not _is_manual_entry(v.entity_id):
            try:
                clause_ids.add(UUID(v.entity_id))
            except (ValueError, TypeError):
                pass

    clauses = {}
    if clause_ids:
        q = select(Clause).where(Clause.id.in_(clause_ids))
        for c in (await db.execute(q)).scalars().all():
            clauses[c.id] = c

    lines = [
        "REFERENCE EXAMPLES — correctly extracted clauses from verified contracts:\n"
    ]
    count = 0
    for v in verifications:
        if count >= 8:
            break

        if _is_manual_entry(v.entity_id):
            # Manual entry — all data is in corrected_value
            corr = v.corrected_value or {}
            ctype = corr.get("clause_type", "unknown")
            risk = corr.get("risk_level", "")
            text = corr.get("text", "")
            if not text:
                continue
        else:
            try:
                cid = UUID(v.entity_id)
            except (ValueError, TypeError):
                continue
            clause = clauses.get(cid)
            if not clause:
                continue
            corr = v.corrected_value or {} if v.status != "correct" else {}
            ctype = corr.get("clause_type") or (
                clause.clause_type.value if clause.clause_type else "unknown"
            )
            risk = corr.get("risk_level") or (
                clause.risk_level.value if clause.risk_level else ""
            )
            text = corr.get("text") or clause.text or ""

        snippet = text[:200] + "..." if len(text) > 200 else text
        lines.append(f"- clause_type: {ctype}")
        if risk:
            lines.append(f"  risk_level: {risk}")
        lines.append(f"  text: \"{snippet}\"")
        lines.append("")
        count += 1

    if count == 0:
        return ""
    return "\n".join(lines)


# ── obligations ──────────────────────────────────────────────────────

async def _obligation_examples(
    db: AsyncSession,
    tenant_id: UUID,
    contract_type: str | None,
    limit: int,
) -> str:
    gc = await _golden_contract_ids(db, tenant_id, contract_type, limit)
    if not gc:
        return ""

    gs_ids = [gsid for gsid, _, _ in gc]
    verifications = await _verifications_for(db, gs_ids, "obligation")
    if not verifications:
        return ""

    obl_ids = set()
    for v in verifications:
        if not _is_manual_entry(v.entity_id):
            try:
                obl_ids.add(UUID(v.entity_id))
            except (ValueError, TypeError):
                pass

    obligations = {}
    if obl_ids:
        q = select(Obligation).where(Obligation.id.in_(obl_ids))
        for o in (await db.execute(q)).scalars().all():
            obligations[o.id] = o

    lines = [
        "REFERENCE EXAMPLES — correctly extracted obligations from verified contracts:\n"
    ]
    count = 0
    for v in verifications:
        if count >= 6:
            break

        if _is_manual_entry(v.entity_id):
            corr = v.corrected_value or {}
            otype = corr.get("obligation_type", "unknown")
            party = corr.get("obligated_party", "")
            desc = corr.get("description", "")
            if not desc:
                continue
        else:
            try:
                oid = UUID(v.entity_id)
            except (ValueError, TypeError):
                continue
            obl = obligations.get(oid)
            if not obl:
                continue
            corr = v.corrected_value or {} if v.status != "correct" else {}
            otype = corr.get("obligation_type") or (
                obl.obligation_type.value if obl.obligation_type else "unknown"
            )
            party = corr.get("obligated_party") or obl.obligated_party or ""
            desc = corr.get("description") or obl.description or ""

        snippet = desc[:200] + "..." if len(desc) > 200 else desc
        lines.append(f"- obligation_type: {otype}")
        if party:
            lines.append(f"  obligated_party: {party}")
        lines.append(f"  description: \"{snippet}\"")
        lines.append("")
        count += 1

    if count == 0:
        return ""
    return "\n".join(lines)


# ── SLAs ─────────────────────────────────────────────────────────────

async def _sla_examples(
    db: AsyncSession,
    tenant_id: UUID,
    contract_type: str | None,
    limit: int,
) -> str:
    gc = await _golden_contract_ids(db, tenant_id, contract_type, limit)
    if not gc:
        return ""

    gs_ids = [gsid for gsid, _, _ in gc]
    verifications = await _verifications_for(db, gs_ids, "sla")
    if not verifications:
        return ""

    sla_ids = set()
    for v in verifications:
        if not _is_manual_entry(v.entity_id):
            try:
                sla_ids.add(UUID(v.entity_id))
            except (ValueError, TypeError):
                pass

    slas = {}
    if sla_ids:
        q = select(ContractSLA).where(ContractSLA.id.in_(sla_ids))
        for s in (await db.execute(q)).scalars().all():
            slas[s.id] = s

    lines = [
        "REFERENCE EXAMPLES — correctly extracted SLAs from verified contracts:\n"
    ]
    count = 0
    for v in verifications:
        if count >= 6:
            break

        if _is_manual_entry(v.entity_id):
            corr = v.corrected_value or {}
            name = corr.get("sla_name", "")
            metric = corr.get("metric_type", "")
            target = corr.get("target_value", "")
            unit = corr.get("metric_unit", "")
            if not name:
                continue
        else:
            try:
                sid = UUID(v.entity_id)
            except (ValueError, TypeError):
                continue
            sla = slas.get(sid)
            if not sla:
                continue
            corr = v.corrected_value or {} if v.status != "correct" else {}
            name = corr.get("sla_name") or sla.sla_name or ""
            metric = sla.metric_type.value if sla.metric_type else ""
            target = corr.get("target_value") or (
                float(sla.target_value) if sla.target_value is not None else ""
            )
            unit = corr.get("metric_unit") or (
                sla.metric_unit.value if sla.metric_unit else ""
            )

        lines.append(f"- sla_name: {name}")
        if metric:
            lines.append(f"  metric_type: {metric}")
        if target != "":
            lines.append(f"  target_value: {target}")
        if unit:
            lines.append(f"  metric_unit: {unit}")
        lines.append("")
        count += 1

    if count == 0:
        return ""
    return "\n".join(lines)
