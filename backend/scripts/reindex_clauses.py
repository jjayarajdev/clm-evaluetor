#!/usr/bin/env python3
"""Re-index all contracts to apply AI clause classification.

This script:
1. Finds all contracts in the database
2. Deletes existing clauses (preserves SLAs, obligations)
3. Re-runs indexing with the new AI classification mapping

Run with: python -m scripts.reindex_clauses
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, select
from app.database import async_session_maker
from app.models.contract import Contract
from app.models.clause import Clause
from app.services.indexer import IndexingService
from app.services.parser import get_parser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def reindex_contract(contract_id: str, file_path: str) -> tuple[bool, int]:
    """Re-index a single contract.

    Args:
        contract_id: Contract UUID
        file_path: Path to contract file

    Returns:
        Tuple of (success, clause_count)
    """
    async with async_session_maker() as db:
        try:
            # Get contract
            result = await db.execute(
                select(Contract).where(Contract.id == contract_id)
            )
            contract = result.scalar_one_or_none()

            if not contract:
                logger.error(f"Contract not found: {contract_id}")
                return False, 0

            # Delete existing clauses for this contract
            await db.execute(
                delete(Clause).where(Clause.contract_id == contract_id)
            )
            logger.info(f"Deleted existing clauses for {contract.filename}")

            # Re-run indexing
            indexer = IndexingService(db)
            success, error = await indexer.index_contract(
                contract=contract,
                user_id="system",
                user_role="admin",
            )

            if not success:
                logger.error(f"Indexing failed for {contract.filename}: {error}")
                await db.rollback()
                return False, 0

            # Count new clauses
            result = await db.execute(
                select(Clause).where(Clause.contract_id == contract_id)
            )
            clauses = result.scalars().all()

            # Log clause type distribution
            type_counts = {}
            for c in clauses:
                type_name = c.clause_type.value if c.clause_type else "unknown"
                type_counts[type_name] = type_counts.get(type_name, 0) + 1

            await db.commit()

            logger.info(f"Re-indexed {contract.filename}: {len(clauses)} clauses")
            logger.info(f"  Distribution: {type_counts}")

            return True, len(clauses)

        except Exception as e:
            logger.exception(f"Error re-indexing {contract_id}: {e}")
            await db.rollback()
            return False, 0


async def main():
    """Re-index all contracts."""
    logger.info("=" * 60)
    logger.info("Starting contract re-indexing for AI clause classification")
    logger.info("=" * 60)

    # Get all contracts
    async with async_session_maker() as db:
        result = await db.execute(
            select(Contract.id, Contract.filename, Contract.file_path)
            .order_by(Contract.filename)
        )
        contracts = result.fetchall()

    logger.info(f"Found {len(contracts)} contracts to re-index")

    success_count = 0
    fail_count = 0
    total_clauses = 0

    for contract_id, filename, file_path in contracts:
        logger.info(f"\nProcessing: {filename}")

        # Check if file exists
        full_path = Path("/app") / file_path
        if not full_path.exists():
            # Try without /app prefix
            full_path = Path(file_path)
            if not full_path.exists():
                logger.warning(f"  File not found: {file_path}")
                fail_count += 1
                continue

        success, clause_count = await reindex_contract(str(contract_id), file_path)

        if success:
            success_count += 1
            total_clauses += clause_count
        else:
            fail_count += 1

    logger.info("\n" + "=" * 60)
    logger.info("Re-indexing complete!")
    logger.info(f"  Success: {success_count}")
    logger.info(f"  Failed: {fail_count}")
    logger.info(f"  Total clauses created: {total_clauses}")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
