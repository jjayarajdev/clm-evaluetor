"""DSPy compilation service — builds training data from golden set and optimizes.

Reads verified extraction data from the golden set, converts to DSPy
training examples, and compiles optimized modules using BootstrapFewShot.

Compilation can be triggered:
- Manually by admin via API endpoint
- Automatically after N new verifications (future)
"""

import json
import logging
from uuid import UUID

import dspy
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contract import Contract
from app.models.clause import Clause
from app.models.obligation import Obligation
from app.models.sla import ContractSLA
from app.models.extraction_quality import (
    GoldenSetContract,
    ExtractionVerification,
)
from app.services.dspy_extractor import (
    ensure_dspy_configured,
    MetadataExtractorModule,
    ClauseExtractorModule,
    ObligationExtractorModule,
    SLAExtractorModule,
    save_compiled_program,
)

logger = logging.getLogger(__name__)

MIN_EXAMPLES_FOR_COMPILATION = 3


# ═══════════════════════════════════════════════════════════════════
# Training Data Builders
# ═══════════════════════════════════════════════════════════════════

async def _get_golden_contracts(
    db: AsyncSession, tenant_id: UUID | None
) -> list[tuple[GoldenSetContract, Contract]]:
    """Get golden set contracts visible to a tenant."""
    query = (
        select(GoldenSetContract, Contract)
        .join(Contract, GoldenSetContract.contract_id == Contract.id)
    )
    if tenant_id is not None:
        query = query.where(
            or_(
                GoldenSetContract.tenant_id == tenant_id,
                GoldenSetContract.tenant_id.is_(None),
            )
        )
    result = await db.execute(query)
    return [(gs, c) for gs, c in result.all()]


async def _get_verifications(
    db: AsyncSession, gs_id: UUID, entity_type: str
) -> list[ExtractionVerification]:
    """Get verified items for a golden set contract."""
    result = await db.execute(
        select(ExtractionVerification).where(
            and_(
                ExtractionVerification.golden_set_id == gs_id,
                ExtractionVerification.entity_type == entity_type,
                ExtractionVerification.status.in_(["correct", "incorrect", "partial"]),
            )
        )
    )
    return list(result.scalars().all())


async def build_metadata_trainset(
    db: AsyncSession, tenant_id: UUID | None
) -> list[dspy.Example]:
    """Build metadata training examples from golden set."""
    pairs = await _get_golden_contracts(db, tenant_id)
    examples = []

    for gs, contract in pairs:
        verifications = await _get_verifications(db, gs.id, "metadata_field")
        if not verifications:
            continue

        # Build the expected metadata output from contract + corrections
        meta = {}
        for v in verifications:
            field = v.entity_id  # e.g. "contract_type"
            if v.status == "correct":
                # Use original value from contract
                raw = getattr(contract, field, None)
                if raw is not None:
                    val = raw.value if hasattr(raw, "value") else raw
                    meta[field] = {"value": str(val), "confidence": 0.95}
            elif v.corrected_value and isinstance(v.corrected_value, dict):
                meta[field] = {
                    "value": str(v.corrected_value.get("value", "")),
                    "confidence": 0.95,
                }

        if not meta:
            continue

        # Use contract text as input
        text = contract.extracted_text or ""
        if not text:
            continue

        meta["overall_confidence"] = 0.9
        meta["parties"] = []

        examples.append(
            dspy.Example(
                contract_text=text[:50000],
                metadata_json=json.dumps(meta),
            ).with_inputs("contract_text")
        )

    return examples


async def build_clause_trainset(
    db: AsyncSession, tenant_id: UUID | None
) -> list[dspy.Example]:
    """Build clause training examples from golden set."""
    pairs = await _get_golden_contracts(db, tenant_id)
    examples = []

    for gs, contract in pairs:
        verifications = await _get_verifications(db, gs.id, "clause")
        if not verifications:
            continue

        text = contract.extracted_text or ""
        if not text:
            continue

        # Build expected clauses from verifications
        clauses = []
        for v in verifications:
            if v.entity_id and v.entity_id.startswith("manual_"):
                # Manual entry — corrected_value has all data
                corr = v.corrected_value or {}
                if corr.get("text"):
                    clauses.append({
                        "clause_type": corr.get("clause_type", "OTHER"),
                        "text": corr["text"],
                        "risk_level": corr.get("risk_level"),
                        "confidence": 0.95,
                    })
            else:
                # AI-extracted — look up the Clause record
                try:
                    clause = await db.get(Clause, UUID(v.entity_id))
                except (ValueError, TypeError):
                    continue
                if not clause:
                    continue

                if v.status == "correct":
                    clauses.append({
                        "clause_type": clause.clause_type.value if clause.clause_type else "OTHER",
                        "text": (clause.text or "")[:500],
                        "risk_level": clause.risk_level.value if clause.risk_level else None,
                        "confidence": 0.95,
                    })
                elif v.corrected_value:
                    corr = v.corrected_value
                    clauses.append({
                        "clause_type": corr.get("clause_type", clause.clause_type.value if clause.clause_type else "OTHER"),
                        "text": corr.get("text", (clause.text or "")[:500]),
                        "risk_level": corr.get("risk_level", clause.risk_level.value if clause.risk_level else None),
                        "confidence": 0.95,
                    })

        if not clauses:
            continue

        output = {
            "extracted_clauses": clauses,
            "missing_clauses": [],
            "overall_confidence": 0.9,
        }
        examples.append(
            dspy.Example(
                contract_chunk=text[:25000],
                clauses_json=json.dumps(output),
            ).with_inputs("contract_chunk")
        )

    return examples


async def build_obligation_trainset(
    db: AsyncSession, tenant_id: UUID | None
) -> list[dspy.Example]:
    """Build obligation training examples from golden set."""
    pairs = await _get_golden_contracts(db, tenant_id)
    examples = []

    for gs, contract in pairs:
        verifications = await _get_verifications(db, gs.id, "obligation")
        if not verifications:
            continue

        text = contract.extracted_text or ""
        if not text:
            continue

        obligations = []
        for v in verifications:
            if v.entity_id and v.entity_id.startswith("manual_"):
                corr = v.corrected_value or {}
                if corr.get("description"):
                    obligations.append({
                        "description": corr["description"],
                        "obligation_type": corr.get("obligation_type", "OTHER"),
                        "obligated_party": corr.get("obligated_party", "Unknown"),
                        "deadline_type": corr.get("deadline_type", "ONGOING"),
                        "confidence": 0.95,
                    })
            else:
                try:
                    obl = await db.get(Obligation, UUID(v.entity_id))
                except (ValueError, TypeError):
                    continue
                if not obl:
                    continue

                if v.status == "correct":
                    obligations.append({
                        "description": (obl.description or "")[:300],
                        "obligation_type": obl.obligation_type.value if obl.obligation_type else "OTHER",
                        "obligated_party": obl.obligated_party or "Unknown",
                        "deadline_type": obl.deadline_type.value if obl.deadline_type else "ONGOING",
                        "confidence": 0.95,
                    })
                elif v.corrected_value:
                    corr = v.corrected_value
                    obligations.append({
                        "description": corr.get("description", (obl.description or "")[:300]),
                        "obligation_type": corr.get("obligation_type", obl.obligation_type.value if obl.obligation_type else "OTHER"),
                        "obligated_party": corr.get("obligated_party", obl.obligated_party or "Unknown"),
                        "deadline_type": corr.get("deadline_type", obl.deadline_type.value if obl.deadline_type else "ONGOING"),
                        "confidence": 0.95,
                    })

        if not obligations:
            continue

        output = {
            "obligations": obligations,
            "party_summary": {},
            "overall_confidence": 0.9,
        }
        examples.append(
            dspy.Example(
                contract_chunk=text[:25000],
                obligations_json=json.dumps(output),
            ).with_inputs("contract_chunk")
        )

    return examples


async def build_sla_trainset(
    db: AsyncSession, tenant_id: UUID | None
) -> list[dspy.Example]:
    """Build SLA training examples from golden set."""
    pairs = await _get_golden_contracts(db, tenant_id)
    examples = []

    for gs, contract in pairs:
        verifications = await _get_verifications(db, gs.id, "sla")
        if not verifications:
            continue

        text = contract.extracted_text or ""
        if not text:
            continue

        slas = []
        for v in verifications:
            if v.entity_id and v.entity_id.startswith("manual_"):
                corr = v.corrected_value or {}
                if corr.get("sla_name"):
                    slas.append({
                        "sla_name": corr["sla_name"],
                        "metric_type": corr.get("metric_type", "CUSTOM"),
                        "target_value": corr.get("target_value"),
                        "metric_unit": corr.get("metric_unit", "PERCENTAGE"),
                        "confidence": 0.95,
                    })
            else:
                try:
                    sla = await db.get(ContractSLA, UUID(v.entity_id))
                except (ValueError, TypeError):
                    continue
                if not sla:
                    continue

                if v.status == "correct":
                    slas.append({
                        "sla_name": sla.sla_name or "",
                        "metric_type": sla.metric_type.value if sla.metric_type else "CUSTOM",
                        "target_value": float(sla.target_value) if sla.target_value else None,
                        "metric_unit": sla.metric_unit.value if sla.metric_unit else "PERCENTAGE",
                        "confidence": 0.95,
                    })
                elif v.corrected_value:
                    corr = v.corrected_value
                    slas.append({
                        "sla_name": corr.get("sla_name", sla.sla_name or ""),
                        "metric_type": corr.get("metric_type", sla.metric_type.value if sla.metric_type else "CUSTOM"),
                        "target_value": corr.get("target_value", float(sla.target_value) if sla.target_value else None),
                        "metric_unit": corr.get("metric_unit", sla.metric_unit.value if sla.metric_unit else "PERCENTAGE"),
                        "confidence": 0.95,
                    })

        if not slas:
            continue

        output = {
            "slas": slas,
            "has_sla_section": True,
            "has_penalty_mechanism": any(s.get("has_penalty") for s in slas),
            "overall_confidence": 0.9,
        }
        examples.append(
            dspy.Example(
                contract_text=text[:100000],
                slas_json=json.dumps(output),
            ).with_inputs("contract_text")
        )

    return examples


# ═══════════════════════════════════════════════════════════════════
# Metric Functions
# ═══════════════════════════════════════════════════════════════════

def _json_field_match(prediction_json: str, expected_json: str) -> float:
    """Compare two JSON outputs and return a match score 0-1."""
    try:
        pred = json.loads(prediction_json) if isinstance(prediction_json, str) else prediction_json
        exp = json.loads(expected_json) if isinstance(expected_json, str) else expected_json
    except (json.JSONDecodeError, TypeError):
        return 0.0

    if not pred or not exp:
        return 0.0

    # Count matching fields
    matches = 0
    total = 0

    for key in exp:
        if key in ("overall_confidence", "party_summary"):
            continue
        total += 1
        if key in pred:
            if isinstance(exp[key], list) and isinstance(pred[key], list):
                # List comparison — check length similarity and first item match
                if len(pred[key]) > 0 and len(exp[key]) > 0:
                    matches += min(len(pred[key]), len(exp[key])) / max(len(pred[key]), len(exp[key]))
                elif len(pred[key]) == 0 and len(exp[key]) == 0:
                    matches += 1
            elif isinstance(exp[key], dict) and isinstance(pred[key], dict):
                ev = exp[key].get("value", exp[key])
                pv = pred[key].get("value", pred[key])
                if str(ev).lower() == str(pv).lower():
                    matches += 1
            else:
                if str(exp[key]).lower() == str(pred[key]).lower():
                    matches += 1

    return matches / total if total > 0 else 0.0


def metadata_metric(example, prediction, trace=None) -> float:
    return _json_field_match(prediction.metadata_json, example.metadata_json)


def clause_metric(example, prediction, trace=None) -> float:
    return _json_field_match(prediction.clauses_json, example.clauses_json)


def obligation_metric(example, prediction, trace=None) -> float:
    return _json_field_match(prediction.obligations_json, example.obligations_json)


def sla_metric(example, prediction, trace=None) -> float:
    return _json_field_match(prediction.slas_json, example.slas_json)


# ═══════════════════════════════════════════════════════════════════
# Compilation
# ═══════════════════════════════════════════════════════════════════

async def compile_for_tenant(
    db: AsyncSession,
    tenant_id: UUID | None,
    agent_types: list[str] | None = None,
) -> dict:
    """Compile DSPy programs for a tenant using their golden set data.

    Args:
        db: Database session.
        tenant_id: Tenant UUID (None for global compilation).
        agent_types: Which agents to compile. Defaults to all four.

    Returns:
        Status dict with results per agent type.
    """
    ensure_dspy_configured()

    if agent_types is None:
        agent_types = ["metadata", "clause", "obligation", "sla"]

    results = {}

    builders = {
        "metadata": (build_metadata_trainset, MetadataExtractorModule, metadata_metric),
        "clause": (build_clause_trainset, ClauseExtractorModule, clause_metric),
        "obligation": (build_obligation_trainset, ObligationExtractorModule, obligation_metric),
        "sla": (build_sla_trainset, SLAExtractorModule, sla_metric),
    }

    for agent_type in agent_types:
        if agent_type not in builders:
            results[agent_type] = {"status": "error", "message": f"Unknown agent type: {agent_type}"}
            continue

        build_fn, module_cls, metric_fn = builders[agent_type]

        try:
            trainset = await build_fn(db, tenant_id)
            if len(trainset) < MIN_EXAMPLES_FOR_COMPILATION:
                results[agent_type] = {
                    "status": "skipped",
                    "message": f"Need at least {MIN_EXAMPLES_FOR_COMPILATION} verified examples, found {len(trainset)}",
                    "examples": len(trainset),
                }
                continue

            logger.info(f"Compiling DSPy {agent_type} extractor with {len(trainset)} examples")

            # BootstrapFewShot: selects optimal demos from trainset
            optimizer = dspy.BootstrapFewShot(
                metric=metric_fn,
                max_bootstrapped_demos=min(4, len(trainset)),
                max_labeled_demos=min(4, len(trainset)),
            )

            module = module_cls()
            compiled = optimizer.compile(module, trainset=trainset)

            path = save_compiled_program(compiled, tenant_id, agent_type)

            results[agent_type] = {
                "status": "compiled",
                "examples": len(trainset),
                "path": str(path),
            }
            logger.info(f"Successfully compiled {agent_type} extractor ({len(trainset)} examples)")

        except Exception as e:
            logger.error(f"Failed to compile {agent_type}: {e}")
            results[agent_type] = {
                "status": "error",
                "message": str(e),
            }

    return results


async def get_compilation_status(tenant_id: UUID | None) -> dict:
    """Check which compiled programs exist for a tenant."""
    from app.services.dspy_extractor import _program_path

    status = {}
    for agent_type in ["metadata", "clause", "obligation", "sla"]:
        path = _program_path(tenant_id, agent_type)
        if path.exists():
            import os
            stat = os.stat(path)
            status[agent_type] = {
                "compiled": True,
                "path": str(path),
                "size_bytes": stat.st_size,
                "compiled_at": stat.st_mtime,
            }
        else:
            status[agent_type] = {"compiled": False}

    return status
