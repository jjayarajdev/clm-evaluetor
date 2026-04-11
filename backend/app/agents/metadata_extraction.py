"""Metadata Extraction Agent (SK-001).

Extracts structured contract metadata including:
- Contract type (NDA, MSA, SOW, etc.)
- Counterparty name
- Effective and expiration dates
- Contract value and currency
- Jurisdiction
"""

import json
import logging
import re
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import (
    AgentConfig,
    ContractSearchTool,
    extract_json_from_response,
    inject_context,
)
from app.config import settings
from app.models.contract import Contract, ContractType
from app.services.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)


# Supported contract types
CONTRACT_TYPES = [
    ("NDA", "Non-Disclosure Agreement"),
    ("MSA", "Master Service Agreement"),
    ("SOW", "Statement of Work"),
    ("AMENDMENT", "Contract Amendment"),
    ("VENDOR", "Vendor Agreement"),
    ("EMPLOYMENT", "Employment Contract"),
]


class MetadataField(BaseModel):
    """A single extracted metadata field with confidence."""

    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    raw_text: str | None = None


class ExtractedMetadata(BaseModel):
    """Structured metadata extracted from a contract."""

    contract_type: MetadataField | None = None
    counterparty: MetadataField | None = None
    effective_date: MetadataField | None = None
    expiration_date: MetadataField | None = None
    contract_value: MetadataField | None = None
    currency: MetadataField | None = None
    jurisdiction: MetadataField | None = None
    parties: list[str] = []
    overall_confidence: float = 0.0


METADATA_EXTRACTION_PROMPT = """You are a contract metadata extraction specialist. Your task is to extract structured information from contract text with high accuracy.

CRITICAL FIRST STEP — TEMPLATE DETECTION:
Before extracting ANY fields, determine if this document is a TEMPLATE or an EXECUTED/SIGNED contract.

TEMPLATE INDICATORS (if ANY of these are present, this is a template):
- Bracketed placeholders: "[Company Name]", "[VENDOR]", "[CLIENT]", "[FULL LEGAL NAME]", "[Party A]"
- Underline blanks: "___________" or "____" for names/dates
- Generic role references used AS party names: "Contractor", "Service Provider", "Supplier", "Client" (without an actual company name)
- Instruction text: "Insert company name here", "to be completed", "fill in"
- No specific signatures, dates, or company names anywhere in the document
- Document title contains "Template" or "Form"

IF THIS IS A TEMPLATE: Set counterparty to null with confidence 0.0. Set parties to an empty list. Still extract contract_type, jurisdiction, and any other fields that are defined in the template.

Extract the following fields from the provided contract text:

1. **contract_type**: Classify the contract as one of:
   - NDA (Non-Disclosure Agreement)
   - MSA (Master Service Agreement)
   - SOW (Statement of Work)
   - AMENDMENT (Contract Amendment)
   - VENDOR (Vendor Agreement)
   - EMPLOYMENT (Employment Contract)
   - OTHER (if none of the above)

2. **counterparty**: Extract the VENDOR/SUPPLIER/SERVICE PROVIDER party — the party providing services.
   STEP-BY-STEP PROCESS:
   a) First, find ALL parties in "between X and Y" or "THE UNDERSIGNED" clauses
   b) Identify each party's ROLE — look for labels like "Client", "Customer", "Buyer" vs "Supplier", "Vendor", "Service Provider", "Contractor"
   c) The COUNTERPARTY is the party labeled as Vendor/Supplier/Service Provider/Contractor
   d) The party labeled Client/Customer/Buyer is the DOCUMENT OWNER — do NOT extract this as the counterparty
   e) The party whose name appears in the FILENAME is the document owner — do NOT extract it as counterparty
      (e.g., "MSA ClientAA.docx" → ClientAA is the owner, the Supplier is the counterparty)

   VALIDATION RULES:
   - A valid counterparty is a REAL COMPANY NAME like "Acme Corporation", "TechServices Inc.", "Infosys Ltd."
   - Look for legal entity suffixes: Inc., LLC, Ltd., Corp., Corporation, BV, GmbH, LP, LLP, PLC
   - Extract the SHORT legal name only, not the full address block
   - DO NOT include addresses, city, state, zip codes
   INVALID counterparty values (MUST return null instead):
   - Template placeholders: "[Company Name]", "Party A", "Party B", "[VENDOR]"
   - Generic terms: "Contractor", "Service Provider", "Supplier", "Client", "Customer", "Vendor"
   - Sentence fragments: "the terms of any SOW", "attached hereto as Exhibit A", "the ones in the RFP"
   - Document references: "this Agreement", "the Contract", "SDLC", "PMI Agreement"
   - Anything that is NOT a proper company/organization name
   If you are not confident this is a real company name, set value to null and confidence to 0.0.

3. **effective_date**: When the contract takes effect (ISO format: YYYY-MM-DD)
   Look for phrases like: "effective as of", "dated", "entered into on", "commences on"

4. **expiration_date**: When the contract expires or terminates (ISO format: YYYY-MM-DD)
   Look for phrases like: "expires on", "terminates on", "valid until", "end date", "expiration date"
   Also calculate from term clauses like: "initial term of X years" (add X years to effective date)
   Look in "Term", "Duration", "Term and Termination" sections

5. **contract_value**: The monetary value of the contract (numeric only)

6. **currency**: The currency of the contract value (USD, EUR, GBP, etc.)

7. **jurisdiction**: The governing law jurisdiction (e.g., "State of Delaware", "England and Wales", "Netherlands")

8. **parties**: List ALL actual party names mentioned in the contract (not generic terms).
   ONLY include real company/organization names. Do NOT include generic labels like "Client" or "Vendor".

For each field, provide:
- The extracted value (MUST be actual names, not placeholders)
- A confidence score (0.0 to 1.0) based on how clearly the information was stated
- The relevant text snippet where you found this information

Respond ONLY with valid JSON in this exact format:
```json
{
  "contract_type": {"value": "NDA", "confidence": 0.95, "raw_text": "Non-Disclosure Agreement"},
  "counterparty": {"value": "Acme Corporation", "confidence": 0.9, "raw_text": "between XYZ Inc. and Acme Corporation"},
  "effective_date": {"value": "2024-01-01", "confidence": 0.85, "raw_text": "effective as of January 1, 2024"},
  "expiration_date": {"value": "2025-01-01", "confidence": 0.8, "raw_text": "expires on the first anniversary"},
  "contract_value": {"value": 50000, "confidence": 0.9, "raw_text": "total amount of $50,000"},
  "currency": {"value": "USD", "confidence": 0.95, "raw_text": "$50,000"},
  "jurisdiction": {"value": "State of Delaware", "confidence": 0.9, "raw_text": "governed by the laws of the State of Delaware"},
  "parties": ["XYZ Inc.", "Acme Corporation"]
}
```

If a field cannot be found or only has generic placeholder text, set its value to null and confidence to 0.0.
"""


def _prepare_metadata_text(contract_text: str, max_length: int = 25000) -> str:
    """Prepare contract text for metadata extraction.

    For full text processing, returns the text directly.
    For fallback/legacy mode, includes beginning + ending.

    Note: Semantic section queries should be used when possible via
    vector_store.query_by_section_type() with contract_id.

    Args:
        contract_text: Full contract text.
        max_length: Maximum text length to return.

    Returns:
        Text sample optimized for metadata extraction.
    """
    if len(contract_text) <= max_length:
        return contract_text

    # For metadata extraction, the most important parts are:
    # 1. Beginning (parties, effective date, preamble) - first 12000 chars
    # 2. End (signature blocks with dates) - last 4000 chars
    # 3. Middle sections are processed by chunked extraction

    beginning = contract_text[:12000]
    ending = contract_text[-4000:]

    # Simple approach: beginning + ending with clear separator
    return f"{beginning}\n\n[...MIDDLE SECTIONS OMITTED - PROCESSED VIA CHUNKED EXTRACTION...]\n\n{ending}"


async def prepare_metadata_text_semantic(
    contract_id: str,
    contract_text: str,
    max_length: int = 30000,
) -> str:
    """Prepare contract text using semantic section queries.

    Uses ChromaDB semantic section types instead of regex patterns.

    Args:
        contract_id: Contract ID for semantic queries.
        contract_text: Full contract text (fallback).
        max_length: Maximum text length.

    Returns:
        Text sample from semantically relevant sections.
    """
    from app.services.vector_store import get_vector_store

    if len(contract_text) <= max_length:
        return contract_text

    vs = get_vector_store()

    # Query for metadata-relevant sections semantically
    relevant_types = ["preamble", "parties", "terms", "payment", "signatures"]
    sections = vs.query_by_section_type(contract_id, relevant_types, top_k=15)

    if not sections:
        # Fallback to simple text preparation
        return _prepare_metadata_text(contract_text, max_length)

    # Combine relevant sections
    result_parts = []
    total_length = 0

    for section in sections:
        if total_length + len(section.text) < max_length:
            section_type = section.metadata.get("section_type", "unknown")
            result_parts.append(f"[{section_type.upper()}]\n{section.text}")
            total_length += len(section.text) + 50

    return "\n\n---\n\n".join(result_parts)


def get_metadata_extraction_config() -> AgentConfig:
    """Get configuration for the metadata extraction agent."""
    return AgentConfig(
        name="metadata_extraction",
        description="""Extract structured metadata from contract text including:
        contract type, counterparty, dates, values, and jurisdiction.
        Use this agent when you need to extract specific fields from a contract.""",
        system_prompt=METADATA_EXTRACTION_PROMPT,
        temperature=0.0,  # Low temperature for consistent extraction
        max_tokens=2500,  # Increased for comprehensive metadata with raw_text snippets
    )


async def extract_metadata(
    contract_text: str,
    contract_id: str | None = None,
    user_id: str | None = None,
    user_role: str | None = None,
    excluded_parties: list[str] | None = None,
) -> ExtractedMetadata:
    """Extract metadata from contract text using the AI agent.

    Args:
        contract_text: The contract text to extract metadata from.
        contract_id: Optional contract ID for context.
        user_id: User ID for RBAC.
        user_role: User role for RBAC.

    Returns:
        ExtractedMetadata with all extracted fields.
    """
    orchestrator = get_orchestrator()

    # Prepare the extraction request
    # Use semantic section selection when contract_id is available (better for large docs)
    if contract_id:
        text_sample = await prepare_metadata_text_semantic(
            contract_id, contract_text, max_length=30000
        )
    else:
        text_sample = _prepare_metadata_text(contract_text)

    # Extract filename hint if contract_id available
    filename_hint = ""
    if contract_id:
        try:
            from app.agents.metadata_extraction import extract_counterparty_from_filename
            # Try to get filename from DB context
            from app.database import async_session_maker
            from app.models.contract import Contract as ContractModel
            async with async_session_maker() as session:
                c = await session.get(ContractModel, uuid.UUID(contract_id))
                if c and c.filename:
                    filename_hint = f"\nDocument filename: {c.filename}\n(Use the filename as a hint for counterparty and contract type, but always verify against the actual document text.)\n"
        except Exception:
            pass

    # Build exclusion context for uploader's organization
    exclusion_hint = ""
    if excluded_parties:
        party_list = ", ".join(f'"{p}"' for p in excluded_parties)
        exclusion_hint = f"""
CRITICAL — COUNTERPARTY EXCLUSION:
The following names belong to the UPLOADING organization (the document owner/client).
Do NOT extract any of these as the counterparty: {party_list}
The counterparty must be the OTHER party — the external vendor, supplier, or partner.
If the document mentions "between {excluded_parties[0]} and [OtherCompany]", the counterparty is [OtherCompany].
"""

    query = f"""Extract metadata from the following contract text:
{filename_hint}{exclusion_hint}
---
{text_sample}
---

Respond with the structured JSON as specified."""

    try:
        # Route to metadata extraction agent
        from app.services.orchestrator import AgentRequest

        response = await orchestrator.route_request(
            AgentRequest(
                query=query,
                user_id=user_id or "system",
                session_id=f"metadata_{contract_id or 'unknown'}",
                contract_id=contract_id,
                context={"task": "metadata_extraction"},
            )
        )

        # Parse the JSON response
        json_data = extract_json_from_response(response.response)
        if json_data:
            logger.info(f"AI metadata extraction result: contract_type={json_data.get('contract_type')}, counterparty={json_data.get('counterparty')}, parties={json_data.get('parties')}")
            metadata = _parse_metadata_response(json_data)

            # Validate/clean counterparty with LLM
            if metadata.counterparty and metadata.counterparty.value:
                raw_value = str(metadata.counterparty.value)
                cleaned = await _clean_counterparty_with_llm(raw_value, excluded_parties)
                if cleaned:
                    metadata.counterparty = MetadataField(
                        value=cleaned,
                        confidence=metadata.counterparty.confidence,
                        raw_text=metadata.counterparty.raw_text,
                    )
                else:
                    # LLM said it's invalid (template placeholder, generic term, etc.)
                    logger.info(f"LLM rejected counterparty: {raw_value}")
                    metadata.counterparty = None

            return metadata
        else:
            logger.warning(f"Could not parse metadata response: {response.response[:200]}")
            return ExtractedMetadata()

    except Exception as e:
        logger.exception(f"Error extracting metadata: {e}")
        return ExtractedMetadata()


async def _clean_counterparty_with_llm(value: str, excluded_parties: list[str] | None = None) -> str | None:
    """Use LLM to extract clean company name from messy text.

    Args:
        value: Raw counterparty value (may include address, placeholder text, etc.)

    Returns:
        Clean company name or None if invalid.
    """
    if not value or len(value.strip()) < 3:
        return None

    # Normalize whitespace
    value = re.sub(r'\s+', ' ', value).strip()

    # Check against excluded parties (uploader's org) — exact match only
    if excluded_parties:
        value_lower = value.strip().lower()
        for ep in excluded_parties:
            ep_lower = ep.strip().lower()
            if value_lower == ep_lower:
                logger.info(f"LLM cleaning rejected '{value}' — matches excluded party '{ep}'")
                return None

    # If it looks clean already (short, has legal suffix), return as-is
    if len(value) < 80 and re.search(r'\b(Inc\.?|LLC|Ltd\.?|Limited|Corp\.?|Corporation|GmbH|BV|B\.V\.?|LP|LLP|PLC|AG|SA|NV|N\.V\.?|Pty|Pvt)\b', value, re.IGNORECASE):
        return value

    # Use LLM to extract clean name
    from openai import AsyncOpenAI
    from app.config import settings

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cheap for simple extraction
            messages=[
                {
                    "role": "system",
                    "content": """Extract ONLY the legal company/organization name from the given text.

Rules:
- Return ONLY the company name (e.g., "Acme Corporation", "TechServices Inc.", "CareerSource Heartland")
- A valid company name is a proper noun, often with a legal suffix (Inc., LLC, Ltd., Corp., etc.)
- Remove any addresses, cities, states, zip codes
- Return NULL if the text is any of these:
  * Template placeholder: "[Company Name]", "[VENDOR]", "Party A/B"
  * Generic role: "Contractor", "Service Provider", "Supplier", "Client", "Vendor"
  * Sentence fragment: "the terms of any SOW", "attached hereto as Exhibit A", "the ones in the RFP"
  * Document reference: "this Agreement", "the Contract", "PMI Agreement", "SDLC"
  * Any text that is NOT a proper company/organization name
- If you are uncertain whether it's a real company name, return: NULL
- Return the name only, nothing else."""
                },
                {
                    "role": "user",
                    "content": value
                }
            ],
            temperature=0,
            max_tokens=100,
        )

        result = response.choices[0].message.content.strip()

        # Check for NULL response
        if result.upper() == "NULL" or not result:
            return None

        return result

    except Exception as e:
        logger.warning(f"LLM counterparty cleaning failed: {e}")
        return None


def _is_generic_counterparty(value: str | None) -> bool:
    """Quick check if a counterparty value is obviously generic or garbage."""
    if not value:
        return True

    value_lower = value.lower().strip()

    if len(value_lower) < 3:
        return True

    # Exact match generic terms
    generic_terms = [
        "the parties", "parties", "party a", "party b", "company", "client",
        "customer", "vendor", "provider", "the company", "the client",
        "unknown", "n/a", "none", "null", "tbd", "contractor", "supplier",
        "service provider", "the vendor", "the contractor", "the supplier",
        "the service provider", "the customer", "recipient", "discloser",
    ]

    if value_lower in generic_terms:
        return True

    # Sentence fragment patterns (garbage extractions)
    garbage_indicators = [
        "the terms of", "attached hereto", "the ones in the", "pursuant to",
        "in accordance with", "as set forth", "as defined in", "hereinafter",
        "notwithstanding", "subject to", "exhibit a", "exhibit b", "schedule",
        "this agreement", "the contract", "the agreement", "any sow",
        "[", "]",  # Template brackets
        "___",  # Template blanks
        "insert ", "fill in", "to be completed",
    ]

    for indicator in garbage_indicators:
        if indicator in value_lower:
            return True

    # Too long to be a company name (likely a sentence fragment)
    if len(value_lower) > 80:
        return True

    # No uppercase letter at all (company names always have capitals)
    if value == value_lower and not any(c.isupper() for c in value):
        return True

    return False


def extract_counterparty_from_filename(filename: str) -> str | None:
    """Extract counterparty names from a contract filename.

    Common patterns:
    - "NDA_CompanyA_CompanyB.pdf" -> "CompanyA" or "CompanyB"
    - "MSA CompanyName Template.pdf" -> "CompanyName"
    - "202401 NDA Company A - Company B.docx" -> "Company A" or "Company B"

    Args:
        filename: The contract filename.

    Returns:
        Extracted counterparty name or None.
    """
    if not filename:
        return None

    # Remove extension
    name = re.sub(r'\.(pdf|docx?)$', '', filename, flags=re.IGNORECASE)

    # Remove common prefixes (dates like 202401, 20240115xx, etc.)
    name = re.sub(r'^\d{4,8}[xX]*\s*', '', name)

    # Remove common contract type prefixes (including compound ones like "Vendor_Agreement")
    name = re.sub(r'^(NDA|MSA|SOW|SLA|Amendment|Vendor[_\s]?Agreement|Vendor|Employment[_\s]?Contract|Employment)[_\s-]*', '', name, flags=re.IGNORECASE)

    # Remove common suffixes
    suffixes = ['_Signed', '_Executed', '_Final', '_Draft', '_Template', '_v1', '_v2', '_signed', '_executed']
    for suffix in suffixes:
        name = re.sub(rf'{re.escape(suffix)}$', '', name, flags=re.IGNORECASE)

    # Replace underscores and multiple spaces
    name = name.replace('_', ' ').strip()
    name = re.sub(r'\s+', ' ', name)

    # If there's a dash separator (e.g., "Company A - Company B"), split and take parts
    if ' - ' in name:
        parts = [p.strip() for p in name.split(' - ') if p.strip()]
        # Filter out generic parts
        parts = [p for p in parts if not _is_generic_counterparty(p)]
        if parts:
            # Return the one that looks most like a company name
            for part in parts:
                if any(suffix in part for suffix in ['Inc', 'LLC', 'Ltd', 'Corp', 'BV', 'GmbH', 'AG', 'SA']):
                    return part
            return parts[0]  # Return first non-generic part

    # If name is meaningful (not just contract type), return it
    if name and len(name) > 3 and not _is_generic_counterparty(name):
        return name

    return None


def _parse_metadata_response(data: dict[str, Any]) -> ExtractedMetadata:
    """Parse the JSON response into ExtractedMetadata.

    Args:
        data: Parsed JSON data from agent response.

    Returns:
        ExtractedMetadata object.
    """
    fields = {}
    total_confidence = 0.0
    field_count = 0

    for field_name in [
        "contract_type",
        "counterparty",
        "effective_date",
        "expiration_date",
        "contract_value",
        "currency",
        "jurisdiction",
    ]:
        field_data = data.get(field_name)
        if not field_data:
            continue

        # Handle both dict format {"value": ..., "confidence": ...} and plain value
        if isinstance(field_data, dict) and field_data.get("value") is not None:
            value = field_data["value"]
            confidence = field_data.get("confidence", 0.5)
            raw_text = field_data.get("raw_text")
        elif isinstance(field_data, (str, int, float)) and field_data:
            # AI returned a plain value instead of the nested format
            value = field_data
            confidence = 0.75  # Default confidence for plain values
            raw_text = None
        else:
            continue

        # Basic validation for counterparty - LLM cleaning happens later in extract_metadata
        if field_name == "counterparty" and _is_generic_counterparty(str(value)):
            logger.debug(f"Rejecting obviously generic counterparty: {value}")
            continue

        fields[field_name] = MetadataField(
            value=value,
            confidence=confidence,
            raw_text=raw_text,
        )
        total_confidence += confidence
        field_count += 1

    parties = data.get("parties", [])
    if not isinstance(parties, list):
        parties = []
    # Filter out generic party names
    parties = [p for p in parties if not _is_generic_counterparty(p)]

    return ExtractedMetadata(
        **fields,
        parties=parties,
        overall_confidence=total_confidence / max(field_count, 1),
    )


async def update_contract_metadata(
    db: AsyncSession,
    contract: Contract,
    metadata: ExtractedMetadata,
    confidence_threshold: float = 0.7,
    excluded_parties: list[str] | None = None,
) -> Contract:
    """Update a contract with extracted metadata.

    Args:
        db: Database session.
        contract: Contract to update.
        metadata: Extracted metadata.
        confidence_threshold: Minimum confidence to apply a field.

    Returns:
        Updated contract.
    """
    # Map contract type
    if metadata.contract_type and metadata.contract_type.confidence >= confidence_threshold:
        type_value = str(metadata.contract_type.value).upper().strip()
        type_map = {
            # NDA variants
            "NDA": ContractType.NDA,
            "NON-DISCLOSURE AGREEMENT": ContractType.NDA,
            "NON DISCLOSURE AGREEMENT": ContractType.NDA,
            "NONDISCLOSURE AGREEMENT": ContractType.NDA,
            "MUTUAL NON-DISCLOSURE AGREEMENT": ContractType.NDA,
            "MUTUAL NDA": ContractType.NDA,
            "CONFIDENTIALITY AGREEMENT": ContractType.NDA,
            "MUTUAL CONFIDENTIALITY AGREEMENT": ContractType.NDA,
            "CONFIDENTIAL DISCLOSURE AGREEMENT": ContractType.NDA,
            "CDA": ContractType.NDA,
            # MSA variants
            "MSA": ContractType.MSA,
            "MASTER SERVICES AGREEMENT": ContractType.MSA,
            "MASTER SERVICE AGREEMENT": ContractType.MSA,
            "MASTER AGREEMENT": ContractType.MSA,
            "FRAMEWORK AGREEMENT": ContractType.MSA,
            "SERVICES AGREEMENT": ContractType.MSA,
            "SERVICE AGREEMENT": ContractType.MSA,
            "PROFESSIONAL SERVICES AGREEMENT": ContractType.MSA,
            "CONSULTING AGREEMENT": ContractType.MSA,
            "CONSULTING SERVICES AGREEMENT": ContractType.MSA,
            "BUSINESS PROCESS OUTSOURCING AGREEMENT": ContractType.MSA,
            "BPO AGREEMENT": ContractType.MSA,
            "OUTSOURCING AGREEMENT": ContractType.MSA,
            # SOW variants
            "SOW": ContractType.SOW,
            "STATEMENT OF WORK": ContractType.SOW,
            "SCOPE OF WORK": ContractType.SOW,
            "WORK ORDER": ContractType.SOW,
            "PURCHASE ORDER": ContractType.SOW,
            "TASK ORDER": ContractType.SOW,
            "PROJECT ORDER": ContractType.SOW,
            "SCHEDULE": ContractType.SOW,
            "SERVICE ORDER": ContractType.SOW,
            "ORDER FORM": ContractType.SOW,
            "CSOW": ContractType.SOW,
            "CHANGE SOW": ContractType.SOW,
            "CHANGE STATEMENT OF WORK": ContractType.SOW,
            # Amendment variants
            "AMENDMENT": ContractType.AMENDMENT,
            "ADDENDUM": ContractType.AMENDMENT,
            "CONTRACT AMENDMENT": ContractType.AMENDMENT,
            "FIRST AMENDMENT": ContractType.AMENDMENT,
            "SECOND AMENDMENT": ContractType.AMENDMENT,
            "THIRD AMENDMENT": ContractType.AMENDMENT,
            "MODIFICATION": ContractType.AMENDMENT,
            "CONTRACT MODIFICATION": ContractType.AMENDMENT,
            "SUPPLEMENT": ContractType.AMENDMENT,
            "SUPPLEMENTAL AGREEMENT": ContractType.AMENDMENT,
            "CHANGE ORDER": ContractType.AMENDMENT,
            "SIDE LETTER": ContractType.AMENDMENT,
            "LETTER AMENDMENT": ContractType.AMENDMENT,
            # Vendor agreement variants
            "VENDOR": ContractType.VENDOR_AGREEMENT,
            "VENDOR_AGREEMENT": ContractType.VENDOR_AGREEMENT,
            "VENDOR AGREEMENT": ContractType.VENDOR_AGREEMENT,
            "SUPPLIER AGREEMENT": ContractType.VENDOR_AGREEMENT,
            "SUPPLY AGREEMENT": ContractType.VENDOR_AGREEMENT,
            "PROCUREMENT AGREEMENT": ContractType.VENDOR_AGREEMENT,
            "LICENSE AGREEMENT": ContractType.VENDOR_AGREEMENT,
            "SOFTWARE LICENSE AGREEMENT": ContractType.VENDOR_AGREEMENT,
            "SAAS AGREEMENT": ContractType.VENDOR_AGREEMENT,
            "SAAS SUBSCRIPTION AGREEMENT": ContractType.VENDOR_AGREEMENT,
            "SUBSCRIPTION AGREEMENT": ContractType.VENDOR_AGREEMENT,
            "RESELLER AGREEMENT": ContractType.VENDOR_AGREEMENT,
            "DISTRIBUTION AGREEMENT": ContractType.VENDOR_AGREEMENT,
            "PARTNERSHIP AGREEMENT": ContractType.VENDOR_AGREEMENT,
            "JOINT VENTURE AGREEMENT": ContractType.VENDOR_AGREEMENT,
            "LEASE AGREEMENT": ContractType.VENDOR_AGREEMENT,
            "LEASE": ContractType.VENDOR_AGREEMENT,
            "RENTAL AGREEMENT": ContractType.VENDOR_AGREEMENT,
            # Employment variants
            "EMPLOYMENT": ContractType.EMPLOYMENT_CONTRACT,
            "EMPLOYMENT_CONTRACT": ContractType.EMPLOYMENT_CONTRACT,
            "EMPLOYMENT CONTRACT": ContractType.EMPLOYMENT_CONTRACT,
            "EMPLOYMENT AGREEMENT": ContractType.EMPLOYMENT_CONTRACT,
            "OFFER LETTER": ContractType.EMPLOYMENT_CONTRACT,
            "INDEPENDENT CONTRACTOR AGREEMENT": ContractType.EMPLOYMENT_CONTRACT,
            "CONTRACTOR AGREEMENT": ContractType.EMPLOYMENT_CONTRACT,
            "FREELANCE AGREEMENT": ContractType.EMPLOYMENT_CONTRACT,
            "SEPARATION AGREEMENT": ContractType.EMPLOYMENT_CONTRACT,
            "NON-COMPETE AGREEMENT": ContractType.EMPLOYMENT_CONTRACT,
            "NON COMPETE AGREEMENT": ContractType.EMPLOYMENT_CONTRACT,
            "NONCOMPETE AGREEMENT": ContractType.EMPLOYMENT_CONTRACT,
        }
        mapped_type = type_map.get(type_value)
        if mapped_type:
            contract.contract_type = mapped_type
        # Don't clear existing contract_type if AI returns unrecognized value

    # Helper to check if a value matches any excluded party (the uploader's org)
    def _is_excluded_party(value: str) -> bool:
        if not excluded_parties or not value:
            return False
        value_lower = value.strip().lower()
        for ep in excluded_parties:
            ep_lower = ep.strip().lower()
            # Only match if excluded party name is a meaningful prefix/match of the value
            # e.g., "ClientAA" matches "ClientAA B.V." or "ClientAA Pvt Ltd"
            # but "DemoSup" should NOT match "DemoSup1 BPO Limited" (different entity)
            if value_lower == ep_lower:
                return True
            # Check if the excluded party is a prefix followed by a legal suffix
            if value_lower.startswith(ep_lower + " ") and len(ep_lower) > 4:
                # Make sure it's not a different entity (e.g., "DemoSup" vs "DemoSup1")
                remainder = value_lower[len(ep_lower):].strip()
                if remainder and remainder[0].isdigit():
                    continue  # Different entity (e.g., "DemoSup1" is not "DemoSup")
                return True
        return False

    # Update counterparty
    counterparty_set = False
    if metadata.counterparty and metadata.counterparty.confidence >= confidence_threshold:
        counterparty_value = str(metadata.counterparty.value)
        if not _is_generic_counterparty(counterparty_value) and not _is_excluded_party(counterparty_value):
            contract.counterparty = counterparty_value
            counterparty_set = True
            logger.info(f"Set counterparty to '{counterparty_value}'")
        elif is_excluded:
            logger.info(f"Rejected counterparty '{counterparty_value}' — matches uploading org")
    # Fallback: try to extract counterparty from filename if not set from metadata
    if not counterparty_set and (not contract.counterparty or _is_generic_counterparty(contract.counterparty)):
        filename_counterparty = extract_counterparty_from_filename(contract.filename)
        if filename_counterparty and not _is_excluded_party(filename_counterparty):
            logger.info(f"Using filename-derived counterparty: {filename_counterparty}")
            contract.counterparty = filename_counterparty
        elif metadata.parties:
            # Try to use first non-generic, non-excluded party from parties list
            for party in metadata.parties:
                if not _is_generic_counterparty(party) and not _is_excluded_party(party):
                    contract.counterparty = party
                    logger.info(f"Using parties list counterparty: {party}")
                    break

    # Update dates
    if metadata.effective_date and metadata.effective_date.confidence >= confidence_threshold:
        try:
            contract.effective_date = _parse_date(metadata.effective_date.value)
        except Exception:
            pass

    if metadata.expiration_date and metadata.expiration_date.confidence >= confidence_threshold:
        try:
            contract.expiration_date = _parse_date(metadata.expiration_date.value)
        except Exception:
            pass

    # Update value
    if metadata.contract_value and metadata.contract_value.confidence >= confidence_threshold:
        try:
            contract.contract_value = Decimal(str(metadata.contract_value.value))
        except Exception:
            pass

    if metadata.currency and metadata.currency.confidence >= confidence_threshold:
        currency_val = str(metadata.currency.value).upper().strip()
        # Map common currency names to ISO codes (VARCHAR(3) column)
        currency_map = {
            "EURO": "EUR", "EUROS": "EUR", "DOLLAR": "USD", "DOLLARS": "USD",
            "POUND": "GBP", "POUNDS": "GBP", "YEN": "JPY", "RUPEE": "INR",
            "RUPEES": "INR",
        }
        currency_val = currency_map.get(currency_val, currency_val)
        if len(currency_val) <= 3:
            contract.currency = currency_val

    # Update jurisdiction
    if metadata.jurisdiction and metadata.jurisdiction.confidence >= confidence_threshold:
        contract.jurisdiction = str(metadata.jurisdiction.value)

    await db.flush()
    return contract


def _parse_date(value: Any) -> date | None:
    """Parse a date value from various formats.

    Args:
        value: Date value (string or date object).

    Returns:
        Parsed date or None.
    """
    if isinstance(value, date):
        return value

    if not value:
        return None

    value_str = str(value)

    # Try ISO format first
    try:
        return date.fromisoformat(value_str)
    except ValueError:
        pass

    # Try common formats
    import datetime

    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]

    for fmt in formats:
        try:
            return datetime.datetime.strptime(value_str, fmt).date()
        except ValueError:
            continue

    return None


def extract_metadata_regex(text: str) -> ExtractedMetadata:
    """Extract metadata using regex patterns as fallback.

    Args:
        text: Contract text to extract from.

    Returns:
        ExtractedMetadata with regex-extracted fields.
    """
    # Normalize quotes
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")

    fields = {}
    parties = []

    # Contract type detection
    type_patterns = [
        (r"(?i)master\s+service[s]?\s+agreement", "MSA"),
        (r"(?i)non[- ]?disclosure\s+agreement", "NDA"),
        (r"(?i)confidentiality\s+agreement", "NDA"),
        (r"(?i)statement\s+of\s+work", "SOW"),
        (r"(?i)work\s+order", "SOW"),
        (r"(?i)amendment\s+(?:no\.?\s*\d+|to)", "AMENDMENT"),
        (r"(?i)vendor\s+agreement", "VENDOR"),
        (r"(?i)supplier\s+agreement", "VENDOR"),
        (r"(?i)employment\s+(?:agreement|contract)", "EMPLOYMENT"),
        (r"(?i)consulting\s+agreement", "MSA"),
        (r"(?i)service[s]?\s+agreement", "MSA"),
    ]

    for pattern, ctype in type_patterns:
        if re.search(pattern, text[:3000]):
            fields["contract_type"] = MetadataField(
                value=ctype,
                confidence=0.8,
                raw_text=pattern,
            )
            break

    # Party extraction patterns
    party_patterns = [
        # "between X and Y" pattern
        r"(?i)(?:between|by and between)\s+([A-Z][A-Za-z0-9\s,\.]+?)(?:\s*\([^)]+\))?\s+(?:and|&)\s+([A-Z][A-Za-z0-9\s,\.]+?)(?:\s*\([^)]+\))?(?:\s*[,\.]|\s+(?:hereinafter|effective))",
        # "X (the/as "Provider")" pattern
        r"([A-Z][A-Za-z0-9\s,\.]+?)\s*\(\s*(?:the\s+)?[\"']?(?:Provider|Vendor|Supplier|Company|Client|Customer|Contractor)[\"']?\s*\)",
        # "X, a corporation" pattern
        r"([A-Z][A-Za-z0-9\s]+),?\s+(?:a|an)\s+(?:corporation|company|LLC|Inc\.|limited)",
    ]

    for pattern in party_patterns:
        matches = re.findall(pattern, text[:5000])
        for match in matches:
            if isinstance(match, tuple):
                for m in match:
                    cleaned = m.strip().strip(',').strip()
                    if len(cleaned) > 2 and len(cleaned) < 100:
                        parties.append(cleaned)
            else:
                cleaned = match.strip().strip(',').strip()
                if len(cleaned) > 2 and len(cleaned) < 100:
                    parties.append(cleaned)

    # Deduplicate parties
    seen = set()
    unique_parties = []
    for p in parties:
        p_lower = p.lower()
        if p_lower not in seen and not any(skip in p_lower for skip in ['hereinafter', 'whereas', 'agreement']):
            seen.add(p_lower)
            unique_parties.append(p)

    # Set counterparty (usually second party mentioned)
    if len(unique_parties) >= 2:
        fields["counterparty"] = MetadataField(
            value=unique_parties[1],
            confidence=0.75,
            raw_text=f"Parties: {', '.join(unique_parties[:2])}",
        )
    elif len(unique_parties) == 1:
        fields["counterparty"] = MetadataField(
            value=unique_parties[0],
            confidence=0.6,
            raw_text=f"Party: {unique_parties[0]}",
        )

    # Effective date patterns
    date_patterns = [
        r"(?i)effective\s+(?:as\s+of\s+)?(\w+\s+\d{1,2},?\s+\d{4})",
        r"(?i)dated\s+(?:as\s+of\s+)?(\w+\s+\d{1,2},?\s+\d{4})",
        r"(?i)entered\s+into\s+(?:as\s+of\s+)?(\w+\s+\d{1,2},?\s+\d{4})",
        r"(?i)this\s+agreement\s+(?:is\s+)?(?:made\s+)?(?:on\s+)?(\w+\s+\d{1,2},?\s+\d{4})",
        r"(?i)effective\s+date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text[:3000])
        if match:
            parsed = _parse_date(match.group(1))
            if parsed:
                fields["effective_date"] = MetadataField(
                    value=str(parsed),
                    confidence=0.8,
                    raw_text=match.group(0),
                )
                break

    # Expiration date patterns
    expiration_patterns = [
        r"(?i)expir(?:es?|ation)\s+(?:date\s*[:\s])?(?:on\s+)?(\w+\s+\d{1,2},?\s+\d{4})",
        r"(?i)terminat(?:es?|ion)\s+(?:date\s*[:\s])?(?:on\s+)?(\w+\s+\d{1,2},?\s+\d{4})",
        r"(?i)valid\s+(?:until|through)\s+(\w+\s+\d{1,2},?\s+\d{4})",
        r"(?i)(?:initial|contract)\s+term\s+(?:ends?|expir(?:es?|ation))\s+(?:on\s+)?(\w+\s+\d{1,2},?\s+\d{4})",
        r"(?i)end\s+date[:\s]+(\w+\s+\d{1,2},?\s+\d{4})",
        r"(?i)(?:expir(?:es?|ation)|termination|end)\s+date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"(?i)until\s+(\w+\s+\d{1,2},?\s+\d{4})",
        r"(?i)through\s+(\w+\s+\d{1,2},?\s+\d{4})",
        # Pattern for "X year term" - calculate from effective date if found
        r"(?i)(?:for\s+)?(?:a\s+)?(?:period\s+of\s+)?(\d+)\s+year[s]?\s+(?:term|period)",
    ]

    for pattern in expiration_patterns:
        match = re.search(pattern, text)
        if match:
            # Handle "X year term" pattern
            if "year" in pattern:
                try:
                    years = int(match.group(1))
                    # If we have an effective date, calculate expiration
                    if "effective_date" in fields:
                        eff_date = _parse_date(fields["effective_date"].value)
                        if eff_date:
                            from datetime import date as dt_date
                            exp_date = dt_date(eff_date.year + years, eff_date.month, eff_date.day)
                            fields["expiration_date"] = MetadataField(
                                value=str(exp_date),
                                confidence=0.7,
                                raw_text=match.group(0),
                            )
                            break
                except (ValueError, OverflowError):
                    pass
            else:
                parsed = _parse_date(match.group(1))
                if parsed:
                    fields["expiration_date"] = MetadataField(
                        value=str(parsed),
                        confidence=0.8,
                        raw_text=match.group(0),
                    )
                    break

    # Jurisdiction patterns
    jurisdiction_patterns = [
        r"(?i)govern(?:ed|ing)\s+(?:by\s+)?(?:the\s+)?law[s]?\s+of\s+(?:the\s+)?(?:State\s+of\s+)?([A-Z][A-Za-z\s]+?)(?:\s*[,\.]|\s+and)",
        r"(?i)law[s]?\s+of\s+(?:the\s+)?(?:State\s+of\s+)?([A-Z][A-Za-z\s]+?)(?:\s+shall\s+govern)",
        r"(?i)jurisdiction\s+of\s+(?:the\s+)?([A-Z][A-Za-z\s]+?)(?:\s*[,\.])",
    ]

    for pattern in jurisdiction_patterns:
        match = re.search(pattern, text)
        if match:
            jurisdiction = match.group(1).strip()
            if len(jurisdiction) > 2 and len(jurisdiction) < 100:
                fields["jurisdiction"] = MetadataField(
                    value=jurisdiction,
                    confidence=0.8,
                    raw_text=match.group(0),
                )
                break

    # Contract value patterns
    value_patterns = [
        r"(?i)(?:total|aggregate|contract)\s+(?:amount|value|sum)[:\s]+\$?([\d,]+(?:\.\d{2})?)",
        r"(?i)not\s+(?:to\s+)?exceed\s+\$?([\d,]+(?:\.\d{2})?)",
        r"\$\s*([\d,]+(?:\.\d{2})?)\s*(?:USD|dollars)?",
    ]

    for pattern in value_patterns:
        match = re.search(pattern, text)
        if match:
            value_str = match.group(1).replace(",", "")
            try:
                value = float(value_str)
                if value > 100:  # Ignore small numbers
                    fields["contract_value"] = MetadataField(
                        value=value,
                        confidence=0.7,
                        raw_text=match.group(0),
                    )
                    fields["currency"] = MetadataField(
                        value="USD",
                        confidence=0.8,
                        raw_text="$",
                    )
                    break
            except ValueError:
                pass

    # Calculate overall confidence
    total_conf = sum(f.confidence for f in fields.values())
    field_count = len(fields)

    return ExtractedMetadata(
        **fields,
        parties=unique_parties[:5],
        overall_confidence=total_conf / max(field_count, 1) if field_count else 0.0,
    )


async def extract_metadata_with_fallback(
    contract_text: str,
    contract_id: str | None = None,
    user_id: str | None = None,
    user_role: str | None = None,
    excluded_parties: list[str] | None = None,
) -> ExtractedMetadata:
    """Extract metadata using AI with regex fallback.

    Args:
        contract_text: The contract text to extract metadata from.
        contract_id: Optional contract ID for context.
        user_id: User ID for RBAC.
        user_role: User role for RBAC.

    Returns:
        ExtractedMetadata with best available data.
    """
    # Try AI extraction first
    ai_metadata = await extract_metadata(contract_text, contract_id, user_id, user_role, excluded_parties)

    # If AI extraction got good results, use it
    if ai_metadata.overall_confidence >= 0.6:
        return ai_metadata

    # Otherwise, use regex fallback and merge
    regex_metadata = extract_metadata_regex(contract_text)

    # Merge: prefer AI results when confident, otherwise use regex
    merged_fields = {}

    for field_name in ["contract_type", "counterparty", "effective_date", "expiration_date",
                       "contract_value", "currency", "jurisdiction"]:
        ai_field = getattr(ai_metadata, field_name)
        regex_field = getattr(regex_metadata, field_name)

        if ai_field and ai_field.confidence >= 0.7:
            merged_fields[field_name] = ai_field
        elif regex_field:
            merged_fields[field_name] = regex_field
        elif ai_field:
            merged_fields[field_name] = ai_field

    # Merge parties
    all_parties = list(set(ai_metadata.parties + regex_metadata.parties))

    return ExtractedMetadata(
        **merged_fields,
        parties=all_parties[:10],
        overall_confidence=max(ai_metadata.overall_confidence, regex_metadata.overall_confidence),
    )


def register_metadata_extraction_agent() -> None:
    """Register the metadata extraction agent with the orchestrator."""
    config = get_metadata_extraction_config()
    orchestrator = get_orchestrator()

    # Check if already registered
    if orchestrator.get_agent(config.name):
        return

    orchestrator.register_agent(
        name=config.name,
        description=config.description,
        system_prompt=config.system_prompt,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
