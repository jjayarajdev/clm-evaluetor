"""Tests for the usage metering pipeline (buffer, flush, LLM interceptor)."""

import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.usage_event import UsageEvent, UsageMetric
from app.services import usage_metering


@pytest.fixture(autouse=True)
def clean_buffer():
    """Each test starts and ends with an empty metering buffer."""
    usage_metering._buffer.clear()
    yield
    usage_metering._buffer.clear()


@pytest_asyncio.fixture(scope="function")
async def session_maker():
    # Only the usage_events table is needed; SQLite doesn't enforce the tenants
    # FK by default, so the full (JSONB-using) schema stays out of the test.
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda c: Base.metadata.create_all(c, tables=[UsageEvent.__table__])
        )
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


class TestRecord:
    def test_record_buffers_event(self):
        tid = uuid.uuid4()
        usage_metering.record(UsageMetric.PAGES_PROCESSED, 12, tenant_id=tid)
        assert usage_metering.pending_count() == 1
        event = usage_metering._buffer[0]
        assert event.metric == UsageMetric.PAGES_PROCESSED
        assert event.quantity == 12
        assert event.tenant_id == tid

    def test_zero_and_negative_quantities_ignored(self):
        usage_metering.record(UsageMetric.AI_ACTIONS, 0)
        usage_metering.record(UsageMetric.AI_ACTIONS, -5)
        usage_metering.record(UsageMetric.AI_ACTIONS, None)
        assert usage_metering.pending_count() == 0

    def test_tenant_defaults_to_llm_contextvar(self):
        from app.core.llm import current_tenant_id

        tid = uuid.uuid4()
        token = current_tenant_id.set(str(tid))
        try:
            usage_metering.record(UsageMetric.AI_ACTIONS, 1)
        finally:
            current_tenant_id.reset(token)
        assert usage_metering._buffer[0].tenant_id == tid

    def test_bad_input_never_raises(self):
        usage_metering.record(UsageMetric.AI_ACTIONS, 1, tenant_id="not-a-uuid")
        assert usage_metering.pending_count() == 0  # swallowed, logged

    def test_hard_cap_drops_oldest(self, monkeypatch):
        monkeypatch.setattr(usage_metering, "BUFFER_HARD_CAP", 3)
        for i in range(5):
            usage_metering.record(UsageMetric.AI_ACTIONS, i + 1)
        assert usage_metering.pending_count() == 3
        assert [e.quantity for e in usage_metering._buffer] == [3, 4, 5]


class TestRecordLLMResponse:
    def test_chat_response_meters_action_and_tokens(self):
        resp = SimpleNamespace(
            model="gpt-4o-2024-08-06",
            usage=SimpleNamespace(prompt_tokens=900, completion_tokens=150),
        )
        usage_metering.record_llm_response(resp, "gpt-4o", kind="chat")
        by_metric = {e.metric: e for e in usage_metering._buffer}
        assert by_metric[UsageMetric.AI_ACTIONS].quantity == 1
        assert by_metric[UsageMetric.TOKENS_PROMPT].quantity == 900
        assert by_metric[UsageMetric.TOKENS_COMPLETION].quantity == 150
        # response.model (exact) wins over the requested model id
        assert by_metric[UsageMetric.TOKENS_PROMPT].model == "gpt-4o-2024-08-06"

    def test_streaming_response_counts_action_only(self):
        stream = SimpleNamespace()  # no .usage, no .model
        usage_metering.record_llm_response(stream, "gpt-4o-mini", kind="chat")
        assert [e.metric for e in usage_metering._buffer] == [UsageMetric.AI_ACTIONS]
        assert usage_metering._buffer[0].model == "gpt-4o-mini"

    def test_embedding_response(self):
        resp = SimpleNamespace(
            model="text-embedding-3-small",
            usage=SimpleNamespace(prompt_tokens=4200),
        )
        usage_metering.record_llm_response(resp, kind="embedding")
        assert [e.metric for e in usage_metering._buffer] == [UsageMetric.TOKENS_EMBEDDING]
        assert usage_metering._buffer[0].quantity == 4200


class TestFlush:
    @pytest.mark.asyncio
    async def test_flush_writes_events(self, session_maker):
        tenant_id = uuid.uuid4()
        usage_metering.record(
            UsageMetric.TOKENS_PROMPT, 500,
            tenant_id=tenant_id, model="gpt-4o", ref_type="contract", ref_id=uuid.uuid4(),
        )
        usage_metering.record(UsageMetric.AI_ACTIONS, 1, tenant_id=tenant_id)

        written = await usage_metering.flush(session_maker)
        assert written == 2
        assert usage_metering.pending_count() == 0

        async with session_maker() as session:
            rows = (await session.execute(select(UsageEvent))).scalars().all()
        assert {r.metric for r in rows} == {UsageMetric.TOKENS_PROMPT, UsageMetric.AI_ACTIONS}
        prompt_row = next(r for r in rows if r.metric == UsageMetric.TOKENS_PROMPT)
        assert prompt_row.quantity == 500
        assert prompt_row.tenant_id == tenant_id
        assert prompt_row.model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_flush_empty_buffer_is_noop(self, session_maker):
        assert await usage_metering.flush(session_maker) == 0

    @pytest.mark.asyncio
    async def test_failed_flush_requeues(self):
        usage_metering.record(UsageMetric.AI_ACTIONS, 1, tenant_id=uuid.uuid4())

        def broken_session_maker():
            raise RuntimeError("db down")

        assert await usage_metering.flush(broken_session_maker) == 0
        assert usage_metering.pending_count() == 1


class TestMeteredClient:
    @pytest.mark.asyncio
    async def test_async_client_calls_are_metered(self):
        from app.core.llm import _meter_async_client

        resp = SimpleNamespace(
            model="gpt-4o", usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5)
        )

        async def fake_create(*args, **kwargs):
            return resp

        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)),
            embeddings=SimpleNamespace(create=fake_create),
        )
        _meter_async_client(client)

        result = await client.chat.completions.create(model="gpt-4o", messages=[])
        assert result is resp  # response passes through untouched
        metrics = [e.metric for e in usage_metering._buffer]
        assert metrics == [
            UsageMetric.AI_ACTIONS,
            UsageMetric.TOKENS_PROMPT,
            UsageMetric.TOKENS_COMPLETION,
        ]
