#!/usr/bin/env python3
"""Test SLA extraction on a sample contract."""

import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_sla_extraction():
    """Test SLA extraction on sample contract text."""
    from app.agents.sla_extraction import extract_slas, SLAExtractionResult
    from app.agents import register_all_agents
    from app.services.orchestrator import initialize_default_agents, get_orchestrator

    # Initialize agents
    print("Initializing agents...")
    initialize_default_agents()
    register_all_agents()

    orchestrator = get_orchestrator()
    print(f"Registered agents: {list(orchestrator.agents.keys())}")

    # Sample contract text with SLAs
    sample_text = """
    SERVICE LEVEL AGREEMENT

    1. AVAILABILITY SLA
    The Provider shall ensure that the Platform maintains an availability of at least
    99.9% measured on a monthly basis ("Uptime SLA"). Availability is calculated as:
    (Total Minutes - Downtime Minutes) / Total Minutes × 100

    Warning threshold: If availability falls below 99.5%, Provider shall notify Client.

    2. RESPONSE TIME SLA
    2.1 Priority 1 (Critical): Response within 15 minutes, Resolution within 4 hours
    2.2 Priority 2 (High): Response within 1 hour, Resolution within 8 hours
    2.3 Priority 3 (Medium): Response within 4 hours, Resolution within 24 hours
    2.4 Priority 4 (Low): Response within 8 hours, Resolution within 5 business days

    3. SERVICE CREDITS
    In the event of SLA breach, Client shall be entitled to service credits as follows:

    | Availability      | Service Credit    |
    |-------------------|-------------------|
    | 99.0% - 99.9%     | 10% monthly fee   |
    | 98.0% - 99.0%     | 25% monthly fee   |
    | Below 98.0%       | 50% monthly fee   |

    Maximum aggregate service credits shall not exceed 50% of monthly fees.

    4. MEASUREMENT AND REPORTING
    Provider shall measure SLA metrics continuously and provide monthly reports
    within 5 business days of each calendar month end.

    5. ERROR RATE
    The system shall maintain an error rate of less than 0.1% of all transactions
    processed. Error rate exceeding 0.5% shall be considered a critical breach.
    """

    print("\n" + "=" * 60)
    print("Testing SLA Extraction")
    print("=" * 60)
    print(f"Input text length: {len(sample_text)} characters")

    # Run extraction
    print("\nCalling SLA extraction agent...")
    result = await extract_slas(
        contract_text=sample_text,
        contract_id="test-contract-001",
        user_id="test-user",
    )

    if not result:
        print("ERROR: No result returned from extraction")
        return

    print(f"\n✓ Extraction completed!")
    print(f"  - SLAs found: {len(result.slas)}")
    print(f"  - Has SLA section: {result.has_sla_section}")
    print(f"  - Has penalty mechanism: {result.has_penalty_mechanism}")
    print(f"  - Overall confidence: {result.overall_confidence:.2f}")

    print("\n" + "-" * 60)
    print("EXTRACTED SLAs:")
    print("-" * 60)

    for i, sla in enumerate(result.slas, 1):
        print(f"\n[{i}] {sla.sla_name}")
        print(f"    Type: {sla.metric_type} ({sla.metric_unit})")
        print(f"    Target: {sla.target_operator} {sla.target_value}")
        if sla.warning_threshold:
            print(f"    Warning: {sla.warning_threshold}")
        print(f"    Severity: {sla.severity}")
        if sla.has_penalty:
            print(f"    Penalty: {sla.penalty_type} - {sla.penalty_value}")
            if sla.penalty_description:
                print(f"    Penalty Details: {sla.penalty_description[:100]}...")
        if sla.measurement_period:
            print(f"    Measurement: {sla.measurement_period}")
        print(f"    Confidence: {sla.confidence:.2f}")

    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)


async def test_on_real_contract():
    """Test SLA extraction on a real contract from the database."""
    from sqlalchemy import select, func
    from app.database import async_session_maker
    from app.models.contract import Contract
    from app.models.sla import ContractSLA
    from app.agents.sla_extraction import extract_slas, store_extracted_slas
    from app.agents import register_all_agents
    from app.services.orchestrator import initialize_default_agents

    # Initialize
    initialize_default_agents()
    register_all_agents()

    async with async_session_maker() as session:
        # Find a contract with extracted text
        result = await session.execute(
            select(Contract)
            .where(Contract.extracted_text.isnot(None))
            .limit(1)
        )
        contract = result.scalar_one_or_none()

        if not contract:
            print("No contracts with extracted text found in database")
            return

        print(f"Testing on contract: {contract.filename}")
        print(f"Contract ID: {contract.id}")
        print(f"Text length: {len(contract.extracted_text)} chars")

        # Check existing SLAs
        sla_count = await session.execute(
            select(func.count(ContractSLA.id))
            .where(ContractSLA.contract_id == contract.id)
        )
        existing = sla_count.scalar()
        print(f"Existing SLAs: {existing}")

        # Run extraction
        print("\nExtracting SLAs...")
        sla_result = await extract_slas(
            contract_text=contract.extracted_text,
            contract_id=str(contract.id),
            user_id="test-user",
        )

        if sla_result and sla_result.slas:
            print(f"Extracted {len(sla_result.slas)} SLAs")

            # Store them
            from sqlalchemy import delete
            await session.execute(
                delete(ContractSLA).where(ContractSLA.contract_id == contract.id)
            )
            stored = await store_extracted_slas(session, contract.id, sla_result)
            await session.commit()
            print(f"Stored {stored} SLAs in database")

            # Show results
            for sla in sla_result.slas:
                print(f"  - {sla.sla_name}: {sla.metric_type} {sla.target_operator} {sla.target_value}")
        else:
            print("No SLAs found in this contract")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test SLA extraction")
    parser.add_argument("--real", action="store_true", help="Test on real contract from DB")
    args = parser.parse_args()

    if args.real:
        asyncio.run(test_on_real_contract())
    else:
        asyncio.run(test_sla_extraction())
