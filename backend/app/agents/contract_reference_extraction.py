"""Contract Reference Extraction Agent.

Extracts parent/related contract references from document text using AI.
Instead of relying on regex patterns, uses the LLM to understand
natural language references like:
- "This Schedule is attached to the Master Services Agreement between X and Y"
- "Amendment No. 2 to the Vendor Agreement dated January 2025"
- "pursuant to the MSA executed on..."

Stores structured reference data on the contract for use by the auto-link detector.
"""

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import AgentConfig, extract_json_from_response
from app.services.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)


class ExtractedReference(BaseModel):
    """A single parent/related contract reference found in the text."""

    referenced_type: str | None = None  # "MSA", "NDA", "SOW", etc.
    relationship: str = "related"       # "parent", "amends", "renews", "references"
    party_names: list[str] = []         # Party names mentioned in reference context
    referenced_date: str | None = None  # Date mentioned (ISO format if possible)
    reference_identifier: str | None = None  # "Amendment No. 2", "Schedule A", etc.
    reference_text: str | None = None   # Verbatim text snippet containing the reference
    confidence: float = 0.0


class ContractReferenceResult(BaseModel):
    """Result of contract reference extraction."""

    is_child_document: bool = False     # True if this doc is a schedule/amendment/exhibit/SOW
    document_role: str | None = None    # "schedule", "amendment", "exhibit", "sow", "standalone"
    parent_references: list[ExtractedReference] = []
    child_references: list[str] = []    # Identifiers of child docs mentioned (e.g., "Schedule A", "Exhibit B")
    overall_confidence: float = 0.0


CONTRACT_REFERENCE_PROMPT = """You are a contract document relationship analyst. Your task is to determine whether this document references or is subordinate to another agreement, and extract structured information about those references.

Analyze the document text and determine:

1. **Is this a child document?** (schedule, exhibit, amendment, addendum, SOW, appendix, annex)
   - Look for language like "This Schedule is part of...", "Amendment to...", "Exhibit A to the...", "Statement of Work under..."
   - Look at the document title/heading for indicators

2. **Parent agreement references**: If this IS a child document, extract details about the parent agreement it references:
   - Type of parent agreement (MSA, NDA, SOW, Vendor Agreement, Employment Contract, etc.)
   - Party names mentioned in the reference context
   - Date of the parent agreement (if mentioned)
   - How it's identified (e.g., "Amendment No. 2", "Schedule A-1")
   - The exact text snippet containing the reference

3. **Child document references**: If this document mentions attached schedules, exhibits, or amendments:
   - List identifiers like "Schedule A", "Exhibit 1", "Appendix B", etc.
   - These help match when child documents are uploaded later

Respond ONLY with valid JSON in this exact format:
```json
{
  "is_child_document": true,
  "document_role": "schedule",
  "parent_references": [
    {
      "referenced_type": "MSA",
      "relationship": "parent",
      "party_names": ["ClientAA Corp", "SupplierBB Inc"],
      "referenced_date": "2022-11-01",
      "reference_identifier": "Schedule 02",
      "reference_text": "This Schedule is an integral part of the Business Process Outsourcing Agreement between DemoSup1 and ClientAA effective November 1, 2022",
      "confidence": 0.95
    }
  ],
  "child_references": [],
  "overall_confidence": 0.92
}
```

For a standalone contract that mentions attached schedules:
```json
{
  "is_child_document": false,
  "document_role": "standalone",
  "parent_references": [],
  "child_references": ["Schedule 1", "Schedule 2", "Schedule 3", "Exhibit A"],
  "overall_confidence": 0.90
}
```

Rules:
- Only include references with confidence >= 0.5
- "referenced_type" should be one of: MSA, NDA, SOW, AMENDMENT, VENDOR_AGREEMENT, EMPLOYMENT_CONTRACT, or the exact type mentioned
- "relationship" should be: "parent" (this doc belongs under it), "amends" (this is an amendment to it), "renews" (this renews it), or "references" (general reference)
- If no references are found, return is_child_document=false and empty arrays
- Extract actual party names, not generic terms like "Client" or "Vendor"
- For dates, use ISO format (YYYY-MM-DD) when possible, otherwise use the text as-is
"""


def get_contract_reference_config() -> AgentConfig:
    """Get configuration for the contract reference extraction agent."""
    return AgentConfig(
        name="contract_reference_extraction",
        description="""Analyze contract text to identify parent/related contract references.
        Determines if a document is a schedule, amendment, exhibit, or SOW
        and extracts details about the parent agreement it references.""",
        system_prompt=CONTRACT_REFERENCE_PROMPT,
        temperature=0.0,
        max_tokens=2000,
    )


def register_contract_reference_agent() -> None:
    """Register the contract reference extraction agent with the orchestrator."""
    config = get_contract_reference_config()
    orchestrator = get_orchestrator()
    orchestrator.register_agent(
        name=config.name,
        description=config.description,
        system_prompt=config.system_prompt,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )


async def extract_contract_references(
    contract_text: str,
    filename: str | None = None,
    contract_id: str | None = None,
    user_id: str | None = None,
) -> ContractReferenceResult:
    """Extract parent/related contract references from contract text.

    Args:
        contract_text: The contract text to analyze.
        filename: Original filename (provides additional hints).
        contract_id: Optional contract ID for context.
        user_id: User ID for tracing.

    Returns:
        ContractReferenceResult with extracted references.
    """
    orchestrator = get_orchestrator()

    # Use first 8000 chars — references are almost always in the preamble/intro
    text_sample = contract_text[:8000]

    filename_hint = ""
    if filename:
        filename_hint = f"\nDocument filename: {filename}\n"

    query = f"""Analyze the following contract text and extract any references to parent or related agreements:
{filename_hint}
---
{text_sample}
---

Respond with the structured JSON as specified."""

    try:
        from app.services.orchestrator import AgentRequest

        response = await orchestrator.route_request(
            AgentRequest(
                query=query,
                user_id=user_id or "system",
                session_id=f"ref_extract_{contract_id or 'unknown'}",
                contract_id=contract_id,
                context={"task": "contract_reference_extraction"},
            )
        )

        json_data = extract_json_from_response(response.response)
        if json_data:
            return _parse_reference_response(json_data)
        else:
            logger.warning(
                f"Could not parse reference response: {response.response[:200]}"
            )
            return ContractReferenceResult()

    except Exception as e:
        logger.exception(f"Error extracting contract references: {e}")
        return ContractReferenceResult()


def _expand_child_reference_ranges(children: list[str]) -> list[str]:
    """Expand range references into individual items.

    Handles patterns like:
    - "Exhibits 2.1 to 2.7" → ["Exhibit 2.1", "Exhibit 2.2", ..., "Exhibit 2.7"]
    - "Attachments 3-A to 3-F" → ["Attachment 3-A", "Attachment 3-B", ..., "Attachment 3-F"]
    - "Schedules 1 to 5" → ["Schedule 1", "Schedule 2", ..., "Schedule 5"]

    Non-range items pass through unchanged.
    """
    import re
    expanded = []

    # Pattern: "Exhibits 2.1 to 2.7" or "Exhibit 2.1 through 2.7"
    range_pattern = re.compile(
        r"^(exhibit|attachment|schedule|appendix|annex)s?\s+"  # prefix (singular or plural)
        r"(\d+(?:\.\d+)?)\s+"            # start number (e.g., "2.1" or "3")
        r"(?:to|through|thru|-)\s+"       # range separator
        r"(\d+(?:\.\d+)?)$",             # end number
        re.IGNORECASE,
    )

    # Pattern for letter ranges: "Attachment 3-A to 3-F"
    letter_range_pattern = re.compile(
        r"^(exhibit|attachment|schedule|appendix|annex)s?\s+"
        r"(\d+)-([A-Za-z])\s+"
        r"(?:to|through|thru|-)\s+"
        r"\d+-([A-Za-z])$",
        re.IGNORECASE,
    )

    for child in children:
        child_stripped = child.strip()

        # Try numeric range (e.g., "Exhibits 2.1 to 2.7")
        m = range_pattern.match(child_stripped)
        if m:
            prefix = m.group(1).capitalize()  # "Exhibit"
            start_str, end_str = m.group(2), m.group(3)

            if "." in start_str and "." in end_str:
                # Decimal range: 2.1, 2.2, ..., 2.7
                major = start_str.split(".")[0]
                start_minor = int(start_str.split(".")[1])
                end_minor = int(end_str.split(".")[1])
                for i in range(start_minor, end_minor + 1):
                    expanded.append(f"{prefix} {major}.{i}")
            else:
                # Integer range: 1, 2, ..., 5
                start_num = int(start_str)
                end_num = int(end_str)
                for i in range(start_num, end_num + 1):
                    expanded.append(f"{prefix} {i}")
            continue

        # Try letter range (e.g., "Attachment 3-A to 3-F")
        m = letter_range_pattern.match(child_stripped)
        if m:
            prefix = m.group(1).capitalize()
            num = m.group(2)
            start_letter = m.group(3).upper()
            end_letter = m.group(4).upper()
            for code in range(ord(start_letter), ord(end_letter) + 1):
                expanded.append(f"{prefix} {num}-{chr(code)}")
            continue

        # Not a range — pass through as-is
        expanded.append(child_stripped)

    return expanded


def _parse_reference_response(data: dict) -> ContractReferenceResult:
    """Parse the LLM JSON response into a ContractReferenceResult."""
    try:
        parent_refs = []
        for ref_data in data.get("parent_references", []):
            ref = ExtractedReference(
                referenced_type=ref_data.get("referenced_type"),
                relationship=ref_data.get("relationship", "related"),
                party_names=ref_data.get("party_names", []),
                referenced_date=ref_data.get("referenced_date"),
                reference_identifier=ref_data.get("reference_identifier"),
                reference_text=ref_data.get("reference_text"),
                confidence=float(ref_data.get("confidence", 0.0)),
            )
            if ref.confidence >= 0.5:
                parent_refs.append(ref)

        # Expand range references in child_references
        # e.g., "Exhibits 2.1 to 2.7" or "Attachments 3-A to 3-F" → individual items
        raw_children = data.get("child_references", [])
        expanded_children = _expand_child_reference_ranges(raw_children)

        return ContractReferenceResult(
            is_child_document=bool(data.get("is_child_document", False)),
            document_role=data.get("document_role"),
            parent_references=parent_refs,
            child_references=expanded_children,
            overall_confidence=float(data.get("overall_confidence", 0.0)),
        )
    except Exception as e:
        logger.warning(f"Error parsing reference data: {e}")
        return ContractReferenceResult()


async def store_contract_references(
    db: "AsyncSession",
    contract: "Contract",
    result: ContractReferenceResult,
) -> None:
    """Store extracted references in the contract's schema_data.

    Stores under the key '_contract_references' in the JSONB schema_data field.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    if not result.parent_references and not result.child_references:
        return

    ref_data = {
        "is_child_document": result.is_child_document,
        "document_role": result.document_role,
        "parent_references": [
            {
                "referenced_type": r.referenced_type,
                "relationship": r.relationship,
                "party_names": r.party_names,
                "referenced_date": r.referenced_date,
                "reference_identifier": r.reference_identifier,
                "reference_text": r.reference_text,
                "confidence": r.confidence,
            }
            for r in result.parent_references
        ],
        "child_references": result.child_references,
        "overall_confidence": result.overall_confidence,
    }

    # Merge into existing schema_data
    existing = contract.schema_data or {}
    existing["_contract_references"] = ref_data
    contract.schema_data = existing
    await db.flush()

    logger.info(
        f"Stored {len(result.parent_references)} parent refs, "
        f"{len(result.child_references)} child refs for contract {contract.id}"
    )
