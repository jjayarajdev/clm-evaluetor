"""Clause Extraction Agent (SK-002).

Identifies and extracts specific clause types from contracts:
- Indemnification
- Limitation of liability
- Termination
- Confidentiality
- And 13 more clause types...
"""

import json
import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import (
    AgentConfig,
    ContractSearchTool,
    extract_json_from_response,
)
from app.config import settings
from app.models.clause import Clause, ClauseType, RiskLevel
from app.services.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)


# All supported clause types with descriptions
SUPPORTED_CLAUSE_TYPES = {
    # Legal/Risk clauses
    "INDEMNIFICATION": "Provisions requiring one party to compensate the other for losses",
    "LIMITATION_OF_LIABILITY": "Caps or limits on liability exposure",
    "TERMINATION": "Conditions and procedures for ending the contract",
    "CONFIDENTIALITY": "Protection of confidential information",
    "INTELLECTUAL_PROPERTY": "Ownership and licensing of IP rights",
    "PAYMENT_TERMS": "Payment schedules, amounts, and conditions",
    "WARRANTY": "Guarantees about products, services, or performance",
    "FORCE_MAJEURE": "Excuses for non-performance due to extraordinary events",
    "NON_COMPETE": "Restrictions on competitive activities",
    "NON_SOLICITATION": "Restrictions on soliciting employees or customers",
    "DATA_PROTECTION": "Privacy and data handling requirements",
    "DISPUTE_RESOLUTION": "How disputes will be handled (arbitration, litigation)",
    "ASSIGNMENT": "Ability to transfer rights or obligations",
    "NOTICE": "Requirements for providing notices between parties",
    "GOVERNING_LAW": "Which jurisdiction's laws apply",
    "SLA": "Service level agreements with specific metrics and penalties",
    "AUTO_RENEWAL": "Automatic renewal terms and conditions",

    # IT Service/Outsourcing contract clauses
    "SERVICE_DESCRIPTION": "Description of services provided, service catalog, bundles",
    "SERVICE_LEVEL": "Performance metrics, targets, KPIs, response times, availability percentages (99.9%, 99.95%), SLA tables with columns like 'Target', 'Minimum', 'Measurement Window', uptime requirements, incident response/resolution times, throughput metrics",
    "DELIVERABLE": "What must be delivered, milestones, acceptance criteria",
    "GOVERNANCE": "Management structure, oversight, escalation, reporting",
    "TRANSITION": "Exit planning, knowledge transfer, handover procedures",
    "CHANGE_MANAGEMENT": "Change request process, impact assessment, approvals",
    "SUPPORT": "Helpdesk, incident management, problem resolution, escalation",
    "SECURITY": "Security requirements, access controls, compliance",
    "PERSONNEL": "Staffing requirements, roles, responsibilities, key personnel",
    "PRICING": "Cost structure, rate cards, pricing models, fee schedules",
    "RISK_MITIGATION": "Risk identification, mitigation strategies, contingency",
    "SCOPE": "Scope of work, inclusions, exclusions, boundaries",
    "ACCEPTANCE": "Acceptance criteria, testing procedures, sign-off process",
}


class ExtractedClause(BaseModel):
    """A single extracted clause."""

    clause_type: str
    text: str
    section_number: str | None = None
    page_number: int | None = None
    risk_level: str | None = None  # LOW, MEDIUM, HIGH
    confidence: float = Field(ge=0.0, le=1.0)
    key_terms: list[str] = []
    notes: str | None = None


class ClauseExtractionResult(BaseModel):
    """Result of clause extraction from a contract."""

    extracted_clauses: list[ExtractedClause] = []
    missing_clauses: list[str] = []  # Expected but not found
    overall_confidence: float = 0.0


CLAUSE_EXTRACTION_PROMPT = f"""You are a contract clause extraction specialist. Your task is to identify and extract specific clause types from contract text.

SUPPORTED CLAUSE TYPES:
{json.dumps(SUPPORTED_CLAUSE_TYPES, indent=2)}

For each clause found in the contract, extract:
1. **clause_type**: One of the supported types above
2. **text**: The exact text of the clause (up to 2000 characters)
3. **section_number**: The section or article number if visible
4. **page_number**: The page number if available
5. **risk_level**: Assess as LOW, MEDIUM, or HIGH based on:
   - HIGH: Unfavorable terms, unlimited liability, one-sided obligations
   - MEDIUM: Standard but could be negotiated better
   - LOW: Standard/favorable terms
6. **confidence**: How confident you are this is the correct clause type (0.0-1.0)
7. **key_terms**: Important terms or values within the clause
8. **notes**: Any important observations about this clause

Also identify any EXPECTED clauses that are MISSING from the contract. Common expected clauses include: LIMITATION_OF_LIABILITY, INDEMNIFICATION, TERMINATION, CONFIDENTIALITY, GOVERNING_LAW.

IMPORTANT - Recognizing SERVICE_LEVEL content:
- SLA metric tables with columns like "Target", "Minimum", "Measurement Window" = SERVICE_LEVEL
- Availability percentages (99.9%, 99.95%, 99.99%) = SERVICE_LEVEL
- Response/resolution time requirements (respond within 4 hours, resolve within 24 hours) = SERVICE_LEVEL
- Performance thresholds with units (minutes, hours, %, count) = SERVICE_LEVEL
- Priority definitions (P1, P2, P3, P4) with response times = SERVICE_LEVEL
- Do NOT classify these as OTHER - they are SERVICE_LEVEL clauses

Respond ONLY with valid JSON in this format:
```json
{{
  "extracted_clauses": [
    {{
      "clause_type": "INDEMNIFICATION",
      "text": "Company agrees to indemnify and hold harmless...",
      "section_number": "8.1",
      "page_number": 5,
      "risk_level": "HIGH",
      "confidence": 0.95,
      "key_terms": ["unlimited", "third party claims"],
      "notes": "Broad indemnification without cap"
    }}
  ],
  "missing_clauses": ["LIMITATION_OF_LIABILITY", "FORCE_MAJEURE"]
}}
```

Extract ALL relevant clauses, not just the first one of each type."""


def get_clause_extraction_config() -> AgentConfig:
    """Get configuration for the clause extraction agent."""
    return AgentConfig(
        name="clause_extraction",
        description="""Extract and classify specific clause types from contract text.
        Identifies 17 clause types including indemnification, liability, termination,
        confidentiality, IP, payment terms, warranties, and more.""",
        system_prompt=CLAUSE_EXTRACTION_PROMPT,
        temperature=0.1,
        max_tokens=12000,  # Increased for contracts with many clauses (50+)
    )


async def extract_clauses(
    contract_text: str,
    contract_id: str | None = None,
    user_id: str | None = None,
    few_shot_context: str = "",
    tenant_id: str | None = None,
    industry_hint: str = "",
) -> ClauseExtractionResult:
    """Extract clauses from contract text using DSPy (if compiled) or AI agent.

    Args:
        contract_text: The contract text to extract clauses from.
        contract_id: Optional contract ID for context.
        user_id: User ID for tracking.
        tenant_id: Tenant UUID string for DSPy compiled program lookup.

    Returns:
        ClauseExtractionResult with all extracted clauses.
    """
    # Try DSPy compiled program first
    if tenant_id:
        try:
            from uuid import UUID as _UUID
            from app.services.dspy_extractor import dspy_extract_clauses
            result = await dspy_extract_clauses(contract_text, _UUID(tenant_id))
            if result and result.extracted_clauses:
                logger.info(f"DSPy clause extraction returned {len(result.extracted_clauses)} clauses")
                return result
        except Exception as e:
            logger.debug(f"DSPy clause extraction unavailable, falling back: {e}")

    orchestrator = get_orchestrator()

    # Process in chunks if document is very long
    # Increased chunk size to 25000 for better context per chunk
    max_chunk_size = 25000
    all_clauses = []
    missing_clauses_set = set()

    logger.info(f"Processing contract for clause extraction (length: {len(contract_text)} chars)")

    # Split into overlapping chunks for better extraction
    chunks = _split_for_extraction(contract_text, max_chunk_size)

    for i, chunk in enumerate(chunks):
        industry_context = f"\nINDUSTRY-SPECIFIC GUIDANCE:\n{industry_hint}\n" if industry_hint else ""

        query = f"""Extract all clauses from this contract section (part {i + 1} of {len(chunks)}):
{industry_context}{few_shot_context}
---
{chunk}
---

Identify all clause types present and note any obviously missing standard clauses."""

        try:
            from app.services.orchestrator import AgentRequest

            response = await orchestrator.route_request(
                AgentRequest(
                    query=query,
                    user_id=user_id or "system",
                    session_id=f"clause_{contract_id or 'unknown'}_{i}",
                    contract_id=contract_id,
                    context={"task": "clause_extraction", "chunk": i},
                )
            )

            # Parse the JSON response
            json_data = extract_json_from_response(response.response)
            if json_data:
                chunk_result = _parse_clause_response(json_data)
                all_clauses.extend(chunk_result.extracted_clauses)
                missing_clauses_set.update(chunk_result.missing_clauses)

        except Exception as e:
            logger.exception(f"Error extracting clauses from chunk {i}: {e}")

    # Deduplicate clauses (same type and similar text)
    unique_clauses = _deduplicate_clauses(all_clauses)

    # Remove from missing list any that were found
    found_types = {c.clause_type for c in unique_clauses}
    final_missing = [m for m in missing_clauses_set if m not in found_types]

    # Calculate overall confidence
    avg_confidence = (
        sum(c.confidence for c in unique_clauses) / len(unique_clauses)
        if unique_clauses
        else 0.0
    )

    return ClauseExtractionResult(
        extracted_clauses=unique_clauses,
        missing_clauses=final_missing,
        overall_confidence=avg_confidence,
    )


def _split_for_extraction(text: str, max_size: int) -> list[str]:
    """Split text into overlapping chunks for extraction.

    Args:
        text: Full contract text.
        max_size: Maximum chunk size.

    Returns:
        List of text chunks.
    """
    if len(text) <= max_size:
        return [text]

    chunks = []
    overlap = 2000  # Increased overlap to better catch clauses at boundaries
    start = 0

    while start < len(text):
        end = start + max_size

        # Find a good break point at section boundaries
        if end < len(text):
            # Look for section break (article/section headers)
            break_point = text.rfind("\n\n", start + max_size - 2000, end)
            if break_point == -1:
                break_point = text.rfind(". ", start + max_size - 1000, end)
            if break_point != -1 and break_point > start:
                end = break_point + 2

        chunks.append(text[start:end])
        start = end - overlap if end < len(text) else end

    logger.info(f"Split contract into {len(chunks)} chunks for clause extraction")
    return chunks


def _parse_clause_response(data: dict[str, Any]) -> ClauseExtractionResult:
    """Parse the JSON response into ClauseExtractionResult.

    Args:
        data: Parsed JSON data from agent response.

    Returns:
        ClauseExtractionResult object.
    """
    clauses = []

    for clause_data in data.get("extracted_clauses", []):
        try:
            clause_type = clause_data.get("clause_type", "").upper()
            if clause_type not in SUPPORTED_CLAUSE_TYPES and clause_type != "OTHER":
                continue

            clauses.append(
                ExtractedClause(
                    clause_type=clause_type,
                    text=clause_data.get("text", "")[:2000],  # Limit text length
                    section_number=clause_data.get("section_number"),
                    page_number=clause_data.get("page_number"),
                    risk_level=clause_data.get("risk_level"),
                    confidence=float(clause_data.get("confidence", 0.5)),
                    key_terms=clause_data.get("key_terms", []),
                    notes=clause_data.get("notes"),
                )
            )
        except Exception as e:
            logger.warning(f"Error parsing clause: {e}")

    missing = data.get("missing_clauses", [])
    if not isinstance(missing, list):
        missing = []

    return ClauseExtractionResult(
        extracted_clauses=clauses,
        missing_clauses=[m.upper() for m in missing if isinstance(m, str)],
    )


def _deduplicate_clauses(clauses: list[ExtractedClause]) -> list[ExtractedClause]:
    """Remove duplicate clauses based on type and text similarity.

    Args:
        clauses: List of extracted clauses.

    Returns:
        Deduplicated list.
    """
    seen = {}  # (type, text_hash) -> clause

    for clause in clauses:
        # Create a hash of the first 200 chars of text
        text_key = clause.text[:200].strip().lower()
        key = (clause.clause_type, text_key)

        if key not in seen or clause.confidence > seen[key].confidence:
            seen[key] = clause

    return list(seen.values())


async def store_extracted_clauses(
    db: AsyncSession,
    contract_id: uuid.UUID,
    result: ClauseExtractionResult,
) -> list[Clause]:
    """Store extracted clauses in the database.

    Args:
        db: Database session.
        contract_id: Contract ID to link clauses to.
        result: Extraction result with clauses.

    Returns:
        List of created Clause records.
    """
    created_clauses = []

    # Map string types to enum
    type_map = {
        # Legal/Risk clauses
        "INDEMNIFICATION": ClauseType.INDEMNIFICATION,
        "LIMITATION_OF_LIABILITY": ClauseType.LIMITATION_OF_LIABILITY,
        "TERMINATION": ClauseType.TERMINATION,
        "CONFIDENTIALITY": ClauseType.CONFIDENTIALITY,
        "INTELLECTUAL_PROPERTY": ClauseType.INTELLECTUAL_PROPERTY,
        "PAYMENT_TERMS": ClauseType.PAYMENT_TERMS,
        "WARRANTY": ClauseType.WARRANTY,
        "FORCE_MAJEURE": ClauseType.FORCE_MAJEURE,
        "NON_COMPETE": ClauseType.NON_COMPETE,
        "NON_SOLICITATION": ClauseType.NON_SOLICITATION,
        "DATA_PROTECTION": ClauseType.DATA_PROTECTION,
        "DISPUTE_RESOLUTION": ClauseType.DISPUTE_RESOLUTION,
        "ASSIGNMENT": ClauseType.ASSIGNMENT,
        "NOTICE": ClauseType.NOTICE,
        "GOVERNING_LAW": ClauseType.GOVERNING_LAW,
        "SLA": ClauseType.SLA,
        "AUTO_RENEWAL": ClauseType.AUTO_RENEWAL,
        # IT Service/Outsourcing contract clauses
        "SERVICE_DESCRIPTION": ClauseType.SERVICE_DESCRIPTION,
        "SERVICE_LEVEL": ClauseType.SERVICE_LEVEL,
        "DELIVERABLE": ClauseType.DELIVERABLE,
        "GOVERNANCE": ClauseType.GOVERNANCE,
        "TRANSITION": ClauseType.TRANSITION,
        "CHANGE_MANAGEMENT": ClauseType.CHANGE_MANAGEMENT,
        "SUPPORT": ClauseType.SUPPORT,
        "SECURITY": ClauseType.SECURITY,
        "PERSONNEL": ClauseType.PERSONNEL,
        "PRICING": ClauseType.PRICING,
        "RISK_MITIGATION": ClauseType.RISK_MITIGATION,
        "SCOPE": ClauseType.SCOPE,
        "ACCEPTANCE": ClauseType.ACCEPTANCE,
    }

    risk_map = {
        "LOW": RiskLevel.LOW,
        "MEDIUM": RiskLevel.MEDIUM,
        "HIGH": RiskLevel.HIGH,
    }

    for extracted in result.extracted_clauses:
        clause_type = type_map.get(extracted.clause_type, ClauseType.OTHER)
        risk_level = risk_map.get(extracted.risk_level) if extracted.risk_level else None

        # Truncate section_number to fit database column (255 chars)
        section_number = extracted.section_number
        if section_number and len(section_number) > 255:
            section_number = section_number[:252] + "..."

        clause = Clause(
            contract_id=contract_id,
            clause_type=clause_type,
            text=extracted.text,
            section_number=section_number,
            page_number=extracted.page_number,
            risk_level=risk_level,
            confidence_score=extracted.confidence,
        )

        db.add(clause)
        created_clauses.append(clause)

    await db.flush()
    return created_clauses


async def classify_uncategorized_chunks(
    db: AsyncSession,
    contract_id: uuid.UUID,
) -> int:
    """Use AI to classify uncategorized chunks into proper clause types.

    Sends each OTHER chunk to the LLM for classification.

    Args:
        db: Database session.
        contract_id: Contract ID to process.

    Returns:
        Number of chunks classified.
    """
    from sqlalchemy import select
    from app.services.orchestrator import get_orchestrator
    from app.agents.base import extract_json_from_response

    logger.info(f"Starting AI classification for contract {contract_id}")

    # Find all OTHER clauses for this contract
    result = await db.execute(
        select(Clause).where(
            Clause.contract_id == contract_id,
            Clause.clause_type == ClauseType.OTHER,
        )
    )
    other_clauses = result.scalars().all()

    logger.info(f"Found {len(other_clauses)} uncategorized chunks to classify")

    if not other_clauses:
        return 0

    orchestrator = get_orchestrator()
    classified_count = 0

    # Build classification prompt
    clause_types_list = ", ".join(SUPPORTED_CLAUSE_TYPES.keys())

    # Process in batches to reduce API calls
    batch_size = 10
    for i in range(0, len(other_clauses), batch_size):
        batch = other_clauses[i:i + batch_size]

        # Build batch prompt
        chunks_text = ""
        for idx, clause in enumerate(batch):
            text_preview = (clause.text or "")[:500]
            chunks_text += f"\n\nCHUNK {idx + 1}:\n{text_preview}"

        prompt = f"""Classify each text chunk into ONE of these clause types:
{clause_types_list}

If the chunk contains SLA metrics, availability percentages, response times,
performance targets, or measurement data - classify as SERVICE_LEVEL.

If it doesn't fit any category, use OTHER.

{chunks_text}

Respond with JSON array:
[{{"chunk": 1, "type": "SERVICE_LEVEL"}}, {{"chunk": 2, "type": "GOVERNANCE"}}, ...]"""

        try:
            logger.info(f"Sending batch {i//batch_size + 1} to LLM for classification")
            response = await orchestrator.invoke_agent(
                agent_name="clause_extraction",
                prompt=prompt,
                user_id="system",
                contract_id=str(contract_id),
            )
            logger.info(f"LLM response received for batch {i//batch_size + 1}")

            json_data = extract_json_from_response(response)
            logger.info(f"Parsed JSON: {json_data}")
            if json_data and isinstance(json_data, list):
                for item in json_data:
                    chunk_idx = item.get("chunk", 0) - 1
                    clause_type_str = item.get("type", "OTHER").upper()

                    if 0 <= chunk_idx < len(batch):
                        # Map to enum
                        new_type = ClauseType.OTHER
                        for ct in ClauseType:
                            if ct.name == clause_type_str:
                                new_type = ct
                                break

                        if new_type != ClauseType.OTHER:
                            batch[chunk_idx].clause_type = new_type
                            classified_count += 1

        except Exception as e:
            logger.warning(f"Failed to classify batch {i}: {e}")

    if classified_count > 0:
        await db.flush()
        logger.info(f"AI classified {classified_count} chunks for contract {contract_id}")

    return classified_count


# Keep old name for backwards compatibility
async def reclassify_sla_chunks(
    db: AsyncSession,
    contract_id: uuid.UUID,
) -> int:
    """Backwards compatible wrapper for classify_uncategorized_chunks."""
    import sys
    logger.warning(f"[RECLASSIFY] Called for contract {contract_id}")
    print(f"[RECLASSIFY] Called for contract {contract_id}", flush=True)
    sys.stdout.flush()
    try:
        result = await classify_uncategorized_chunks(db, contract_id)
        logger.warning(f"[RECLASSIFY] Completed with {result} reclassified")
        return result
    except Exception as e:
        logger.exception(f"[RECLASSIFY] ERROR in classify_uncategorized_chunks: {e}")
        return 0


def register_clause_extraction_agent() -> None:
    """Register the clause extraction agent with the orchestrator."""
    config = get_clause_extraction_config()
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
