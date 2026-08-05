"""Backfill filename-based structural contract-type corrections.

New uploads get this correction in the extraction pipeline
(agents/metadata_extraction → services.contract_types.structural_contract_type_from_filename):
a subordinate document (schedule, exhibit, allonge) is never left mis-typed as a
master, which would poison family root selection and counterparty-master linking.
This aligns the back catalogue using the SAME function, so old and new rows agree.

Idempotent — safe to re-run. Pass --dry-run to preview without writing.

    uv run python -m scripts.backfill_structural_contract_types [--dry-run]
"""

import asyncio
import sys
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.contract import Contract
from app.services.contract_types import structural_contract_type_from_filename

# Own unpooled engine — the app engine's pool_pre_ping trips MissingGreenlet
# when driven from a bare asyncio.run() script.
_engine = create_async_engine(settings.database_url, poolclass=NullPool)
async_session_maker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def main(dry_run: bool) -> None:
    changed: Counter[str] = Counter()
    n = 0
    async with async_session_maker() as db:
        contracts = (await db.execute(select(Contract))).scalars().all()
        for c in contracts:
            corrected = structural_contract_type_from_filename(c.filename, c.contract_type)
            if corrected and corrected != c.contract_type:
                changed[f"{c.contract_type} -> {corrected}"] += 1
                n += 1
                if not dry_run:
                    c.contract_type = corrected
        if not dry_run:
            await db.commit()
    print(f"Contracts scanned: {len(contracts)}")
    print(f"Rows {'that WOULD change' if dry_run else 'changed'}: {n}\n")
    for mapping, count in changed.most_common():
        print(f"  {count:3d}  {mapping}")
    if dry_run:
        print("\n(dry run — no changes written)")
    await _engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(dry_run="--dry-run" in sys.argv))
