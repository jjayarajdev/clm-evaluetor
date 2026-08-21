"""Central LLM client factory with per-tenant Azure OpenAI support.

Every AI call goes through get_async_openai()/get_sync_openai() instead of
constructing an OpenAI client directly. The client is resolved from the current
tenant (a ContextVar set by middleware for requests and by the upload pipeline
for background work):

  * tenant has an enabled Azure OpenAI config  -> AsyncAzureOpenAI on their
    endpoint/key (they consume their own Azure resource)
  * otherwise                                   -> the platform's global OpenAI

The fallback is always safe: a tenant with no config, or any error building the
Azure client, transparently uses the global OpenAI client — so existing behavior
is unchanged for anyone who hasn't set Azure up.

Azure note: Azure addresses models by *deployment name*, and the app calls models
by id ("gpt-4o", "gpt-4o-mini"). So a tenant's Azure deployments must be named
exactly `gpt-4o` and `gpt-4o-mini` (documented in the setup UI). No per-call
model rewriting needed.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar

from openai import AsyncOpenAI, AsyncAzureOpenAI, OpenAI, AzureOpenAI

from app.config import settings
from app.services.usage_metering import record_llm_response

logger = logging.getLogger(__name__)

# Current tenant for LLM resolution. None => use the global client.
current_tenant_id: ContextVar[str | None] = ContextVar("llm_current_tenant_id", default=None)

DEFAULT_AZURE_API_VERSION = "2024-08-01-preview"


def _client_hardening() -> dict:
    """Shared timeout/retry kwargs applied to every OpenAI/Azure client.

    A bounded request timeout stops the extraction pipeline hanging on a
    stalled connection; max_retries lets the SDK ride out transient blips
    (network/5xx) before the call surfaces as an error.
    """
    return {
        "timeout": settings.openai_timeout_seconds,
        "max_retries": settings.openai_max_retries,
    }


def _global_client_kwargs() -> dict:
    """Kwargs for the platform's global (non-Azure) OpenAI clients.

    Adds the cell-level base URL override (e.g. an EU-resident OpenAI-compatible
    endpoint) on top of the shared hardening. Azure clients must NOT get this —
    they address their own endpoint.
    """
    kw = _client_hardening()
    if settings.openai_base_url:
        kw["base_url"] = settings.openai_base_url
    return kw

# tenant_id(str) -> azure config dict {endpoint, api_key, api_version}. In-memory,
# refreshed at startup and on save. NOTE: per-process — with multiple workers a
# save only updates one worker, so it's a best-effort fallback. The authoritative
# source is the per-request config loaded into _ctx_azure (below) from the DB.
_azure_cache: dict[str, dict] = {}

# Request/task-scoped provider config, loaded fresh from the DB where we have a
# session (get_current_user, upload pipeline). Correct across all workers.
_UNSET = object()
_ctx_azure: ContextVar = ContextVar("llm_ctx_azure", default=_UNSET)


def set_request_azure(cfg: dict | None) -> None:
    """Bind the current tenant's provider config for this request/task."""
    _ctx_azure.set(cfg if _valid(cfg) else None)


def _valid(cfg: dict | None) -> bool:
    if not (cfg and cfg.get("enabled") and cfg.get("api_key")):
        return False
    # OpenAI provider needs only a key; Azure also needs an endpoint.
    if cfg.get("provider") == "openai":
        return True
    return bool(cfg.get("endpoint"))


def set_tenant_azure(tenant_id, cfg: dict | None) -> None:
    """Update the in-memory cache for one tenant (call after saving config)."""
    key = str(tenant_id)
    if _valid(cfg):
        _azure_cache[key] = cfg
    else:
        _azure_cache.pop(key, None)


async def refresh_azure_cache(db) -> int:
    """Load every tenant's Azure OpenAI config from tenant.config_overrides."""
    from sqlalchemy import select
    from app.models.tenant import Tenant

    _azure_cache.clear()
    for t in (await db.execute(select(Tenant))).scalars().all():
        cfg = (t.config_overrides or {}).get("azure_openai") if t.config_overrides else None
        if _valid(cfg):
            _azure_cache[str(t.id)] = cfg
    logger.info("Loaded Azure OpenAI config for %d tenant(s)", len(_azure_cache))
    return len(_azure_cache)


def _cell_azure() -> dict | None:
    """Cell-level (env-configured) Azure endpoint — the residency default.

    On a data-residency cell (e.g. EU), AZURE_OPENAI_ENDPOINT routes every
    tenant WITHOUT its own AI config through an in-region Azure resource, so
    no LLM traffic leaves the cell's geography by default. A tenant's own
    config still wins.
    """
    if not settings.azure_openai_endpoint:
        return None
    return {
        "enabled": True,
        "provider": "azure",
        "endpoint": settings.azure_openai_endpoint,
        "api_key": settings.azure_openai_api_key or settings.openai_api_key,
        "api_version": settings.azure_openai_api_version or None,
    }


def _azure_for(tenant_id) -> dict | None:
    # Prefer the per-request config loaded from the DB (authoritative, multi-worker
    # safe). It's set (possibly to None) whenever we had a session; only fall back
    # to the process cache when it was never loaded for this request/task.
    # Either way, a tenant without its own config gets the cell-level default.
    ctx = _ctx_azure.get()
    if ctx is not _UNSET:
        return ctx or _cell_azure()
    tid = tenant_id if tenant_id is not None else current_tenant_id.get()
    cfg = _azure_cache.get(str(tid)) if tid is not None else None
    return cfg or _cell_azure()


def _langfuse_on() -> bool:
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)


# Reasoning models (gpt-5 / o-series) reject max_tokens + non-default temperature.
_REASONING_HINTS = ("gpt-5", "o1", "o3", "o4")


def _is_reasoning(deployment: str) -> bool:
    d = deployment.lower()
    return any(h in d for h in _REASONING_HINTS)


def _normalize_kwargs(deployment: str, kwargs: dict) -> dict:
    """Route the call to the tenant's deployment and translate params for
    reasoning models (max_tokens -> max_completion_tokens, drop temperature)."""
    kwargs["model"] = deployment
    if _is_reasoning(deployment):
        if "max_tokens" in kwargs:
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
        kwargs.pop("temperature", None)  # only the default (1) is allowed
    return kwargs


def _apply_async_deployment(client, deployment: str | None):
    """If a single deployment name is set, route every model id to it (Azure
    addresses models by deployment). Leaves the client untouched when unset."""
    if not deployment:
        return client
    try:
        comp = client.chat.completions
        _orig = comp.create

        async def _create(*args, _orig=_orig, _dep=deployment, **kwargs):
            return await _orig(*args, **_normalize_kwargs(_dep, kwargs))

        comp.create = _create
    except Exception:  # noqa: BLE001
        logger.warning("Could not apply Azure deployment override", exc_info=True)
    return client


def _meter_async_client(client):
    """Attach usage metering to a client's chat + embeddings calls.

    Applied to every client the factory hands out (global, tenant Azure, tenant
    OpenAI), so all consumption is metered per tenant regardless of whose key
    the call runs on. Metering reads response.usage after the call and buffers
    a usage event (app.services.usage_metering) — it never raises and adds no
    I/O to the call path.
    """
    try:
        comp = client.chat.completions
        _orig_chat = comp.create

        async def _chat_create(*args, _orig=_orig_chat, **kwargs):
            resp = await _orig(*args, **kwargs)
            record_llm_response(resp, kwargs.get("model"), kind="chat")
            return resp

        comp.create = _chat_create

        emb = client.embeddings
        _orig_emb = emb.create

        async def _emb_create(*args, _orig=_orig_emb, **kwargs):
            resp = await _orig(*args, **kwargs)
            record_llm_response(resp, kwargs.get("model"), kind="embedding")
            return resp

        emb.create = _emb_create
    except Exception:  # noqa: BLE001 — never let metering break client construction
        logger.warning("Could not attach usage metering (async)", exc_info=True)
    return client


def _meter_sync_client(client):
    """Sync twin of _meter_async_client."""
    try:
        comp = client.chat.completions
        _orig_chat = comp.create

        def _chat_create(*args, _orig=_orig_chat, **kwargs):
            resp = _orig(*args, **kwargs)
            record_llm_response(resp, kwargs.get("model"), kind="chat")
            return resp

        comp.create = _chat_create

        emb = client.embeddings
        _orig_emb = emb.create

        def _emb_create(*args, _orig=_orig_emb, **kwargs):
            resp = _orig(*args, **kwargs)
            record_llm_response(resp, kwargs.get("model"), kind="embedding")
            return resp

        emb.create = _emb_create
    except Exception:  # noqa: BLE001
        logger.warning("Could not attach usage metering (sync)", exc_info=True)
    return client


def get_async_openai(tenant_id=None, trace: bool = False) -> AsyncOpenAI:
    """Async OpenAI/Azure client for the current (or given) tenant."""
    az = _azure_for(tenant_id)
    if az:
        try:
            if az.get("provider") == "openai":
                # Tenant's own OpenAI key (models called by id — no remapping).
                return _meter_async_client(
                    AsyncOpenAI(api_key=az["api_key"], **_client_hardening())
                )
            client = AsyncAzureOpenAI(
                api_key=az["api_key"],
                azure_endpoint=az["endpoint"],
                api_version=az.get("api_version") or DEFAULT_AZURE_API_VERSION,
                **_client_hardening(),
            )
            client = _apply_async_deployment(client, (az.get("deployment") or "").strip() or None)
            return _meter_async_client(client)
        except Exception:  # noqa: BLE001 — never let a tenant's AI config break AI; fall back
            logger.warning("Tenant AI client build failed; using global OpenAI", exc_info=True)
    if trace and _langfuse_on():
        try:
            from langfuse.openai import AsyncOpenAI as LangfuseAsyncOpenAI
            return _meter_async_client(
                LangfuseAsyncOpenAI(api_key=settings.openai_api_key, **_global_client_kwargs())
            )
        except Exception:  # noqa: BLE001
            pass
    return _meter_async_client(
        AsyncOpenAI(api_key=settings.openai_api_key, **_global_client_kwargs())
    )


def get_sync_openai(tenant_id=None) -> OpenAI:
    """Sync OpenAI/Azure client for the current (or given) tenant."""
    az = _azure_for(tenant_id)
    if az:
        try:
            if az.get("provider") == "openai":
                return _meter_sync_client(
                    OpenAI(api_key=az["api_key"], **_client_hardening())
                )
            client = AzureOpenAI(
                api_key=az["api_key"],
                azure_endpoint=az["endpoint"],
                api_version=az.get("api_version") or DEFAULT_AZURE_API_VERSION,
                **_client_hardening(),
            )
            deployment = (az.get("deployment") or "").strip() or None
            if deployment:
                try:
                    comp = client.chat.completions
                    _orig = comp.create

                    def _create(*args, _orig=_orig, _dep=deployment, **kwargs):
                        return _orig(*args, **_normalize_kwargs(_dep, kwargs))

                    comp.create = _create
                except Exception:  # noqa: BLE001
                    logger.warning("Could not apply Azure deployment override (sync)", exc_info=True)
            return _meter_sync_client(client)
        except Exception:  # noqa: BLE001
            logger.warning("Azure OpenAI (sync) build failed; using global OpenAI", exc_info=True)
    return _meter_sync_client(
        OpenAI(api_key=settings.openai_api_key, **_global_client_kwargs())
    )
