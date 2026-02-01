"""Service for extracting process steps from contract procedural clauses."""

import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.process_step import ContractProcessStep, StepType, StepStatus
from app.models.clause import Clause


def normalize_quotes(text: str) -> str:
    """Normalize curly/smart quotes to straight quotes."""
    text = text.replace('\u201c', '"')  # LEFT DOUBLE QUOTATION MARK
    text = text.replace('\u201d', '"')  # RIGHT DOUBLE QUOTATION MARK
    text = text.replace('\u2018', "'")  # LEFT SINGLE QUOTATION MARK
    text = text.replace('\u2019', "'")  # RIGHT SINGLE QUOTATION MARK
    return text


# Keywords to identify step types
STEP_TYPE_PATTERNS = {
    StepType.SUBMISSION: r"submit|submission|provide|deliver\s+sample|send\s+to",
    StepType.REVIEW: r"review|evaluat|assess|check|verify|inspect|audit",
    StepType.TESTING: r"test|testing|laboratory|lab\s+|sample\s+test",
    StepType.APPROVAL: r"approv|accept|sign.off|authorize|consent",
    StepType.DELIVERY: r"deliver|ship|provid|handover|transfer",
    StepType.CERTIFICATION: r"certif|certificate|credential|qualify|accredit",
    StepType.PAYMENT: r"pay|fee|invoice|billing|cost|price|charge",
    StepType.REPORTING: r"report|document|record|summary|result",
    StepType.RENEWAL: r"renew|extend|continu|prolong|maintain",
}


def determine_step_type(text: str) -> StepType:
    """Determine the step type based on text content."""
    text_lower = text.lower()

    for step_type, pattern in STEP_TYPE_PATTERNS.items():
        if re.search(pattern, text_lower, re.IGNORECASE):
            return step_type

    return StepType.OTHER


def extract_duration(text: str) -> int | None:
    """Extract duration in days from text."""
    text = normalize_quotes(text)

    # Look for patterns like "within X days", "X business days", "X calendar days"
    patterns = [
        r"within\s+(\d+)\s+(?:business\s+)?days?",
        r"(\d+)\s+(?:business\s+)?days?\s+(?:of|after|from|following)",
        r"no\s+(?:more|later)\s+than\s+(\d+)\s+days?",
        r"(\d+)\s+day\s+(?:period|timeline|deadline)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    # Look for week patterns
    week_pattern = r"(\d+)\s+weeks?"
    match = re.search(week_pattern, text, re.IGNORECASE)
    if match:
        return int(match.group(1)) * 7

    return None


def extract_responsible_party(text: str) -> str | None:
    """Extract the responsible party from text."""
    text = normalize_quotes(text)

    # Look for common patterns
    patterns = [
        r"(?:the\s+)?(provider|client|vendor|customer)\s+(?:shall|will|must|is\s+responsible)",
        r"(?:shall|will|must)\s+be\s+(?:the\s+)?(?:responsibility\s+of\s+)?(?:the\s+)?(provider|client|vendor|customer)",
        r"(provider|client|vendor|customer)['']?s?\s+responsibility",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).title()

    return None


def extract_deliverables(text: str) -> list[str]:
    """Extract deliverables from text."""
    text = normalize_quotes(text)
    deliverables = []

    # Look for document/output mentions
    patterns = [
        r"provide\s+(?:a\s+)?([^,.;]+(?:report|certificate|document|form|plan))",
        r"submit\s+(?:a\s+)?([^,.;]+(?:report|certificate|document|form|plan))",
        r"deliver\s+(?:a\s+)?([^,.;]+(?:report|certificate|document|form|plan))",
        r"([^,.;]+(?:report|certificate|document|form|plan))\s+(?:will|shall)\s+be\s+(?:provided|delivered|submitted)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            clean = match.strip()
            if len(clean) > 3 and len(clean) < 100:
                deliverables.append(clean)

    return list(set(deliverables))[:5]  # Limit to 5


def is_valid_step_name(title: str) -> bool:
    """Check if a title is a valid process step name."""
    title_lower = title.lower().strip()

    # Skip if too short or too long
    if len(title_lower) < 5 or len(title_lower) > 100:
        return False

    # Skip common non-step patterns
    skip_patterns = [
        r'^article\s+\d',
        r'^section\s+\d',
        r'^\d+\.\d+',  # Just numbers
        r'^services?$',
        r'^general$',
        r'^agreement$',
        r'^terms?$',
        r'^definitions?$',
        r'^\s*$',
        r'^[a-z]\s*$',  # Single letter
        r'https?://',  # URLs
        r'^note\s*to',  # Notes to drafter
        r'^[^a-z]*$',  # No letters
        r'means?\s+the',  # Definition patterns
        r'^the\s+',  # Starting with "the"
        r'^a\.?m\.?\s+to',  # Time patterns
        r'infringement',  # Legal boilerplate
        r'warranty',  # Warranty section
        r'disclaimer',
        r'expressly',
        r'available\s+basis',
    ]

    for pattern in skip_patterns:
        if re.search(pattern, title_lower):
            return False

    # Must contain meaningful action words or nouns
    good_patterns = [
        r'process',
        r'procedure',
        r'step',
        r'phase',
        r'stage',
        r'screening',
        r'testing',
        r'sampling',
        r'certification',
        r'approval',
        r'review',
        r'submission',
        r'delivery',
        r'payment',
        r'reporting',
        r'information',
        r'data',
        r'personnel',
        r'operations',
        r'requirements',
        r'responsibilities',
        r'services',
        r'change\s+order',
        r'cancellation',
        r'renewal',
        r'collaboration',
        r'integrity',
        r'branding',
    ]

    for pattern in good_patterns:
        if re.search(pattern, title_lower):
            return True

    return False


def parse_process_steps_from_text(
    text: str,
    clause_id: uuid.UUID | None = None,
    page_number: int | None = None,
) -> list[dict[str, Any]]:
    """Parse process steps from clause text."""
    text = normalize_quotes(text)
    steps = []

    # Look for lettered items like "(a) Product Sampling:" or "(b) Testing:"
    section_pattern = r'\(([a-z])\)\s*([A-Z][^:\n]{3,60}):'

    matches = list(re.finditer(section_pattern, text))

    for i, match in enumerate(matches):
        letter = match.group(1)
        title = match.group(2).strip()

        # Validate the step name
        if not is_valid_step_name(title):
            continue

        # Determine section reference
        section_ref = letter.upper()

        # Extract the content until next match or end
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        # Skip if content is too short
        if len(content) < 30:
            continue

        steps.append({
            "step_number": i + 1,
            "step_name": title[:255],
            "step_type": determine_step_type(title + " " + content),
            "description": content[:2000],
            "responsible_party": extract_responsible_party(content),
            "duration_days": extract_duration(content),
            "sla_days": None,
            "dependencies": None,
            "deliverables": ",".join(extract_deliverables(content)) or None,
            "source_text": (title + ": " + content)[:2000],
            "section_reference": section_ref,
            "source_clause_id": clause_id,
        })

    return steps


async def extract_process_steps_from_clauses(
    db: AsyncSession,
    contract_id: uuid.UUID,
) -> list[ContractProcessStep]:
    """Extract process steps from contract clauses."""
    # Get clauses that likely contain procedural content
    result = await db.execute(
        select(Clause)
        .where(Clause.contract_id == contract_id)
        .order_by(Clause.page_number.asc().nulls_last())
    )

    clauses = result.scalars().all()
    all_steps = []
    step_counter = 0
    seen_names = set()  # Track to avoid duplicates

    for clause in clauses:
        text = clause.text

        # Must have lettered sub-sections like (a), (b), (c)
        if not re.search(r'\([a-z]\)\s*[A-Z]', text):
            continue

        # Check for responsibilities/process content
        text_lower = text.lower()
        if not any(kw in text_lower for kw in [
            'responsibilities', 'client', 'provider',
            'process', 'procedure', 'certification',
            'screening', 'testing', 'sampling',
        ]):
            continue

        # Parse steps from this clause
        parsed = parse_process_steps_from_text(
            text,
            clause_id=clause.id,
            page_number=clause.page_number,
        )

        for step_data in parsed:
            # Skip duplicates
            name_key = step_data["step_name"].lower().strip()
            if name_key in seen_names:
                continue
            seen_names.add(name_key)

            step_counter += 1
            step = ContractProcessStep(
                contract_id=contract_id,
                source_clause_id=step_data["source_clause_id"],
                step_number=step_counter,
                step_name=step_data["step_name"],
                step_type=step_data["step_type"],
                description=step_data["description"],
                responsible_party=step_data["responsible_party"],
                duration_days=step_data["duration_days"],
                sla_days=step_data["sla_days"],
                dependencies=step_data["dependencies"],
                deliverables=step_data["deliverables"],
                status=StepStatus.PENDING,
                source_text=step_data["source_text"],
                section_reference=step_data["section_reference"],
            )
            all_steps.append(step)

    return all_steps


async def sync_process_steps_to_db(
    db: AsyncSession,
    contract_id: uuid.UUID,
    steps: list[ContractProcessStep],
) -> int:
    """Save extracted process steps to the database, replacing any existing ones."""
    # Delete existing steps for this contract
    await db.execute(
        delete(ContractProcessStep).where(ContractProcessStep.contract_id == contract_id)
    )

    # Add new steps
    for step in steps:
        db.add(step)

    await db.commit()

    return len(steps)


async def extract_and_save_process_steps(
    db: AsyncSession,
    contract_id: uuid.UUID,
) -> int:
    """Extract process steps from clauses and save to database."""
    steps = await extract_process_steps_from_clauses(db, contract_id)
    count = await sync_process_steps_to_db(db, contract_id, steps)
    return count
