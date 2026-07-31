"""Buffered, fire-and-forget usage metering.

Product code calls record() (or record_llm_response() from the LLM factory);
events land in an in-process buffer and a background task flushes them to the
usage_events table. Design constraints:

  * Metering must NEVER fail or slow a product call — record() swallows all
    errors and does no I/O.
  * The buffer is per-process, so the flusher runs in EVERY worker (unlike the
    scheduler, which is single-worker via file lock).
  * If the DB is down, events are re-queued up to a hard cap; beyond that the
    oldest are dropped (bounded memory beats perfect metering).

Tenant attribution defaults to the LLM factory's current_tenant_id ContextVar,
which is set by request middleware and by the upload pipeline — the same source
get_async_openai() uses to pick the tenant's key, so usage is attributed to
whoever's key (or fair-use ceiling) the call consumed.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.models.usage_event import UsageMetric

logger = logging.getLogger(__name__)

FLUSH_INTERVAL_SECONDS = 30
FLUSH_BATCH_THRESHOLD = 200  # flush early once this many events are pending
BUFFER_HARD_CAP = 50_000  # oldest events dropped beyond this


@dataclass
class _PendingEvent:
    tenant_id: uuid.UUID | None
    metric: str
    quantity: int
    model: str | None = None
    ref_type: str | None = None
    ref_id: uuid.UUID | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


_buffer: list[_PendingEvent] = []
_lock = threading.Lock()  # record() may be called from sync (threaded) contexts
_flusher_task: asyncio.Task | None = None


def _coerce_uuid(value) -> uuid.UUID | None:
    if value is None:
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def record(
    metric: str,
    quantity: int | None,
    *,
    tenant_id=None,
    model: str | None = None,
    ref_type: str | None = None,
    ref_id=None,
) -> None:
    """Queue one usage event. Never raises; zero/negative quantities are ignored."""
    try:
        if not quantity or quantity <= 0:
            return
        if tenant_id is None:
            from app.core.llm import current_tenant_id

            tenant_id = current_tenant_id.get()
        event = _PendingEvent(
            tenant_id=_coerce_uuid(tenant_id),
            metric=metric,
            quantity=int(quantity),
            model=model,
            ref_type=ref_type,
            ref_id=_coerce_uuid(ref_id),
        )
        with _lock:
            _buffer.append(event)
            overflow = len(_buffer) - BUFFER_HARD_CAP
            if overflow > 0:
                del _buffer[:overflow]
    except Exception:  # noqa: BLE001 — metering must never break the caller
        logger.warning("Usage metering record failed", exc_info=True)


def record_llm_response(response, model: str | None = None, kind: str = "chat") -> None:
    """Meter one OpenAI response (chat or embedding). Never raises.

    Streaming responses have no .usage attribute — the AI action is still
    counted, the token events are simply skipped.
    """
    try:
        model = getattr(response, "model", None) or model
        usage = getattr(response, "usage", None)
        if kind == "chat":
            record(UsageMetric.AI_ACTIONS, 1, model=model)
            if usage is not None:
                record(UsageMetric.TOKENS_PROMPT, getattr(usage, "prompt_tokens", 0), model=model)
                record(UsageMetric.TOKENS_COMPLETION, getattr(usage, "completion_tokens", 0), model=model)
        elif usage is not None:
            record(UsageMetric.TOKENS_EMBEDDING, getattr(usage, "prompt_tokens", 0), model=model)
    except Exception:  # noqa: BLE001
        logger.warning("Usage metering of LLM response failed", exc_info=True)


def pending_count() -> int:
    with _lock:
        return len(_buffer)


async def flush(session_maker=None) -> int:
    """Persist all buffered events. Returns rows written (0 on failure, re-queued)."""
    with _lock:
        if not _buffer:
            return 0
        events = _buffer[:]
        _buffer.clear()

    from app.models.usage_event import UsageEvent

    if session_maker is None:
        from app.database import async_session_maker as session_maker

    try:
        async with session_maker() as session:
            session.add_all(
                UsageEvent(
                    tenant_id=e.tenant_id,
                    metric=e.metric,
                    quantity=e.quantity,
                    model=e.model,
                    ref_type=e.ref_type,
                    ref_id=e.ref_id,
                    occurred_at=e.occurred_at,
                )
                for e in events
            )
            await session.commit()
        return len(events)
    except Exception:  # noqa: BLE001
        logger.warning("Usage metering flush failed; re-queuing %d events", len(events), exc_info=True)
        with _lock:
            _buffer[:0] = events
            overflow = len(_buffer) - BUFFER_HARD_CAP
            if overflow > 0:
                del _buffer[:overflow]
        return 0


async def _flush_loop() -> None:
    elapsed = 0
    while True:
        await asyncio.sleep(5)
        elapsed += 5
        if elapsed >= FLUSH_INTERVAL_SECONDS or pending_count() >= FLUSH_BATCH_THRESHOLD:
            await flush()
            elapsed = 0


def start_flusher() -> None:
    """Start the periodic flush task (call once per worker at startup)."""
    global _flusher_task
    if _flusher_task is None or _flusher_task.done():
        _flusher_task = asyncio.get_running_loop().create_task(_flush_loop())
        logger.info("Usage metering flusher started")


async def stop_flusher() -> None:
    """Cancel the flush task and write out whatever is still buffered."""
    global _flusher_task
    if _flusher_task is not None:
        _flusher_task.cancel()
        try:
            await _flusher_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        _flusher_task = None
    await flush()
