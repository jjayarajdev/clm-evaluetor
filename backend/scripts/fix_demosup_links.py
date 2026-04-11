"""Fix DemoSup tenant contract links.

Issues:
1. Schedule 01 Definitions misclassified as contract_type='msa'
2. MSA ClientAA.docx has no contract_type set
3. Suggested links point to Schedule 01 instead of the actual MSA
4. Links are all in 'pending' status instead of approved

This script:
- Sets MSA ClientAA.docx contract_type to 'msa'
- Clears Schedule 01's incorrect 'msa' classification
- Deletes incorrect suggested links pointing to Schedule 01
- Re-runs auto-link detection for all schedule contracts
- Auto-approves the corrected links
"""

import asyncio
import logging
import uuid

from sqlalchemy import select, update, delete

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEMOSUP_TENANT_ID = "a6e70351-6c84-4538-b632-8248fd83a36b"


async def main():
    from app.database import async_session_maker
    from app.models.contract import Contract, ContractType, ContractStatus
    from app.models.suggested_link import SuggestedContractLink
    from app.models.contract_link import ContractLink
    from app.services.auto_link_detector import auto_approve_batch_links

    tenant_uuid = uuid.UUID(DEMOSUP_TENANT_ID)

    async with async_session_maker() as db:
        # 1. Find the actual MSA (filename contains "MSA")
        result = await db.execute(
            select(Contract).where(
                Contract.tenant_id == tenant_uuid,
                Contract.filename.ilike("%MSA%"),
                Contract.status == ContractStatus.COMPLETED,
            )
        )
        msa_contracts = result.scalars().all()
        logger.info(f"Found {len(msa_contracts)} MSA contracts")
        for c in msa_contracts:
            logger.info(f"  {c.id} | type={c.contract_type} | {c.filename}")

        # 2. Find Schedule 01 (misclassified as MSA)
        result = await db.execute(
            select(Contract).where(
                Contract.tenant_id == tenant_uuid,
                Contract.filename.ilike("%Schedule 01%"),
            )
        )
        schedule_01 = result.scalar_one_or_none()

        if schedule_01 and schedule_01.contract_type and schedule_01.contract_type.value == "msa":
            logger.info(f"Fixing Schedule 01 ({schedule_01.id}): clearing incorrect MSA type")
            schedule_01.contract_type = None
            await db.flush()

        # 3. Set contract_type='msa' on actual MSA files that don't have it
        for c in msa_contracts:
            if not c.contract_type:
                logger.info(f"Setting MSA type on {c.filename} ({c.id})")
                c.contract_type = ContractType.MSA
                await db.flush()

        # 4. Delete all existing suggested links for this tenant (we'll recreate correct ones)
        result = await db.execute(
            select(SuggestedContractLink).where(
                SuggestedContractLink.tenant_id == tenant_uuid,
            )
        )
        old_suggestions = result.scalars().all()
        logger.info(f"Removing {len(old_suggestions)} old suggested links")
        for s in old_suggestions:
            await db.delete(s)
        await db.flush()

        # 5. Get all contracts in this tenant
        result = await db.execute(
            select(Contract).where(
                Contract.tenant_id == tenant_uuid,
                Contract.status == ContractStatus.COMPLETED,
            )
        )
        all_contracts = result.scalars().all()
        contract_ids = [str(c.id) for c in all_contracts]

        logger.info(f"Re-running auto-link detection for {len(all_contracts)} contracts")

        # 6. Re-run auto-link detection for each schedule contract
        from app.services.auto_link_detector import AutoLinkDetector
        detector = AutoLinkDetector(db, tenant_uuid)

        for contract in all_contracts:
            if contract.filename and ("Schedule" in contract.filename or "schedule" in contract.filename.lower()):
                suggestions = await detector.detect_links(
                    contract=contract,
                    batch_contract_ids=contract_ids,
                )
                for s in suggestions:
                    db.add(s)
                logger.info(f"  {contract.filename}: {len(suggestions)} suggestions")

        await db.flush()

        # 7. Auto-approve high-confidence links
        approved = await auto_approve_batch_links(db, contract_ids, confidence_threshold=0.30)
        logger.info(f"Auto-approved {len(approved)} links")

        await db.commit()
        logger.info("Done! Contract links fixed.")

        # 8. Summary
        result = await db.execute(
            select(ContractLink).where(
                ContractLink.parent_contract_id.in_([uuid.UUID(cid) for cid in contract_ids])
                | ContractLink.child_contract_id.in_([uuid.UUID(cid) for cid in contract_ids])
            )
        )
        links = result.scalars().all()
        logger.info(f"\nFinal state: {len(links)} active contract links")
        for link in links:
            logger.info(f"  {link.link_type}: parent={str(link.parent_contract_id)[:8]} → child={str(link.child_contract_id)[:8]}")


if __name__ == "__main__":
    asyncio.run(main())
