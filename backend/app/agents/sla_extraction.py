"""SLA Extraction Agent.

Extracts Service Level Agreements from contract text with:
- Metric types and target values
- Warning and breach thresholds
- Penalty/credit clauses
- Measurement periods
"""

import json
import logging
import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentResponseError, extract_json_from_response
from app.models.sla import ContractSLA, SLAMetricType, SLAUnit, SLASeverity
from app.services.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)


# Metric type descriptions for the prompt
METRIC_TYPES = {
    # Availability metrics
    "UPTIME_PERCENTAGE": "System uptime percentage (e.g., 99.9% uptime, 99.95% availability)",
    "AVAILABILITY": "Service availability windows (e.g., available 24/7, 99.99% available)",

    # Time-based metrics
    "RESPONSE_TIME": "Time to respond/acknowledge (e.g., respond within 4 hours, answer in 30 seconds)",
    "RESOLUTION_TIME": "Time to resolve/fix (e.g., resolve within 24 hours, incident containment 1 hour)",
    "DELIVERY_TIME": "Time to deliver/deploy (e.g., deliver within 5 days, patch deployment 24 hours)",

    # Rate/percentage metrics
    "SUCCESS_RATE": "Success/completion rates (e.g., first call resolution 75%, change success 98%, backup success 99.9%, DR test 100%)",
    "ERROR_RATE": "Error/failure rates (e.g., error rate <0.1%, call abandonment <3%, false positive <5%)",
    "COMPLIANCE_RATE": "Compliance percentages (e.g., patch compliance >98%, security compliance 100%)",

    # Capacity/utilization metrics
    "UTILIZATION": "Resource utilization (e.g., CPU <70%, memory <75%, storage <80%, bandwidth <60%)",
    "THROUGHPUT": "Processing rate/capacity (e.g., process 1000 transactions/hour)",

    # Recovery metrics
    "RECOVERY_TIME": "Recovery time objectives (e.g., RTO 4 hours, restore within 8 hours, incident eradication 4 hours)",
    "RECOVERY_POINT": "Recovery point objectives (e.g., RPO 1 hour max data loss)",

    # Quality metrics
    "QUALITY_SCORE": "Quality/satisfaction scores (e.g., CSAT 4.5/5.0, NPS >50, quality score >95)",

    # Fallback
    "CUSTOM": "Other SLA metrics that don't fit above categories",
}

UNITS = {
    "PERCENTAGE": "Percentage value (e.g., 99.9%)",
    "HOURS": "Hours (e.g., 4 hours)",
    "MINUTES": "Minutes (e.g., 30 minutes)",
    "DAYS": "Days (e.g., 5 days)",
    "BUSINESS_DAYS": "Business days (e.g., 3 business days)",
    "COUNT": "Count/number (e.g., 1000 transactions)",
    "SCORE": "Score value (e.g., score of 95)",
}


class ExtractedSLA(BaseModel):
    """A single extracted SLA."""

    sla_name: str = Field(description="Name/title of the SLA")
    sla_description: str | None = Field(default=None, description="Description of what the SLA measures")

    metric_type: str = Field(description="Type of metric (from METRIC_TYPES)")
    metric_unit: str = Field(description="Unit of measurement (from UNITS)")

    target_value: float = Field(description="Target value to meet")
    target_operator: str | None = Field(default=">=", description="Comparison operator: >=, <=, >, <, =")
    warning_threshold: float | None = Field(default=None, description="Warning threshold before breach")

    severity: str = Field(default="MEDIUM", description="Severity level: CRITICAL, HIGH, MEDIUM, LOW")

    has_penalty: bool = Field(default=False, description="Whether there's a penalty for breach")
    penalty_type: str | None = Field(default=None, description="Type: fixed, percentage, credit, tiered")
    penalty_value: float | None = Field(default=None, description="Penalty amount or rate")
    penalty_description: str | None = Field(default=None, description="Description of penalty terms")
    max_penalty_cap: float | None = Field(default=None, description="Maximum penalty cap if specified")

    measurement_period: str | None = Field(default=None, description="Measurement period: monthly, quarterly, annual")

    section_reference: str | None = Field(default=None, description="Section number in the contract")
    source_text: str | None = Field(default=None, description="Exact quote from contract (up to 500 chars)")

    confidence: float = Field(ge=0.0, le=1.0, description="Extraction confidence score")


class SLAExtractionResult(BaseModel):
    """Result of SLA extraction from a contract."""

    slas: list[ExtractedSLA] = []
    has_sla_section: bool = False
    has_penalty_mechanism: bool = False
    overall_confidence: float = 0.0
    # True when not every SLA-bearing section of the contract could be sent to
    # the model (e.g. a chunk was truncated or dropped), so callers must not
    # treat the SLA list as exhaustive.
    partial: bool = False


def clean_sla_value(value: Any, default: float | None = None) -> float | None:
    """Clean and convert SLA value to float."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Remove common suffixes
        cleaned = value.strip().rstrip('%').rstrip('h').rstrip('d').strip()
        try:
            return float(cleaned)
        except ValueError:
            return default
    return default


def preprocess_sla_data(data: dict) -> dict:
    """Preprocess SLA data to fix common AI response issues."""
    if not data:
        return data

    # Process each SLA in the list
    if "slas" in data and isinstance(data["slas"], list):
        cleaned_slas = []
        for sla in data["slas"]:
            if not isinstance(sla, dict):
                continue

            # Clean numeric fields
            sla["target_value"] = clean_sla_value(sla.get("target_value"), 0.0)
            sla["warning_threshold"] = clean_sla_value(sla.get("warning_threshold"))
            sla["penalty_value"] = clean_sla_value(sla.get("penalty_value"))
            sla["max_penalty_cap"] = clean_sla_value(sla.get("max_penalty_cap"))
            sla["confidence"] = clean_sla_value(sla.get("confidence"), 0.5)

            # Ensure confidence is in valid range
            if sla["confidence"] is not None:
                sla["confidence"] = max(0.0, min(1.0, sla["confidence"]))

            # Ensure required string fields exist
            if not sla.get("sla_name"):
                sla["sla_name"] = "Unnamed SLA"
            if not sla.get("metric_type"):
                sla["metric_type"] = "CUSTOM"
            if not sla.get("metric_unit"):
                sla["metric_unit"] = "SCORE"
            if not sla.get("target_operator"):
                sla["target_operator"] = ">="

            cleaned_slas.append(sla)

        data["slas"] = cleaned_slas

    # Clean overall confidence
    data["overall_confidence"] = clean_sla_value(data.get("overall_confidence"), 0.5)
    if data["overall_confidence"] is not None:
        data["overall_confidence"] = max(0.0, min(1.0, data["overall_confidence"]))

    return data


SLA_EXTRACTION_PROMPT = f"""You are a contract SLA (Service Level Agreement) extraction specialist. Your task is to identify and extract all SLAs and service level commitments from the provided contract text.

METRIC TYPES:
{json.dumps(METRIC_TYPES, indent=2)}

UNITS:
{json.dumps(UNITS, indent=2)}

For each SLA found, extract:
1. **sla_name**: A clear name for the SLA (e.g., "System Uptime", "Response Time - Priority 1")
2. **sla_description**: Description of what is being measured
3. **metric_type**: One of: UPTIME_PERCENTAGE, AVAILABILITY, RESPONSE_TIME, RESOLUTION_TIME, DELIVERY_TIME, SUCCESS_RATE, ERROR_RATE, COMPLIANCE_RATE, UTILIZATION, THROUGHPUT, RECOVERY_TIME, RECOVERY_POINT, QUALITY_SCORE, CUSTOM
4. **metric_unit**: One of: PERCENTAGE, HOURS, MINUTES, DAYS, BUSINESS_DAYS, COUNT, SCORE
5. **target_value**: The numerical target (e.g., 99.9 for 99.9% uptime)
6. **target_operator**: How to compare: >= (at least), <= (at most), >, <, = (exactly)
7. **warning_threshold**: Optional threshold that triggers warning before breach
8. **severity**: CRITICAL, HIGH, MEDIUM, or LOW based on business impact
9. **has_penalty**: true if there's a financial penalty or credit for breach
10. **penalty_type**: If has_penalty, one of: fixed (fixed amount), percentage (% of contract), credit (service credit), tiered (varies by severity)
11. **penalty_value**: The penalty amount or percentage
12. **penalty_description**: Description of penalty terms
13. **max_penalty_cap**: Maximum penalty cap if specified
14. **measurement_period**: How often measured: monthly, quarterly, annual, weekly
15. **section_reference**: The section number where this SLA is defined
16. **source_text**: The EXACT quote from the contract (up to 500 chars)
17. **confidence**: Your confidence in this extraction (0.0-1.0)

Look for SLAs in:
- Service Level sections/exhibits
- Performance requirements
- Availability commitments
- Response/resolution time requirements
- Quality metrics
- Penalty/credit clauses
- KPIs and measurements

IMPORTANT:
- Extract actual numerical values, not placeholders
- Identify all metrics with targets, even if penalties aren't specified
- Note relationships between metrics (e.g., tiered response times by priority)
- Include both hard SLAs (with penalties) and soft SLAs (commitments without penalties)

Respond with a JSON object:
{{
    "slas": [<list of ExtractedSLA objects>],
    "has_sla_section": <boolean - whether contract has a dedicated SLA section>,
    "has_penalty_mechanism": <boolean - whether any SLA has penalties>,
    "overall_confidence": <float 0.0-1.0>
}}"""


async def extract_slas(
    contract_text: str,
    contract_id: str,
    user_id: str,
    few_shot_context: str = "",
    tenant_id: str | None = None,
    industry_hint: str = "",
) -> SLAExtractionResult | None:
    """Extract SLAs from contract text using DSPy (if compiled) or AI.

    Args:
        contract_text: The full contract text.
        contract_id: Contract ID for context.
        user_id: User ID for tracing.
        tenant_id: Tenant UUID string for DSPy compiled program lookup.

    Returns:
        SLAExtractionResult or None if extraction fails.
    """
    # Try DSPy compiled program first
    if tenant_id:
        try:
            from uuid import UUID as _UUID
            from app.services.dspy_extractor import dspy_extract_slas
            result = await dspy_extract_slas(contract_text, _UUID(tenant_id))
            if result and result.slas:
                logger.info(f"DSPy SLA extraction returned {len(result.slas)} SLAs for {contract_id}")
                return result
        except Exception as e:
            logger.debug(f"DSPy SLA extraction unavailable, falling back: {e}")

    logger.info(f"Extracting SLAs from contract {contract_id}")

    orchestrator = get_orchestrator()

    # Build the list of text segments to send. For short contracts it's the
    # whole text in one call. For long contracts we previously kept ONLY the
    # first 10 SLA-keyword windows in a single call and reported the result as
    # complete — silently dropping SLAs in later sections. Now we iterate over
    # EVERY SLA-bearing window so nothing is dropped, and flag `partial` if any
    # window can't be processed.
    max_chars = 100000
    segments: list[str]
    if len(contract_text) <= max_chars:
        segments = [contract_text]
    else:
        sla_keywords = ["service level", "sla", "availability", "uptime", "response time",
                        "performance", "penalty", "credit", "measurement"]
        chunk_size = 10000
        segments = [
            contract_text[i:i + chunk_size]
            for i in range(0, len(contract_text), chunk_size)
            if any(kw in contract_text[i:i + chunk_size].lower() for kw in sla_keywords)
        ]
        if not segments:
            # No keyword hits — fall back to the leading window rather than the
            # whole (huge) document.
            segments = [contract_text[:max_chars]]

    logger.info(f"Extracting SLAs from contract {contract_id} across {len(segments)} segment(s)")

    all_slas: list[dict] = []
    has_sla_section = False
    has_penalty_mechanism = False
    confidences: list[float] = []
    partial = False
    parsed_ok = 0
    parse_failures = 0

    for seg_idx, segment in enumerate(segments):
        seg_label = f" (part {seg_idx + 1}/{len(segments)})" if len(segments) > 1 else ""
        try:
            response, finish_reason = await orchestrator.invoke_agent_with_meta(
                agent_name="sla_extraction",
                prompt=(
                    f"Extract all SLAs from this contract{seg_label}:\n"
                    f"{f'INDUSTRY-SPECIFIC GUIDANCE: {industry_hint}' + chr(10) if industry_hint else ''}"
                    f"{few_shot_context}\n{segment}"
                ),
                user_id=user_id,
                contract_id=contract_id,
            )

            json_data = extract_json_from_response(response, finish_reason=finish_reason)
            if json_data is None:
                logger.warning(
                    f"No JSON found in SLA extraction response for {contract_id}{seg_label}"
                )
                logger.debug(f"Raw SLA response (first 2000 chars): {response[:2000]}")
                parsed_ok += 1  # clean empty response, not a failure
                continue

            if isinstance(json_data, list):
                # Model returned a bare array of SLAs.
                json_data = {"slas": json_data}

            json_data = preprocess_sla_data(json_data)
            seg_result = SLAExtractionResult(**json_data)
            parsed_ok += 1

            all_slas.extend(sla.model_dump() for sla in seg_result.slas)
            has_sla_section = has_sla_section or seg_result.has_sla_section
            has_penalty_mechanism = has_penalty_mechanism or seg_result.has_penalty_mechanism
            if seg_result.overall_confidence:
                confidences.append(seg_result.overall_confidence)

        except AgentResponseError as e:
            # Truncated / unparseable segment. Don't fail the whole contract —
            # keep whatever other segments produced, but mark the result partial
            # so completeness isn't overstated.
            parse_failures += 1
            partial = True
            logger.warning(f"SLA segment {seg_idx} truncated/unparseable for {contract_id}: {e}")
            continue
        except Exception as e:
            parse_failures += 1
            partial = True
            logger.error(f"SLA extraction failed for {contract_id}{seg_label}: {e}")
            continue

    # If every segment failed to parse (vs. cleanly finding no SLAs), surface a
    # failure so the pipeline records SLA_EXTRACTION as failed.
    if parsed_ok == 0 and parse_failures:
        raise AgentResponseError(
            f"SLA extraction could not parse any of {len(segments)} segment(s) "
            f"({parse_failures} truncated/unparseable) for {contract_id}."
        )

    # Deduplicate identical SLAs that appear across overlapping segments.
    seen: set[tuple] = set()
    deduped: list[ExtractedSLA] = []
    for sla_dict in all_slas:
        key = (
            (sla_dict.get("sla_name") or "").strip().lower(),
            sla_dict.get("metric_type"),
            sla_dict.get("target_value"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ExtractedSLA(**sla_dict))

    result = SLAExtractionResult(
        slas=deduped,
        has_sla_section=has_sla_section,
        has_penalty_mechanism=has_penalty_mechanism,
        overall_confidence=(sum(confidences) / len(confidences)) if confidences else 0.0,
        partial=partial,
    )
    logger.info(
        f"Extracted {len(result.slas)} SLAs from contract {contract_id}"
        f"{' (partial coverage)' if partial else ''}"
    )
    return result


async def store_extracted_slas(
    db: AsyncSession,
    contract_id: uuid.UUID,
    result: SLAExtractionResult,
) -> int:
    """Store extracted SLAs in the database.

    Args:
        db: Database session.
        contract_id: Contract ID.
        result: Extraction result.

    Returns:
        Number of SLAs stored.
    """
    stored_count = 0

    for extracted in result.slas:
        try:
            # Map metric type
            metric_type = SLAMetricType.CUSTOM
            metric_name = extracted.metric_type.upper()
            for mt in SLAMetricType:
                if mt.name == metric_name or mt.value == metric_name.lower():
                    metric_type = mt
                    break

            # Map unit
            metric_unit = SLAUnit.PERCENTAGE
            unit_name = extracted.metric_unit.upper()
            for u in SLAUnit:
                if u.name == unit_name or u.value == unit_name.lower():
                    metric_unit = u
                    break

            # Map severity
            severity = SLASeverity.MEDIUM
            sev_name = extracted.severity.upper()
            for s in SLASeverity:
                if s.name == sev_name or s.value == sev_name.lower():
                    severity = s
                    break

            sla = ContractSLA(
                contract_id=contract_id,
                sla_name=extracted.sla_name,
                sla_description=extracted.sla_description,
                section_reference=extracted.section_reference,
                metric_type=metric_type,
                metric_unit=metric_unit,
                target_value=Decimal(str(extracted.target_value)),
                target_operator=extracted.target_operator or ">=",
                warning_threshold=Decimal(str(extracted.warning_threshold)) if extracted.warning_threshold else None,
                severity=severity,
                has_penalty=extracted.has_penalty,
                penalty_type=extracted.penalty_type,
                penalty_value=Decimal(str(extracted.penalty_value)) if extracted.penalty_value else None,
                penalty_description=extracted.penalty_description,
                max_penalty_cap=Decimal(str(extracted.max_penalty_cap)) if extracted.max_penalty_cap else None,
                measurement_period=extracted.measurement_period,
                source_text=extracted.source_text,
                is_active=True,
            )

            db.add(sla)
            stored_count += 1

        except Exception as e:
            logger.warning(f"Failed to store SLA '{extracted.sla_name}': {e}")

    await db.flush()
    logger.info(f"Stored {stored_count} SLAs for contract {contract_id}")

    return stored_count


def register_sla_extraction_agent() -> None:
    """Register the SLA extraction agent with the orchestrator."""
    orchestrator = get_orchestrator()

    orchestrator.register_agent(
        name="sla_extraction",
        description="""You extract Service Level Agreements (SLAs) from contracts.
        Use this agent for: identifying performance metrics, uptime requirements,
        response times, penalty clauses, service credits, and KPIs.""",
        system_prompt=SLA_EXTRACTION_PROMPT,
        temperature=0.1,
        max_tokens=16000,  # Increased for contracts with many SLAs (70+)
    )

    logger.info("Registered SLA extraction agent")
