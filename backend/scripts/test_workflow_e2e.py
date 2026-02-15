#!/usr/bin/env python3
"""End-to-end test for the actionable contracts workflow system.

This script:
1. Generates synthetic SLA breach data
2. Runs event detection to create events
3. Processes workflows to execute actions
4. Shows the results

Run with: python scripts/test_workflow_e2e.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import async_session_maker
from app.generators.synthetic_data import SyntheticDataGenerator
from app.workflows import run_on_demand_scan, run_on_demand_processing
from app.models.event import Event, EventStatus
from app.models.approval import ApprovalRequest, ApprovalStatus
from sqlalchemy import select


async def run_e2e_test():
    """Run the end-to-end workflow test."""
    print("=" * 60)
    print("ACTIONABLE CONTRACTS - END-TO-END TEST")
    print("=" * 60)
    print()

    async with async_session_maker() as db:
        # Step 1: Generate test data
        print("STEP 1: Generating synthetic SLA breach data...")
        print("-" * 40)

        generator = SyntheticDataGenerator(db)

        try:
            scenario = await generator.create_test_scenario("sla_breach")
            print(f"  Created breach scenario:")
            print(f"    Contract: {scenario.get('contract_name', 'N/A')}")
            print(f"    SLA: {scenario.get('sla_name', 'N/A')}")
            print(f"    Target: {scenario.get('target_value', 'N/A')}")
            print(f"    Actual: {scenario.get('actual_value', 'N/A')}")
            print(f"    Deviation: {scenario.get('deviation', 'N/A')}%")
            print()
        except Exception as e:
            print(f"  Warning: Could not create scenario: {e}")
            print("  Continuing with existing data...")
            print()

        # Step 2: Run event detection
        print("STEP 2: Running event detection scan...")
        print("-" * 40)

        try:
            scan_results = await run_on_demand_scan(db)
            print(f"  Events detected:")
            print(f"    SLA Breaches: {scan_results.get('sla_breaches', 0)}")
            print(f"    SLA Warnings: {scan_results.get('sla_warnings', 0)}")
            print(f"    Renewals: {scan_results.get('renewals_approaching', 0)}")
            print(f"    Milestones Overdue: {scan_results.get('milestones_overdue', 0)}")
            print(f"    Obligations Due: {scan_results.get('obligations_due', 0)}")
            print(f"    TOTAL: {scan_results.get('total_events', 0)}")
            print()
        except Exception as e:
            print(f"  Error during scan: {e}")
            print()

        # Step 3: Show created events
        print("STEP 3: Listing pending events...")
        print("-" * 40)

        result = await db.execute(
            select(Event)
            .where(Event.status == EventStatus.pending)
            .order_by(Event.detected_at.desc())
            .limit(5)
        )
        events = result.scalars().all()

        if events:
            for event in events:
                print(f"  [{event.event_type.value}] {event.title}")
                print(f"    Severity: {event.severity.value}")
                print(f"    Status: {event.status.value}")
                print(f"    Workflow: {event.workflow_id or 'None'}")
                print()
        else:
            print("  No pending events found.")
            print()

        # Step 4: Process workflows
        print("STEP 4: Processing workflows...")
        print("-" * 40)

        try:
            process_results = await run_on_demand_processing(db)
            print(f"  Processing results:")
            print(f"    Pending events processed: {process_results.get('pending_processed', 0)}")
            print(f"    In-progress advanced: {process_results.get('in_progress_processed', 0)}")
            print(f"    Approvals checked: {process_results.get('approvals_processed', 0)}")
            print()
        except Exception as e:
            print(f"  Error during processing: {e}")
            print()

        # Step 5: Show approval requests
        print("STEP 5: Checking approval requests...")
        print("-" * 40)

        result = await db.execute(
            select(ApprovalRequest)
            .where(ApprovalRequest.status == ApprovalStatus.pending)
            .order_by(ApprovalRequest.requested_at.desc())
            .limit(5)
        )
        approvals = result.scalars().all()

        if approvals:
            for approval in approvals:
                print(f"  [{approval.status.value}] {approval.title}")
                print(f"    Requested: {approval.requested_at}")
                print(f"    Expires: {approval.expires_at}")
                print()
        else:
            print("  No pending approvals found.")
            print()

        # Step 6: Show final event status
        print("STEP 6: Final event status...")
        print("-" * 40)

        for status in [EventStatus.pending, EventStatus.processing, EventStatus.awaiting_approval, EventStatus.executing, EventStatus.completed, EventStatus.failed]:
            result = await db.execute(
                select(Event).where(Event.status == status)
            )
            count = len(result.scalars().all())
            if count > 0:
                print(f"  {status.value}: {count} events")

        print()
        print("=" * 60)
        print("END-TO-END TEST COMPLETE")
        print("=" * 60)
        print()
        print("Next steps:")
        print("  1. Use the API at /api/monitor/stats to view statistics")
        print("  2. Use /api/monitor/events to list all events")
        print("  3. Use /api/monitor/approvals to view pending approvals")
        print("  4. Use /api/monitor/approvals/{id}/decide to approve/reject")
        print()


if __name__ == "__main__":
    asyncio.run(run_e2e_test())
