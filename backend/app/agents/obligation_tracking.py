"""Obligation Tracking Agent (SK-003).

Extracts contractual obligations with:
- Responsible parties
- Deadlines (fixed, recurring, relative)
- Obligation types
- Triggering conditions
"""

import json
import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import (
    AgentConfig,
    extract_json_from_response,
)
from app.config import settings
from app.models.obligation import Obligation, ObligationType, DeadlineType, ObligationStatus
from app.services.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)


# Obligation types
OBLIGATION_TYPES = {
    "PAYMENT": "Monetary payment obligations",
    "DELIVERY": "Delivery of goods or services",
    "REPORTING": "Reporting or notification requirements",
    "COMPLIANCE": "Regulatory or contractual compliance",
    "NOTIFICATION": "Notice requirements",
    "PERFORMANCE": "Performance or service obligations",
    "OTHER": "Other contractual obligations",
}

# Deadline types
DEADLINE_TYPES = {
    "FIXED": "Specific date (e.g., January 1, 2025)",
    "RECURRING": "Repeating schedule (e.g., monthly, quarterly)",
    "RELATIVE": "Relative to an event (e.g., 30 days after signing)",
    "ONGOING": "Continuous obligation with no specific deadline",
}


class ExtractedObligation(BaseModel):
    """A single extracted obligation."""

    description: str
    obligation_type: str
    obligated_party: str  # Who must perform
    beneficiary_party: str | None = None  # Who benefits
    deadline_type: str
    deadline_value: str | None = None  # The actual deadline or schedule
    deadline_date: str | None = None  # Parsed date if applicable (YYYY-MM-DD)
    recurrence_pattern: str | None = None  # For recurring deadlines (e.g., "monthly", "quarterly")
    triggering_condition: str | None = None  # What triggers this obligation
    consequences: str | None = None  # Consequences of non-compliance
    section_number: str | None = None
    source_quote: str | None = None  # Direct quote from contract
    confidence: float = Field(ge=0.0, le=1.0)


class ObligationExtractionResult(BaseModel):
    """Result of obligation extraction from a contract."""

    obligations: list[ExtractedObligation] = []
    party_summary: dict[str, int] = {}  # Count of obligations per party
    overall_confidence: float = 0.0


OBLIGATION_EXTRACTION_PROMPT = f"""You are a contract obligation extraction specialist. Your task is to identify and extract all contractual obligations from the provided text.

OBLIGATION TYPES:
{json.dumps(OBLIGATION_TYPES, indent=2)}

DEADLINE TYPES:
{json.dumps(DEADLINE_TYPES, indent=2)}

For each obligation found, extract:
1. **description**: Clear description of what must be done
2. **obligation_type**: One of: PAYMENT, DELIVERY, REPORTING, COMPLIANCE, NOTIFICATION, PERFORMANCE, OTHER
3. **obligated_party**: Who must perform this obligation
4. **beneficiary_party**: Who benefits from this obligation (if clear)
5. **deadline_type**: FIXED, RECURRING, RELATIVE, or ONGOING
6. **deadline_value**: The deadline specification as written in the contract
7. **deadline_date**: If a specific date is determinable, provide in YYYY-MM-DD format
8. **recurrence_pattern**: For recurring obligations, the pattern (e.g., "monthly", "quarterly", "annually")
9. **triggering_condition**: What event triggers this obligation (if applicable)
10. **consequences**: What happens if the obligation is not met
11. **section_number**: The section reference
12. **source_quote**: The EXACT quote from the contract that defines this obligation (up to 500 chars)
13. **confidence**: How confident you are (0.0-1.0)

Look for obligations in:
- Payment terms and schedules
- Delivery requirements
- Reporting and notification duties
- Compliance requirements
- Performance metrics and SLAs
- Warranty obligations
- Confidentiality duties

Respond ONLY with valid JSON:
```json
{{
  "obligations": [
    {{
      "description": "Pay monthly service fee",
      "obligation_type": "PAYMENT",
      "obligated_party": "Client",
      "beneficiary_party": "Service Provider",
      "deadline_type": "RECURRING",
      "deadline_value": "Within 30 days of invoice",
      "deadline_date": null,
      "recurrence_pattern": "monthly",
      "triggering_condition": "Receipt of invoice",
      "consequences": "Late fee of 1.5% per month",
      "section_number": "5.2",
      "source_quote": "Client shall pay the monthly service fee within thirty (30) days of receipt of invoice. Failure to pay shall result in a late fee of 1.5% per month.",
      "confidence": 0.9
    }}
  ],
  "party_summary": {{
    "Client": 5,
    "Service Provider": 3
  }}
}}
```"""


def get_obligation_tracking_config() -> AgentConfig:
    """Get configuration for the obligation tracking agent."""
    return AgentConfig(
        name="obligation_tracking",
        description="""Extract contractual obligations including deadlines, responsible parties,
        and compliance requirements. Use for tracking deliverables, payments, and duties.""",
        system_prompt=OBLIGATION_EXTRACTION_PROMPT,
        temperature=0.1,
        max_tokens=6000,  # Increased for comprehensive obligation extraction
    )


def _split_text_for_obligations(text: str, chunk_size: int = 25000, overlap: int = 2000) -> list[str]:
    """Split large text into overlapping chunks for obligation extraction.

    Args:
        text: Full contract text.
        chunk_size: Maximum size per chunk.
        overlap: Overlap between chunks to capture obligations at boundaries.

    Returns:
        List of text chunks.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        # Try to break at a paragraph or section boundary
        if end < len(text):
            # Look for section header or paragraph break
            break_point = text.rfind('\n\n', start + chunk_size - 1500, end)
            if break_point > start:
                end = break_point
        chunks.append(text[start:end])
        start = end - overlap if end < len(text) else end

    return chunks


async def extract_obligations(
    contract_text: str,
    contract_id: str | None = None,
    user_id: str | None = None,
) -> ObligationExtractionResult:
    """Extract obligations from contract text using the AI agent.

    Processes full contract by splitting into chunks and aggregating results.

    Args:
        contract_text: The contract text to extract obligations from.
        contract_id: Optional contract ID for context.
        user_id: User ID for tracking.

    Returns:
        ObligationExtractionResult with all extracted obligations.
    """
    orchestrator = get_orchestrator()

    # Split large contracts into chunks for complete processing
    chunks = _split_text_for_obligations(contract_text, chunk_size=25000, overlap=2000)
    logger.info(f"Processing contract in {len(chunks)} chunk(s) for obligation extraction")

    all_obligations: list[ExtractedObligation] = []
    all_party_counts: dict[str, int] = {}

    for chunk_idx, chunk_text in enumerate(chunks):
        chunk_label = f"[Part {chunk_idx + 1}/{len(chunks)}]" if len(chunks) > 1 else ""

        query = f"""Extract all contractual obligations from the following contract {chunk_label}:

---
{chunk_text}
---

Identify ALL obligations, deadlines, and responsible parties in this section."""

        try:
            from app.services.orchestrator import AgentRequest

            response = await orchestrator.route_request(
                AgentRequest(
                    query=query,
                    user_id=user_id or "system",
                    session_id=f"obligation_{contract_id or 'unknown'}_{chunk_idx}",
                    contract_id=contract_id,
                    context={"task": "obligation_tracking", "chunk": chunk_idx},
                )
            )

            json_data = extract_json_from_response(response.response)
            if json_data:
                chunk_result = _parse_obligation_response(json_data)
                all_obligations.extend(chunk_result.obligations)
                # Aggregate party counts
                for party, count in chunk_result.party_summary.items():
                    all_party_counts[party] = all_party_counts.get(party, 0) + count

        except Exception as e:
            logger.warning(f"Error processing chunk {chunk_idx} for obligations: {e}")
            continue

    if not all_obligations:
        logger.warning("No obligations found in any chunk")
        return ObligationExtractionResult()

    # Deduplicate obligations by description similarity
    unique_obligations = _deduplicate_obligations(all_obligations)

    logger.info(f"Extracted {len(unique_obligations)} unique obligations from {len(all_obligations)} total")

    avg_confidence = (
        sum(o.confidence for o in unique_obligations) / len(unique_obligations)
        if unique_obligations
        else 0.0
    )

    return ObligationExtractionResult(
        obligations=unique_obligations,
        party_summary=all_party_counts,
        overall_confidence=avg_confidence,
    )


def _deduplicate_obligations(obligations: list[ExtractedObligation]) -> list[ExtractedObligation]:
    """Deduplicate obligations by description similarity.

    Args:
        obligations: List of obligations from multiple chunks.

    Returns:
        Deduplicated list of obligations.
    """
    if not obligations:
        return []

    unique: list[ExtractedObligation] = []
    seen_descriptions: set[str] = set()

    for obl in obligations:
        # Normalize description for comparison
        norm_desc = obl.description.lower().strip()[:100]

        # Check for similar descriptions
        is_duplicate = False
        for seen in seen_descriptions:
            # Simple similarity check - if 80% of words match, consider duplicate
            obl_words = set(norm_desc.split())
            seen_words = set(seen.split())
            if len(obl_words & seen_words) >= 0.8 * min(len(obl_words), len(seen_words)):
                is_duplicate = True
                break

        if not is_duplicate:
            seen_descriptions.add(norm_desc)
            unique.append(obl)

    return unique


def _parse_obligation_response(data: dict[str, Any]) -> ObligationExtractionResult:
    """Parse the JSON response into ObligationExtractionResult."""
    obligations = []

    for obl_data in data.get("obligations", []):
        try:
            obl_type = obl_data.get("obligation_type", "OTHER").upper()
            if obl_type not in OBLIGATION_TYPES:
                obl_type = "OTHER"

            deadline_type = obl_data.get("deadline_type", "ONGOING").upper()
            if deadline_type not in DEADLINE_TYPES:
                deadline_type = "ONGOING"

            obligations.append(
                ExtractedObligation(
                    description=obl_data.get("description", "")[:500],
                    obligation_type=obl_type,
                    obligated_party=obl_data.get("obligated_party", "Unknown"),
                    beneficiary_party=obl_data.get("beneficiary_party"),
                    deadline_type=deadline_type,
                    deadline_value=obl_data.get("deadline_value"),
                    deadline_date=obl_data.get("deadline_date"),
                    recurrence_pattern=obl_data.get("recurrence_pattern"),
                    triggering_condition=obl_data.get("triggering_condition"),
                    consequences=obl_data.get("consequences"),
                    section_number=obl_data.get("section_number"),
                    source_quote=obl_data.get("source_quote"),
                    confidence=float(obl_data.get("confidence", 0.5)),
                )
            )
        except Exception as e:
            logger.warning(f"Error parsing obligation: {e}")

    party_summary = data.get("party_summary", {})

    avg_confidence = (
        sum(o.confidence for o in obligations) / len(obligations)
        if obligations
        else 0.0
    )

    return ObligationExtractionResult(
        obligations=obligations,
        party_summary=party_summary,
        overall_confidence=avg_confidence,
    )


async def store_extracted_obligations(
    db: AsyncSession,
    contract_id: uuid.UUID,
    result: ObligationExtractionResult,
) -> list[Obligation]:
    """Store extracted obligations in the database.

    Args:
        db: Database session.
        contract_id: Contract ID to link obligations to.
        result: Extraction result with obligations.

    Returns:
        List of created Obligation records.
    """
    created = []

    type_map = {
        "PAYMENT": ObligationType.PAYMENT,
        "DELIVERY": ObligationType.DELIVERY,
        "REPORTING": ObligationType.REPORTING,
        "COMPLIANCE": ObligationType.COMPLIANCE,
        "NOTIFICATION": ObligationType.NOTIFICATION,
        "PERFORMANCE": ObligationType.PERFORMANCE,
        "OTHER": ObligationType.OTHER,
    }

    deadline_map = {
        "FIXED": DeadlineType.FIXED_DATE,
        "FIXED_DATE": DeadlineType.FIXED_DATE,
        "RECURRING": DeadlineType.RECURRING,
        "RELATIVE": DeadlineType.RELATIVE,
        "ONGOING": DeadlineType.ONGOING,
    }

    for extracted in result.obligations:
        # Parse deadline date if provided
        deadline = None
        if extracted.deadline_date:
            try:
                deadline = date.fromisoformat(extracted.deadline_date)
            except ValueError:
                pass

        obligation = Obligation(
            contract_id=contract_id,
            description=extracted.description,
            obligation_type=type_map.get(extracted.obligation_type, ObligationType.OTHER),
            obligated_party=extracted.obligated_party,
            beneficiary_party=extracted.beneficiary_party,
            deadline_type=deadline_map.get(extracted.deadline_type, DeadlineType.ONGOING),
            deadline=deadline,
            recurrence_pattern=extracted.recurrence_pattern,
            relative_deadline_text=extracted.deadline_value,
            trigger_condition=extracted.triggering_condition,
            consequence_of_breach=extracted.consequences,
            source_text=extracted.source_quote[:1000] if extracted.source_quote else None,
            status=ObligationStatus.PENDING,
        )

        db.add(obligation)
        created.append(obligation)
        print(f"  [OBLIGATION] Added: {extracted.description[:50]}...")

    print(f"[OBLIGATION] Flushing {len(created)} obligations...")
    await db.flush()
    print(f"[OBLIGATION] Flush complete")
    return created


def register_obligation_tracking_agent() -> None:
    """Register the obligation tracking agent with the orchestrator."""
    config = get_obligation_tracking_config()
    orchestrator = get_orchestrator()

    if orchestrator.get_agent(config.name):
        return

    orchestrator.register_agent(
        name=config.name,
        description=config.description,
        system_prompt=config.system_prompt,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
