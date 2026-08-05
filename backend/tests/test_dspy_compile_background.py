"""Regression tests for DSPy compile durability + backgrounding (2026-08-05).

- Compiled programs (and their lock sentinels) must live on a persistent path,
  not a container-local dir wiped on every deploy.
- POST /compile must dispatch compilation to a background task and return
  'started' immediately, never run BootstrapFewShot inline.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import BackgroundTasks


def test_compiled_dir_is_persistent_by_default(monkeypatch):
    """Default compiled dir must be under storage/ (volume-mounted), not data/."""
    monkeypatch.delenv("DSPY_COMPILED_DIR", raising=False)
    import importlib

    import app.services.dspy_extractor as ext

    importlib.reload(ext)
    try:
        assert ext.COMPILED_DIR.parts[-1] == "dspy_compiled"
        assert "storage" in ext.COMPILED_DIR.parts, ext.COMPILED_DIR
        # The .compiling lock sentinel lives beside the program → also persistent.
        lock = ext._program_path(None, "metadata").with_suffix(".compiling")
        assert "storage" in lock.parts
    finally:
        importlib.reload(ext)


def test_env_override_respected(monkeypatch, tmp_path):
    monkeypatch.setenv("DSPY_COMPILED_DIR", str(tmp_path / "custom"))
    import importlib

    import app.services.dspy_extractor as ext

    importlib.reload(ext)
    try:
        assert ext.COMPILED_DIR == tmp_path / "custom"
    finally:
        monkeypatch.delenv("DSPY_COMPILED_DIR", raising=False)
        importlib.reload(ext)


@pytest.mark.asyncio
async def test_compile_endpoint_backgrounds_and_returns_started(monkeypatch):
    """Endpoint acquires the lock, schedules a background task, returns 'started'
    — it must NOT call compile_for_tenant inline (which would block on LLM calls)."""
    import app.services.dspy_compiler as comp
    from app.routers.extraction_quality import compile_dspy_programs

    monkeypatch.setattr(comp, "acquire_compile_lock", lambda tid, agent: True)

    inline_calls = []

    async def _fail_if_called(*a, **k):
        inline_calls.append(a)

    # If the endpoint ran compilation inline, this would be invoked during await.
    monkeypatch.setattr(comp, "compile_for_tenant", _fail_if_called)

    bg = BackgroundTasks()
    resp = await compile_dspy_programs(
        tenant_id=None, current_user=MagicMock(), background_tasks=bg, agent_types=["metadata", "clause"]
    )

    assert resp["results"]["metadata"]["status"] == "started"
    assert resp["results"]["clause"]["status"] == "started"
    assert len(bg.tasks) == 1  # one _bg_compile task covering both agents
    assert inline_calls == []  # nothing compiled synchronously in the request


@pytest.mark.asyncio
async def test_compile_endpoint_reports_in_progress_when_locked(monkeypatch):
    import app.services.dspy_compiler as comp
    from app.routers.extraction_quality import compile_dspy_programs

    monkeypatch.setattr(comp, "acquire_compile_lock", lambda tid, agent: False)
    bg = BackgroundTasks()
    resp = await compile_dspy_programs(
        tenant_id=None, current_user=MagicMock(), background_tasks=bg, agent_types=["sla"]
    )
    assert resp["results"]["sla"]["status"] == "in_progress"
    assert len(bg.tasks) == 0  # nothing scheduled — already running


@pytest.mark.asyncio
async def test_compile_endpoint_rejects_unknown_agent(monkeypatch):
    import app.services.dspy_compiler as comp
    from app.routers.extraction_quality import compile_dspy_programs

    monkeypatch.setattr(comp, "acquire_compile_lock", lambda tid, agent: True)
    bg = BackgroundTasks()
    resp = await compile_dspy_programs(
        tenant_id=None, current_user=MagicMock(), background_tasks=bg, agent_types=["bogus"]
    )
    assert resp["results"]["bogus"]["status"] == "error"
    assert len(bg.tasks) == 0
