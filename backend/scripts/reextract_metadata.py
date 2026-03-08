"""Re-extract metadata for contracts with bad counterparty values."""

import asyncio
import sys
import uuid

async def reextract():
    # Initialize agents first (needed for orchestrator routing)
    from app.services.orchestrator import initialize_default_agents
    from app.agents import register_all_agents
    initialize_default_agents()
    register_all_agents()

    from app.database import async_session_maker
    from app.models.contract import Contract
    from app.agents.metadata_extraction import extract_metadata, update_contract_metadata

    bad_ids = [
        '128e224a-7958-4b97-88af-1a0bf397ac80',  # MSA_CareerSource → "the terms of any SOW"
        '980d89f2-083f-4d50-a9bd-29376d30016f',  # MSA_MercyCorps_Template → "the ones in the RFP"
        'c4204c15-4554-4001-b572-5c10d80b7ea6',  # Vendor_Agreement_Pace → "attached hereto as Exhibit A"
        'cb0dc891-0d35-4a67-ad78-3392502bd362',  # SLA_Northwestern_IT → "the"
        '7e7224e4-b6c8-466d-b668-48804430bb8b',  # MSA_WENGER_PLATTNER → "January 15"
        '0ebddf30-4749-4b83-a566-b0a539bd4f04',  # Amendment_001_MSA_TechServices → address as counterparty
        '563453de-72e9-4cbb-941d-dbd5294f4e34',  # SOW_InfraManagement_Acme → address as counterparty
        'c7fff088-9575-4ff6-9585-ff14f8de2b5a',  # Huurcontract → filename as counterparty
    ]

    async with async_session_maker() as db:
        for cid in bad_ids:
            contract = await db.get(Contract, uuid.UUID(cid))
            if not contract:
                print(f'Contract {cid} not found, skipping')
                continue

            old_cp = contract.counterparty
            print(f'\n--- {contract.filename} ---')
            print(f'  Old counterparty: {old_cp}')

            if not contract.extracted_text:
                print(f'  No extracted text, skipping')
                continue

            print(f'  Text length: {len(contract.extracted_text)} chars')
            print(f'  Running metadata extraction...')

            metadata = await extract_metadata(
                contract_text=contract.extracted_text,
                contract_id=str(contract.id),
                user_id='system',
                user_role='admin',
            )

            cp_val = metadata.counterparty.value if metadata.counterparty else None
            cp_conf = metadata.counterparty.confidence if metadata.counterparty else 0
            print(f'  Extracted counterparty: {cp_val}')
            print(f'  Confidence: {cp_conf}')
            print(f'  Parties: {metadata.parties}')

            # Update the contract
            await update_contract_metadata(db, contract, metadata, confidence_threshold=0.5)
            print(f'  New counterparty: {contract.counterparty}')

        await db.commit()
        print('\n=== Done, all changes committed ===')


if __name__ == '__main__':
    asyncio.run(reextract())
