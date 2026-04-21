"""Import CUAD dataset into the global golden set.

Downloads the CUAD (Contract Understanding Atticus Dataset) from GitHub,
creates Contract records under a dedicated tenant, and populates the global
golden set with lawyer-verified clause annotations.

This gives all tenants optimized extraction from day one via DSPy compilation.

Usage:
    uv run python -m scripts.import_cuad                # Import all 510 contracts
    uv run python -m scripts.import_cuad --limit 50     # Import first 50
    uv run python -m scripts.import_cuad --dry-run      # Preview without DB changes
    uv run python -m scripts.import_cuad --compile      # Import + trigger DSPy compilation
"""

import argparse
import asyncio
import json
import io
import logging
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# CUAD dataset URL (SQuAD-format JSON inside data.zip)
CUAD_ZIP_URL = "https://github.com/TheAtticusProject/cuad/raw/main/data.zip"
CUAD_CACHE_DIR = Path("data/cuad")
CUAD_JSON_PATH = CUAD_CACHE_DIR / "CUADv1.json"

# Dedicated tenant name for CUAD benchmark contracts
CUAD_TENANT_NAME = "CUAD Benchmark"

# ═══════════════════════════════════════════════════════════════════
# CUAD → Evaluetor Clause Type Mapping
# ═══════════════════════════════════════════════════════════════════

# Maps CUAD's 41 categories to our clause types.
# Categories 1-5 are metadata (dates, parties) → handled separately.
# None = skip (no good mapping).
CUAD_CLAUSE_MAP: dict[str, str | None] = {
    # Metadata fields (mapped to metadata extractor, not clauses)
    "Document Name": None,
    "Parties": None,
    "Agreement Date": None,
    "Effective Date": None,
    "Expiration Date": None,

    # Renewal / Termination
    "Renewal Term": "AUTO_RENEWAL",
    "Notice Period To Terminate Renewal": "AUTO_RENEWAL",
    "Termination For Convenience": "TERMINATION",
    "Post-Termination Services": "TERMINATION",

    # Governance / Jurisdiction
    "Governing Law": "GOVERNING_LAW",

    # Restrictive covenants
    "Non-Compete": "NON_COMPETE",
    "Exclusivity": "NON_COMPETE",
    "Competitive Restriction Exception": "NON_COMPETE",
    "No-Solicit Of Customers": "NON_SOLICITATION",
    "No-Solicit Of Employees": "NON_SOLICITATION",
    "Non-Disparagement": None,  # No match

    # Corporate / Assignment
    "Change Of Control": "ASSIGNMENT",
    "Anti-Assignment": "ASSIGNMENT",
    "Rofr/Rofo/Rofn": None,  # Right of First Refusal — niche

    # Financial
    "Revenue/Profit Sharing": "PAYMENT_TERMS",
    "Price Restrictions": "PRICING",
    "Minimum Commitment": "PAYMENT_TERMS",
    "Volume Restriction": None,  # Too niche

    # IP / Licensing
    "Ip Ownership Assignment": "INTELLECTUAL_PROPERTY",
    "Joint Ip Ownership": "INTELLECTUAL_PROPERTY",
    "License Grant": "INTELLECTUAL_PROPERTY",
    "Non-Transferable License": "INTELLECTUAL_PROPERTY",
    "Affiliate License-Licensor": "INTELLECTUAL_PROPERTY",
    "Affiliate License-Licensee": "INTELLECTUAL_PROPERTY",
    "Unlimited/All-You-Can-Eat-License": "INTELLECTUAL_PROPERTY",
    "Irrevocable Or Perpetual License": "INTELLECTUAL_PROPERTY",
    "Source Code Escrow": "INTELLECTUAL_PROPERTY",

    # Liability / Risk
    "Uncapped Liability": "LIMITATION_OF_LIABILITY",
    "Cap On Liability": "LIMITATION_OF_LIABILITY",
    "Liquidated Damages": "LIMITATION_OF_LIABILITY",
    "Insurance": "RISK_MITIGATION",
    "Audit Rights": "GOVERNANCE",

    # Warranty / Dispute
    "Warranty Duration": "WARRANTY",
    "Covenant Not To Sue": "DISPUTE_RESOLUTION",
    "Third Party Beneficiary": None,  # No match
    "Most Favored Nation": "PRICING",
}

# Metadata field mapping: CUAD category → our metadata field name
CUAD_METADATA_MAP: dict[str, str] = {
    "Agreement Date": "effective_date",
    "Effective Date": "effective_date",
    "Expiration Date": "expiration_date",
    "Parties": "parties",
}


# ═══════════════════════════════════════════════════════════════════
# Download & Parse
# ═══════════════════════════════════════════════════════════════════

async def download_cuad() -> dict:
    """Download and cache the CUAD SQuAD-format JSON."""
    if CUAD_JSON_PATH.exists():
        logger.info(f"Using cached CUAD data: {CUAD_JSON_PATH}")
        with open(CUAD_JSON_PATH) as f:
            return json.load(f)

    CUAD_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Downloading CUAD dataset from GitHub...")

    async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
        resp = await client.get(CUAD_ZIP_URL)
        resp.raise_for_status()

    logger.info(f"Downloaded {len(resp.content) / 1024 / 1024:.1f} MB, extracting...")

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        # Find the JSON file in the zip
        json_names = [n for n in zf.namelist() if n.endswith(".json")]
        if not json_names:
            raise RuntimeError("No JSON file found in CUAD zip")

        json_name = json_names[0]
        with zf.open(json_name) as jf:
            data = json.load(jf)

        # Cache to disk
        with open(CUAD_JSON_PATH, "w") as f:
            json.dump(data, f)

    logger.info(f"Cached CUAD data to {CUAD_JSON_PATH}")
    return data


def parse_cuad_contract(entry: dict) -> dict:
    """Parse a single CUAD contract entry into structured data.

    Args:
        entry: A single item from CUAD's data[] array.

    Returns:
        Dict with title, text, clause_annotations, metadata_annotations.
    """
    title = entry.get("title", "unknown")
    paragraphs = entry.get("paragraphs", [])

    # CUAD has one paragraph per contract with all QAs
    if not paragraphs:
        return {"title": title, "text": "", "clauses": [], "metadata": []}

    context = paragraphs[0].get("context", "")
    qas = paragraphs[0].get("qas", [])

    clauses = []
    metadata = []

    for qa in qas:
        question = qa.get("question", "")
        answers = qa.get("answers", [])
        is_impossible = qa.get("is_impossible", True)

        if is_impossible or not answers:
            continue

        # Extract category name from question
        # Format: "Highlight the parts (if any) of this contract related to 'Category Name'."
        category = _extract_category(question)
        if not category:
            continue

        # Get all answer spans
        spans = [
            {"text": a["text"], "start": a.get("answer_start", 0)}
            for a in answers
            if a.get("text", "").strip()
        ]

        if not spans:
            continue

        # Check if this is a metadata field or clause
        if category in CUAD_METADATA_MAP:
            metadata.append({
                "field": CUAD_METADATA_MAP[category],
                "category": category,
                "spans": spans,
            })
        elif category in CUAD_CLAUSE_MAP and CUAD_CLAUSE_MAP[category]:
            clauses.append({
                "cuad_category": category,
                "clause_type": CUAD_CLAUSE_MAP[category],
                "spans": spans,
            })

    return {
        "title": title,
        "text": context,
        "clauses": clauses,
        "metadata": metadata,
    }


def _extract_category(question: str) -> str | None:
    """Extract category name from CUAD question text."""
    # Pattern: "Highlight the parts ... related to 'Category Name'."
    # or "Highlight the parts ... related to \"Category Name\"."
    import re
    match = re.search(r"related to ['\"](.+?)['\"]", question, re.IGNORECASE)
    if match:
        return match.group(1)

    # Fallback: try quotes anywhere
    match = re.search(r"['\"]([^'\"]+)['\"]", question)
    if match:
        return match.group(1)

    return None


# ═══════════════════════════════════════════════════════════════════
# Database Import
# ═══════════════════════════════════════════════════════════════════

async def ensure_cuad_tenant(db) -> tuple:
    """Create or find the CUAD benchmark tenant and admin user.

    Returns:
        (tenant_id, user_id) tuple.
    """
    from sqlalchemy import select
    from app.models.tenant import Tenant
    from app.models.user import User

    # Find super admin by username (reliable across environments)
    result = await db.execute(
        select(User).where(User.username == "superadmin")
    )
    superadmin = result.scalar_one_or_none()
    if not superadmin:
        # Fallback: any admin user
        result = await db.execute(
            select(User).where(User.role == "admin").limit(1)
        )
        superadmin = result.scalar_one_or_none()
    if not superadmin:
        raise RuntimeError("No admin user found — run seed_data first")

    # Find or create CUAD tenant
    result = await db.execute(
        select(Tenant).where(Tenant.name == CUAD_TENANT_NAME)
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        tenant = Tenant(
            id=uuid4(),
            name=CUAD_TENANT_NAME,
            slug="cuad-benchmark",
            is_active=True,
        )
        db.add(tenant)
        await db.flush()
        logger.info(f"Created tenant: {CUAD_TENANT_NAME} ({tenant.id})")

    # Create a system user under the CUAD tenant for the uploaded_by FK
    result = await db.execute(
        select(User).where(
            User.tenant_id == tenant.id,
            User.username == "cuad_system",
        )
    )
    cuad_user = result.scalar_one_or_none()
    if not cuad_user:
        from app.core.security import hash_password
        cuad_user = User(
            id=uuid4(),
            tenant_id=tenant.id,
            username="cuad_system",
            email="cuad@benchmark.local",
            password_hash=hash_password("cuad_system_nologin"),
            full_name="CUAD Import System",
            role="admin",
            is_active=True,
        )
        db.add(cuad_user)
        await db.flush()
        logger.info(f"Created CUAD system user: {cuad_user.id}")

    return tenant.id, cuad_user.id


async def import_contract(
    db, tenant_id: UUID, user_id: UUID, parsed: dict
) -> UUID | None:
    """Import a single CUAD contract into the database.

    Returns:
        Contract ID if created, None if skipped.
    """
    from sqlalchemy import select
    from app.models.contract import Contract, ContractStatus

    title = parsed["title"]
    text = parsed["text"]

    if not text or len(text) < 100:
        return None

    # Check for duplicate
    result = await db.execute(
        select(Contract.id).where(
            Contract.tenant_id == tenant_id,
            Contract.filename == f"cuad_{title}.txt",
        )
    )
    if result.scalar_one_or_none():
        logger.debug(f"  Skipping duplicate: {title}")
        return None

    contract = Contract(
        id=uuid4(),
        tenant_id=tenant_id,
        filename=f"cuad_{title}.txt",
        file_path=f"cuad_dataset/{title}.txt",
        file_size=len(text.encode()),
        mime_type="text/plain",
        extracted_text=text,
        status=ContractStatus.COMPLETED,
        uploaded_by=user_id,
    )
    db.add(contract)
    await db.flush()
    return contract.id


async def create_golden_set_entry(
    db, contract_id: UUID, user_id: UUID, parsed: dict
) -> int:
    """Create golden set entry and verifications for a CUAD contract.

    Returns:
        Number of verification records created.
    """
    from app.models.extraction_quality import (
        GoldenSetContract,
        ExtractionVerification,
    )

    gs = GoldenSetContract(
        id=uuid4(),
        tenant_id=None,  # Global
        contract_id=contract_id,
        added_by=user_id,
        is_global=True,
        is_baseline=True,
        notes="CUAD dataset — lawyer-verified clause annotations (NeurIPS 2021)",
    )
    db.add(gs)
    await db.flush()

    count = 0

    # Add clause verifications
    for i, clause in enumerate(parsed["clauses"]):
        # Use the longest span as the representative text
        best_span = max(clause["spans"], key=lambda s: len(s["text"]))
        text = best_span["text"][:1000]  # Truncate very long spans

        ev = ExtractionVerification(
            id=uuid4(),
            golden_set_id=gs.id,
            entity_type="clause",
            entity_id=f"cuad_{clause['cuad_category'].lower().replace(' ', '_')}_{i}",
            status="correct",
            corrected_value={
                "clause_type": clause["clause_type"],
                "text": text,
                "source": "CUAD",
                "cuad_category": clause["cuad_category"],
            },
            verified_by=user_id,
            verified_at=datetime.utcnow(),
        )
        db.add(ev)
        count += 1

    # Add metadata verifications (deduplicate by field name)
    seen_fields: set[str] = set()
    for meta in parsed["metadata"]:
        field = meta["field"]
        if field in seen_fields:
            continue
        seen_fields.add(field)

        # Use first span value
        value = meta["spans"][0]["text"] if meta["spans"] else ""
        if not value:
            continue

        ev = ExtractionVerification(
            id=uuid4(),
            golden_set_id=gs.id,
            entity_type="metadata_field",
            entity_id=field,
            status="correct",
            corrected_value={
                "value": value,
                "confidence": 0.95,
                "source": "CUAD",
            },
            verified_by=user_id,
            verified_at=datetime.utcnow(),
        )
        db.add(ev)
        count += 1

    return count


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(description="Import CUAD dataset into golden set")
    parser.add_argument("--limit", type=int, default=None, help="Max contracts to import")
    parser.add_argument("--dry-run", action="store_true", help="Preview without DB changes")
    parser.add_argument("--compile", action="store_true", help="Trigger DSPy compilation after import")
    args = parser.parse_args()

    # Download CUAD
    cuad_data = await download_cuad()
    entries = cuad_data.get("data", [])
    logger.info(f"CUAD dataset: {len(entries)} contracts")

    if args.limit:
        entries = entries[:args.limit]
        logger.info(f"Limited to {len(entries)} contracts")

    # Parse all contracts
    parsed_contracts = []
    total_clauses = 0
    total_metadata = 0
    clause_type_counts: dict[str, int] = {}
    skipped_categories: dict[str, int] = {}

    for entry in entries:
        parsed = parse_cuad_contract(entry)
        if not parsed["text"]:
            continue

        parsed_contracts.append(parsed)
        total_clauses += len(parsed["clauses"])
        total_metadata += len(parsed["metadata"])

        for c in parsed["clauses"]:
            clause_type_counts[c["clause_type"]] = clause_type_counts.get(c["clause_type"], 0) + 1

    # Count skipped
    for entry in entries:
        for para in entry.get("paragraphs", []):
            for qa in para.get("qas", []):
                if qa.get("is_impossible", True) or not qa.get("answers"):
                    continue
                cat = _extract_category(qa.get("question", ""))
                if cat and cat in CUAD_CLAUSE_MAP and CUAD_CLAUSE_MAP[cat] is None:
                    skipped_categories[cat] = skipped_categories.get(cat, 0) + 1

    logger.info(f"\n{'='*60}")
    logger.info(f"CUAD Import Summary")
    logger.info(f"{'='*60}")
    logger.info(f"Contracts with text:    {len(parsed_contracts)}")
    logger.info(f"Total clause labels:    {total_clauses}")
    logger.info(f"Total metadata labels:  {total_metadata}")
    logger.info(f"\nClause type distribution:")
    for ct, count in sorted(clause_type_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {ct:30s}  {count:4d}")
    if skipped_categories:
        logger.info(f"\nSkipped CUAD categories (no mapping):")
        for cat, count in sorted(skipped_categories.items(), key=lambda x: -x[1]):
            logger.info(f"  {cat:30s}  {count:4d}")

    if args.dry_run:
        logger.info(f"\n[DRY RUN] No database changes made.")
        return

    # Import to database
    logger.info(f"\nImporting to database...")

    from app.database import async_session_maker

    async with async_session_maker() as db:
        tenant_id, user_id = await ensure_cuad_tenant(db)
        logger.info(f"Using tenant: {tenant_id}, user: {user_id}")

        imported = 0
        verifications = 0

        for i, parsed in enumerate(parsed_contracts):
            contract_id = await import_contract(db, tenant_id, user_id, parsed)
            if not contract_id:
                continue

            ver_count = await create_golden_set_entry(
                db, contract_id, user_id, parsed
            )
            imported += 1
            verifications += ver_count

            if (i + 1) % 50 == 0:
                logger.info(f"  Progress: {i+1}/{len(parsed_contracts)} contracts...")

        await db.commit()

    logger.info(f"\n{'='*60}")
    logger.info(f"Import Complete")
    logger.info(f"{'='*60}")
    logger.info(f"Contracts imported:     {imported}")
    logger.info(f"Verifications created:  {verifications}")
    logger.info(f"Golden set entries:     {imported} (global)")

    # Trigger DSPy compilation
    if args.compile:
        logger.info(f"\nTriggering DSPy compilation...")
        async with async_session_maker() as db:
            from app.services.dspy_compiler import compile_for_tenant
            results = await compile_for_tenant(db, None)  # Global compilation
            for agent_type, result in results.items():
                logger.info(f"  {agent_type}: {result['status']}")


if __name__ == "__main__":
    asyncio.run(main())
