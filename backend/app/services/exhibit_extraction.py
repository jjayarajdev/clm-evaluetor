"""Service for extracting exhibits/schedules from contracts."""

import re
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.exhibit import ContractExhibit, ExhibitFeeItem, ExhibitType
from app.models.clause import Clause


def normalize_quotes(text: str) -> str:
    """Normalize curly/smart quotes to straight quotes."""
    text = text.replace('\u201c', '"').replace('\u201d', '"')
    text = text.replace('\u2018', "'").replace('\u2019', "'")
    return text


def determine_exhibit_type(identifier: str, title: str) -> ExhibitType:
    """Determine the type of exhibit from identifier and title."""
    combined = (identifier + " " + (title or "")).lower()

    if "schedule" in combined:
        return ExhibitType.SCHEDULE
    elif "appendix" in combined:
        return ExhibitType.APPENDIX
    elif "annexure" in combined:
        return ExhibitType.ANNEXURE
    elif "attachment" in combined:
        return ExhibitType.ATTACHMENT
    elif any(kw in combined for kw in ["pricing", "fee", "rate", "cost"]):
        return ExhibitType.PRICING
    elif any(kw in combined for kw in ["sow", "statement of work", "scope"]):
        return ExhibitType.SOW
    elif "exhibit" in combined:
        return ExhibitType.EXHIBIT
    else:
        return ExhibitType.OTHER


def extract_fee_items_from_text(text: str) -> list[dict[str, Any]]:
    """Extract fee items from exhibit text (pricing tables)."""
    text = normalize_quotes(text)
    fee_items = []

    # Pattern for table-like fee entries:
    # Service Name | Quantity | Unit Price | Total
    # or: Service Name ... $XXX
    patterns = [
        # Tabular format: Name | Qty | Price | Total
        r'([A-Za-z][^|$\n]{5,50})\s*\|?\s*(\d+)?\s*\|?\s*\$?\s*([\d,]+(?:\.\d{2})?)\s*\|?\s*\$?\s*([\d,]+(?:\.\d{2})?)?',
        # Simple format: Service ... $XXX
        r'([A-Za-z][^\n$]{5,80}?)\s+\$\s*([\d,]+(?:\.\d{2})?)',
        # Format with quantity: Name (X units) @ $Y = $Z
        r'([A-Za-z][^\n@]{5,50})\s*\(?\s*(\d+)\s*(?:units?)?\s*\)?\s*@\s*\$\s*([\d,]+(?:\.\d{2})?)',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if isinstance(match, tuple):
                name = match[0].strip()

                # Skip if looks like a header or non-fee text
                if any(skip in name.lower() for skip in ['total', 'subtotal', 'description', 'service', 'item']):
                    if len(name) < 15:  # Short generic words
                        continue

                item = {"item_name": name[:500]}

                # Try to extract numbers
                numbers = [m for m in match[1:] if m]
                if len(numbers) >= 1:
                    try:
                        # Last number is usually total
                        total = float(numbers[-1].replace(",", ""))
                        item["total_price"] = total
                        item["currency"] = "USD"

                        if len(numbers) >= 2:
                            # Second to last might be unit price or quantity
                            second = float(numbers[-2].replace(",", ""))
                            if second < 1000 and total > second:
                                item["quantity"] = int(second)
                            else:
                                item["unit_price"] = second

                        if len(numbers) >= 3:
                            item["quantity"] = int(float(numbers[0].replace(",", "")))

                        fee_items.append(item)
                    except (ValueError, IndexError):
                        pass

    # Deduplicate by name
    seen = set()
    unique_items = []
    for item in fee_items:
        name_key = item["item_name"].lower()[:50]
        if name_key not in seen:
            seen.add(name_key)
            unique_items.append(item)

    return unique_items[:20]  # Limit to 20 items


def parse_exhibits_from_text(text: str, clause_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
    """Parse exhibits/schedules from contract text.

    Args:
        text: Contract text to parse.
        clause_id: Optional source clause ID.

    Returns:
        List of exhibit data dictionaries.
    """
    text = normalize_quotes(text)
    exhibits = []

    # Pattern to find exhibit/schedule headers
    header_patterns = [
        r'(EXHIBIT|SCHEDULE|APPENDIX|ANNEXURE|ATTACHMENT)\s*([A-Z0-9]+)\s*[-–:]?\s*([^\n]*)',
        r'\b(Exhibit|Schedule|Appendix|Annexure|Attachment)\s+([A-Z0-9]+)\s*[-–:]?\s*([^\n]*)',
    ]

    for pattern in header_patterns:
        matches = list(re.finditer(pattern, text))

        for i, match in enumerate(matches):
            exhibit_type_str = match.group(1).upper()
            identifier = f"{exhibit_type_str} {match.group(2)}"
            title = match.group(3).strip() if match.group(3) else None

            # Get content until next exhibit or end
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()

            # Skip if too short
            if len(content) < 50:
                continue

            # Extract fee items if this looks like a pricing exhibit
            fee_items = []
            if any(kw in (title or "").lower() + content[:500].lower()
                   for kw in ["fee", "price", "cost", "rate", "$"]):
                fee_items = extract_fee_items_from_text(content)

            exhibits.append({
                "exhibit_identifier": identifier,
                "exhibit_type": determine_exhibit_type(identifier, title),
                "title": title[:500] if title else None,
                "description": content[:1000] if len(content) > 1000 else content,
                "source_text": content[:2000],
                "source_clause_id": clause_id,
                "fee_items": fee_items,
            })

    return exhibits


async def extract_exhibits_from_clauses(
    db: AsyncSession,
    contract_id: uuid.UUID,
) -> tuple[list[ContractExhibit], list[tuple[int, list[ExhibitFeeItem]]]]:
    """Extract exhibits from contract clauses.

    Returns:
        Tuple of (exhibits, [(exhibit_index, fee_items)])
    """
    # Get clauses that might contain exhibits
    result = await db.execute(
        select(Clause)
        .where(Clause.contract_id == contract_id)
        .order_by(Clause.page_number.asc().nulls_last())
    )

    clauses = result.scalars().all()
    all_exhibits = []
    all_fee_items = []
    seen_identifiers = set()

    for clause in clauses:
        text_lower = clause.text.lower()

        # Check if clause contains exhibit/schedule content
        if not any(kw in text_lower for kw in ['exhibit', 'schedule', 'appendix', 'annexure', 'attachment']):
            continue

        parsed = parse_exhibits_from_text(clause.text, clause.id)

        for exhibit_data in parsed:
            # Skip duplicates
            ident = exhibit_data["exhibit_identifier"].lower()
            if ident in seen_identifiers:
                continue
            seen_identifiers.add(ident)

            exhibit = ContractExhibit(
                contract_id=contract_id,
                source_clause_id=exhibit_data["source_clause_id"],
                exhibit_identifier=exhibit_data["exhibit_identifier"],
                exhibit_type=exhibit_data["exhibit_type"],
                title=exhibit_data["title"],
                description=exhibit_data["description"],
                source_text=exhibit_data["source_text"],
                page_number=clause.page_number,
            )
            exhibit_idx = len(all_exhibits)
            all_exhibits.append(exhibit)

            # Create fee items
            fee_items = []
            for i, fi_data in enumerate(exhibit_data["fee_items"]):
                fee_item = ExhibitFeeItem(
                    item_name=fi_data["item_name"],
                    item_description=fi_data.get("item_description"),
                    quantity=fi_data.get("quantity"),
                    unit_price=fi_data.get("unit_price"),
                    total_price=fi_data.get("total_price"),
                    currency=fi_data.get("currency", "USD"),
                    item_order=i,
                )
                fee_items.append(fee_item)

            if fee_items:
                all_fee_items.append((exhibit_idx, fee_items))

    return all_exhibits, all_fee_items


async def sync_exhibits_to_db(
    db: AsyncSession,
    contract_id: uuid.UUID,
    exhibits: list[ContractExhibit],
    fee_items_by_exhibit: list[tuple[int, list[ExhibitFeeItem]]],
) -> int:
    """Save extracted exhibits to database, replacing any existing ones."""
    # Delete existing exhibits for this contract (cascade deletes fee items)
    await db.execute(
        delete(ContractExhibit).where(ContractExhibit.contract_id == contract_id)
    )

    # Add exhibits
    for exhibit in exhibits:
        db.add(exhibit)

    await db.flush()

    # Refresh to get IDs
    for exhibit in exhibits:
        await db.refresh(exhibit)

    # Add fee items with exhibit IDs
    total_items = 0
    for exhibit_idx, fee_items in fee_items_by_exhibit:
        exhibit = exhibits[exhibit_idx]
        for item in fee_items:
            item.exhibit_id = exhibit.id
            db.add(item)
            total_items += 1

    await db.commit()

    return len(exhibits) + total_items


async def extract_and_save_exhibits(
    db: AsyncSession,
    contract_id: uuid.UUID,
) -> int:
    """Extract exhibits from clauses and save to database.

    Returns:
        Count of records created.
    """
    exhibits, fee_items_by_exhibit = await extract_exhibits_from_clauses(db, contract_id)

    if not exhibits:
        return 0

    count = await sync_exhibits_to_db(db, contract_id, exhibits, fee_items_by_exhibit)
    return count
