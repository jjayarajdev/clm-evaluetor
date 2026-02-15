"""Reprocess failed contracts with updated parser."""

import asyncio
import logging
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.database import async_session_maker
from app.models import Contract
from app.models.contract import ContractStatus
from app.services.parser import get_parser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def reprocess_pending():
    """Reprocess all pending contracts through the full pipeline."""
    parser = get_parser()

    async with async_session_maker() as db:
        # Get pending contracts
        result = await db.execute(select(Contract).where(Contract.status == ContractStatus.PENDING))
        contracts = result.scalars().all()

        logger.info(f"Found {len(contracts)} pending contracts to process")

        for contract in contracts:
            logger.info(f"\nProcessing: {contract.filename}")

            file_path = contract.file_path
            if not Path(file_path).exists():
                logger.error(f"  File not found: {file_path}")
                continue

            try:
                # Parse the document
                parsed = parser.parse_file(str(file_path))

                if not parsed.success:
                    logger.error(f"  Parse FAILED: {parsed.error}")
                    contract.status = ContractStatus.FAILED
                    contract.processing_error = f"Parse error: {parsed.error}"
                    await db.commit()
                    continue

                logger.info(f"  Parse SUCCESS: {len(parsed.full_text)} chars")

                # Update contract with raw text and set to processing
                contract.raw_text = parsed.full_text
                contract.extracted_text = parsed.full_text
                contract.status = ContractStatus.PROCESSING
                contract.processing_error = None
                await db.commit()

                logger.info(f"  Running AI extraction...")

                # Run deep analysis
                from app.agents.clause_extraction import extract_clauses, store_extracted_clauses
                from app.agents.obligation_tracking import extract_obligations, store_extracted_obligations
                from app.agents.sla_extraction import extract_slas, store_extracted_slas
                from app.agents.metadata_extraction import extract_metadata

                full_text = parsed.full_text

                # Extract metadata
                try:
                    metadata = await extract_metadata(full_text, contract.filename)
                    if metadata:
                        contract.counterparty = metadata.get("counterparty")
                        contract.contract_type = metadata.get("contract_type")
                        contract.effective_date = metadata.get("effective_date")
                        contract.expiration_date = metadata.get("expiration_date")
                        contract.total_value = metadata.get("total_value")
                        await db.commit()
                        logger.info(f"  Metadata extracted: counterparty={contract.counterparty}")
                except Exception as e:
                    logger.warning(f"  Metadata extraction failed: {e}")

                # Extract clauses
                try:
                    clause_result = await extract_clauses(full_text, str(contract.id), contract.filename)
                    if clause_result and clause_result.extracted_clauses:
                        await store_extracted_clauses(db, str(contract.id), clause_result.extracted_clauses)
                        await db.commit()
                        logger.info(f"  Extracted {len(clause_result.extracted_clauses)} clauses")
                except Exception as e:
                    logger.warning(f"  Clause extraction failed: {e}")

                # Extract obligations
                try:
                    obligation_result = await extract_obligations(full_text, str(contract.id), contract.filename)
                    if obligation_result and obligation_result.obligations:
                        await store_extracted_obligations(db, str(contract.id), obligation_result.obligations)
                        await db.commit()
                        logger.info(f"  Extracted {len(obligation_result.obligations)} obligations")
                except Exception as e:
                    logger.warning(f"  Obligation extraction failed: {e}")

                # Extract SLAs
                try:
                    sla_result = await extract_slas(full_text, str(contract.id), contract.filename)
                    if sla_result and sla_result.slas:
                        await store_extracted_slas(db, str(contract.id), sla_result.slas)
                        await db.commit()
                        logger.info(f"  Extracted {len(sla_result.slas)} SLAs")
                except Exception as e:
                    logger.warning(f"  SLA extraction failed: {e}")

                # Mark as completed
                contract.status = ContractStatus.COMPLETED
                await db.commit()
                logger.info(f"  Processing COMPLETED")

            except Exception as e:
                logger.exception(f"  Error processing: {e}")
                contract.status = ContractStatus.FAILED
                contract.processing_error = str(e)[:500]
                await db.commit()


if __name__ == "__main__":
    asyncio.run(reprocess_pending())
