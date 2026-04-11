#!/usr/bin/env python3
"""Reprocess all contracts: re-extract SLAs, obligations, renewal terms, and fix metadata.

Uses stored `extracted_text` to avoid re-parsing documents or wasting tokens on parsing.
Only re-runs the AI extraction stages that are missing data.

Run with: cd backend && uv run python -m scripts.reprocess_all_contracts
"""

import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, func, select
from app.database import async_session_maker
from app.models.contract import Contract, ContractStatus
from app.models.clause import Clause, ClauseType
from app.models.obligation import Obligation
from app.models.sla import ContractSLA
from app.services.orchestrator import initialize_default_agents
from app.agents import register_all_agents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def get_contract_stats(db, contract_id: UUID) -> dict:
    """Get counts of clauses, obligations, SLAs for a contract."""
    clause_count = (await db.execute(
        select(func.count()).where(Clause.contract_id == contract_id)
    )).scalar() or 0

    obligation_count = (await db.execute(
        select(func.count()).where(Obligation.contract_id == contract_id)
    )).scalar() or 0

    sla_count = (await db.execute(
        select(func.count()).where(ContractSLA.contract_id == contract_id)
    )).scalar() or 0

    return {
        "clauses": clause_count,
        "obligations": obligation_count,
        "slas": sla_count,
    }


async def reprocess_contract(contract_id: str, extracted_text: str, user_id: str = "system") -> dict:
    """Re-run AI extraction (clauses, obligations, SLAs, renewals) for a contract.

    Uses the already-stored extracted_text — no re-parsing needed.
    """
    from app.agents.clause_extraction import extract_clauses, reclassify_sla_chunks
    from app.agents.obligation_tracking import extract_obligations
    from app.agents.sla_extraction import extract_slas
    from app.agents.renewal_monitoring import analyze_renewal_terms, update_contract_renewal
    from app.agents import (
        store_extracted_clauses,
        store_extracted_obligations,
        store_extracted_slas,
    )

    result = {
        "clauses": 0,
        "obligations": 0,
        "slas": 0,
        "renewal": False,
        "errors": [],
    }

    uid = UUID(contract_id)

    # Extract clauses
    try:
        clause_result = await extract_clauses(
            contract_text=extracted_text,
            contract_id=contract_id,
            user_id=user_id,
        )
        result["clauses"] = len(clause_result.extracted_clauses) if clause_result else 0
    except Exception as e:
        result["errors"].append(f"clauses: {e}")
        clause_result = None

    # Extract obligations
    try:
        obligation_result = await extract_obligations(
            contract_text=extracted_text,
            contract_id=contract_id,
            user_id=user_id,
        )
        result["obligations"] = len(obligation_result.obligations) if obligation_result else 0
    except Exception as e:
        result["errors"].append(f"obligations: {e}")
        obligation_result = None

    # Extract SLAs
    try:
        sla_result = await extract_slas(
            contract_text=extracted_text,
            contract_id=contract_id,
            user_id=user_id,
        )
        result["slas"] = len(sla_result.slas) if sla_result else 0
    except Exception as e:
        result["errors"].append(f"slas: {e}")
        sla_result = None

    # Store results (clean up old data first)
    async with async_session_maker() as session:
        # Delete existing (except OTHER clause types — those come from chunk classification)
        await session.execute(
            delete(Clause)
            .where(Clause.contract_id == uid)
            .where(Clause.clause_type != ClauseType.OTHER)
        )
        await session.execute(
            delete(Obligation).where(Obligation.contract_id == uid)
        )
        await session.execute(
            delete(ContractSLA).where(ContractSLA.contract_id == uid)
        )

        if clause_result and clause_result.extracted_clauses:
            await store_extracted_clauses(db=session, contract_id=uid, result=clause_result)

        # Reclassify SLA chunks
        try:
            await reclassify_sla_chunks(db=session, contract_id=uid)
        except Exception:
            pass

        if obligation_result and obligation_result.obligations:
            await store_extracted_obligations(db=session, contract_id=uid, result=obligation_result)

        if sla_result and sla_result.slas:
            await store_extracted_slas(db=session, contract_id=uid, result=sla_result)

        await session.commit()

    # Extract renewal terms
    try:
        renewal_result = await analyze_renewal_terms(
            contract_text=extracted_text,
            contract_id=contract_id,
            user_id=user_id,
        )
        if renewal_result and renewal_result.terms:
            async with async_session_maker() as session:
                c = (await session.execute(
                    select(Contract).where(Contract.id == uid)
                )).scalar_one_or_none()
                if c:
                    await update_contract_renewal(session, c, renewal_result)
                    await session.commit()
                    result["renewal"] = True
    except Exception as e:
        result["errors"].append(f"renewal: {e}")

    return result


async def fix_metadata(contract, db) -> list[str]:
    """Fix bad metadata on a contract. Returns list of fixes applied."""
    fixes = []

    # Fix bad counterparty values (filename fragments)
    bad_counterparty_patterns = [
        "Service Levels",
        "Transition",
        "Pricing",
        "Schedule",
        "Exhibit",
        "Appendix",
        "Amendment",
    ]

    if contract.counterparty:
        is_bad = any(
            pat.lower() in contract.counterparty.lower()
            for pat in bad_counterparty_patterns
        )
        if is_bad:
            old_val = contract.counterparty
            # Try to get counterparty from AI-extracted references
            new_counterparty = None
            refs = (contract.schema_data or {}).get("_contract_references", {})
            parent_refs = refs.get("parent_references", [])
            if parent_refs:
                parties = parent_refs[0].get("party_names", [])
                if parties:
                    new_counterparty = parties[0]

            if new_counterparty:
                contract.counterparty = new_counterparty
                fixes.append(f"counterparty: '{old_val}' -> '{new_counterparty}'")
            else:
                # Clear bad value — better to show empty than wrong data
                contract.counterparty = None
                fixes.append(f"counterparty: cleared '{old_val}' (no AI data)")

    # Fix empty counterparty — try AI refs
    if not contract.counterparty:
        refs = (contract.schema_data or {}).get("_contract_references", {})
        parent_refs = refs.get("parent_references", [])
        if parent_refs:
            parties = parent_refs[0].get("party_names", [])
            if parties:
                contract.counterparty = parties[0]
                fixes.append(f"counterparty: set from AI refs -> '{parties[0]}'")

    if fixes:
        await db.flush()

    return fixes


async def main():
    logger.info("=" * 70)
    logger.info("REPROCESSING ALL CONTRACTS — Super Admin View")
    logger.info("=" * 70)

    # Initialize AI agents
    logger.info("Initializing AI agents...")
    initialize_default_agents()
    register_all_agents()
    logger.info("Agents ready")

    # Get all contracts with their stats
    async with async_session_maker() as db:
        result = await db.execute(
            select(Contract).order_by(Contract.tenant_id, Contract.filename)
        )
        contracts = result.scalars().all()

    logger.info(f"Found {len(contracts)} total contracts across all tenants")

    # Phase 1: Audit current state
    logger.info("\n" + "=" * 70)
    logger.info("PHASE 1: AUDIT CURRENT STATE")
    logger.info("=" * 70)

    needs_reprocess = []
    needs_metadata_fix = []
    needs_text = []

    for contract in contracts:
        async with async_session_maker() as db:
            c = (await db.execute(
                select(Contract).where(Contract.id == contract.id)
            )).scalar_one_or_none()
            if not c:
                continue

            stats = await get_contract_stats(db, c.id)

            status_parts = []
            if stats["slas"] == 0:
                status_parts.append("NO SLAs")
            if stats["obligations"] == 0:
                status_parts.append("NO obligations")
            if stats["clauses"] == 0:
                status_parts.append("NO clauses")

            needs_work = stats["slas"] == 0 or stats["obligations"] == 0

            if not c.extracted_text:
                needs_text.append(c.filename)

            if needs_work and c.extracted_text:
                needs_reprocess.append(str(c.id))
            elif needs_work and not c.extracted_text:
                status_parts.append("NO extracted_text")

            # Check for bad metadata
            bad_patterns = ["Service Levels", "Transition", "Pricing", "Schedule"]
            if c.counterparty and any(p.lower() in c.counterparty.lower() for p in bad_patterns):
                needs_metadata_fix.append(str(c.id))

            status_str = ", ".join(status_parts) if status_parts else "OK"
            logger.info(
                f"  [{c.tenant_id}] {c.filename:50s} | "
                f"clauses={stats['clauses']:2d} oblig={stats['obligations']:2d} "
                f"slas={stats['slas']:2d} | type={c.contract_type or 'N/A':15s} | "
                f"counterparty={c.counterparty or 'N/A':30s} | {status_str}"
            )

    logger.info(f"\nContracts needing reprocessing: {len(needs_reprocess)}")
    logger.info(f"Contracts needing metadata fix: {len(needs_metadata_fix)}")
    logger.info(f"Contracts missing extracted_text: {len(needs_text)}")

    if needs_text:
        logger.warning(f"Contracts without extracted_text (will skip): {needs_text}")

    # Phase 2: Fix metadata
    logger.info("\n" + "=" * 70)
    logger.info("PHASE 2: FIX BAD METADATA")
    logger.info("=" * 70)

    metadata_fixed = 0
    async with async_session_maker() as db:
        for contract in contracts:
            c = (await db.execute(
                select(Contract).where(Contract.id == contract.id)
            )).scalar_one_or_none()
            if not c:
                continue

            fixes = await fix_metadata(c, db)
            if fixes:
                metadata_fixed += 1
                for fix in fixes:
                    logger.info(f"  [{c.filename}] {fix}")

        await db.commit()

    logger.info(f"Fixed metadata on {metadata_fixed} contracts")

    # Phase 3: Reprocess contracts missing SLAs/obligations
    logger.info("\n" + "=" * 70)
    logger.info("PHASE 3: RE-EXTRACT SLAs, OBLIGATIONS, RENEWAL TERMS")
    logger.info("=" * 70)

    if not needs_reprocess:
        logger.info("No contracts need reprocessing!")
    else:
        success_count = 0
        fail_count = 0
        total_slas = 0
        total_obligations = 0

        for i, contract_id in enumerate(needs_reprocess):
            async with async_session_maker() as db:
                c = (await db.execute(
                    select(Contract).where(Contract.id == UUID(contract_id))
                )).scalar_one_or_none()
                if not c or not c.extracted_text:
                    continue

                filename = c.filename
                text = c.extracted_text

            logger.info(f"\n[{i+1}/{len(needs_reprocess)}] Processing: {filename}")
            logger.info(f"  Text length: {len(text)} chars")

            try:
                result = await reprocess_contract(contract_id, text)

                logger.info(
                    f"  Extracted: {result['clauses']} clauses, "
                    f"{result['obligations']} obligations, "
                    f"{result['slas']} SLAs, "
                    f"renewal={'yes' if result['renewal'] else 'no'}"
                )
                if result["errors"]:
                    logger.warning(f"  Errors: {result['errors']}")

                success_count += 1
                total_slas += result["slas"]
                total_obligations += result["obligations"]

            except Exception as e:
                logger.exception(f"  FAILED: {e}")
                fail_count += 1

        logger.info(f"\nReprocessing complete:")
        logger.info(f"  Success: {success_count}")
        logger.info(f"  Failed: {fail_count}")
        logger.info(f"  Total new SLAs: {total_slas}")
        logger.info(f"  Total new obligations: {total_obligations}")

    # Phase 4: Final audit
    logger.info("\n" + "=" * 70)
    logger.info("PHASE 4: FINAL AUDIT")
    logger.info("=" * 70)

    async with async_session_maker() as db:
        for contract in contracts:
            c = (await db.execute(
                select(Contract).where(Contract.id == contract.id)
            )).scalar_one_or_none()
            if not c:
                continue

            stats = await get_contract_stats(db, c.id)
            logger.info(
                f"  {c.filename:50s} | "
                f"clauses={stats['clauses']:2d} oblig={stats['obligations']:2d} "
                f"slas={stats['slas']:2d} | type={c.contract_type or 'N/A':15s} | "
                f"counterparty={c.counterparty or 'N/A':30s}"
            )

    logger.info("\n" + "=" * 70)
    logger.info("ALL DONE")
    logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
