"""Backfill existing contracts into the canonical contract-type vocabulary.

Historic rows stored the raw AI-extracted type (dozens of one-off values like
"roles_and_responsibilities_matrix"). New uploads now store the canonical code
(see agents/metadata_extraction + services/contract_types.canonical_contract_type);
this one-off aligns the back catalogue so filters, lists, and family linking are
consistent.

Idempotent — safe to re-run. Pass --dry-run to preview without writing.

    uv run python -m scripts.backfill_contract_types [--dry-run]
"""

import asyncio
import sys
from collections import Counter

from sqlalchemy import select

from app.database import async_session_maker
from app.models.contract import Contract
from app.services.contract_types import canonical_contract_type


async def main(dry_run: bool) -> None:
    changed: Counter[str] = Counter()
    before: Counter[str] = Counter()
    after: Counter[str] = Counter()
    n_changed = 0

    async with async_session_maker() as db:
        contracts = (await db.execute(select(Contract))).scalars().all()
        for c in contracts:
            raw = c.contract_type
            if not raw:
                continue
            before[raw] += 1
            canon = canonical_contract_type(raw)
            after[canon or raw] += 1
            if canon and canon != raw:
                changed[f"{raw} -> {canon}"] += 1
                n_changed += 1
                if not dry_run:
                    c.contract_type = canon
        if not dry_run:
            await db.commit()

    print(f"Contracts scanned: {sum(before.values())}")
    print(f"Distinct types: {len(before)} raw  ->  {len(after)} canonical")
    print(f"Rows {'that WOULD change' if dry_run else 'changed'}: {n_changed}\n")
    for mapping, n in changed.most_common():
        print(f"  {n:3d}  {mapping}")
    print("\nCanonical distribution:")
    for code, n in after.most_common():
        print(f"  {n:3d}  {code}")
    if dry_run:
        print("\n(dry run — no changes written)")


if __name__ == "__main__":
    asyncio.run(main(dry_run="--dry-run" in sys.argv))
