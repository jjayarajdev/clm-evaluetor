"""Base agent utilities and tools for contract analysis."""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from langfuse import Langfuse
from langfuse.openai import AsyncOpenAI as LangfuseAsyncOpenAI
from openai import AsyncOpenAI
from pydantic import BaseModel

# Try to import decorators (available in newer versions)
try:
    from langfuse.decorators import observe, langfuse_context
    LANGFUSE_DECORATORS_AVAILABLE = True
except ImportError:
    LANGFUSE_DECORATORS_AVAILABLE = False
    # Create a no-op decorator
    def observe(name: str = None, **kwargs):
        def decorator(func):
            return func
        return decorator
    langfuse_context = None

from app.config import settings
from app.services.vector_store import get_vector_store, QueryResult
from app.services.langfuse_service import (
    get_langfuse,
    get_prompt_manager,
    set_user_context,
)

logger = logging.getLogger(__name__)

# Initialize Langfuse client if configured
langfuse_client: Langfuse | None = None
if settings.langfuse_public_key and settings.langfuse_secret_key:
    try:
        langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.effective_langfuse_host,
        )
        # Use Langfuse-wrapped OpenAI client for automatic tracing
        openai_client = LangfuseAsyncOpenAI(api_key=settings.openai_api_key)
        logger.info("Langfuse integration enabled for agent LLM calls")
    except Exception as e:
        logger.warning(f"Failed to initialize Langfuse: {e}")
        openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
else:
    # Fall back to standard OpenAI client
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


@dataclass
class AgentConfig:
    """Configuration for creating an agent."""

    name: str
    description: str
    system_prompt: str
    model_id: str = field(default_factory=lambda: settings.openai_model)
    temperature: float = 0.1
    max_tokens: int = 2000
    streaming: bool = False
    tools: list[Any] = field(default_factory=list)


class ContractSearchTool:
    """Tool for searching contract chunks in ChromaDB.

    This tool is used by agents to retrieve relevant contract context
    for RAG-based question answering and analysis.
    """

    def __init__(
        self,
        user_id: str | None = None,
        user_role: str | None = None,
        contract_id: str | None = None,
        tenant_id: str | None = None,
        n_results: int = 10,
    ) -> None:
        """Initialize the search tool.

        Args:
            user_id: User ID for RBAC filtering.
            user_role: User role for RBAC filtering.
            contract_id: Optional contract ID to scope search.
            tenant_id: Tenant ID for isolation.
            n_results: Number of results to retrieve.
        """
        self.vector_store = get_vector_store()
        self.user_id = user_id
        self.user_role = user_role
        self.contract_id = contract_id
        self.tenant_id = tenant_id
        self.n_results = n_results

    def search(
        self,
        query: str,
        section_types: list[str] | None = None,
        semantic_tags: list[str] | None = None,
    ) -> list[QueryResult]:
        """Search for relevant contract chunks with optional semantic filtering.

        Args:
            query: Search query text.
            section_types: Optional filter by section types (e.g., ["payment", "terms"]).
            semantic_tags: Optional filter by semantic tags (e.g., ["auto_renewal"]).

        Returns:
            List of QueryResult with relevant chunks.
        """
        return self.vector_store.query_similar(
            query_text=query,
            top_k=self.n_results,
            contract_id=self.contract_id,
            section_types=section_types,
            semantic_tags=semantic_tags,
            user_id=self.user_id,
            user_role=self.user_role,
            tenant_id=self.tenant_id,
        )

    def search_by_section_type(self, section_types: list[str]) -> list[QueryResult]:
        """Get chunks by semantic section type without similarity search.

        Args:
            section_types: Section types to retrieve (e.g., ["payment", "liability"]).

        Returns:
            List of QueryResult matching section types.
        """
        if not self.contract_id:
            return []
        return self.vector_store.query_by_section_type(
            contract_id=self.contract_id,
            section_types=section_types,
            top_k=self.n_results,
        )

    def search_with_context(self, query: str) -> str:
        """Search and format results as context string.

        Args:
            query: Search query text.

        Returns:
            Formatted context string for LLM consumption.
        """
        results = self.search(query)

        if not results:
            return "No relevant contract content found."

        context_parts = []
        for i, result in enumerate(results, 1):
            metadata = result.metadata or {}
            context_parts.append(
                f"[Source {i}]\n"
                f"Contract: {metadata.get('contract_id', 'Unknown')}\n"
                f"Section: {metadata.get('section_number', 'N/A')}\n"
                f"Page: {metadata.get('page_number', 'N/A')}\n"
                f"Relevance: {result.distance:.2f}\n"
                f"Content:\n{result.text}\n"
            )

        return "\n---\n".join(context_parts)

    def get_tool_definition(self) -> dict[str, Any]:
        """Get OpenAI function tool definition for this tool.

        Returns:
            Tool definition dictionary for OpenAI function calling.
        """
        return {
            "type": "function",
            "function": {
                "name": "search_contracts",
                "description": "Search contract documents for relevant information. Use this to find specific clauses, terms, or information in contracts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to find relevant contract content",
                        },
                        "contract_id": {
                            "type": "string",
                            "description": "Optional: specific contract ID to search within",
                        },
                    },
                    "required": ["query"],
                },
            },
        }

    def execute_tool_call(self, arguments: dict[str, Any]) -> str:
        """Execute a tool call from the agent.

        Args:
            arguments: Tool call arguments.

        Returns:
            Search results as formatted string.
        """
        query = arguments.get("query", "")
        contract_id = arguments.get("contract_id") or self.contract_id

        if contract_id:
            # Temporarily override contract_id for this search
            original = self.contract_id
            self.contract_id = contract_id
            result = self.search_with_context(query)
            self.contract_id = original
            return result

        return self.search_with_context(query)


class SourceCitation(BaseModel):
    """Citation for a source used in an answer."""

    contract_id: str
    filename: str | None = None
    section_number: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    relevance_score: float | None = None
    excerpt: str | None = None
    chunk_index: int | None = None


class AgentOutput(BaseModel):
    """Structured output from an agent."""

    response: str
    confidence: float | None = None
    sources: list[SourceCitation] = []
    follow_up_questions: list[str] = []
    metadata: dict[str, Any] = {}


@observe(name="run_agent")
async def run_agent(
    config: AgentConfig,
    user_message: str,
    context: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    contract_id: str | None = None,
) -> str:
    """Run an agent with the given configuration and message.

    Args:
        config: Agent configuration.
        user_message: User's message/question.
        context: Optional context to include.
        user_id: User ID for Langfuse tracking.
        session_id: Session ID for conversation grouping.
        contract_id: Contract ID for metadata.

    Returns:
        Agent's response text.
    """
    # Set user context for Langfuse tracking
    if user_id and LANGFUSE_DECORATORS_AVAILABLE and langfuse_context:
        try:
            langfuse_context.update_current_observation(
                user_id=user_id,
                session_id=session_id,
                metadata={
                    "agent_name": config.name,
                    "contract_id": contract_id,
                },
            )
        except Exception:
            pass  # Langfuse context may not be available

    # Try to get prompt from Langfuse, fall back to config
    system_prompt = config.system_prompt
    try:
        prompt_manager = get_prompt_manager()
        managed_prompt = prompt_manager.get_prompt(config.name)
        if managed_prompt:
            system_prompt = managed_prompt
    except Exception:
        pass  # Use config prompt as fallback

    messages = [
        {"role": "system", "content": system_prompt},
    ]

    if context:
        messages.append({
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion/Task:\n{user_message}"
        })
    else:
        messages.append({"role": "user", "content": user_message})

    from app.core.llm import get_async_openai
    response = await get_async_openai(trace=True).chat.completions.create(
        model=config.model_id,
        messages=messages,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )

    return response.choices[0].message.content or ""


def inject_context(
    query: str,
    search_tool: ContractSearchTool,
    max_context_length: int = 32000,
    kg_context: str | None = None,
) -> str:
    """Inject relevant context into a query for RAG.

    Args:
        query: Original user query.
        search_tool: Search tool to retrieve context.
        max_context_length: Maximum context length in characters (default 32KB for GPT-4).
        kg_context: Optional knowledge graph context to include.

    Returns:
        Query with injected context.
    """
    context = search_tool.search_with_context(query)

    # Include knowledge graph context if available
    if kg_context:
        context = f"KNOWLEDGE GRAPH CONTEXT:\n{kg_context}\n\n---\n\nDOCUMENT CONTEXT:\n{context}"

    # Truncate context if too long (32KB is safe for GPT-4's 128K context)
    if len(context) > max_context_length:
        context = context[:max_context_length] + "\n\n[Context truncated...]"

    return f"""Based on the following contract context, please answer the question.

CONTEXT:
{context}

QUESTION:
{query}

Please provide a clear, accurate answer based on the context above. Use the knowledge graph entities and relationships to resolve terms (e.g., "Provider" refers to a specific company) and understand obligations. If the answer cannot be found in the context, say so clearly."""


async def get_kg_context_for_query(
    query: str,
    contract_id: str,
    tenant_id: str,
) -> str | None:
    """Get relevant knowledge graph context for a query.

    Extracts relevant entities, resolved terms, and relationships
    from the knowledge graph to enhance Q&A responses.

    Args:
        query: User's query.
        contract_id: Contract ID to search.
        tenant_id: Tenant ID for isolation.

    Returns:
        Formatted knowledge graph context or None if unavailable.
    """
    try:
        from app.database import async_session_maker
        from app.services.knowledge_graph_service import get_knowledge_graph_service

        async with async_session_maker() as db:
            service = await get_knowledge_graph_service(db)

            # Get entities that might be relevant to the query
            context_parts = []

            # Extract potential term references from the query
            query_lower = query.lower()

            # Key terms that often need resolution
            key_terms = [
                "provider", "client", "customer", "vendor", "service", "company",
                "party", "parties", "effective date", "termination", "renewal",
            ]

            # Look for terms mentioned in the query
            resolved_terms = []
            for term in key_terms:
                if term in query_lower:
                    resolution = await service.resolve_term(contract_id, term)
                    if resolution.definition or resolution.resolved_entity:
                        resolved_terms.append(
                            f"- \"{term.title()}\" refers to: {resolution.definition or resolution.resolved_entity.name}"
                        )
                        # If it's a resolved entity, check for portfolio-wide context
                        if resolution.resolved_entity and resolution.resolved_entity.id:
                            timeline = await service.get_entity_timeline(resolution.resolved_entity.id)
                            if len(timeline) > 1:
                                resolved_terms.append(
                                    f"  (This entity appears in {len(timeline)} contracts/amendments in this portfolio)"
                                )

            if resolved_terms:
                context_parts.append("TERM DEFINITIONS & PORTFOLIO CONTEXT:\n" + "\n".join(resolved_terms))

            # Get party obligations if query mentions obligations or parties
            if any(word in query_lower for word in ["obligation", "must", "shall", "duty", "responsible", "liability"]):
                try:
                    party_obligations = await service.get_party_obligations(contract_id)
                    if party_obligations:
                        obl_lines = []
                        for po in party_obligations[:3]:  # Top 3 parties
                            for obl in po.obligations[:3]:  # Top 3 obligations per party
                                limits = ", ".join(
                                    f"capped at {l.properties.get('value', 'N/A')} {l.properties.get('currency', '')}"
                                    for l in obl.limited_by
                                ) if obl.limited_by else "no cap specified"
                                obl_lines.append(
                                    f"- {po.party_name} has obligation: {obl.obligation_name} ({limits})"
                                )
                        if obl_lines:
                            context_parts.append("PARTY OBLIGATIONS:\n" + "\n".join(obl_lines))
                except Exception:
                    pass  # Skip if obligation lookup fails

            # Get graph stats as overview
            try:
                graph = await service.get_full_graph(contract_id, tenant_id)
                if graph.stats.total_entities > 0:
                    summary_parts = []
                    for entity_type, count in graph.stats.entities_by_type.items():
                        summary_parts.append(f"{count} {entity_type}(s)")
                    context_parts.append(
                        f"CONTRACT ENTITIES: {', '.join(summary_parts)}"
                    )
            except Exception:
                pass

            if context_parts:
                return "\n\n".join(context_parts)

    except Exception as e:
        logger.warning(f"Failed to get KG context: {e}")

    return None


def extract_confidence(response: str) -> float | None:
    """Extract confidence score from agent response.

    Args:
        response: Agent response text.

    Returns:
        Confidence score (0.0-1.0) or None if not found.
    """
    import re

    patterns = [
        r"confidence[:\s]+(\d+(?:\.\d+)?)\s*%",
        r"(\d+(?:\.\d+)?)\s*%\s*confiden",
        r"confidence[:\s]+(\d+(?:\.\d+)?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            return value / 100 if value > 1 else value

    return None


class AgentResponseError(Exception):
    """Raised when an agent response could not be interpreted as a usable
    result — e.g. the model output was truncated (finish_reason == "length")
    or the JSON could not be parsed at all.

    Callers on the extraction pipeline MUST let this propagate (or convert it
    into a recorded *failed* stage) rather than swallowing it into an empty /
    zero result. A truncated high-risk contract silently reported as LOW/0 is
    the exact data-loss bug this exception exists to prevent.
    """


class LLMTruncationError(AgentResponseError):
    """The LLM stopped because it hit max_tokens (finish_reason == "length").

    The response is incomplete, so any parsed result is at best partial and
    must not be treated as a complete "nothing found" answer.
    """


def _find_balanced_span(text: str, open_ch: str, close_ch: str) -> str | None:
    """Return the first top-level balanced ``open_ch..close_ch`` span in ``text``.

    Uses a depth scanner that is string-literal aware (so braces/brackets inside
    JSON string values don't confuse the balance), unlike a greedy regex which
    mis-captures when there is prose or multiple blocks around the JSON.

    Returns the substring including the delimiters, or None if no opener found.
    If the span never closes (truncated output), returns from the opener to the
    end of the string so the caller can attempt a salvage.
    """
    start = text.find(open_ch)
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    # Never balanced — truncated. Hand back the tail for salvage.
    return text[start:]


def _salvage_truncated_json(fragment: str) -> Any | None:
    """Best-effort recovery of a truncated JSON object/array.

    Strategy: walk the fragment tracking bracket depth (string-literal aware),
    remember the position of the last point where we were back at depth 1 having
    just completed an element (i.e. a valid place to close the container), trim
    the fragment there, and append the missing closing brackets.

    For an array this yields the complete prefix of elements. For an object it
    yields the complete prefix of key/value pairs. Returns the parsed value or
    None if nothing salvageable.
    """
    fragment = fragment.strip()
    if not fragment or fragment[0] not in "{[":
        return None

    stack: list[str] = []
    in_string = False
    escape = False
    # Index of the last position, at the OUTER container's inner depth
    # (len(stack) == 1), that is a valid place to cut so the retained prefix
    # holds only complete elements/pairs. Two such boundaries exist:
    #   * a comma at depth 1 — separates complete array elements / object pairs
    #     (we trim *before* it), and
    #   * the close of a nested value at depth 1 — a whole element just finished
    #     (we trim *after* it).
    # We deliberately do NOT treat bare scalars or lone strings at depth 1 as
    # boundaries: a depth-1 string may be an object *key* whose value hasn't
    # arrived yet, and cutting there would leave a dangling key.
    last_safe = -1

    for i, ch in enumerate(fragment):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack:
                stack.pop()
            if len(stack) == 1:
                last_safe = i + 1
        elif ch == "," and len(stack) == 1:
            last_safe = i  # trim before the dangling comma

    # Try progressively: full fragment closed, then trimmed-to-last-safe closed.
    candidates: list[str] = []
    if stack:
        candidates.append(fragment + "".join(reversed(stack)))
    if last_safe > 0:
        head = fragment[:last_safe].rstrip().rstrip(",")
        # Recompute the closers needed for the trimmed head.
        depth_stack: list[str] = []
        s2 = e2 = False
        for ch in head:
            if s2:
                if e2:
                    e2 = False
                elif ch == "\\":
                    e2 = True
                elif ch == '"':
                    s2 = False
                continue
            if ch == '"':
                s2 = True
            elif ch in "{[":
                depth_stack.append("}" if ch == "{" else "]")
            elif ch in "}]" and depth_stack:
                depth_stack.pop()
        candidates.append(head + "".join(reversed(depth_stack)))

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def extract_json_from_response(
    response: str,
    finish_reason: str | None = None,
) -> dict[str, Any] | list[Any] | None:
    """Extract JSON (object OR top-level array) from an agent response.

    Robust parsing strategy, in order:
      1. Whole-string ``json.loads`` (fast path for clean JSON).
      2. Markdown code-fence contents (```json ... ```).
      3. A depth-balanced, string-literal-aware scan for the first top-level
         ``{...}`` or ``[...]`` — not a greedy regex (which mis-captures when
         prose or multiple blocks surround the JSON).
      4. Best-effort salvage of *truncated* JSON (model hit max_tokens): trim to
         the last complete array element / object pair and balance the brackets.

    Args:
        response: Agent response text.
        finish_reason: OpenAI finish_reason for the call, when available. When
            it is ``"length"`` the output is truncated; we salvage the complete
            prefix if we can, otherwise raise :class:`LLMTruncationError` rather
            than return a None that a caller would misread as "nothing found".

    Returns:
        Parsed dict or list, or None ONLY when the text genuinely contains no
        JSON and the call was not truncated.

    Raises:
        LLMTruncationError: output was truncated and nothing could be salvaged.
    """
    import re

    if response is None:
        response = ""
    text = response.strip()

    # 1. Whole-string parse (handles bare object or bare top-level array).
    if text:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # 2. Markdown code fence.
    fence = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", response)
    if fence:
        inner = fence.group(1).strip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            # Fence may itself be truncated (no closing ```): salvage below on
            # the inner text if it starts a container.
            salvaged = _salvage_truncated_json(inner)
            if salvaged is not None:
                return salvaged

    # 3. Depth-balanced scan for the first top-level object or array. Prefer
    #    whichever delimiter appears first in the text.
    obj_at = response.find("{")
    arr_at = response.find("[")
    order: list[tuple[str, str]] = []
    if arr_at != -1 and (obj_at == -1 or arr_at < obj_at):
        order = [("[", "]"), ("{", "}")]
    else:
        order = [("{", "}"), ("[", "]")]

    for open_ch, close_ch in order:
        span = _find_balanced_span(response, open_ch, close_ch)
        if span is None:
            continue
        try:
            return json.loads(span)
        except json.JSONDecodeError:
            # 4. Truncation salvage on the (possibly unbalanced) span.
            salvaged = _salvage_truncated_json(span)
            if salvaged is not None:
                return salvaged

    # Nothing parsed. If the model was truncated, this is a FAILURE, not an
    # empty result — signal it loudly so the pipeline records a failed stage.
    if finish_reason == "length":
        raise LLMTruncationError(
            "LLM response was truncated (finish_reason=length) and no complete "
            "JSON prefix could be salvaged."
        )

    return None
