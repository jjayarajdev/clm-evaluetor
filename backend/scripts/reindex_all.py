"""Re-index all contracts: ChromaDB embeddings + KG extraction with Pass 2 orphan resolution.

Usage:
    cd backend && uv run python -m scripts.reindex_all
"""

import asyncio
import logging
import sys

from sqlalchemy import select, text as sql_text

from app.database import async_session_maker
from app.models.contract import Contract, ContractStatus
from app.services.indexer import IndexingService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Suppress noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)


async def get_contract_ids():
    """Get all contract IDs that have extracted text."""
    async with async_session_maker() as db:
        result = await db.execute(
            select(Contract.id, Contract.filename, Contract.tenant_id)
            .where(Contract.extracted_text.isnot(None))
            .where(Contract.extracted_text != "")
            .order_by(Contract.filename)
        )
        return [(str(row[0]), row[1], str(row[2])) for row in result.all()]


async def reindex_one(contract_id: str, filename: str, index: int, total: int):
    """Re-index a single contract in its own session."""
    async with async_session_maker() as db:
        try:
            result = await db.execute(
                select(Contract).where(Contract.id == contract_id)
            )
            contract = result.scalar_one_or_none()
            if not contract:
                logger.error(f"  Contract {contract_id} not found")
                return False

            indexer = IndexingService(db)
            ok, error = await indexer.reindex_contract(
                contract, user_id="system", user_role="admin"
            )

            if ok:
                await db.commit()
                logger.info(f"  [{index}/{total}] OK: {filename}")
                return True
            else:
                await db.rollback()
                logger.error(f"  [{index}/{total}] FAILED: {filename} - {error}")
                return False

        except Exception as e:
            await db.rollback()
            logger.error(f"  [{index}/{total}] ERROR: {filename} - {e}")
            return False


async def print_stats():
    """Print final KG and ChromaDB stats."""
    async with async_session_maker() as db:
        r = await db.execute(sql_text("""
            SELECT
                (SELECT COUNT(*) FROM kg_entities) as entities,
                (SELECT COUNT(*) FROM kg_relationships) as relationships,
                (SELECT COUNT(*) FROM kg_entities e
                 WHERE NOT EXISTS (
                     SELECT 1 FROM kg_relationships r
                     WHERE r.source_entity_id = e.id OR r.target_entity_id = e.id
                 )) as orphans
        """))
        row = r.fetchone()
        logger.info(
            f"KG totals: {row[0]} entities, {row[1]} relationships, "
            f"{row[2]} orphans"
        )

        # Per-tenant breakdown
        r = await db.execute(sql_text("""
            SELECT t.name,
                   COUNT(DISTINCT e.id) as entities,
                   COUNT(DISTINCT r.id) as relationships
            FROM tenants t
            LEFT JOIN kg_entities e ON e.tenant_id = t.id
            LEFT JOIN kg_relationships r ON r.tenant_id = t.id
            GROUP BY t.name ORDER BY t.name
        """))
        logger.info("\nPer-tenant KG breakdown:")
        for row in r.fetchall():
            logger.info(f"  {row[0]}: {row[1]} entities, {row[2]} relationships")

    # ChromaDB stats
    try:
        from app.services.vector_store import get_vector_store
        vs = get_vector_store()
        count = vs.collection.count()
        logger.info(f"\nChromaDB: {count} embeddings")
    except Exception as e:
        logger.warning(f"ChromaDB stats failed: {e}")


async def reindex_all():
    """Re-index all contracts that have extracted text."""
    contracts = await get_contract_ids()
    total = len(contracts)
    logger.info(f"Found {total} contracts with extracted text to re-index\n")

    success_count = 0
    fail_count = 0

    for i, (cid, filename, tid) in enumerate(contracts, 1):
        logger.info(f"[{i}/{total}] Re-indexing: {filename}")
        ok = await reindex_one(cid, filename, i, total)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    logger.info(
        f"\nDone. {success_count} succeeded, {fail_count} failed "
        f"out of {total} contracts.\n"
    )

    await print_stats()


if __name__ == "__main__":
    asyncio.run(reindex_all())
