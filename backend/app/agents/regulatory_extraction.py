"""Regulatory Obligation Extraction Agent.

Extracts industry-specific regulatory obligations from contracts in regulated
industries. Focuses on obligations related to:
- Audit rights and inspection requirements
- Change control and approval processes
- Deviation and incident reporting
- Recall and safety response
- Record retention and documentation
- Training and qualification requirements
"""

import json
import logging
import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import (
    AgentConfig,
    extract_json_from_response,
)
from app.models.industry import Industry, REGULATED_INDUSTRIES
from app.models.obligation import RAGStatus
from app.models.regulatory_obligation import (
    RegulatoryObligation,
    RegulationType,
    ObligationCategory,
)
from app.services.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)


# Regulatory categories with descriptions for the LLM
REGULATORY_CATEGORIES = {
    "audit_rights": {
        "description": "Rights to audit supplier/partner operations, records, or facilities",
        "keywords": ["audit", "inspection", "examine records", "right to audit", "access to facilities"],
        "typical_frequency": "annual",
    },
    "change_control": {
        "description": "Requirements to notify or get approval for changes",
        "keywords": ["change control", "prior approval", "written consent", "modification", "change notification"],
        "typical_frequency": "as_needed",
    },
    "deviation_reporting": {
        "description": "Requirements to report deviations, incidents, or non-conformances",
        "keywords": ["deviation", "incident report", "notify immediately", "non-conformance", "oos", "oat"],
        "typical_frequency": "as_needed",
    },
    "recall_response": {
        "description": "Product recall or field action response procedures",
        "keywords": ["recall", "field action", "safety alert", "product withdrawal", "market action"],
        "typical_frequency": "as_needed",
    },
    "adverse_event_reporting": {
        "description": "Requirements to report adverse events or safety issues",
        "keywords": ["adverse event", "pharmacovigilance", "safety report", "medical event", "serious adverse"],
        "typical_frequency": "as_needed",
    },
    "record_retention": {
        "description": "Requirements for record keeping and retention periods",
        "keywords": ["retain records", "record retention", "maintain documentation", "archive", "preserve records"],
        "typical_frequency": "ongoing",
    },
    "training_requirements": {
        "description": "Training and qualification requirements for personnel",
        "keywords": ["training", "qualification", "certified personnel", "competency", "education"],
        "typical_frequency": "annual",
    },
    "quality_review": {
        "description": "Periodic quality reviews and assessments",
        "keywords": ["quality review", "management review", "annual review", "performance review", "quality assessment"],
        "typical_frequency": "annual",
    },
    "regulatory_reporting": {
        "description": "Required submissions to regulatory authorities",
        "keywords": ["regulatory submission", "fda submission", "annual report", "regulatory filing"],
        "typical_frequency": "varies",
    },
    "data_protection": {
        "description": "Data protection and privacy compliance requirements",
        "keywords": ["data protection", "privacy", "gdpr", "hipaa", "data security", "breach notification"],
        "typical_frequency": "ongoing",
    },
}


# Regulation type keywords for detection
REGULATION_KEYWORDS = {
    "fda": ["fda", "21 cfr", "food and drug", "new drug application", "nda", "anda"],
    "hipaa": ["hipaa", "45 cfr", "protected health information", "phi", "covered entity"],
    "gmp": ["gmp", "good manufacturing practice", "current good manufacturing", "cgmp"],
    "gdpr": ["gdpr", "general data protection", "data subject", "controller", "processor"],
    "iso_9001": ["iso 9001", "quality management system", "qms"],
    "iso_13485": ["iso 13485", "medical device quality"],
    "osha": ["osha", "occupational safety", "29 cfr", "workplace safety"],
    "epa": ["epa", "environmental protection", "environmental compliance", "rcra"],
    "soc2": ["soc 2", "soc2", "service organization control", "trust services"],
}


class ExtractedRegulatoryObligation(BaseModel):
    """A single extracted regulatory obligation."""

    title: str
    description: str
    obligation_category: str
    regulation_type: str
    regulation_reference: str | None = None
    source_text: str | None = None
    source_section: str | None = None
    responsible_party: str | None = None
    frequency: str | None = None
    deadline_days: int | None = None  # If there's a specific deadline in days
    confidence: float = Field(ge=0.0, le=1.0)


class RegulatoryExtractionResult(BaseModel):
    """Result of regulatory obligation extraction."""

    industry: str
    obligations: list[ExtractedRegulatoryObligation] = []
    regulation_summary: dict[str, int] = {}  # Count per regulation type
    overall_confidence: float = 0.0


REGULATORY_EXTRACTION_PROMPT = f"""You are a regulatory compliance extraction specialist. Your task is to identify and extract regulatory obligations from contracts in regulated industries.

REGULATORY CATEGORIES:
{json.dumps({k: v["description"] for k, v in REGULATORY_CATEGORIES.items()}, indent=2)}

REGULATION TYPES:
- FDA: US Food and Drug Administration (pharmaceuticals, medical devices, food)
- HIPAA: Health Insurance Portability and Accountability Act
- GMP: Good Manufacturing Practice
- GDPR: General Data Protection Regulation
- ISO_9001: Quality Management System standard
- ISO_13485: Medical Device Quality Management
- OSHA: Occupational Safety and Health
- EPA: Environmental Protection Agency
- SOC2: Service Organization Control Type 2
- Other: Other regulatory frameworks

For each regulatory obligation found, extract:
1. **title**: Short title describing the obligation (max 100 chars)
2. **description**: Full description of the regulatory requirement
3. **obligation_category**: One of: audit_rights, change_control, deviation_reporting, recall_response, adverse_event_reporting, record_retention, training_requirements, quality_review, regulatory_reporting, data_protection, other
4. **regulation_type**: Which regulation this relates to (fda, hipaa, gmp, gdpr, iso_9001, iso_13485, osha, epa, soc2, other)
5. **regulation_reference**: Specific regulatory reference (e.g., "21 CFR 211.68", "HIPAA 45 CFR 164.502")
6. **source_text**: Direct quote from the contract (up to 500 chars)
7. **source_section**: Contract section reference
8. **responsible_party**: Who must comply
9. **frequency**: How often this must be performed (ongoing, annual, quarterly, monthly, as_needed, other)
10. **deadline_days**: If a specific timeline is mentioned (e.g., "within 5 days" = 5)
11. **confidence**: How confident you are (0.0-1.0)

Focus on obligations that are:
- Mandated by regulations (FDA, HIPAA, GMP, GDPR, etc.)
- Related to audits, inspections, change control
- Required reporting or notification duties
- Record retention and documentation requirements
- Training and qualification requirements
- Quality and compliance reviews

Respond ONLY with valid JSON:
```json
{{
  "industry": "pharmaceutical",
  "obligations": [
    {{
      "title": "Annual Quality Audit",
      "description": "Supplier shall permit annual quality audits of manufacturing facilities to verify GMP compliance",
      "obligation_category": "audit_rights",
      "regulation_type": "gmp",
      "regulation_reference": "21 CFR Part 211",
      "source_text": "Supplier shall permit Customer to conduct annual audits of Supplier's manufacturing facilities...",
      "source_section": "8.3",
      "responsible_party": "Supplier",
      "frequency": "annual",
      "deadline_days": null,
      "confidence": 0.95
    }}
  ],
  "regulation_summary": {{
    "gmp": 3,
    "fda": 2
  }}
}}
```"""


def get_regulatory_extraction_config() -> AgentConfig:
    """Get configuration for the regulatory extraction agent."""
    return AgentConfig(
        name="regulatory_extraction",
        description="""Extract regulatory compliance obligations from contracts in regulated industries.
        Identifies audit rights, change control, deviation reporting, and other regulatory requirements.""",
        system_prompt=REGULATORY_EXTRACTION_PROMPT,
        temperature=0.1,
        max_tokens=5000,  # Increased for comprehensive regulatory extraction
    )


def _split_for_regulatory_extraction(text: str, chunk_size: int = 30000, overlap: int = 2000) -> list[str]:
    """Split large text into overlapping chunks for regulatory extraction.

    Args:
        text: Full contract text.
        chunk_size: Maximum size per chunk.
        overlap: Overlap between chunks.

    Returns:
        List of text chunks.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            break_point = text.rfind('\n\n', start + chunk_size - 2000, end)
            if break_point > start:
                end = break_point
        chunks.append(text[start:end])
        start = end - overlap if end < len(text) else end

    return chunks


async def extract_regulatory_obligations(
    contract_text: str,
    industry: Industry,
    contract_id: str | None = None,
    user_id: str | None = None,
) -> RegulatoryExtractionResult:
    """Extract regulatory obligations from contract text.

    Args:
        contract_text: The contract text to analyze.
        industry: The detected industry of the contract.
        contract_id: Optional contract ID for context.
        user_id: User ID for tracking.

    Returns:
        RegulatoryExtractionResult with extracted obligations.
    """
    # Only extract for regulated industries
    if industry not in REGULATED_INDUSTRIES:
        logger.info(f"Skipping regulatory extraction for non-regulated industry: {industry.value}")
        return RegulatoryExtractionResult(industry=industry.value)

    orchestrator = get_orchestrator()

    # Process full contract in chunks for large documents
    chunks = _split_for_regulatory_extraction(contract_text, chunk_size=30000, overlap=2000)
    logger.info(f"Processing contract in {len(chunks)} chunk(s) for regulatory extraction")

    all_obligations: list = []
    all_regulation_counts: dict = {}

    for chunk_idx, text_sample in enumerate(chunks):
        chunk_label = f"[Part {chunk_idx + 1}/{len(chunks)}]" if len(chunks) > 1 else ""

        query = f"""Extract all regulatory compliance obligations from the following {industry.value} industry contract {chunk_label}.

Industry: {industry.value}

Focus on:
- FDA, HIPAA, GMP, GDPR, or other regulatory requirements
- Audit and inspection rights
- Change control procedures
- Deviation and incident reporting
- Record retention requirements
- Training and qualification requirements

CONTRACT TEXT:
---
{text_sample}
---

Identify ALL regulatory obligations, compliance requirements, and reporting duties."""

        try:
            from app.services.orchestrator import AgentRequest

            response = await orchestrator.route_request(
                AgentRequest(
                    query=query,
                    user_id=user_id or "system",
                    session_id=f"regulatory_{contract_id or 'unknown'}_{chunk_idx}",
                    contract_id=contract_id,
                    context={"task": "regulatory_extraction", "industry": industry.value, "chunk": chunk_idx},
                )
            )

            json_data = extract_json_from_response(response.response)
            if json_data:
                chunk_result = _parse_regulatory_response(json_data, industry)
                all_obligations.extend(chunk_result.obligations)
                # Aggregate regulation counts
                for reg, count in chunk_result.regulation_counts.items():
                    all_regulation_counts[reg] = all_regulation_counts.get(reg, 0) + count

        except Exception as e:
            logger.warning(f"Error processing chunk {chunk_idx} for regulatory obligations: {e}")
            continue

    if not all_obligations:
        logger.warning("No regulatory obligations found in any chunk")
        return RegulatoryExtractionResult(industry=industry.value)

    # Deduplicate obligations
    unique_obligations = _deduplicate_regulatory_obligations(all_obligations)

    avg_confidence = (
        sum(o.confidence for o in unique_obligations) / len(unique_obligations)
        if unique_obligations
        else 0.0
    )

    return RegulatoryExtractionResult(
        industry=industry.value,
        obligations=unique_obligations,
        regulation_counts=all_regulation_counts,
        overall_confidence=avg_confidence,
    )


def _deduplicate_regulatory_obligations(obligations: list) -> list:
    """Deduplicate regulatory obligations by description similarity."""
    if not obligations:
        return []

    unique = []
    seen_descriptions = set()

    for obl in obligations:
        norm_desc = obl.description.lower().strip()[:100]
        if norm_desc not in seen_descriptions:
            seen_descriptions.add(norm_desc)
            unique.append(obl)

    return unique


def _parse_regulatory_response(data: dict[str, Any], industry: Industry) -> RegulatoryExtractionResult:
    """Parse the JSON response into RegulatoryExtractionResult."""
    obligations = []

    category_map = {
        "audit_rights": ObligationCategory.AUDIT_RIGHTS,
        "change_control": ObligationCategory.CHANGE_CONTROL,
        "deviation_reporting": ObligationCategory.DEVIATION_REPORTING,
        "recall_response": ObligationCategory.RECALL_RESPONSE,
        "adverse_event_reporting": ObligationCategory.ADVERSE_EVENT_REPORTING,
        "record_retention": ObligationCategory.RECORD_RETENTION,
        "training_requirements": ObligationCategory.TRAINING_REQUIREMENTS,
        "quality_review": ObligationCategory.QUALITY_REVIEW,
        "regulatory_reporting": ObligationCategory.REGULATORY_REPORTING,
        "data_protection": ObligationCategory.DATA_PROTECTION,
        "other": ObligationCategory.OTHER,
    }

    regulation_map = {
        "fda": RegulationType.FDA,
        "hipaa": RegulationType.HIPAA,
        "gmp": RegulationType.GMP,
        "gdpr": RegulationType.GDPR,
        "iso_9001": RegulationType.ISO_9001,
        "iso_13485": RegulationType.ISO_13485,
        "osha": RegulationType.OSHA,
        "epa": RegulationType.EPA,
        "soc2": RegulationType.SOC2,
        "other": RegulationType.OTHER,
    }

    for obl_data in data.get("obligations", []):
        try:
            category_str = obl_data.get("obligation_category", "other").lower().replace(" ", "_")
            regulation_str = obl_data.get("regulation_type", "other").lower().replace(" ", "_")

            obligations.append(
                ExtractedRegulatoryObligation(
                    title=obl_data.get("title", "")[:100],
                    description=obl_data.get("description", "")[:2000],
                    obligation_category=category_str,
                    regulation_type=regulation_str,
                    regulation_reference=obl_data.get("regulation_reference"),
                    source_text=obl_data.get("source_text"),
                    source_section=obl_data.get("source_section"),
                    responsible_party=obl_data.get("responsible_party"),
                    frequency=obl_data.get("frequency"),
                    deadline_days=obl_data.get("deadline_days"),
                    confidence=float(obl_data.get("confidence", 0.5)),
                )
            )
        except Exception as e:
            logger.warning(f"Error parsing regulatory obligation: {e}")

    regulation_summary = data.get("regulation_summary", {})

    avg_confidence = (
        sum(o.confidence for o in obligations) / len(obligations)
        if obligations
        else 0.0
    )

    return RegulatoryExtractionResult(
        industry=industry.value,
        obligations=obligations,
        regulation_summary=regulation_summary,
        overall_confidence=avg_confidence,
    )


async def store_regulatory_obligations(
    db: AsyncSession,
    contract_id: uuid.UUID,
    industry: Industry,
    result: RegulatoryExtractionResult,
) -> list[RegulatoryObligation]:
    """Store extracted regulatory obligations in the database.

    Args:
        db: Database session.
        contract_id: Contract ID to link obligations to.
        industry: Industry of the contract.
        result: Extraction result with obligations.

    Returns:
        List of created RegulatoryObligation records.
    """
    created = []

    category_map = {
        "audit_rights": ObligationCategory.AUDIT_RIGHTS,
        "change_control": ObligationCategory.CHANGE_CONTROL,
        "deviation_reporting": ObligationCategory.DEVIATION_REPORTING,
        "recall_response": ObligationCategory.RECALL_RESPONSE,
        "adverse_event_reporting": ObligationCategory.ADVERSE_EVENT_REPORTING,
        "record_retention": ObligationCategory.RECORD_RETENTION,
        "training_requirements": ObligationCategory.TRAINING_REQUIREMENTS,
        "quality_review": ObligationCategory.QUALITY_REVIEW,
        "regulatory_reporting": ObligationCategory.REGULATORY_REPORTING,
        "data_protection": ObligationCategory.DATA_PROTECTION,
        "other": ObligationCategory.OTHER,
    }

    regulation_map = {
        "fda": RegulationType.FDA,
        "hipaa": RegulationType.HIPAA,
        "gmp": RegulationType.GMP,
        "gdpr": RegulationType.GDPR,
        "iso_9001": RegulationType.ISO_9001,
        "iso_13485": RegulationType.ISO_13485,
        "osha": RegulationType.OSHA,
        "epa": RegulationType.EPA,
        "soc2": RegulationType.SOC2,
        "other": RegulationType.OTHER,
    }

    for extracted in result.obligations:
        category = category_map.get(extracted.obligation_category, ObligationCategory.OTHER)
        regulation = regulation_map.get(extracted.regulation_type, RegulationType.OTHER)

        obligation = RegulatoryObligation(
            contract_id=contract_id,
            industry=industry,
            regulation_type=regulation,
            regulation_reference=extracted.regulation_reference,
            obligation_category=category,
            title=extracted.title,
            description=extracted.description,
            source_text=extracted.source_text,
            source_section=extracted.source_section,
            responsible_party=extracted.responsible_party,
            frequency=extracted.frequency,
            compliance_status=RAGStatus.NOT_ASSESSED,
            extraction_confidence=extracted.confidence,
        )

        db.add(obligation)
        created.append(obligation)
        logger.debug(f"Added regulatory obligation: {extracted.title[:50]}...")

    await db.flush()
    logger.info(f"Stored {len(created)} regulatory obligations for contract {contract_id}")

    return created


def register_regulatory_extraction_agent() -> None:
    """Register the regulatory extraction agent with the orchestrator."""
    config = get_regulatory_extraction_config()
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
