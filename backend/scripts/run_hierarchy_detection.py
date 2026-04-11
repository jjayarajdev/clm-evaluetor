"""Run hierarchy detection for a tenant's completed contracts.

Runs the new pairwise hierarchy detection pipeline (v2) on all
completed contracts for a given tenant, or for a specific batch.

Usage:
    # All completed contracts for a tenant
    docker exec deploy-backend-1 python -m scripts.run_hierarchy_detection --tenant nova_admin

    # Specific tenant by ID
    docker exec deploy-backend-1 python -m scripts.run_hierarchy_detection --tenant-id 4daa0c29-050b-4f27-941b-d3d83f40029f

    # Clear old v2 suggestions first
    docker exec deploy-backend-1 python -m scripts.run_hierarchy_detection --tenant nova_admin --clear
"""

import argparse
import asyncio
import logging
import sys
import uuid

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Run hierarchy detection")
    parser.add_argument("--tenant", help="Admin username to look up tenant")
    parser.add_argument("--tenant-id", help="Tenant UUID directly")
    parser.add_argument("--clear", action="store_true", help="Clear old hierarchy_v2 suggestions first")
    parser.add_argument("--batch-id", help="Optional batch ID label")
    args = parser.parse_args()

    from app.database import async_session_maker
    from app.models.contract import Contract, ContractStatus
    from app.models.suggested_link import SuggestedContractLink
    from app.models.user import User
    from sqlalchemy import select, delete

    # Resolve tenant_id
    tenant_id = None
    if args.tenant_id:
        tenant_id = uuid.UUID(args.tenant_id)
    elif args.tenant:
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.username == args.tenant)
            )
            user = result.scalar_one_or_none()
            if not user:
                logger.error(f"User '{args.tenant}' not found")
                sys.exit(1)
            tenant_id = user.tenant_id
            logger.info(f"Resolved tenant: {tenant_id} (from user '{args.tenant}')")
    else:
        logger.error("Must provide --tenant or --tenant-id")
        sys.exit(1)

    # Optionally clear old hierarchy_v2 suggestions
    if args.clear:
        logger.info("=== Clearing old hierarchy_v2 suggestions ===")
        async with async_session_maker() as session:
            result = await session.execute(
                delete(SuggestedContractLink).where(
                    SuggestedContractLink.tenant_id == tenant_id,
                    SuggestedContractLink.matching_signals["detection_method"].astext == "hierarchy_v2",
                )
            )
            logger.info(f"Deleted {result.rowcount} old hierarchy_v2 suggestions")
            await session.commit()

    # Load completed contracts for tenant
    async with async_session_maker() as session:
        result = await session.execute(
            select(Contract).where(
                Contract.tenant_id == tenant_id,
                Contract.status == ContractStatus.COMPLETED,
            )
        )
        contracts = result.scalars().all()

    logger.info(f"Found {len(contracts)} completed contracts for tenant {tenant_id}")
    if len(contracts) < 2:
        logger.info("Need at least 2 contracts for hierarchy detection")
        return

    # List them
    for c in contracts:
        logger.info(f"  {c.filename} (type={c.contract_type}, counterparty={c.counterparty})")

    # Run hierarchy detection
    logger.info("=== Running hierarchy detection ===")
    from app.services.hierarchy_detection import detect_hierarchy

    contract_ids = [c.id for c in contracts]
    batch_id = args.batch_id or f"hierarchy_rerun_{tenant_id}"

    async with async_session_maker() as session:
        num_suggestions = await detect_hierarchy(
            db=session,
            contract_ids=contract_ids,
            tenant_id=tenant_id,
            batch_id=batch_id,
        )
        await session.commit()

    logger.info(f"=== DONE: Created {num_suggestions} hierarchy suggestions ===")

    # Show results summary
    async with async_session_maker() as session:
        result = await session.execute(
            select(SuggestedContractLink).where(
                SuggestedContractLink.tenant_id == tenant_id,
                SuggestedContractLink.matching_signals["detection_method"].astext == "hierarchy_v2",
            )
        )
        suggestions = result.scalars().all()

        logger.info(f"\n=== Results: {len(suggestions)} suggestions ===")
        for s in suggestions:
            # Load contract filenames
            src = await session.execute(
                select(Contract.filename).where(Contract.id == s.source_contract_id)
            )
            tgt = await session.execute(
                select(Contract.filename).where(Contract.id == s.target_contract_id)
            )
            src_name = src.scalar() or "?"
            tgt_name = tgt.scalar() or "?"

            signals = s.matching_signals or {}
            logger.info(
                f"  {src_name} → {tgt_name} "
                f"[{s.suggested_link_type}, {s.confidence_score:.0%}, "
                f"{signals.get('relationship_type', '?')}]"
            )


if __name__ == "__main__":
    asyncio.run(main())
