"""Service for extracting definitions from contract text."""

import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.definition import ContractDefinition
from app.models.clause import Clause, ClauseType


# Patterns for extracting definitions
DEFINITION_PATTERNS = [
    # "Term" means ...
    r'"([^"]+)"\s+(?:means?|shall mean|refers? to|is defined as)',
    # 'Term' means ...
    r"'([^']+)'\s+(?:means?|shall mean|refers? to|is defined as)",
    # "Term" or "Term" means ...
    r'"([^"]+)"(?:\s+or\s+"[^"]+")*\s+(?:means?|shall mean)',
    # (a) "Term" means ...
    r'\([a-z0-9]+\)\s*"([^"]+)"\s+(?:means?|shall mean)',
    # 1.1. "Term" means ...
    r'\d+\.\d+\.?\s*"([^"]+)"\s+(?:means?|shall mean)',
    # Term: definition (colon-based)
    r'^([A-Z][A-Za-z\s]+):\s+(?=means?|shall)',
]

# Categories for definitions based on common contract terms
CATEGORY_PATTERNS = {
    "party": r"(party|parties|provider|client|vendor|customer|company|corporation|entity)",
    "service": r"(service|services|solution|deliverable|work|performance)",
    "document": r"(agreement|contract|order|schedule|exhibit|annexure|amendment)",
    "term": r"(term|period|duration|year|month|day)",
    "financial": r"(fee|fees|payment|price|cost|amount|value|charge)",
    "data": r"(data|information|record|report|document)",
    "process": r"(process|procedure|certification|testing|audit|review)",
    "legal": r"(confidential|intellectual property|liability|indemnif|warrant|represent)",
}


def categorize_definition(term: str, definition_text: str) -> str | None:
    """Categorize a definition based on the term and text."""
    combined = f"{term} {definition_text}".lower()

    for category, pattern in CATEGORY_PATTERNS.items():
        if re.search(pattern, combined, re.IGNORECASE):
            return category

    return None


def extract_cross_references(definition_text: str) -> list[str]:
    """Extract references to other defined terms from a definition."""
    # Normalize quotes first
    definition_text = normalize_quotes(definition_text)
    # Look for quoted terms in the definition
    refs = re.findall(r'"([^"]+)"', definition_text)
    refs.extend(re.findall(r"'([^']+)'", definition_text))

    # Filter out common non-term words
    filtered = []
    for ref in refs:
        if len(ref) > 2 and not ref.lower() in ["the", "and", "for", "with", "this"]:
            filtered.append(ref)

    return list(set(filtered))


def normalize_quotes(text: str) -> str:
    """Normalize curly/smart quotes to straight quotes."""
    # Unicode curly quotes to straight quotes
    text = text.replace('\u201c', '"')  # LEFT DOUBLE QUOTATION MARK
    text = text.replace('\u201d', '"')  # RIGHT DOUBLE QUOTATION MARK
    text = text.replace('\u2018', "'")  # LEFT SINGLE QUOTATION MARK
    text = text.replace('\u2019', "'")  # RIGHT SINGLE QUOTATION MARK
    # Also handle other common quote variants
    text = text.replace('„', '"')  # DOUBLE LOW-9 QUOTATION MARK
    text = text.replace('«', '"')  # LEFT-POINTING DOUBLE ANGLE QUOTATION MARK
    text = text.replace('»', '"')  # RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK
    return text


def parse_definitions_from_text(text: str, page_number: int | None = None) -> list[dict[str, Any]]:
    """Parse definitions from a block of text (typically from a Definitions section)."""
    definitions = []

    # Normalize quotes first
    text = normalize_quotes(text)

    # Split by numbered items or paragraph breaks
    # Pattern for numbered definitions: 1.1., (a), etc.
    parts = re.split(r'(?=\d+\.\d+\.?\s+"|\([a-z]\)\s+")', text)

    for part in parts:
        if not part.strip():
            continue

        # Try each pattern to extract the term
        for pattern in DEFINITION_PATTERNS:
            match = re.search(pattern, part, re.IGNORECASE)
            if match:
                term = match.group(1).strip()

                # Extract the definition text (everything after the pattern)
                def_start = match.end()
                # Find end of definition (next definition or end of text)
                def_text = part[def_start:].strip()

                # Clean up the definition text
                # Remove trailing periods if they look like end of sentence
                def_text = def_text.rstrip(".")

                if term and def_text and len(def_text) > 10:
                    # Extract section reference
                    section_match = re.search(r'^(\d+\.\d+)', part)
                    section_ref = section_match.group(1) if section_match else None

                    definitions.append({
                        "term": term,
                        "term_normalized": term.lower().strip(),
                        "definition_text": def_text[:2000],  # Limit length
                        "category": categorize_definition(term, def_text),
                        "section_reference": section_ref,
                        "page_number": page_number,
                        "cross_references": extract_cross_references(def_text),
                    })
                break

    return definitions


async def extract_definitions_from_clauses(
    db: AsyncSession,
    contract_id: uuid.UUID,
) -> list[ContractDefinition]:
    """Extract definitions from DEFINITIONS type clauses for a contract."""
    # Get all DEFINITIONS type clauses
    result = await db.execute(
        select(Clause)
        .where(Clause.contract_id == contract_id)
        .where(Clause.clause_type == ClauseType.DEFINITIONS)
        .order_by(Clause.page_number.asc().nulls_last())
    )

    clauses = result.scalars().all()

    if not clauses:
        # Try to find clauses with "definition" in the text
        result = await db.execute(
            select(Clause)
            .where(Clause.contract_id == contract_id)
            .where(Clause.text.ilike("%definition%"))
            .order_by(Clause.page_number.asc().nulls_last())
        )
        clauses = result.scalars().all()

    all_definitions = []

    for clause in clauses:
        parsed = parse_definitions_from_text(clause.text, clause.page_number)

        for defn_data in parsed:
            defn = ContractDefinition(
                contract_id=contract_id,
                source_clause_id=clause.id,
                term=defn_data["term"],
                term_normalized=defn_data["term_normalized"],
                definition_text=defn_data["definition_text"],
                category=defn_data["category"],
                section_reference=defn_data["section_reference"],
                page_number=defn_data["page_number"],
                cross_references=",".join(defn_data["cross_references"]) if defn_data["cross_references"] else None,
            )
            all_definitions.append(defn)

    return all_definitions


async def sync_definitions_to_db(
    db: AsyncSession,
    contract_id: uuid.UUID,
    definitions: list[ContractDefinition],
) -> int:
    """Save extracted definitions to the database, replacing any existing ones."""
    # Delete existing definitions for this contract
    await db.execute(
        delete(ContractDefinition).where(ContractDefinition.contract_id == contract_id)
    )

    # Add new definitions
    for defn in definitions:
        db.add(defn)

    await db.commit()

    return len(definitions)


async def extract_and_save_definitions(
    db: AsyncSession,
    contract_id: uuid.UUID,
) -> int:
    """Extract definitions from clauses and save to database."""
    definitions = await extract_definitions_from_clauses(db, contract_id)
    count = await sync_definitions_to_db(db, contract_id, definitions)
    return count
