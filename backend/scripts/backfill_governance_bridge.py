"""Backfill the governance bridge for contracts that missed it.

The bridge was silently broken (syntax error, see fix commit) between the
per-tenant AI factory refactor and 2026-08-04 — uploads in that window got no
vendor-org/relationship auto-creation and no contract.organization_id stamp.
This re-runs bridge_contract_to_governance for completed contracts that have
a counterparty but no organization_id.

Usage (inside the backend container or a dev checkout):
    python -m scripts.backfill_governance_bridge --tenant "Square-one" --tenant "Greenberg" [--dry-run]

--tenant matches tenant name or slug (case-insensitive substring). Commits per
contract so one failure never rolls back the rest. Flushes usage metering at
the end so the LLM calls are billed to the right tenants.
"""

import argparse
import asyncio
import uuid

from sqlalchemy import or_, select

from app.database import async_session_maker
from app.models.contract import Contract, ContractStatus
from app.models.tenant import Tenant


async def _resolve_tenants(db, patterns: list[str]) -> list[Tenant]:
    clauses = []
    for p in patterns:
        try:
            clauses.append(Tenant.id == uuid.UUID(p))
        except ValueError:
            clauses.append(Tenant.name.ilike(f"%{p}%"))
            clauses.append(Tenant.slug.ilike(f"%{p}%"))
    return (await db.execute(select(Tenant).where(or_(*clauses)))).scalars().all()


async def main(tenant_patterns: list[str], dry_run: bool) -> None:
    from app.core.llm import current_tenant_id
    from app.services import usage_metering
    from app.services.governance_bridge import GovernanceBridgeService

    async with async_session_maker() as db:
        tenants = await _resolve_tenants(db, tenant_patterns)
        if not tenants:
            print(f"No tenants match {tenant_patterns}")
            return
        print(f"Tenants: {[t.name for t in tenants]}")

        for tenant in tenants:
            contract_ids = (
                await db.execute(
                    select(Contract.id).where(
                        Contract.tenant_id == tenant.id,
                        Contract.status == ContractStatus.COMPLETED,
                        Contract.organization_id.is_(None),
                        Contract.counterparty.isnot(None),
                    )
                )
            ).scalars().all()
            print(f"\n{tenant.name}: {len(contract_ids)} contract(s) to bridge"
                  + (" [DRY RUN]" if dry_run else ""))
            if dry_run:
                continue

            # Attribute the bridge's LLM calls to the tenant in usage metering
            current_tenant_id.set(str(tenant.id))
            ok = failed = 0
            for cid in contract_ids:
                # Fresh session per contract: fault isolation, no partial rollbacks
                async with async_session_maker() as session:
                    try:
                        bridge = GovernanceBridgeService(session)
                        summary = await bridge.bridge_contract_to_governance(
                            contract_id=cid, tenant_id=tenant.id
                        )
                        await session.commit()
                        ok += 1
                        print(f"  ✓ {cid}: {summary}")
                    except Exception as e:  # noqa: BLE001 — keep going
                        failed += 1
                        print(f"  ✗ {cid}: {e}")
            print(f"{tenant.name}: {ok} bridged, {failed} failed")

    flushed = await usage_metering.flush()
    print(f"\nUsage metering: {flushed} events flushed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", action="append", required=True,
                        help="Tenant name/slug substring or UUID (repeatable)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.tenant, args.dry_run))
