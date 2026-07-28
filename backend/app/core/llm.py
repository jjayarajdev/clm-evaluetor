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

logger = logging.getLogger(__name__)

# Current tenant for LLM resolution. None => use the global client.
current_tenant_id: ContextVar[str | None] = ContextVar("llm_current_tenant_id", default=None)

DEFAULT_AZURE_API_VERSION = "2024-08-01-preview"

# tenant_id(str) -> azure config dict {endpoint, api_key, api_version}. In-memory,
# refreshed at startup and on save so the (sync) factory needs no DB access.
_azure_cache: dict[str, dict] = {}


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


def _azure_for(tenant_id) -> dict | None:
    tid = tenant_id if tenant_id is not None else current_tenant_id.get()
    return _azure_cache.get(str(tid)) if tid is not None else None


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


def get_async_openai(tenant_id=None, trace: bool = False) -> AsyncOpenAI:
    """Async OpenAI/Azure client for the current (or given) tenant."""
    az = _azure_for(tenant_id)
    if az:
        try:
            if az.get("provider") == "openai":
                # Tenant's own OpenAI key (models called by id — no remapping).
                return AsyncOpenAI(api_key=az["api_key"])
            client = AsyncAzureOpenAI(
                api_key=az["api_key"],
                azure_endpoint=az["endpoint"],
                api_version=az.get("api_version") or DEFAULT_AZURE_API_VERSION,
            )
            return _apply_async_deployment(client, (az.get("deployment") or "").strip() or None)
        except Exception:  # noqa: BLE001 — never let a tenant's AI config break AI; fall back
            logger.warning("Tenant AI client build failed; using global OpenAI", exc_info=True)
    if trace and _langfuse_on():
        try:
            from langfuse.openai import AsyncOpenAI as LangfuseAsyncOpenAI
            return LangfuseAsyncOpenAI(api_key=settings.openai_api_key)
        except Exception:  # noqa: BLE001
            pass
    return AsyncOpenAI(api_key=settings.openai_api_key)


def get_sync_openai(tenant_id=None) -> OpenAI:
    """Sync OpenAI/Azure client for the current (or given) tenant."""
    az = _azure_for(tenant_id)
    if az:
        try:
            if az.get("provider") == "openai":
                return OpenAI(api_key=az["api_key"])
            client = AzureOpenAI(
                api_key=az["api_key"],
                azure_endpoint=az["endpoint"],
                api_version=az.get("api_version") or DEFAULT_AZURE_API_VERSION,
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
            return client
        except Exception:  # noqa: BLE001
            logger.warning("Azure OpenAI (sync) build failed; using global OpenAI", exc_info=True)
    return OpenAI(api_key=settings.openai_api_key)
