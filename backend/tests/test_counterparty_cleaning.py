"""Tests for counterparty cleaning — international names must survive.

Regression for the Square-one (French client) issue: the extraction model
correctly returned bare French company names ("OPENWORK", "ALTHEA") but the
cleaning step rejected any short name without an Anglo legal suffix.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents import metadata_extraction as me


class TestSuffixSkip:
    """Names with recognized legal suffixes skip the cleaning LLM entirely."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("value", [
        "OPENWORK SAS", "Acme SARL", "Bidule EURL", "Machin SASU",
        "Beispiel GmbH", "Acme Inc.", "Widget B.V.", "Esempio S.p.A.",
        "Nordic AB", "Suomi Oy",
    ])
    async def test_suffixed_names_kept_without_llm(self, value, monkeypatch):
        llm = AsyncMock()
        monkeypatch.setattr(me, "get_async_openai", llm, raising=False)
        out = await me._clean_counterparty_with_llm(value, ["Square-one"])
        assert out == value
        llm.assert_not_called()

    @pytest.mark.asyncio
    async def test_excluded_party_rejected_before_llm(self):
        assert await me._clean_counterparty_with_llm("SQUARE-ONE", ["Square-one", "SQUARE-ONE"]) is None
        assert await me._clean_counterparty_with_llm(
            "Square-one SAS", ["Square-one"]
        ) is None  # substring of value → still the uploader's org


class TestPartiesFallback:
    @pytest.mark.asyncio
    async def test_rejected_counterparty_recovers_from_parties(self, monkeypatch):
        """Model returns the uploader's org as counterparty (nulled by
        exclusion) but the real counterparty is in the parties list."""
        fake_response = SimpleNamespace(
            response='{"contract_type": "msa", "counterparty": "SQUARE-ONE",'
                     ' "parties": ["SQUARE-ONE", "OPENWORK SAS"]}',
        )

        class FakeOrchestrator:
            async def route_request(self, request):
                return fake_response

        monkeypatch.setattr(me, "get_orchestrator", lambda: FakeOrchestrator(), raising=False)
        # Patch orchestrator import used inside extract_metadata
        import app.services.orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "get_orchestrator", lambda: FakeOrchestrator())

        result = await me.extract_metadata(
            "contract text " * 20,
            excluded_parties=["Square-one", "SQUARE-ONE"],
        )
        assert result.counterparty is not None
        assert result.counterparty.value == "OPENWORK SAS"  # suffix skip, no LLM needed
