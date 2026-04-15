"""DSPy-powered contract extraction with optimized prompts.

Replaces manual few-shot injection with DSPy's programmatic prompt
optimization. Uses the golden set verification data as training examples
to compile optimized extractors per tenant.

Architecture:
- DSPy Signatures define input/output schemas
- DSPy Modules wrap ChainOfThought predictors
- Compiled programs are cached to disk per tenant
- Falls back to unoptimized extraction if no compiled program exists
"""

import json
import logging
import os
import pickle
from pathlib import Path
from uuid import UUID

import dspy

from app.agents.clause_extraction import (
    ClauseExtractionResult,
    ExtractedClause,
    SUPPORTED_CLAUSE_TYPES,
)
from app.agents.obligation_tracking import (
    ObligationExtractionResult,
    ExtractedObligation,
    OBLIGATION_TYPES,
)
from app.agents.sla_extraction import (
    SLAExtractionResult,
    ExtractedSLA,
    METRIC_TYPES,
    UNITS,
)
from app.agents.metadata_extraction import (
    ExtractedMetadata,
    MetadataField,
)
from app.agents.base import extract_json_from_response

logger = logging.getLogger(__name__)

# Where compiled programs are stored
COMPILED_DIR = Path(os.environ.get("DSPY_COMPILED_DIR", "data/dspy_compiled"))
COMPILED_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════
# DSPy Signatures
# ═══════════════════════════════════════════════════════════════════

class MetadataExtractionSig(dspy.Signature):
    """Extract structured metadata from a contract document.

    Identify contract type, counterparty, dates, monetary values,
    and jurisdiction. Return null for fields that cannot be determined.
    If the document is a template with placeholders, return null for
    placeholder fields.
    """
    contract_text: str = dspy.InputField(desc="Full or partial contract text")
    metadata_json: str = dspy.OutputField(
        desc='JSON with keys: contract_type, counterparty, effective_date (YYYY-MM-DD), '
             'expiration_date (YYYY-MM-DD), contract_value (number), currency (ISO 3-letter), '
             'jurisdiction, parties (list of strings), overall_confidence (0-1). '
             'Each field (except parties/overall_confidence) is {value, confidence, raw_text}.'
    )


class ClauseExtractionSig(dspy.Signature):
    """Extract and classify legal clauses from contract text.

    Identify clause types, extract the relevant text, assess risk level,
    and note any standard clauses that are missing.
    """
    contract_chunk: str = dspy.InputField(desc="Contract text section to analyze")
    clauses_json: str = dspy.OutputField(
        desc='JSON with keys: extracted_clauses (list of {clause_type, text, section_number, '
             'page_number, risk_level, confidence, key_terms, notes}), '
             'missing_clauses (list of string), overall_confidence (0-1). '
             f'Clause types: {", ".join(SUPPORTED_CLAUSE_TYPES.keys())}.'
    )


class ObligationExtractionSig(dspy.Signature):
    """Extract contractual obligations from contract text.

    Identify what each party must do, deadlines, consequences of
    non-compliance, and triggering conditions.
    """
    contract_chunk: str = dspy.InputField(desc="Contract text section to analyze")
    obligations_json: str = dspy.OutputField(
        desc='JSON with keys: obligations (list of {description, obligation_type, '
             'obligated_party, beneficiary_party, deadline_type, deadline_value, '
             'deadline_date, recurrence_pattern, triggering_condition, consequences, '
             'section_number, source_quote, confidence}), '
             'party_summary (dict of party->count), overall_confidence (0-1).'
    )


class SLAExtractionSig(dspy.Signature):
    """Extract Service Level Agreements from contract text.

    Identify SLA metrics, targets, penalties, measurement periods,
    and severity levels.
    """
    contract_text: str = dspy.InputField(desc="Contract text to analyze for SLAs")
    slas_json: str = dspy.OutputField(
        desc='JSON with keys: slas (list of {sla_name, sla_description, metric_type, '
             'metric_unit, target_value, target_operator, warning_threshold, severity, '
             'has_penalty, penalty_type, penalty_value, penalty_description, max_penalty_cap, '
             'measurement_period, section_reference, source_text, confidence}), '
             'has_sla_section (bool), has_penalty_mechanism (bool), overall_confidence (0-1). '
             f'Metric types: {", ".join(METRIC_TYPES.keys())}. '
             f'Units: {", ".join(UNITS.keys())}.'
    )


# ═══════════════════════════════════════════════════════════════════
# DSPy Modules
# ═══════════════════════════════════════════════════════════════════

class MetadataExtractorModule(dspy.Module):
    def __init__(self):
        self.extract = dspy.ChainOfThought(MetadataExtractionSig)

    def forward(self, contract_text: str) -> dspy.Prediction:
        return self.extract(contract_text=contract_text)


class ClauseExtractorModule(dspy.Module):
    def __init__(self):
        self.extract = dspy.ChainOfThought(ClauseExtractionSig)

    def forward(self, contract_chunk: str) -> dspy.Prediction:
        return self.extract(contract_chunk=contract_chunk)


class ObligationExtractorModule(dspy.Module):
    def __init__(self):
        self.extract = dspy.ChainOfThought(ObligationExtractionSig)

    def forward(self, contract_chunk: str) -> dspy.Prediction:
        return self.extract(contract_chunk=contract_chunk)


class SLAExtractorModule(dspy.Module):
    def __init__(self):
        self.extract = dspy.ChainOfThought(SLAExtractionSig)

    def forward(self, contract_text: str) -> dspy.Prediction:
        return self.extract(contract_text=contract_text)


# ═══════════════════════════════════════════════════════════════════
# Compiled Program Cache
# ═══════════════════════════════════════════════════════════════════

def _program_path(tenant_id: UUID | None, agent_type: str) -> Path:
    """Get the filesystem path for a compiled program."""
    tid = str(tenant_id) if tenant_id else "global"
    return COMPILED_DIR / f"{tid}_{agent_type}.json"


def load_compiled_program(
    tenant_id: UUID | None, agent_type: str
) -> dspy.Module | None:
    """Load a compiled DSPy program from disk.

    Returns None if no compiled program exists.
    """
    path = _program_path(tenant_id, agent_type)
    if not path.exists():
        return None

    try:
        module_cls = {
            "metadata": MetadataExtractorModule,
            "clause": ClauseExtractorModule,
            "obligation": ObligationExtractorModule,
            "sla": SLAExtractorModule,
        }[agent_type]

        module = module_cls()
        module.load(str(path))
        logger.info(f"Loaded compiled DSPy program: {path.name}")
        return module
    except Exception as e:
        logger.warning(f"Failed to load compiled program {path.name}: {e}")
        return None


def save_compiled_program(
    module: dspy.Module, tenant_id: UUID | None, agent_type: str
) -> Path:
    """Save a compiled DSPy program to disk."""
    path = _program_path(tenant_id, agent_type)
    module.save(str(path))
    logger.info(f"Saved compiled DSPy program: {path.name}")
    return path


# ═══════════════════════════════════════════════════════════════════
# DSPy LM Configuration
# ═══════════════════════════════════════════════════════════════════

_lm_configured = False


def ensure_dspy_configured():
    """Configure DSPy's language model (idempotent)."""
    global _lm_configured
    if _lm_configured:
        return

    from app.core.config import settings

    model = getattr(settings, "openai_model", "gpt-4o")
    lm = dspy.LM(
        f"openai/{model}",
        api_key=getattr(settings, "openai_api_key", None),
        temperature=0.1,
        max_tokens=12000,
    )
    dspy.configure(lm=lm)
    _lm_configured = True
    logger.info(f"DSPy configured with model: {model}")


# ═══════════════════════════════════════════════════════════════════
# Extraction Functions (called by agents)
# ═══════════════════════════════════════════════════════════════════

def _parse_json_output(raw: str) -> dict | None:
    """Parse JSON from DSPy output, handling markdown fences."""
    # DSPy may wrap output in markdown code fences
    result = extract_json_from_response(raw)
    if result:
        return result
    # Direct parse attempt
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


async def dspy_extract_metadata(
    contract_text: str,
    tenant_id: UUID | None,
) -> ExtractedMetadata | None:
    """Extract metadata using DSPy compiled program.

    Returns None if no compiled program or extraction fails.
    """
    ensure_dspy_configured()

    # Try tenant-specific first, then global
    module = load_compiled_program(tenant_id, "metadata")
    if not module and tenant_id:
        module = load_compiled_program(None, "metadata")
    if not module:
        return None

    try:
        # DSPy modules are sync — run in thread
        async_module = dspy.asyncify(module)
        result = await async_module(contract_text=contract_text[:50000])

        data = _parse_json_output(result.metadata_json)
        if not data:
            logger.warning("DSPy metadata extraction returned unparseable output")
            return None

        return _build_metadata(data)
    except Exception as e:
        logger.warning(f"DSPy metadata extraction failed: {e}")
        return None


async def dspy_extract_clauses(
    contract_chunk: str,
    tenant_id: UUID | None,
) -> ClauseExtractionResult | None:
    """Extract clauses using DSPy compiled program."""
    ensure_dspy_configured()

    module = load_compiled_program(tenant_id, "clause")
    if not module and tenant_id:
        module = load_compiled_program(None, "clause")
    if not module:
        return None

    try:
        async_module = dspy.asyncify(module)
        result = await async_module(contract_chunk=contract_chunk)

        data = _parse_json_output(result.clauses_json)
        if not data:
            return None

        return _build_clause_result(data)
    except Exception as e:
        logger.warning(f"DSPy clause extraction failed: {e}")
        return None


async def dspy_extract_obligations(
    contract_chunk: str,
    tenant_id: UUID | None,
) -> ObligationExtractionResult | None:
    """Extract obligations using DSPy compiled program."""
    ensure_dspy_configured()

    module = load_compiled_program(tenant_id, "obligation")
    if not module and tenant_id:
        module = load_compiled_program(None, "obligation")
    if not module:
        return None

    try:
        async_module = dspy.asyncify(module)
        result = await async_module(contract_chunk=contract_chunk)

        data = _parse_json_output(result.obligations_json)
        if not data:
            return None

        return _build_obligation_result(data)
    except Exception as e:
        logger.warning(f"DSPy obligation extraction failed: {e}")
        return None


async def dspy_extract_slas(
    contract_text: str,
    tenant_id: UUID | None,
) -> SLAExtractionResult | None:
    """Extract SLAs using DSPy compiled program."""
    ensure_dspy_configured()

    module = load_compiled_program(tenant_id, "sla")
    if not module and tenant_id:
        module = load_compiled_program(None, "sla")
    if not module:
        return None

    try:
        async_module = dspy.asyncify(module)
        result = await async_module(contract_text=contract_text[:100000])

        data = _parse_json_output(result.slas_json)
        if not data:
            return None

        from app.agents.sla_extraction import preprocess_sla_data
        data = preprocess_sla_data(data)
        return SLAExtractionResult(**data)
    except Exception as e:
        logger.warning(f"DSPy SLA extraction failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
# Pydantic Model Builders (from JSON dicts)
# ═══════════════════════════════════════════════════════════════════

def _build_metadata(data: dict) -> ExtractedMetadata:
    """Build ExtractedMetadata from parsed JSON."""
    def _field(d) -> MetadataField | None:
        if d is None:
            return None
        if isinstance(d, dict) and "value" in d:
            return MetadataField(
                value=d["value"],
                confidence=float(d.get("confidence", 0.5)),
                raw_text=d.get("raw_text"),
            )
        # Bare value
        return MetadataField(value=d, confidence=0.5)

    return ExtractedMetadata(
        contract_type=_field(data.get("contract_type")),
        counterparty=_field(data.get("counterparty")),
        effective_date=_field(data.get("effective_date")),
        expiration_date=_field(data.get("expiration_date")),
        contract_value=_field(data.get("contract_value")),
        currency=_field(data.get("currency")),
        jurisdiction=_field(data.get("jurisdiction")),
        parties=data.get("parties", []),
        overall_confidence=float(data.get("overall_confidence", 0.5)),
    )


def _build_clause_result(data: dict) -> ClauseExtractionResult:
    """Build ClauseExtractionResult from parsed JSON."""
    clauses = []
    for c in data.get("extracted_clauses", []):
        if not isinstance(c, dict):
            continue
        try:
            clauses.append(ExtractedClause(
                clause_type=c.get("clause_type", "OTHER"),
                text=c.get("text", ""),
                section_number=c.get("section_number"),
                page_number=c.get("page_number"),
                risk_level=c.get("risk_level"),
                confidence=max(0.0, min(1.0, float(c.get("confidence", 0.5)))),
                key_terms=c.get("key_terms", []),
                notes=c.get("notes"),
            ))
        except Exception:
            continue

    return ClauseExtractionResult(
        extracted_clauses=clauses,
        missing_clauses=data.get("missing_clauses", []),
        overall_confidence=float(data.get("overall_confidence", 0.5)),
    )


def _build_obligation_result(data: dict) -> ObligationExtractionResult:
    """Build ObligationExtractionResult from parsed JSON."""
    obls = []
    for o in data.get("obligations", []):
        if not isinstance(o, dict):
            continue
        try:
            obls.append(ExtractedObligation(
                description=o.get("description", ""),
                obligation_type=o.get("obligation_type", "OTHER"),
                obligated_party=o.get("obligated_party", "Unknown"),
                beneficiary_party=o.get("beneficiary_party"),
                deadline_type=o.get("deadline_type", "ONGOING"),
                deadline_value=o.get("deadline_value"),
                deadline_date=o.get("deadline_date"),
                recurrence_pattern=o.get("recurrence_pattern"),
                triggering_condition=o.get("triggering_condition"),
                consequences=o.get("consequences"),
                section_number=o.get("section_number"),
                source_quote=o.get("source_quote"),
                confidence=max(0.0, min(1.0, float(o.get("confidence", 0.5)))),
            ))
        except Exception:
            continue

    return ObligationExtractionResult(
        obligations=obls,
        party_summary=data.get("party_summary", {}),
        overall_confidence=float(data.get("overall_confidence", 0.5)),
    )
