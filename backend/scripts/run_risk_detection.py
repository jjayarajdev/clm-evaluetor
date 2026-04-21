"""Run risk detection on contracts that have null risk_score.

Usage:
    cd backend && uv run python -m scripts.run_risk_detection [--limit N] [--contract-id UUID]

Registers the risk_detection agent, loads contract text from DB, runs
GPT-4o risk analysis, and saves results back to the contract.
"""

import asyncio
import argparse
import logging
import sys

from sqlalchemy import or_

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main(limit: int = 5, contract_id: str | None = None) -> None:
    from sqlalchemy import select
    from app.database import async_session_maker
    from app.models.contract import Contract, ContractStatus
    from app.agents.risk_detection import (
        assess_risk,
        update_contract_risk,
        register_risk_detection_agent,
    )

    # Register the agent so orchestrator can route to it
    register_risk_detection_agent()
    logger.info("Risk detection agent registered")

    async with async_session_maker() as db:
        # Build query
        query = select(Contract).where(
            Contract.status == ContractStatus.COMPLETED,
        )

        if contract_id:
            import uuid as _uuid
            query = query.where(Contract.id == _uuid.UUID(contract_id))
        else:
            query = query.where(or_(Contract.risk_score.is_(None), Contract.risk_score == 0))
            query = query.limit(limit)

        result = await db.execute(query)
        contracts = list(result.scalars().all())

        if not contracts:
            logger.info("No contracts found to process")
            return

        logger.info(f"Processing {len(contracts)} contract(s)")

        for contract in contracts:
            text = contract.extracted_text
            if not text:
                logger.warning(f"SKIP {contract.id} ({contract.filename}) — no extracted text")
                continue

            logger.info(f"Analyzing {contract.filename} ({len(text)} chars) ...")
            try:
                risk_result = await assess_risk(
                    contract_text=text,
                    contract_id=str(contract.id),
                    user_id="system",
                )
                await update_contract_risk(db, contract, risk_result)
                await db.commit()

                logger.info(
                    f"  → {contract.filename}: "
                    f"score={risk_result.overall_score}, "
                    f"level={risk_result.risk_level}, "
                    f"factors={len(risk_result.risk_factors)}"
                )

                # Print risk factors
                for f in risk_result.risk_factors:
                    logger.info(f"    [{f.category}] score={f.score} severity={f.severity} — {f.description[:80]}")

                if risk_result.top_recommendations:
                    logger.info("    Recommendations:")
                    for rec in risk_result.top_recommendations:
                        logger.info(f"      - {rec[:100]}")

            except Exception as e:
                logger.error(f"  FAILED {contract.filename}: {e}")
                await db.rollback()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run risk detection on contracts")
    parser.add_argument("--limit", type=int, default=5, help="Max contracts to process")
    parser.add_argument("--contract-id", type=str, help="Specific contract ID")
    args = parser.parse_args()

    asyncio.run(main(limit=args.limit, contract_id=args.contract_id))
