"""Ask-AI intent routing consistency (2026-08-05).

A count/aggregate question must always route to the structured (DB) path, never
to RAG — regardless of singular/plural, typos, or language. Reproduces the bug
where "how many contract do i have" (singular) fell through to RAG and answered
5 from a retrieval sample instead of the true DB count.
"""

import pytest

from app.agents import intent_router
from app.agents.intent_router import detect_intent, is_aggregate_question, resolve_intent


def test_keyword_plural_hits_portfolio():
    assert detect_intent("How many contracts do I have?") == "portfolio"


def test_keyword_singular_misses():
    # The original bug: singular "contract" isn't in the keyword list.
    assert detect_intent("how many contract do i have") == "document_qa"


@pytest.mark.parametrize("q", [
    "how many contract do i have",
    "how much is my total contract value",
    "number of vendors",
    "combien de contrat ai-je",          # French
    "liste des contrats",
])
def test_aggregate_markers(q):
    assert is_aggregate_question(q) is True


@pytest.mark.parametrize("q", [
    "what does the indemnification clause say",
    "explain the termination provision",
    "de quoi parle ce document",
])
def test_non_aggregate(q):
    assert is_aggregate_question(q) is False


@pytest.mark.asyncio
async def test_resolve_forces_portfolio_for_aggregate_on_keyword_miss(monkeypatch):
    # LLM planner unavailable / returns document_qa → aggregate backstop kicks in.
    async def _llm(question, language="en"):
        return "document_qa"
    monkeypatch.setattr(intent_router, "classify_intent_llm", _llm)
    assert await resolve_intent("how many contract do i have", None, "en") == "portfolio"


@pytest.mark.asyncio
async def test_resolve_uses_llm_intent_on_keyword_miss(monkeypatch):
    async def _llm(question, language="en"):
        return "renewals"
    monkeypatch.setattr(intent_router, "classify_intent_llm", _llm)
    # Not an aggregate phrasing, but the LLM recognises a renewals question.
    assert await resolve_intent("anything expiring on me soon", None, "en") == "renewals"


@pytest.mark.asyncio
async def test_resolve_document_scope_always_rag(monkeypatch):
    # A document-scoped chat must never hit the portfolio path.
    async def _llm(question, language="en"):
        raise AssertionError("planner must not run for a document-scoped chat")
    monkeypatch.setattr(intent_router, "classify_intent_llm", _llm)
    assert await resolve_intent("how many obligations", "contract-123", "en") == "document_qa"


@pytest.mark.parametrize("q,intent", [
    ("who are my vendors", "vendors"),
    ("top counterparties by value", "vendors"),
    ("combien de fournisseurs ai-je", "vendors"),
    ("what are my SLAs", "sla"),
    ("what expires in the next 90 days", "renewals"),
    ("my riskiest contracts", "risk"),
])
def test_keyword_catalog_covers_common_intents(q, intent):
    assert detect_intent(q) == intent


@pytest.mark.asyncio
async def test_resolve_keyword_fastpath_skips_llm(monkeypatch):
    async def _llm(question, language="en"):
        raise AssertionError("planner must not run when keywords already matched")
    monkeypatch.setattr(intent_router, "classify_intent_llm", _llm)
    assert await resolve_intent("How many contracts do I have?", None, "en") == "portfolio"
