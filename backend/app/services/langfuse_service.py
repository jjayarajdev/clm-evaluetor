"""Langfuse integration service for user tracking and prompt management."""

import logging
from functools import lru_cache
from typing import Any

from langfuse import Langfuse

# Try to import decorators (available in newer versions)
try:
    from langfuse.decorators import observe, langfuse_context
    LANGFUSE_DECORATORS_AVAILABLE = True
except ImportError:
    LANGFUSE_DECORATORS_AVAILABLE = False
    observe = None
    langfuse_context = None

from app.config import settings

logger = logging.getLogger(__name__)

# Global Langfuse client
_langfuse_client: Langfuse | None = None


def get_langfuse() -> Langfuse | None:
    """Get or create the global Langfuse client."""
    global _langfuse_client

    if _langfuse_client is None:
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            try:
                _langfuse_client = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.effective_langfuse_host,
                )
                logger.info("Langfuse client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse: {e}")

    return _langfuse_client


def set_user_context(
    user_id: str,
    session_id: str | None = None,
    user_metadata: dict[str, Any] | None = None,
) -> None:
    """Set user context for the current trace.

    Call this at the start of a request to associate all subsequent
    LLM calls with the user.

    Args:
        user_id: Unique user identifier (e.g., user UUID)
        session_id: Optional session identifier for grouping conversations
        user_metadata: Optional metadata about the user (role, email, etc.)
    """
    if not LANGFUSE_DECORATORS_AVAILABLE or langfuse_context is None:
        return

    try:
        langfuse_context.update_current_trace(
            user_id=user_id,
            session_id=session_id,
            metadata=user_metadata or {},
        )
    except Exception as e:
        logger.debug(f"Could not set user context: {e}")


def flush_langfuse() -> None:
    """Flush any pending Langfuse events."""
    client = get_langfuse()
    if client:
        try:
            client.flush()
        except Exception as e:
            logger.debug(f"Failed to flush Langfuse: {e}")


class PromptManager:
    """Manages prompts with Langfuse integration.

    Provides:
    - Fetching prompts from Langfuse with local fallback
    - Caching for performance
    - Version tracking
    """

    # Local fallback prompts (used when Langfuse is unavailable)
    _local_prompts: dict[str, str] = {
        "contract_qa": """You are a Contract Intelligence Assistant specializing in analyzing legal contracts.

Your capabilities:
- Answer questions about contract terms, clauses, and obligations
- Identify risks and compliance issues
- Explain legal terminology in plain language
- Compare contract provisions

Always cite specific sections when referencing contract content.
If information is not found in the provided context, clearly state that.""",

        "clause_extraction": """You are an expert legal analyst specializing in contract clause extraction.

Your task is to identify and extract specific clause types from contract text:
- Termination clauses
- Liability and indemnification clauses
- Payment terms
- Confidentiality provisions
- Force majeure clauses
- Notice requirements
- Governing law and jurisdiction

For each clause found, provide:
1. The clause type
2. The exact text
3. A risk assessment (low/medium/high)
4. Key obligations or requirements""",

        "obligation_tracking": """You are an expert at identifying contractual obligations.

Extract all obligations from the contract text, including:
- Payment obligations (amounts, due dates, conditions)
- Delivery obligations (what, when, where)
- Reporting requirements (frequency, format, recipients)
- Compliance requirements (regulations, standards)
- Notification obligations (events, timeframes)
- Performance obligations (SLAs, KPIs, metrics)

For each obligation, identify:
1. The obligated party (who must perform)
2. The obligation description
3. The deadline or frequency
4. Any conditions or triggers
5. Consequences of non-compliance""",

        "risk_assessment": """You are a legal risk analyst specializing in contract risk assessment.

Analyze contracts for potential risks including:
- Unlimited liability exposure
- Unfavorable indemnification terms
- Automatic renewal traps
- Inadequate termination rights
- Missing limitation of liability
- Broad IP assignment clauses
- Onerous confidentiality terms
- Unclear payment terms
- Missing force majeure protection

Provide a risk score (1-100) and detailed risk breakdown.""",

        "summary_generation": """You are an expert at creating clear, concise contract summaries.

Create a structured summary including:
- Contract type and purpose
- Key parties and their roles
- Important dates (effective, expiration, renewal)
- Financial terms (value, payment schedule)
- Main obligations of each party
- Notable risks or unusual terms
- Recommended actions or next steps

Keep the summary actionable and highlight what matters most.""",

        "comparison": """You are an expert at comparing contract documents.

When comparing contracts:
- Identify differences in key terms
- Highlight missing clauses in either document
- Note changes in obligations or rights
- Flag risk level changes
- Summarize what has improved or worsened

Present differences in a clear, structured format.""",

        "schema_extraction": """You are an expert at extracting structured data from contracts.

Extract data according to the provided schema, ensuring:
- All required fields are populated
- Data types are correct
- Values are normalized (dates, currencies, etc.)
- Confidence scores reflect extraction certainty

If a field cannot be extracted, explain why.""",
    }

    def __init__(self) -> None:
        """Initialize the prompt manager."""
        self._langfuse = get_langfuse()
        self._cache: dict[str, tuple[str, str | None]] = {}  # name -> (prompt, version)

    def get_prompt(
        self,
        name: str,
        version: str | None = None,
        fallback: str | None = None,
    ) -> str:
        """Get a prompt by name from Langfuse or local fallback.

        Args:
            name: Prompt name/identifier
            version: Optional specific version (default: latest)
            fallback: Optional custom fallback if not in local prompts

        Returns:
            The prompt text
        """
        # Try cache first
        cache_key = f"{name}:{version or 'latest'}"
        if cache_key in self._cache:
            return self._cache[cache_key][0]

        # Try Langfuse
        if self._langfuse:
            try:
                prompt = self._langfuse.get_prompt(name, version=version)
                prompt_text = prompt.compile()
                self._cache[cache_key] = (prompt_text, prompt.version)
                logger.debug(f"Loaded prompt '{name}' v{prompt.version} from Langfuse")
                return prompt_text
            except Exception as e:
                logger.debug(f"Prompt '{name}' not found in Langfuse: {e}")

        # Fall back to local prompts
        if name in self._local_prompts:
            prompt_text = self._local_prompts[name]
            self._cache[cache_key] = (prompt_text, "local")
            return prompt_text

        # Use custom fallback or raise
        if fallback:
            return fallback

        raise ValueError(f"Prompt not found: {name}")

    def get_prompt_with_variables(
        self,
        name: str,
        variables: dict[str, Any],
        version: str | None = None,
    ) -> str:
        """Get a prompt and compile it with variables.

        Args:
            name: Prompt name
            variables: Variables to substitute in the prompt
            version: Optional version

        Returns:
            Compiled prompt text
        """
        if self._langfuse:
            try:
                prompt = self._langfuse.get_prompt(name, version=version)
                return prompt.compile(**variables)
            except Exception as e:
                logger.debug(f"Failed to get prompt from Langfuse: {e}")

        # Fall back to simple string formatting
        base_prompt = self.get_prompt(name, version)
        try:
            return base_prompt.format(**variables)
        except KeyError:
            # If formatting fails, return base prompt
            return base_prompt

    def clear_cache(self) -> None:
        """Clear the prompt cache."""
        self._cache.clear()

    def list_local_prompts(self) -> list[str]:
        """List available local prompt names."""
        return list(self._local_prompts.keys())

    def sync_to_langfuse(self) -> dict[str, bool]:
        """Sync local prompts to Langfuse (creates if not exists).

        Returns:
            Dict of prompt name -> success status
        """
        if not self._langfuse:
            return {name: False for name in self._local_prompts}

        results = {}
        for name, text in self._local_prompts.items():
            try:
                # Check if prompt exists
                try:
                    self._langfuse.get_prompt(name)
                    results[name] = True  # Already exists
                    logger.debug(f"Prompt '{name}' already exists in Langfuse")
                except Exception:
                    # Create the prompt with 'production' label so it's fetchable by default
                    self._langfuse.create_prompt(
                        name=name,
                        prompt=text,
                        labels=["production", "contract-intel", "auto-synced"],
                    )
                    results[name] = True
                    logger.info(f"Created prompt '{name}' in Langfuse")
            except Exception as e:
                logger.warning(f"Failed to sync prompt '{name}': {e}")
                results[name] = False

        return results


# Global prompt manager instance
_prompt_manager: PromptManager | None = None


def get_prompt_manager() -> PromptManager:
    """Get the global prompt manager instance."""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager


# Convenience function for getting prompts
def get_prompt(name: str, version: str | None = None) -> str:
    """Get a prompt by name.

    Args:
        name: Prompt name
        version: Optional version

    Returns:
        Prompt text
    """
    return get_prompt_manager().get_prompt(name, version)
