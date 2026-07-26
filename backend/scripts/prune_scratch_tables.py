"""Retention prune for unbounded AI-scratch / history tables.

These tables accumulate without any retention and dwarf the real data
(suggested_contract_links was ~13.7k vs 609 contracts). They are regenerated on
demand (link suggestions, extraction QA) or are pure history, so trimming old
rows is safe.

Intentionally does NOT touch audit_logs — that trail is kept for compliance.

    uv run python -m scripts.prune_scratch_tables            # dry-run, 90 days
    uv run python -m scripts.prune_scratch_tables --days 60
    uv run python -m scripts.prune_scratch_tables --apply    # actually delete

Safe to run repeatedly; schedule (e.g. weekly) to keep growth bounded.
"""

import asyncio
import sys

from sqlalchemy import text

from app.database import async_session_maker

# table -> the timestamp column used for age
TABLES = {
    "suggested_contract_links": "created_at",
    "extraction_verifications": "created_at",
    "scheduler_job_history": "created_at",
}


async def main(days: int, apply: bool) -> None:
    async with async_session_maker() as db:
        print(f"Retention: rows older than {days} days  ({'APPLY' if apply else 'DRY-RUN'})\n")
        grand = 0
        for table, col in TABLES.items():
            total = (await db.execute(text(f"SELECT count(*) FROM {table}"))).scalar() or 0
            old = (
                await db.execute(
                    text(
                        f"SELECT count(*) FROM {table} "
                        f"WHERE {col} < now() - make_interval(days => :d)"
                    ),
                    {"d": days},
                )
            ).scalar() or 0
            grand += old
            print(f"  {table:28s} {total:>7} total | {old:>7} older than {days}d "
                  f"({'would delete' if not apply else 'deleting'})")
            if apply and old:
                await db.execute(
                    text(f"DELETE FROM {table} WHERE {col} < now() - make_interval(days => :d)"),
                    {"d": days},
                )
        if apply:
            await db.commit()
            print(f"\nDeleted {grand} rows.")
        else:
            print(f"\nWould delete {grand} rows. Re-run with --apply to execute.")


if __name__ == "__main__":
    days = 90
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    asyncio.run(main(days=days, apply="--apply" in sys.argv))
