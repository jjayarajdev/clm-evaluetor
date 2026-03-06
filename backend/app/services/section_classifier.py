"""Semantic section classifier using LLM.

Replaces brittle regex patterns with LLM-based classification for:
- Section type detection (preamble, definitions, payment, etc.)
- Semantic tagging (liability, confidentiality, renewal, etc.)
- Context-aware extraction
"""

import asyncio
import logging
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.config import settings
from app.services.vector_store import SectionType

logger = logging.getLogger(__name__)

# Initialize OpenAI client
_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    """Get or create OpenAI client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


class SectionClassification(BaseModel):
    """Result of section classification."""

    section_type: str
    semantic_tags: list[str]
    confidence: float
    section_title: str | None = None


# Classification prompt - focused and efficient
CLASSIFICATION_PROMPT = """Classify this contract section. Return JSON only.

SECTION TEXT:
{text}

Classify into ONE primary type:
- preamble: Opening, recitals, WHEREAS clauses, introduction
- definitions: Defined terms, "means", glossary
- parties: Party names, addresses, identification
- scope: Scope of work, services description, deliverables
- terms: Term, duration, effective date, contract period
- payment: Payment terms, pricing, fees, invoicing
- confidentiality: NDA provisions, confidential information
- liability: Liability caps, indemnification, damages
- termination: Termination rights, renewal, notice periods
- ip: Intellectual property, licensing, ownership
- compliance: Regulatory, GDPR, audit rights
- governance: Reporting, oversight, governance structure
- sla: Service levels, KPIs, performance metrics
- exhibits: Exhibits, schedules, appendices, attachments
- signatures: Signature blocks, execution
- general: Miscellaneous, general provisions, boilerplate

Also identify semantic tags (0-3 tags):
auto_renewal, force_majeure, warranty, dispute_resolution, assignment,
non_compete, data_protection, insurance, audit, change_control

Respond with JSON:
{{"type": "payment", "tags": ["pricing"], "confidence": 0.9, "title": "Payment Terms"}}"""


async def classify_section(text: str, max_chars: int = 2000) -> SectionClassification:
    """Classify a single section using LLM.

    Args:
        text: Section text to classify.
        max_chars: Maximum characters to send to LLM.

    Returns:
        SectionClassification with type, tags, and confidence.
    """
    client = get_openai_client()

    # Truncate for efficiency
    sample = text[:max_chars] if len(text) > max_chars else text

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cheap (~$0.00015 per call)
            messages=[
                {"role": "system", "content": "You are a contract section classifier. Return valid JSON only."},
                {"role": "user", "content": CLASSIFICATION_PROMPT.format(text=sample)},
            ],
            temperature=0,
            max_tokens=100,
        )

        result_text = response.choices[0].message.content or "{}"

        # Parse JSON response
        import json
        import re

        # Handle markdown code blocks if present
        if "```" in result_text:
            # Extract content between ``` markers
            code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', result_text, re.DOTALL)
            if code_block_match:
                result_text = code_block_match.group(1)
            else:
                # Fallback: split and extract
                parts = result_text.split("```")
                if len(parts) >= 2:
                    result_text = parts[1]
                    if result_text.strip().startswith("json"):
                        result_text = result_text.strip()[4:]

        # Try to find JSON object in the text
        result_text = result_text.strip()
        if not result_text.startswith("{"):
            # Look for JSON object in the response
            json_match = re.search(r'\{[^{}]*\}', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(0)
            else:
                # No valid JSON found, return default
                logger.warning(f"No valid JSON found in response: {result_text[:200]}")
                return SectionClassification(
                    section_type="general",
                    semantic_tags=[],
                    confidence=0.5,
                )

        data = json.loads(result_text)

        section_type = data.get("type", "general").lower()
        # Validate section type
        valid_types = {
            "preamble", "definitions", "parties", "scope", "terms",
            "payment", "confidentiality", "liability", "termination",
            "ip", "compliance", "governance", "sla", "exhibits",
            "signatures", "general"
        }
        if section_type not in valid_types:
            section_type = "general"

        return SectionClassification(
            section_type=section_type,
            semantic_tags=data.get("tags", [])[:3],
            confidence=float(data.get("confidence", 0.7)),
            section_title=data.get("title"),
        )

    except Exception as e:
        logger.warning(f"Section classification failed: {e}")
        return SectionClassification(
            section_type="general",
            semantic_tags=[],
            confidence=0.5,
        )


async def classify_sections_batch(
    texts: list[str],
    batch_size: int = 10,
    max_chars: int = 1500,
) -> list[SectionClassification]:
    """Classify multiple sections in parallel batches.

    Args:
        texts: List of section texts.
        batch_size: Number of concurrent requests.
        max_chars: Maximum characters per section.

    Returns:
        List of SectionClassification results.
    """
    results: list[SectionClassification] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_results = await asyncio.gather(
            *[classify_section(text, max_chars) for text in batch],
            return_exceptions=True,
        )

        for result in batch_results:
            if isinstance(result, Exception):
                logger.warning(f"Batch classification error: {result}")
                results.append(SectionClassification(
                    section_type="general",
                    semantic_tags=[],
                    confidence=0.5,
                ))
            else:
                results.append(result)

    return results


def get_sections_by_type(
    section_types: list[str],
) -> dict[str, Any]:
    """Build ChromaDB filter for section types.

    Args:
        section_types: List of section types to match.

    Returns:
        ChromaDB where filter.
    """
    if len(section_types) == 1:
        return {"section_type": section_types[0]}
    return {"section_type": {"$in": section_types}}


def get_sections_by_tags(
    tags: list[str],
) -> dict[str, Any]:
    """Build ChromaDB filter for semantic tags.

    Note: Tags are stored as comma-separated string.

    Args:
        tags: List of tags to match (any).

    Returns:
        ChromaDB where filter for $contains.
    """
    # For single tag
    if len(tags) == 1:
        return {"semantic_tags": {"$contains": tags[0]}}
    # For multiple tags, need $or
    return {"$or": [{"semantic_tags": {"$contains": tag}} for tag in tags]}


# Quick classification without LLM for obvious cases
def quick_classify(text: str) -> SectionClassification | None:
    """Fast heuristic classification for obvious sections.

    Falls back to None if not obvious, triggering LLM classification.

    Args:
        text: Section text.

    Returns:
        SectionClassification if obvious, None otherwise.
    """
    text_lower = text[:500].lower()

    # Obvious patterns that don't need LLM
    if text_lower.startswith("whereas") or "now, therefore" in text_lower:
        return SectionClassification(
            section_type="preamble",
            semantic_tags=["recitals"],
            confidence=0.95,
        )

    if '"' in text_lower and (" means " in text_lower or " shall mean " in text_lower):
        return SectionClassification(
            section_type="definitions",
            semantic_tags=[],
            confidence=0.95,
        )

    if "in witness whereof" in text_lower or "executed as of" in text_lower:
        return SectionClassification(
            section_type="signatures",
            semantic_tags=[],
            confidence=0.95,
        )

    if text_lower.startswith("exhibit ") or text_lower.startswith("schedule "):
        return SectionClassification(
            section_type="exhibits",
            semantic_tags=[],
            confidence=0.95,
        )

    # Not obvious - needs LLM
    return None


async def smart_classify_section(text: str) -> SectionClassification:
    """Classify section using quick heuristics first, then LLM if needed.

    Args:
        text: Section text to classify.

    Returns:
        SectionClassification result.
    """
    # Try quick classification first
    quick_result = quick_classify(text)
    if quick_result:
        return quick_result

    # Fall back to LLM
    return await classify_section(text)


async def smart_classify_batch(
    texts: list[str],
    batch_size: int = 10,
) -> list[SectionClassification]:
    """Classify sections using quick heuristics where possible, LLM for rest.

    Args:
        texts: List of section texts.
        batch_size: Batch size for LLM calls.

    Returns:
        List of SectionClassification results.
    """
    results: list[SectionClassification | None] = []
    llm_needed: list[tuple[int, str]] = []

    # First pass: quick classification
    for i, text in enumerate(texts):
        quick_result = quick_classify(text)
        results.append(quick_result)
        if quick_result is None:
            llm_needed.append((i, text))

    # Second pass: LLM for remaining
    if llm_needed:
        indices, texts_for_llm = zip(*llm_needed)
        llm_results = await classify_sections_batch(list(texts_for_llm), batch_size)

        for idx, result in zip(indices, llm_results):
            results[idx] = result

    # All results should be filled now
    return [r for r in results if r is not None]
