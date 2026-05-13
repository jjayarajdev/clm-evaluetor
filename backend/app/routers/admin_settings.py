"""Settings and admin configuration router."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.deps import CurrentTenantId, require_role
from app.database import get_db
from app.models.tenant import Tenant
from app.models.user import Role, User
from app.services.langfuse_service import (
    get_langfuse,
    get_prompt_manager,
    flush_langfuse,
)

router = APIRouter(prefix="/api/settings", tags=["Settings"])


class LangfuseStatusResponse(BaseModel):
    """Langfuse integration status."""

    enabled: bool
    connected: bool
    host: str | None
    prompts_available: list[str]
    prompts_in_langfuse: list[str]


class PromptSyncResponse(BaseModel):
    """Response from syncing prompts to Langfuse."""

    synced: dict[str, bool]
    total: int
    successful: int
    failed: int


class PromptResponse(BaseModel):
    """Response with a prompt."""

    name: str
    text: str
    source: str  # "langfuse" or "local"
    version: str | None


@router.get("/langfuse/status", response_model=LangfuseStatusResponse)
async def get_langfuse_status(
    current_user: Annotated[User, Depends(require_role(Role.ADMIN))],
) -> LangfuseStatusResponse:
    """Get Langfuse integration status.

    Admin only.
    """
    from app.config import settings

    langfuse = get_langfuse()
    prompt_manager = get_prompt_manager()

    # Check connection
    connected = False
    prompts_in_langfuse = []

    if langfuse:
        try:
            # Try to list prompts to verify connection
            # Note: This is a simple health check
            langfuse.flush()
            connected = True

            # Try to get each local prompt from Langfuse
            for name in prompt_manager.list_local_prompts():
                try:
                    langfuse.get_prompt(name)
                    prompts_in_langfuse.append(name)
                except Exception:
                    pass
        except Exception:
            connected = False

    return LangfuseStatusResponse(
        enabled=langfuse is not None,
        connected=connected,
        host=settings.effective_langfuse_host if langfuse else None,
        prompts_available=prompt_manager.list_local_prompts(),
        prompts_in_langfuse=prompts_in_langfuse,
    )


@router.post("/langfuse/sync-prompts", response_model=PromptSyncResponse)
async def sync_prompts_to_langfuse(
    current_user: Annotated[User, Depends(require_role(Role.ADMIN))],
) -> PromptSyncResponse:
    """Sync local prompts to Langfuse.

    Creates prompts in Langfuse if they don't exist.
    Admin only.
    """
    prompt_manager = get_prompt_manager()
    results = prompt_manager.sync_to_langfuse()

    successful = sum(1 for v in results.values() if v)
    failed = sum(1 for v in results.values() if not v)

    return PromptSyncResponse(
        synced=results,
        total=len(results),
        successful=successful,
        failed=failed,
    )


@router.get("/langfuse/prompts", response_model=list[PromptResponse])
async def list_prompts(
    current_user: Annotated[User, Depends(require_role(Role.ADMIN))],
) -> list[PromptResponse]:
    """List all available prompts.

    Shows both local and Langfuse prompts.
    Admin only.
    """
    prompt_manager = get_prompt_manager()
    langfuse = get_langfuse()

    prompts = []
    for name in prompt_manager.list_local_prompts():
        source = "local"
        version = None
        text = prompt_manager._local_prompts[name]

        # Check if it's in Langfuse
        if langfuse:
            try:
                lf_prompt = langfuse.get_prompt(name)
                source = "langfuse"
                version = str(lf_prompt.version)
                text = lf_prompt.compile()
            except Exception:
                pass

        prompts.append(PromptResponse(
            name=name,
            text=text[:500] + "..." if len(text) > 500 else text,
            source=source,
            version=version,
        ))

    return prompts


@router.get("/langfuse/prompts/{name}", response_model=PromptResponse)
async def get_prompt(
    name: str,
    current_user: Annotated[User, Depends(require_role(Role.ADMIN))],
    version: str | None = None,
) -> PromptResponse:
    """Get a specific prompt by name.

    Admin only.
    """
    prompt_manager = get_prompt_manager()
    langfuse = get_langfuse()

    source = "local"
    prompt_version = None

    try:
        text = prompt_manager.get_prompt(name, version=version)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt not found: {name}",
        )

    # Check source
    if langfuse:
        try:
            lf_prompt = langfuse.get_prompt(name, version=version)
            source = "langfuse"
            prompt_version = str(lf_prompt.version)
            text = lf_prompt.compile()
        except Exception:
            pass

    return PromptResponse(
        name=name,
        text=text,
        source=source,
        version=prompt_version,
    )


@router.post("/langfuse/flush")
async def flush_langfuse_events(
    current_user: Annotated[User, Depends(require_role(Role.ADMIN))],
) -> dict[str, str]:
    """Flush pending Langfuse events.

    Admin only.
    """
    flush_langfuse()
    return {"message": "Langfuse events flushed"}


@router.delete("/langfuse/prompts/cache")
async def clear_prompt_cache(
    current_user: Annotated[User, Depends(require_role(Role.ADMIN))],
) -> dict[str, str]:
    """Clear the prompt cache.

    Forces prompts to be re-fetched from Langfuse on next use.
    Admin only.
    """
    prompt_manager = get_prompt_manager()
    prompt_manager.clear_cache()
    return {"message": "Prompt cache cleared"}


# -----------------------------------------------------------------------------
# Per-tenant extraction confidence thresholds
# -----------------------------------------------------------------------------
#
# Stored under tenant.config_overrides["confidence_thresholds"]:
#   {
#     "default": 0.7,
#     "fields": {"counterparty": 0.85, "contract_value": 0.9, ...}
#   }
#
# Tenants in regulated industries can raise thresholds on critical fields so
# low-confidence AI extractions get dropped instead of silently overwriting.

EXTRACTION_THRESHOLD_FIELDS: tuple[str, ...] = (
    "contract_type",
    "counterparty",
    "effective_date",
    "expiration_date",
    "contract_value",
    "currency",
    "jurisdiction",
)

DEFAULT_THRESHOLD = 0.7


class ExtractionThresholdsResponse(BaseModel):
    default: float
    fields: dict[str, float]
    available_fields: list[str]


class ExtractionThresholdsUpdate(BaseModel):
    default: float | None = Field(default=None, ge=0.0, le=1.0)
    fields: dict[str, float] | None = None


def _validate_field_thresholds(fields: dict[str, float] | None) -> dict[str, float]:
    if not fields:
        return {}
    cleaned: dict[str, float] = {}
    for k, v in fields.items():
        if k not in EXTRACTION_THRESHOLD_FIELDS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown field '{k}'. Allowed: {list(EXTRACTION_THRESHOLD_FIELDS)}",
            )
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Threshold for '{k}' must be a number in [0.0, 1.0]",
            )
        if not (0.0 <= f <= 1.0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Threshold for '{k}' must be in [0.0, 1.0]",
            )
        cleaned[k] = f
    return cleaned


@router.get("/extraction-thresholds", response_model=ExtractionThresholdsResponse)
async def get_extraction_thresholds(
    tenant_id: CurrentTenantId,
    current_user: Annotated[User, Depends(require_role(Role.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExtractionThresholdsResponse:
    """Get the per-field confidence thresholds for the current tenant.

    Falls back to the platform default (0.7) when no overrides exist.
    """
    if tenant_id is None:
        # Super admin without an active tenant — return defaults
        return ExtractionThresholdsResponse(
            default=DEFAULT_THRESHOLD,
            fields={},
            available_fields=list(EXTRACTION_THRESHOLD_FIELDS),
        )

    tenant = await db.get(Tenant, tenant_id)
    cfg = (tenant.config_overrides or {}).get("confidence_thresholds") if tenant else {}
    cfg = cfg or {}

    default = cfg.get("default") if isinstance(cfg.get("default"), (int, float)) else DEFAULT_THRESHOLD
    fields_cfg = cfg.get("fields") or {}
    fields = {k: float(v) for k, v in fields_cfg.items()
              if k in EXTRACTION_THRESHOLD_FIELDS and isinstance(v, (int, float))}

    return ExtractionThresholdsResponse(
        default=float(default),
        fields=fields,
        available_fields=list(EXTRACTION_THRESHOLD_FIELDS),
    )


@router.put("/extraction-thresholds", response_model=ExtractionThresholdsResponse)
async def update_extraction_thresholds(
    payload: ExtractionThresholdsUpdate,
    tenant_id: CurrentTenantId,
    current_user: Annotated[User, Depends(require_role(Role.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExtractionThresholdsResponse:
    """Update per-field confidence thresholds for the current tenant.

    Sending ``fields: {}`` clears all per-field overrides.
    Sending ``default: null`` leaves the default unchanged.
    """
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot set thresholds without an active tenant. Switch tenant context first.",
        )

    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    fields_clean = _validate_field_thresholds(payload.fields)

    overrides = dict(tenant.config_overrides or {})
    ct_cfg = dict(overrides.get("confidence_thresholds") or {})

    if payload.default is not None:
        ct_cfg["default"] = float(payload.default)
    elif "default" not in ct_cfg:
        ct_cfg["default"] = DEFAULT_THRESHOLD

    # PUT semantics: replace the field map (empty dict clears all overrides)
    if payload.fields is not None:
        ct_cfg["fields"] = fields_clean

    overrides["confidence_thresholds"] = ct_cfg
    tenant.config_overrides = overrides
    flag_modified(tenant, "config_overrides")
    await db.commit()
    await db.refresh(tenant)

    final_cfg = (tenant.config_overrides or {}).get("confidence_thresholds") or {}
    return ExtractionThresholdsResponse(
        default=float(final_cfg.get("default", DEFAULT_THRESHOLD)),
        fields={k: float(v) for k, v in (final_cfg.get("fields") or {}).items()
                if k in EXTRACTION_THRESHOLD_FIELDS},
        available_fields=list(EXTRACTION_THRESHOLD_FIELDS),
    )


# -----------------------------------------------------------------------------
# DSPy auto-recompile config
# -----------------------------------------------------------------------------
#
# Stored under tenant.config_overrides["dspy_auto_recompile"]:
#   {
#     "enabled": false,        # opt-in; off by default
#     "threshold": 5           # min new "correct" verifications since last
#                              # compile before a background recompile fires
#   }
#
# When enabled, the /verify and /verify/bulk endpoints schedule a background
# task that calls dspy_compiler.maybe_auto_recompile() after the response is
# sent. See app.routers.extraction_quality._bg_auto_recompile.

DSPY_AUTO_RECOMPILE_DEFAULT_THRESHOLD = 5
DSPY_AUTO_RECOMPILE_DEFAULT_ENABLED = False


class DspyAutoRecompileResponse(BaseModel):
    enabled: bool
    threshold: int


class DspyAutoRecompileUpdate(BaseModel):
    enabled: bool | None = None
    threshold: int | None = Field(default=None, ge=1, le=100)


@router.get("/dspy-auto-recompile", response_model=DspyAutoRecompileResponse)
async def get_dspy_auto_recompile(
    tenant_id: CurrentTenantId,
    current_user: Annotated[User, Depends(require_role(Role.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DspyAutoRecompileResponse:
    """Get the current tenant's DSPy auto-recompile config.

    Falls back to platform defaults (disabled, threshold=5).
    """
    if tenant_id is None:
        return DspyAutoRecompileResponse(
            enabled=DSPY_AUTO_RECOMPILE_DEFAULT_ENABLED,
            threshold=DSPY_AUTO_RECOMPILE_DEFAULT_THRESHOLD,
        )

    tenant = await db.get(Tenant, tenant_id)
    cfg = (tenant.config_overrides or {}).get("dspy_auto_recompile") if tenant else {}
    cfg = cfg or {}

    return DspyAutoRecompileResponse(
        enabled=bool(cfg.get("enabled", DSPY_AUTO_RECOMPILE_DEFAULT_ENABLED)),
        threshold=int(cfg.get("threshold", DSPY_AUTO_RECOMPILE_DEFAULT_THRESHOLD)),
    )


@router.put("/dspy-auto-recompile", response_model=DspyAutoRecompileResponse)
async def update_dspy_auto_recompile(
    payload: DspyAutoRecompileUpdate,
    tenant_id: CurrentTenantId,
    current_user: Annotated[User, Depends(require_role(Role.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DspyAutoRecompileResponse:
    """Update the current tenant's DSPy auto-recompile config.

    Sending only ``enabled`` or only ``threshold`` updates that single field.
    """
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot configure auto-recompile without an active tenant.",
        )

    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    overrides = dict(tenant.config_overrides or {})
    cfg = dict(overrides.get("dspy_auto_recompile") or {})

    if payload.enabled is not None:
        cfg["enabled"] = bool(payload.enabled)
    elif "enabled" not in cfg:
        cfg["enabled"] = DSPY_AUTO_RECOMPILE_DEFAULT_ENABLED

    if payload.threshold is not None:
        cfg["threshold"] = int(payload.threshold)
    elif "threshold" not in cfg:
        cfg["threshold"] = DSPY_AUTO_RECOMPILE_DEFAULT_THRESHOLD

    overrides["dspy_auto_recompile"] = cfg
    tenant.config_overrides = overrides
    flag_modified(tenant, "config_overrides")
    await db.commit()
    await db.refresh(tenant)

    final_cfg = (tenant.config_overrides or {}).get("dspy_auto_recompile") or {}
    return DspyAutoRecompileResponse(
        enabled=bool(final_cfg.get("enabled", DSPY_AUTO_RECOMPILE_DEFAULT_ENABLED)),
        threshold=int(final_cfg.get("threshold", DSPY_AUTO_RECOMPILE_DEFAULT_THRESHOLD)),
    )
