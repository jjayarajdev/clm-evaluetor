"""Reconcile auto_family contract groups for every tenant.

Collapses the duplicate/orphaned auto_family groups that older sync runs left
behind (a family's root contract being deleted set its group's root to NULL and
a fresh duplicate was created; the cleanup pass could never reap the NULL-root
orphan). The reconciler is now merge-based and self-healing, so a full-tenant
run folds each family down to a single group and reaps the orphans.

Idempotent — safe to re-run. Pass --dry-run to preview counts without writing.

    uv run python -m scripts.resync_auto_family_groups [--dry-run]
"""

import asyncio
import sys

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.contract_group import ContractGroup
from app.models.tenant import Tenant
from app.services.group_sync import sync_auto_family_groups

# Own engine: the app engine's pool_pre_ping trips MissingGreenlet when driven
# from a bare asyncio.run() script, so use a fresh, unpooled connection here.
_engine = create_async_engine(settings.database_url, poolclass=NullPool)
async_session_maker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def _auto_group_count(db, tenant_id) -> int:
    return (
        await db.execute(
            select(func.count(ContractGroup.id)).where(
                ContractGroup.tenant_id == tenant_id,
                ContractGroup.group_type == "auto_family",
            )
        )
    ).scalar_one()


async def main(dry_run: bool) -> None:
    async with async_session_maker() as db:
        tenants = (await db.execute(select(Tenant))).scalars().all()
        total_before = total_after = 0
        for t in tenants:
            before = await _auto_group_count(db, t.id)
            touched = await sync_auto_family_groups(db, t.id)
            if dry_run:
                await db.rollback()
            else:
                await db.commit()
            after = await _auto_group_count(db, t.id)
            total_before += before
            total_after += after
            if before or after or touched:
                print(
                    f"  {t.name:<28} groups {before:3d} -> {after:3d}  "
                    f"(touched {touched})"
                )
        print(
            f"\nauto_family groups: {total_before} -> {total_after}"
            f"{'  (dry run — not written)' if dry_run else ''}"
        )
    await _engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(dry_run="--dry-run" in sys.argv))
