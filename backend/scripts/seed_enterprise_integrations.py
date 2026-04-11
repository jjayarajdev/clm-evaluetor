#!/usr/bin/env python3
"""Seed enterprise integration mock data for all tenants.

Creates contract-aware mock configs for ServiceNow, Salesforce, Teams,
SendGrid with contextual SLA mappings, measurements, and API logs
derived from actual extracted contract data.

Idempotent — skips tenants that already have integration configs.
Use --reset to clear existing demo data and re-provision.

Run with:
    cd backend && uv run python -m scripts.seed_enterprise_integrations
    cd backend && uv run python -m scripts.seed_enterprise_integrations --reset
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.integration import IntegrationConfig, IntegrationLog, SLAMeasurement
from app.models.snow_sla_mapping import SnowSLAMapping
from app.models.tenant import Tenant
from app.services.tenant_provisioner import provision_integrations


async def reset_demo_data(session: AsyncSession, tenant_id, tenant_name: str):
    """Remove all demo integration data for a tenant so it can be re-provisioned."""
    # Find demo configs
    result = await session.execute(
        select(IntegrationConfig)
        .where(IntegrationConfig.tenant_id == tenant_id)
    )
    configs = result.scalars().all()

    if not configs:
        print(f"  No existing data to reset")
        return

    config_ids = [c.id for c in configs]

    # Delete in dependency order
    await session.execute(
        delete(IntegrationLog).where(IntegrationLog.integration_id.in_(config_ids))
    )
    await session.execute(
        delete(SnowSLAMapping).where(SnowSLAMapping.integration_config_id.in_(config_ids))
    )
    # Delete SLA measurements that reference these configs via source_reference
    str_ids = [str(cid) for cid in config_ids]
    await session.execute(
        delete(SLAMeasurement).where(SLAMeasurement.source_reference.in_(str_ids))
    )
    await session.execute(
        delete(IntegrationConfig).where(IntegrationConfig.id.in_(config_ids))
    )
    await session.flush()
    print(f"  Reset {len(configs)} configs and associated data")


async def main():
    parser = argparse.ArgumentParser(description="Seed enterprise integration mock data")
    parser.add_argument("--reset", action="store_true", help="Clear existing demo data before re-provisioning")
    args = parser.parse_args()

    print("=" * 60)
    if args.reset:
        print("RESETTING & RE-SEEDING ENTERPRISE INTEGRATIONS — All Tenants")
    else:
        print("SEEDING ENTERPRISE INTEGRATIONS — All Tenants")
    print("=" * 60)

    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get all tenants
        result = await session.execute(select(Tenant).where(Tenant.is_active == True))
        tenants = result.scalars().all()

        print(f"Found {len(tenants)} active tenants\n")

        seeded = 0
        skipped = 0

        for tenant in tenants:
            print(f"--- {tenant.name} ({tenant.id}) ---")

            if args.reset:
                await reset_demo_data(session, tenant.id, tenant.name)

            counts = await provision_integrations(
                db=session,
                tenant_id=tenant.id,
                tenant_name=tenant.name,
            )
            if counts.get("skipped"):
                print(f"  Skipped (already has data)")
                skipped += 1
            else:
                print(f"  Created: {counts['configs']} configs, "
                      f"{counts['mappings']} SLA mappings, "
                      f"{counts['measurements']} measurements, "
                      f"{counts['logs']} API logs")
                seeded += 1

        await session.commit()

    await engine.dispose()

    print(f"\n{'='*60}")
    print(f"Done! Seeded: {seeded}, Skipped: {skipped}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
