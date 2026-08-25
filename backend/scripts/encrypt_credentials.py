#!/usr/bin/env python3
"""One-shot migration: encrypt legacy plaintext integration credentials.

The EncryptedJSON column type encrypts on write, so pre-existing plaintext
rows stay plaintext until re-saved. This rewrites every row that still holds
a plaintext credentials dict. Uses raw SQL on purpose: the ORM decrypts on
load, so through the ORM an encrypted row is indistinguishable from a
plaintext one. Idempotent — rows already carrying the {"__enc__": ...}
envelope are skipped.

Run with: python -m scripts.encrypt_credentials
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.core.crypto import encrypt_dict, is_encrypted
from app.database import async_session_maker

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    async with async_session_maker() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, name, credentials FROM integration_configs "
                    "WHERE credentials IS NOT NULL"
                )
            )
        ).all()
        migrated = skipped = 0
        for row_id, name, creds in rows:
            if isinstance(creds, str):
                creds = json.loads(creds)
            if is_encrypted(creds):
                skipped += 1
                continue
            await session.execute(
                text(
                    "UPDATE integration_configs "
                    "SET credentials = CAST(:val AS jsonb) "
                    "WHERE id = CAST(:id AS uuid)"
                ),
                {"val": json.dumps(encrypt_dict(creds)), "id": str(row_id)},
            )
            migrated += 1
            logger.info("encrypted credentials for %s", name)
        await session.commit()
        logger.info("done: %d encrypted, %d already-encrypted/skipped", migrated, skipped)


if __name__ == "__main__":
    asyncio.run(main())
