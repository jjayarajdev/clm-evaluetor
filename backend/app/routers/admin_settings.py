"""Settings and admin configuration router."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.deps import require_role
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
