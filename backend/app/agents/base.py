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

    response = await openai_client.chat.completions.create(
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
) -> str:
    """Inject relevant context into a query for RAG.

    Args:
        query: Original user query.
        search_tool: Search tool to retrieve context.
        max_context_length: Maximum context length in characters (default 32KB for GPT-4).

    Returns:
        Query with injected context.
    """
    context = search_tool.search_with_context(query)

    # Truncate context if too long (32KB is safe for GPT-4's 128K context)
    if len(context) > max_context_length:
        context = context[:max_context_length] + "\n\n[Context truncated...]"

    return f"""Based on the following contract context, please answer the question.

CONTEXT:
{context}

QUESTION:
{query}

Please provide a clear, accurate answer based on the context above. If the answer cannot be found in the context, say so clearly."""


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


def extract_json_from_response(response: str) -> dict[str, Any] | None:
    """Extract JSON data from an agent response.

    Args:
        response: Agent response text.

    Returns:
        Parsed JSON dictionary or None if not found.
    """
    import re

    # Try to find JSON block in markdown code fence
    json_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", response)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find raw JSON object
    json_match = re.search(r"\{[\s\S]*\}", response)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return None
