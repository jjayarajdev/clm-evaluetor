"""Regression tests for the index_contract tuple-truthiness data-integrity bug.

`IndexingService.index_contract` returns `tuple[bool, str | None]`. A non-empty
tuple is ALWAYS truthy, so a previous bug that did `success = await
index_contract(...)` / `if success:` treated `(False, "boom")` as success and
marked failed uploads COMPLETED. These tests pin the correct behavior: on a
failed index the contract ends up FAILED (never COMPLETED) with the real error
message recorded; and an indexed-but-deep-analysis-failed contract is COMPLETED
yet records the degradation rather than silently claiming full completion.
"""

import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import JSON, Uuid, event, select
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import Base
from app.models.contract import Contract, ContractStatus
from app.models.tenant import Tenant


sqlite3.register_adapter(uuid.UUID, lambda u: str(u))

TENANT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


def _patch_columns_for_sqlite():
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
            if isinstance(col.type, (PG_UUID, Uuid)):
                col.type = Uuid(native_uuid=False)


@pytest_asyncio.fixture(scope="function")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)

    @event.listens_for(eng.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    _patch_columns_for_sqlite()

    seen_idx = set()
    for table in Base.metadata.tables.values():
        deduped = []
        for idx in table.indexes:
            if idx.name not in seen_idx:
                seen_idx.add(idx.name)
                deduped.append(idx)
        table.indexes.clear()
        table.indexes.update(deduped)

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture(scope="function")
async def db(engine):
    session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def failing_contract(db):
    """A freshly-uploaded contract sitting in PENDING, ready to be processed."""
    db.add(Tenant(id=TENANT_ID, name="T", slug="t", is_active=True,
                  created_at=datetime.utcnow()))
    contract = Contract(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        filename="corrupt.pdf",
        file_path="/uploads/corrupt.pdf",
        file_size=10,
        mime_type="application/pdf",
        status=ContractStatus.PENDING,
        uploaded_by=uuid.uuid4(),
        created_at=datetime.utcnow(),
    )
    db.add(contract)
    await db.commit()
    return contract


def _session_maker_yielding(session):
    """async_session_maker replacement that yields the given session."""

    @asynccontextmanager
    async def _maker():
        yield session

    return _maker


def _patched(db, mock_indexer):
    """Common patch context: route sessions + indexer construction to mocks.

    async_session_maker and IndexingService are imported *inside*
    _auto_process_contract from their source modules, so patch there.
    """
    return (
        patch("app.database.async_session_maker", _session_maker_yielding(db)),
        patch("app.services.indexer.IndexingService", return_value=mock_indexer),
    )


@pytest.mark.asyncio
async def test_auto_process_marks_failed_when_index_returns_false(db, failing_contract):
    """(False, "boom") => contract FAILED (never COMPLETED), error recorded.

    This is the exact tuple-truthiness regression: bool-checking the raw tuple
    would wrongly mark the contract COMPLETED. We assert the opposite.
    """
    from app.routers import contracts as contracts_router

    mock_indexer = MagicMock()
    mock_indexer.index_contract = AsyncMock(return_value=(False, "boom"))
    p_sess, p_idx = _patched(db, mock_indexer)

    with p_sess, p_idx, patch.object(
        contracts_router, "_run_deep_analysis", new=AsyncMock()
    ) as mock_deep:
        await contracts_router._auto_process_contract(
            str(failing_contract.id),
            str(failing_contract.tenant_id),
            failing_contract.file_path,
        )

    await db.refresh(failing_contract)
    assert failing_contract.status == ContractStatus.FAILED
    assert failing_contract.status != ContractStatus.COMPLETED
    assert failing_contract.processing_error is not None
    assert "boom" in failing_contract.processing_error
    mock_deep.assert_not_called()  # a failed index must never reach deep analysis


@pytest.mark.asyncio
async def test_auto_process_completes_when_index_succeeds(db, failing_contract):
    """(True, None) => contract COMPLETED (positive control for the unpacking)."""
    from app.routers import contracts as contracts_router

    mock_indexer = MagicMock()
    mock_indexer.index_contract = AsyncMock(return_value=(True, None))
    p_sess, p_idx = _patched(db, mock_indexer)

    with p_sess, p_idx, patch.object(
        contracts_router, "_run_deep_analysis", new=AsyncMock()
    ):
        await contracts_router._auto_process_contract(
            str(failing_contract.id),
            str(failing_contract.tenant_id),
            failing_contract.file_path,
        )

    await db.refresh(failing_contract)
    assert failing_contract.status == ContractStatus.COMPLETED


@pytest.mark.asyncio
async def test_auto_process_records_deep_analysis_degradation(db, failing_contract):
    """Index OK but deep analysis raises => COMPLETED, degradation recorded.

    Status honesty: we do not silently claim full completion. The contract is
    COMPLETED (indexed/searchable) but extraction_health flags the failure.
    """
    from app.routers import contracts as contracts_router

    mock_indexer = MagicMock()
    mock_indexer.index_contract = AsyncMock(return_value=(True, None))
    p_sess, p_idx = _patched(db, mock_indexer)

    with p_sess, p_idx, patch.object(
        contracts_router,
        "_run_deep_analysis",
        new=AsyncMock(side_effect=RuntimeError("clause extraction blew up")),
    ):
        await contracts_router._auto_process_contract(
            str(failing_contract.id),
            str(failing_contract.tenant_id),
            failing_contract.file_path,
        )

    await db.refresh(failing_contract)
    assert failing_contract.status == ContractStatus.COMPLETED
    assert failing_contract.extraction_health is not None
    assert failing_contract.extraction_health["deep_analysis"]["status"] == "failed"
    assert failing_contract.processing_error is not None
    assert "incomplete" in failing_contract.processing_error.lower()
