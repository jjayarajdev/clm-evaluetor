"""Service for extracting preamble/header data from contracts."""

import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.preamble import ContractPreamble, ContractPartyDetail
from app.models.clause import Clause


def normalize_quotes(text: str) -> str:
    """Normalize curly/smart quotes to straight quotes."""
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    return text


def extract_document_title(text: str) -> str | None:
    """Extract the document title from the preamble."""
    text = normalize_quotes(text)

    # Look for common title patterns at the start
    patterns = [
        # "MASTER SERVICE AGREEMENT" type titles
        r'^[\s\n]*([A-Z][A-Z\s\-]+AGREEMENT[A-Z\s\-]*)',
        # Title followed by "between"
        r'^[\s\n]*([A-Z][A-Za-z\s\-]+)\s*(?:\n|between)',
        # "CONTRACT FOR..." pattern
        r'^[\s\n]*(CONTRACT\s+FOR[^\n]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text[:1000], re.MULTILINE)
        if match:
            title = match.group(1).strip()
            # Clean up title
            title = re.sub(r'\s+', ' ', title)
            if len(title) > 5 and len(title) < 300:
                return title

    return None


def extract_effective_date_text(text: str) -> str | None:
    """Extract effective date text from preamble."""
    text = normalize_quotes(text)

    patterns = [
        r'(?i)(?:effective|dated)\s+(?:as\s+of\s+)?([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        r'(?i)entered\s+into\s+(?:on\s+)?(?:this\s+)?(\d{1,2}(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?[A-Za-z]+,?\s+\d{4})',
        r'(?i)this\s+(?:agreement\s+)?(?:is\s+)?made\s+(?:on\s+)?([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
        r'(?i)date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
    ]

    for pattern in patterns:
        match = re.search(pattern, text[:3000])
        if match:
            return match.group(1).strip()

    return None


def extract_recitals(text: str) -> tuple[str | None, str | None]:
    """Extract recitals/whereas clauses and create a summary.

    Returns:
        Tuple of (recitals_text, background_summary)
    """
    text = normalize_quotes(text)

    # Find WHEREAS/RECITALS section
    recitals_patterns = [
        r'(?i)(WHEREAS[^A-Z]*(?:WHEREAS[^\n]+\n?)+)',
        r'(?i)RECITALS[:\s]*((?:.*?\n)+?)(?:NOW,?\s*THEREFORE|AGREEMENT)',
        r'(?i)(BACKGROUND[:\s]*(?:.*?\n)+?)(?:NOW,?\s*THEREFORE|AGREEMENT|Article)',
    ]

    recitals_text = None
    for pattern in recitals_patterns:
        match = re.search(pattern, text[:5000])
        if match:
            recitals_text = match.group(1).strip()
            break

    if not recitals_text:
        return None, None

    # Create summary from recitals
    # Extract key points from WHEREAS clauses
    whereas_points = re.findall(r'(?i)WHEREAS[,\s]+([^;]+)[;.]', recitals_text)

    if whereas_points:
        summary = " | ".join([p.strip()[:150] for p in whereas_points[:3]])
        return recitals_text[:2000], summary[:500]

    return recitals_text[:2000], recitals_text[:300]


def extract_parties_from_preamble(text: str) -> list[dict[str, Any]]:
    """Extract party details from the preamble section."""
    text = normalize_quotes(text)
    parties = []

    # Pattern: "COMPANY NAME (the/as "Role")"
    pattern1 = r'([A-Z][A-Za-z0-9\s,\.]+?)\s*\(\s*(?:the\s+|as\s+)?["\']?([A-Za-z]+)["\']?\s*\)'
    matches1 = re.findall(pattern1, text[:3000])

    for name, role in matches1:
        name = name.strip().strip(',')
        if len(name) > 2 and len(name) < 150:
            parties.append({
                "party_name": name,
                "party_role": role.strip(),
                "party_short_name": role.strip(),
            })

    # Pattern: "between X and Y"
    pattern2 = r'(?i)between\s+([A-Z][A-Za-z0-9\s,\.]+?)(?:\s*\([^)]+\))?\s+(?:and|&)\s+([A-Z][A-Za-z0-9\s,\.]+?)(?:\s*\([^)]+\))?(?:\s*[,\.]|\s+(?:herein|effective))'
    match2 = re.search(pattern2, text[:3000])

    if match2:
        party1 = match2.group(1).strip().strip(',')
        party2 = match2.group(2).strip().strip(',')

        # Only add if not already found
        existing_names = {p["party_name"].lower() for p in parties}

        if party1.lower() not in existing_names and len(party1) > 2:
            parties.append({
                "party_name": party1,
                "party_role": "Party A",
                "party_short_name": None,
            })

        if party2.lower() not in existing_names and len(party2) > 2:
            parties.append({
                "party_name": party2,
                "party_role": "Party B",
                "party_short_name": None,
            })

    # Extract legal form and jurisdiction
    for party in parties:
        name = party["party_name"]

        # Legal form patterns
        legal_forms = [
            (r'(?i)\b(corporation)\b', 'corporation'),
            (r'(?i)\b(LLC|L\.L\.C\.)\b', 'LLC'),
            (r'(?i)\b(Inc\.|Incorporated)\b', 'Inc'),
            (r'(?i)\b(Ltd\.|Limited)\b', 'Ltd'),
            (r'(?i)\b(LLP|L\.L\.P\.)\b', 'LLP'),
        ]

        for pattern, form in legal_forms:
            if re.search(pattern, name):
                party["legal_form"] = form
                break

        # Try to find jurisdiction after party name
        jurisdiction_pattern = rf'{re.escape(name)}[^,]*,?\s*(?:a|an)\s+[A-Za-z]+\s+(?:organized|incorporated|formed)\s+(?:under\s+the\s+laws\s+of\s+)?([A-Za-z\s]+?)(?:\s*[,\.])'
        jur_match = re.search(jurisdiction_pattern, text[:3000], re.IGNORECASE)
        if jur_match:
            party["jurisdiction_of_incorporation"] = jur_match.group(1).strip()

    return parties


def parse_preamble_from_text(text: str) -> dict[str, Any]:
    """Parse preamble data from contract text.

    Args:
        text: The contract text (typically first few pages).

    Returns:
        Dictionary with preamble data.
    """
    text = normalize_quotes(text)

    document_title = extract_document_title(text)
    effective_date_text = extract_effective_date_text(text)
    recitals_text, background_summary = extract_recitals(text)
    parties = extract_parties_from_preamble(text)

    return {
        "document_title": document_title,
        "effective_date_text": effective_date_text,
        "background_summary": background_summary,
        "recitals_text": recitals_text,
        "source_text": text[:3000],  # Store first part as source
        "parties": parties,
    }


async def extract_preamble_from_clauses(
    db: AsyncSession,
    contract_id: uuid.UUID,
) -> tuple[ContractPreamble | None, list[ContractPartyDetail]]:
    """Extract preamble data from contract clauses.

    Args:
        db: Database session.
        contract_id: Contract ID to extract from.

    Returns:
        Tuple of (preamble, party_details)
    """
    # Get first few clauses (typically contains preamble)
    result = await db.execute(
        select(Clause)
        .where(Clause.contract_id == contract_id)
        .order_by(Clause.page_number.asc().nulls_last())
        .limit(5)
    )

    clauses = result.scalars().all()

    if not clauses:
        return None, []

    # Combine text from first clauses
    combined_text = "\n\n".join([c.text for c in clauses])

    # Parse preamble
    data = parse_preamble_from_text(combined_text)

    # Create preamble record
    preamble = ContractPreamble(
        contract_id=contract_id,
        document_title=data["document_title"],
        effective_date_text=data["effective_date_text"],
        background_summary=data["background_summary"],
        recitals_text=data["recitals_text"],
        source_text=data["source_text"],
    )

    # Create party details
    party_details = []
    for i, party_data in enumerate(data["parties"]):
        detail = ContractPartyDetail(
            party_name=party_data["party_name"],
            party_role=party_data.get("party_role"),
            party_short_name=party_data.get("party_short_name"),
            legal_form=party_data.get("legal_form"),
            jurisdiction_of_incorporation=party_data.get("jurisdiction_of_incorporation"),
            party_order=i,
        )
        party_details.append(detail)

    return preamble, party_details


async def sync_preamble_to_db(
    db: AsyncSession,
    contract_id: uuid.UUID,
    preamble: ContractPreamble,
    party_details: list[ContractPartyDetail],
) -> int:
    """Save extracted preamble to database, replacing any existing one."""
    # Delete existing preamble for this contract (cascade deletes party details)
    await db.execute(
        delete(ContractPreamble).where(ContractPreamble.contract_id == contract_id)
    )

    # Add preamble
    db.add(preamble)
    await db.flush()
    await db.refresh(preamble)

    # Add party details with preamble ID
    for detail in party_details:
        detail.preamble_id = preamble.id
        db.add(detail)

    await db.commit()

    return 1 + len(party_details)


async def extract_and_save_preamble(
    db: AsyncSession,
    contract_id: uuid.UUID,
) -> int:
    """Extract preamble from clauses and save to database.

    Returns:
        Count of records created (1 preamble + N party details).
    """
    preamble, party_details = await extract_preamble_from_clauses(db, contract_id)

    if preamble is None:
        return 0

    count = await sync_preamble_to_db(db, contract_id, preamble, party_details)
    return count
