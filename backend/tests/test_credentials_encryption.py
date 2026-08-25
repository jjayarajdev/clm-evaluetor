"""Tests for at-rest encryption of integration credentials (EncryptedJSON).

The application reads/writes plain dicts; the stored value is a Fernet
envelope {"__enc__": token}. Legacy plaintext rows must keep loading, and a
wrong/rotated key must degrade to None (credentials re-entered), never a 500.
"""

import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.crypto import decrypt_dict, encrypt_dict, is_encrypted
from app.database import Base
from app.models.integration import IntegrationConfig, IntegrationSystem
from app.models.tenant import Tenant

TENANT_ID = uuid.uuid4()
CREDS = {"username": "snow-admin", "password": "s3cret-value"}


class TestEnvelope:
    def test_roundtrip(self):
        env = encrypt_dict(CREDS)
        assert is_encrypted(env)
        assert "s3cret-value" not in json.dumps(env)
        assert decrypt_dict(env) == CREDS

    def test_wrong_key_returns_none(self, monkeypatch):
        env = encrypt_dict(CREDS)
        from app.config import settings
        monkeypatch.setattr(settings, "credentials_encryption_key", "a-different-key")
        assert decrypt_dict(env) is None

    def test_key_derivation_is_stable(self):
        assert decrypt_dict(encrypt_dict(CREDS)) == CREDS  # two _fernet() instances


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    from sqlalchemy import JSON
    from sqlalchemy.dialects.postgresql import JSONB
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
    seen_idx = set()
    for table in Base.metadata.tables.values():
        deduped = [i for i in table.indexes if i.name not in seen_idx and not seen_idx.add(i.name)]
        table.indexes.clear()
        table.indexes.update(deduped)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


def _config(**kw) -> IntegrationConfig:
    return IntegrationConfig(
        id=uuid.uuid4(), tenant_id=TENANT_ID, system=IntegrationSystem.servicenow,
        name="snow", base_url="https://x.service-now.com", auth_type="basic", **kw,
    )


@pytest.mark.asyncio
class TestColumnEncryption:
    async def test_stored_value_is_ciphertext(self, db):
        db.add(Tenant(id=TENANT_ID, name="T", slug="t", is_active=True))
        cfg = _config(credentials=dict(CREDS))
        db.add(cfg)
        await db.commit()

        raw = (
            await db.execute(
                text("SELECT credentials FROM integration_configs"),
            )
        ).scalar()
        raw_str = raw if isinstance(raw, str) else json.dumps(raw)
        assert "s3cret-value" not in raw_str
        assert "__enc__" in raw_str

        db.expunge_all()
        loaded = (await db.execute(select(IntegrationConfig))).scalar_one().credentials
        assert loaded == CREDS

    async def test_legacy_plaintext_row_still_loads(self, db):
        db.add(Tenant(id=TENANT_ID, name="T", slug="t", is_active=True))
        cfg = _config(credentials=None)
        db.add(cfg)
        await db.commit()
        # Simulate a pre-encryption row written before EncryptedJSON existed.
        await db.execute(
            text("UPDATE integration_configs SET credentials = :v"),
            {"v": json.dumps(CREDS)},
        )
        await db.commit()
        db.expunge_all()
        loaded = (await db.execute(select(IntegrationConfig))).scalar_one().credentials
        assert loaded == CREDS

    async def test_null_credentials_stay_null(self, db):
        db.add(Tenant(id=TENANT_ID, name="T", slug="t", is_active=True))
        cfg = _config(credentials=None)
        db.add(cfg)
        await db.commit()
        db.expunge_all()
        assert (await db.execute(select(IntegrationConfig))).scalar_one().credentials is None
