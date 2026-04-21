"""Backfill highlight_rects for all existing contracts (clauses, obligations, SLAs).

Usage:
    cd backend && uv run python -m scripts.backfill_highlights
    # Or in Docker:
    docker-compose -f docker-compose.prod.yml exec -T backend python -m scripts.backfill_highlights
"""

import asyncio
import logging

from sqlalchemy import select

from app.database import async_session_maker
from app.models.clause import Clause
from app.models.contract import Contract
from app.models.obligation import Obligation
from app.models.sla import ContractSLA
from app.services.highlight_extractor import extract_highlight_rects

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)


async def backfill():
    async with async_session_maker() as db:
        result = await db.execute(
            select(Contract.id, Contract.file_path)
            .where(Contract.file_path.isnot(None))
            .order_by(Contract.created_at.desc())
        )
        contracts = result.all()
        logger.info(f"Found {len(contracts)} contracts with files")

        clause_total = 0
        obl_total = 0
        sla_total = 0

        for i, (contract_id, file_path) in enumerate(contracts):
            # --- Clauses ---
            clause_q = await db.execute(
                select(Clause).where(
                    Clause.contract_id == contract_id,
                    Clause.highlight_rects.is_(None),
                )
            )
            clauses = clause_q.scalars().all()
            if clauses:
                clause_data = [
                    {"id": str(c.id), "text": c.text, "page_number": c.page_number}
                    for c in clauses if c.text
                ]
                if clause_data:
                    rects_map = extract_highlight_rects(file_path, clause_data)
                    for c in clauses:
                        cid = str(c.id)
                        if cid in rects_map:
                            c.highlight_rects = rects_map[cid]
                            clause_total += 1

            # --- Obligations ---
            obl_q = await db.execute(
                select(Obligation).where(
                    Obligation.contract_id == contract_id,
                    Obligation.highlight_rects.is_(None),
                )
            )
            obligations = obl_q.scalars().all()
            if obligations:
                obl_data = [
                    {"id": str(o.id), "text": o.source_text or o.description, "page_number": None}
                    for o in obligations if o.source_text or o.description
                ]
                if obl_data:
                    rects_map = extract_highlight_rects(file_path, obl_data)
                    for o in obligations:
                        oid = str(o.id)
                        if oid in rects_map:
                            o.highlight_rects = rects_map[oid]
                            obl_total += 1

            # --- SLAs ---
            sla_q = await db.execute(
                select(ContractSLA).where(
                    ContractSLA.contract_id == contract_id,
                    ContractSLA.highlight_rects.is_(None),
                )
            )
            slas = sla_q.scalars().all()
            if slas:
                sla_data = [
                    {"id": str(s.id), "text": s.source_text or s.sla_description or s.sla_name, "page_number": None}
                    for s in slas if s.source_text or s.sla_description
                ]
                if sla_data:
                    rects_map = extract_highlight_rects(file_path, sla_data)
                    for s in slas:
                        sid = str(s.id)
                        if sid in rects_map:
                            s.highlight_rects = rects_map[sid]
                            sla_total += 1

            has_updates = any([clauses, obligations, slas])
            if has_updates:
                await db.commit()

            if (i + 1) % 50 == 0 or i == len(contracts) - 1:
                logger.info(f"[{i+1}/{len(contracts)}] Clauses: {clause_total}, Obligations: {obl_total}, SLAs: {sla_total}")

        logger.info(f"Done. Clauses: {clause_total}, Obligations: {obl_total}, SLAs: {sla_total}")


if __name__ == "__main__":
    asyncio.run(backfill())
