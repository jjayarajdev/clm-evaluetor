"""DSPy compilation/extraction must honor a tenant's own provider (2026-08-05).

Previously DSPy always used the global platform OpenAI key. Now _build_lm
resolves the tenant's Azure deployment or own OpenAI key, matching how the rest
of the app (app.core.llm) selects a provider.
"""

from app.services.dspy_extractor import (
    _build_lm,
    build_lm_for_tenant,
    load_program_meta,
    provider_descriptor,
    save_program_meta,
)


def test_azure_config_builds_azure_lm():
    az = {
        "enabled": True,
        "provider": "azure",
        "api_key": "az-key",
        "endpoint": "https://acme.openai.azure.com",
        "api_version": "2025-01-01-preview",
        "deployment": "acme-gpt4o",
    }
    lm = _build_lm(az)
    assert lm.model == "azure/acme-gpt4o"
    assert lm.kwargs["api_key"] == "az-key"
    assert lm.kwargs["api_base"] == "https://acme.openai.azure.com"
    assert lm.kwargs["api_version"] == "2025-01-01-preview"


def test_azure_without_deployment_falls_back_to_model_name():
    az = {"enabled": True, "provider": "azure", "api_key": "k", "endpoint": "https://x.openai.azure.com"}
    lm = _build_lm(az)
    # Deployment defaults to the model id (per the app's naming convention).
    assert lm.model.startswith("azure/")
    assert lm.kwargs["api_base"] == "https://x.openai.azure.com"


def test_tenant_openai_key_used():
    az = {"enabled": True, "provider": "openai", "api_key": "tenant-openai-key"}
    lm = _build_lm(az)
    assert lm.model.startswith("openai/")
    assert lm.kwargs["api_key"] == "tenant-openai-key"


def test_disabled_or_missing_config_uses_global_default():
    from app.config import settings

    for cfg in (None, {}, {"enabled": False, "api_key": "x"}, {"enabled": True}):
        lm = _build_lm(cfg)
        assert lm.model.startswith("openai/")
        # Global platform key, not a tenant one.
        assert lm.kwargs["api_key"] == getattr(settings, "openai_api_key", None)


def test_azure_missing_endpoint_falls_back_to_default():
    # Azure needs an endpoint; without one we must not build a broken azure/ LM.
    az = {"enabled": True, "provider": "azure", "api_key": "k"}
    lm = _build_lm(az)
    assert lm.model.startswith("openai/")


def test_provider_descriptor_labels():
    az = {"enabled": True, "provider": "azure", "api_key": "k",
          "endpoint": "https://acme.openai.azure.com", "deployment": "acme-gpt4o"}
    d = provider_descriptor(az)
    assert d["provider"] == "azure"
    assert d["label"] == "Azure · acme-gpt4o"

    assert provider_descriptor({"enabled": True, "provider": "openai", "api_key": "k"})["label"] == "OpenAI (tenant key)"
    assert provider_descriptor(None)["label"] == "OpenAI (platform)"
    assert provider_descriptor({"enabled": False, "api_key": "k"})["provider"] == "openai_platform"


def test_program_meta_roundtrip(monkeypatch, tmp_path):
    import app.services.dspy_extractor as ext

    monkeypatch.setattr(ext, "COMPILED_DIR", tmp_path)
    meta = {"provider": provider_descriptor(None), "examples": 7}
    save_program_meta(None, "metadata", meta)
    loaded = load_program_meta(None, "metadata")
    assert loaded == meta
    assert load_program_meta(None, "clause") is None  # no file → None


def test_build_lm_for_tenant_uses_request_context(monkeypatch):
    # build_lm_for_tenant resolves via app.core.llm._azure_for (request/cache).
    import app.core.llm as llm

    monkeypatch.setattr(
        llm,
        "_azure_for",
        lambda tid: {"enabled": True, "provider": "azure", "api_key": "ctx-key",
                     "endpoint": "https://ctx.openai.azure.com", "deployment": "ctx-dep"},
    )
    lm = build_lm_for_tenant(None)
    assert lm.model == "azure/ctx-dep"
    assert lm.kwargs["api_key"] == "ctx-key"
