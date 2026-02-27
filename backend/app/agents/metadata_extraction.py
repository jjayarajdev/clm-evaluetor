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

Extract the following fields from the provided contract text:

1. **contract_type**: Classify the contract as one of:
   - NDA (Non-Disclosure Agreement)
   - MSA (Master Service Agreement)
   - SOW (Statement of Work)
   - AMENDMENT (Contract Amendment)
   - VENDOR (Vendor Agreement)
   - EMPLOYMENT (Employment Contract)
   - OTHER (if none of the above)

2. **counterparty**: Extract ONLY the legal entity name of the other contracting party.
   RULES:
   - Extract ONLY the company/organization name (e.g., "Acme Corporation", "TechServices Inc.")
   - DO NOT include addresses, city, state, zip codes, or any location information
   - DO NOT use template placeholders like "the ones in the RFP", "[Company Name]", "Party A/B", "Client", "Vendor"
   - If the document is a template with placeholders, set counterparty to null with confidence 0.0
   - Look for legal entity suffixes: Inc., LLC, Ltd., Corp., Corporation, BV, GmbH, LP, LLP, PLC
   - In "between X and Y" clauses, extract the party that is NOT the document owner/drafter
   - Extract the SHORT legal name only, not the full address block

3. **effective_date**: When the contract takes effect (ISO format: YYYY-MM-DD)
   Look for phrases like: "effective as of", "dated", "entered into on", "commences on"

4. **expiration_date**: When the contract expires or terminates (ISO format: YYYY-MM-DD)
   Look for phrases like: "expires on", "terminates on", "valid until", "end date", "expiration date"
   Also calculate from term clauses like: "initial term of X years" (add X years to effective date)
   Look in "Term", "Duration", "Term and Termination" sections

5. **contract_value**: The monetary value of the contract (numeric only)

6. **currency**: The currency of the contract value (USD, EUR, GBP, etc.)

7. **jurisdiction**: The governing law jurisdiction (e.g., "State of Delaware", "England and Wales", "Netherlands")

8. **parties**: List ALL actual party names mentioned in the contract (not generic terms)

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

    Includes the beginning (parties, dates) plus relevant sections
    like Term, Duration, Termination, Payment, Value where key metadata appears.

    Args:
        contract_text: Full contract text.
        max_length: Maximum text length to return (increased for better coverage).

    Returns:
        Text sample optimized for metadata extraction.
    """
    if len(contract_text) <= max_length:
        return contract_text

    # Always include first 10000 chars (parties, effective date, preamble, initial sections)
    beginning = contract_text[:10000]

    # Search for metadata-rich sections in the rest
    remaining = contract_text[10000:]
    important_sections = []

    # Patterns that indicate sections with important metadata
    section_patterns = [
        # Term and duration
        r"(?i)(?:^|\n)\s*\d*\.?\s*(?:TERM|DURATION|EXPIRATION|TERMINATION)[^\n]*\n",
        r"(?i)(?:^|\n)\s*(?:ARTICLE|SECTION)\s+\d+[.:]\s*(?:TERM|DURATION)[^\n]*\n",
        r"(?i)initial\s+term",
        r"(?i)contract\s+(?:term|period|duration)",
        r"(?i)(?:expires?|terminates?)\s+(?:on|after)",
        r"(?i)valid\s+(?:until|through|for)",
        # Payment and value
        r"(?i)(?:^|\n)\s*\d*\.?\s*(?:PAYMENT|COMPENSATION|FEES|PRICING)[^\n]*\n",
        r"(?i)(?:^|\n)\s*(?:ARTICLE|SECTION)\s+\d+[.:]\s*(?:PAYMENT|FEE)[^\n]*\n",
        r"(?i)(?:total|aggregate|contract)\s+(?:amount|value|sum)",
        r"(?i)not\s+(?:to\s+)?exceed",
        # Governing law / jurisdiction
        r"(?i)(?:^|\n)\s*\d*\.?\s*(?:GOVERNING\s+LAW|JURISDICTION)[^\n]*\n",
        r"(?i)govern(?:ed|ing)\s+(?:by\s+)?(?:the\s+)?law",
        # Auto-renewal
        r"(?i)(?:auto[- ]?renew|automatic\s+renewal)",
        r"(?i)renewal\s+(?:term|period|notice)",
    ]

    for pattern in section_patterns:
        for match in re.finditer(pattern, remaining):
            # Extract ~2000 chars around the match for better context
            start = max(0, match.start() - 300)
            end = min(len(remaining), match.end() + 1700)
            section = remaining[start:end]
            # Avoid duplicate sections
            if not any(section[:200] in s for s in important_sections):
                important_sections.append(section)

    # Also include the last 3000 chars (often contains signature blocks with dates)
    ending = contract_text[-3000:] if len(contract_text) > 13000 else ""

    # Combine beginning with found sections and ending
    result = beginning
    for section in important_sections[:5]:  # Increased to 5 sections
        if len(result) + len(section) < max_length - 3500:
            result += "\n\n[...]\n\n" + section

    # Add ending if room
    if ending and len(result) + len(ending) < max_length:
        result += "\n\n[...END OF CONTRACT...]\n\n" + ending

    return result


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
    # Include beginning (parties, effective date) + search for term/expiration sections
    text_sample = _prepare_metadata_text(contract_text)

    query = f"""Extract metadata from the following contract text:

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
            metadata = _parse_metadata_response(json_data)

            # Validate/clean counterparty with LLM
            if metadata.counterparty and metadata.counterparty.value:
                raw_value = str(metadata.counterparty.value)
                cleaned = await _clean_counterparty_with_llm(raw_value)
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


async def _clean_counterparty_with_llm(value: str) -> str | None:
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

    # If it looks clean already (short, has legal suffix), return as-is
    if len(value) < 50 and re.search(r'\b(Inc\.?|LLC|Ltd\.?|Corp\.?|Corporation|GmbH|BV|LP|LLP|PLC)\b', value, re.IGNORECASE):
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
- Return ONLY the company name (e.g., "Acme Corporation", "TechServices Inc.")
- Remove any addresses, cities, states, zip codes
- If the text is a template placeholder (e.g., "[Company Name]", "the ones in the RFP", "Party A"), return: NULL
- If no valid company name exists, return: NULL
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
    """Quick check if a counterparty value is obviously generic."""
    if not value:
        return True

    value_lower = value.lower().strip()

    if len(value_lower) < 3:
        return True

    # Only check obvious generic terms - let LLM handle the rest
    generic_terms = [
        "the parties", "parties", "party a", "party b", "company", "client",
        "customer", "vendor", "provider", "the company", "the client",
        "unknown", "n/a", "none", "null", "tbd",
    ]

    return value_lower in generic_terms


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
        if field_data and isinstance(field_data, dict) and field_data.get("value") is not None:
            value = field_data["value"]
            confidence = field_data.get("confidence", 0.5)

            # Basic validation for counterparty - LLM cleaning happens later in extract_metadata
            if field_name == "counterparty" and _is_generic_counterparty(str(value)):
                logger.debug(f"Rejecting obviously generic counterparty: {value}")
                continue

            fields[field_name] = MetadataField(
                value=value,
                confidence=confidence,
                raw_text=field_data.get("raw_text"),
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
        type_value = str(metadata.contract_type.value).upper()
        type_map = {
            "NDA": ContractType.NDA,
            "MSA": ContractType.MSA,
            "SOW": ContractType.SOW,
            "AMENDMENT": ContractType.AMENDMENT,
            "VENDOR": ContractType.VENDOR_AGREEMENT,
            "VENDOR_AGREEMENT": ContractType.VENDOR_AGREEMENT,
            "EMPLOYMENT": ContractType.EMPLOYMENT_CONTRACT,
            "EMPLOYMENT_CONTRACT": ContractType.EMPLOYMENT_CONTRACT,
        }
        contract.contract_type = type_map.get(type_value)

    # Update counterparty
    counterparty_set = False
    if metadata.counterparty and metadata.counterparty.confidence >= confidence_threshold:
        counterparty_value = str(metadata.counterparty.value)
        if not _is_generic_counterparty(counterparty_value):
            contract.counterparty = counterparty_value
            counterparty_set = True

    # Fallback: try to extract counterparty from filename if not set from metadata
    if not counterparty_set and (not contract.counterparty or _is_generic_counterparty(contract.counterparty)):
        filename_counterparty = extract_counterparty_from_filename(contract.filename)
        if filename_counterparty:
            logger.info(f"Using filename-derived counterparty: {filename_counterparty}")
            contract.counterparty = filename_counterparty
        elif metadata.parties:
            # Try to use first non-generic party from parties list
            for party in metadata.parties:
                if not _is_generic_counterparty(party):
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
        contract.currency = str(metadata.currency.value).upper()

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
    ai_metadata = await extract_metadata(contract_text, contract_id, user_id, user_role)

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
