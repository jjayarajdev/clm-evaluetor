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
        '0309d333-5024-4c9b-be8b-59fd01a43d9e',  # MSA_CareerSource
        '1c285f5e-eebc-494c-81ce-33fc69792f88',  # SOW_SDLC_Template
        '62e68ff0-5382-43f6-8785-a6ba7b0cf4ef',  # SLA_PMI_Agreement
        'f30ac2d9-b769-4493-b758-1c9a1badc133',  # Vendor_Agreement_Pace
        'c2d61a18-d658-44ea-9c13-06fa0808febb',  # MSA_MercyCorps_Template
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
