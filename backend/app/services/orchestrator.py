"""Agent orchestrator service with OpenAI and Langfuse integration."""

import asyncio
import json
from typing import Any

from langfuse import Langfuse
from openai import AsyncOpenAI, OpenAI, RateLimitError, APIError
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.services.langfuse_service import get_langfuse, get_prompt_manager, set_user_context


class AgentRequest(BaseModel):
    """Request to the orchestrator."""

    query: str
    user_id: str
    session_id: str | None = None
    contract_id: str | None = None
    context: dict[str, Any] | None = None


class AgentResponseModel(BaseModel):
    """Response from the orchestrator."""

    response: str
    agent_name: str
    confidence: float | None = None
    sources: list[dict[str, Any]] | None = None
    session_id: str


class AgentConfig(BaseModel):
    """Configuration for an agent."""

    name: str
    description: str
    system_prompt: str
    model_id: str = "gpt-4o"
    temperature: float = 0.1
    max_tokens: int = 2000


class OrchestratorService:
    """Simple agent orchestrator with OpenAI and Langfuse observability."""

    def __init__(self) -> None:
        """Initialize the orchestrator service."""
        self._async_client: AsyncOpenAI | None = None
        self._sync_client: OpenAI | None = None
        self._langfuse: Langfuse | None = None
        self._agents: dict[str, AgentConfig] = {}
        self._default_agent: str = "contract_qa"

    @property
    def langfuse(self) -> Langfuse | None:
        """Get Langfuse client for observability."""
        if self._langfuse is None and settings.langfuse_public_key:
            try:
                self._langfuse = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host,
                )
            except Exception:
                pass  # Langfuse is optional
        return self._langfuse

    @property
    def async_client(self) -> AsyncOpenAI:
        """Get async OpenAI client (with Langfuse tracing if available)."""
        if self._async_client is None:
            # Try to use Langfuse-wrapped client for automatic tracing
            if settings.langfuse_public_key and settings.langfuse_secret_key:
                try:
                    from langfuse.openai import AsyncOpenAI as LangfuseAsyncOpenAI
                    self._async_client = LangfuseAsyncOpenAI(api_key=settings.openai_api_key)
                except ImportError:
                    self._async_client = AsyncOpenAI(api_key=settings.openai_api_key)
            else:
                self._async_client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._async_client

    @property
    def sync_client(self) -> OpenAI:
        """Get sync OpenAI client."""
        if self._sync_client is None:
            self._sync_client = OpenAI(api_key=settings.openai_api_key)
        return self._sync_client

    def register_agent(
        self,
        name: str,
        description: str,
        system_prompt: str | None = None,
        model_id: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        streaming: bool = False,  # Kept for API compatibility
    ) -> AgentConfig:
        """Register a new agent.

        Args:
            name: Unique agent name.
            description: Description for routing.
            system_prompt: System prompt for the agent.
            model_id: Model to use.
            temperature: Temperature for generation.
            max_tokens: Maximum tokens in response.
            streaming: Ignored (for API compatibility).

        Returns:
            The created agent config.
        """
        agent = AgentConfig(
            name=name,
            description=description,
            system_prompt=system_prompt or f"You are {name}, a helpful assistant.",
            model_id=model_id or settings.openai_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self._agents[name] = agent
        return agent

    def get_agent(self, name: str) -> AgentConfig | None:
        """Get a registered agent by name."""
        return self._agents.get(name)

    def list_agents(self) -> list[str]:
        """List all registered agent names."""
        return list(self._agents.keys())

    async def _classify_intent(self, query: str) -> str:
        """Classify user intent to route to appropriate agent."""
        if not self._agents:
            return self._default_agent

        # Build classification prompt
        agent_descriptions = "\n".join(
            f"- {name}: {agent.description}"
            for name, agent in self._agents.items()
        )

        classification_prompt = f"""Based on the user query, determine which agent should handle it.

Available agents:
{agent_descriptions}

User query: {query}

Respond with ONLY the agent name (one of: {', '.join(self._agents.keys())}).
If unsure, respond with: {self._default_agent}"""

        try:
            response = await self.async_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": "You are a routing assistant. Respond with only the agent name."},
                    {"role": "user", "content": classification_prompt},
                ],
                temperature=0.0,
                max_tokens=50,
            )
            agent_name = response.choices[0].message.content.strip().lower()

            # Validate agent exists
            if agent_name in self._agents:
                return agent_name
        except Exception:
            pass

        return self._default_agent

    @retry(
        retry=retry_if_exception_type((RateLimitError, APIError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
    )
    async def route_request(self, request: AgentRequest) -> AgentResponseModel:
        """Route a request to the appropriate agent.

        Args:
            request: The agent request with query and context.

        Returns:
            AgentResponseModel with the response.
        """
        # Create Langfuse trace if available
        trace = None
        if self.langfuse:
            try:
                trace = self.langfuse.trace(
                    name="orchestrator_request",
                    user_id=request.user_id,
                    session_id=request.session_id,
                    metadata={
                        "contract_id": request.contract_id,
                    },
                )
            except Exception:
                pass

        try:
            # Classify intent and get agent. Chat Q&A requests must never be
            # routed to extraction agents (their prompts demand raw JSON
            # output) — pin them to the conversational contract_qa agent.
            if request.context and request.context.get("task") == "contract_qa":
                agent_name = "contract_qa"
            else:
                agent_name = await self._classify_intent(request.query)
            agent = self._agents.get(agent_name) or self._agents.get(self._default_agent)

            if not agent:
                raise ValueError("No agents registered")

            # Build messages
            messages = [{"role": "system", "content": agent.system_prompt}]

            # Add context if provided
            if request.context:
                context_str = json.dumps(request.context, indent=2)
                messages.append({
                    "role": "system",
                    "content": f"Additional context:\n{context_str}",
                })

            messages.append({"role": "user", "content": request.query})

            # Call OpenAI
            response = await self.async_client.chat.completions.create(
                model=agent.model_id,
                messages=messages,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
            )

            result = AgentResponseModel(
                response=response.choices[0].message.content or "",
                agent_name=agent_name,
                session_id=request.session_id or request.user_id,
            )

            # Log success to Langfuse
            if trace:
                try:
                    trace.update(
                        output=result.response[:500],
                        metadata={"agent": result.agent_name},
                    )
                except Exception:
                    pass

            return result

        except Exception as e:
            # Log error to Langfuse
            if trace:
                try:
                    trace.update(
                        level="ERROR",
                        status_message=str(e),
                    )
                except Exception:
                    pass
            raise

    async def invoke_agent(
        self,
        agent_name: str,
        prompt: str,
        context: dict[str, Any] | None = None,
        user_id: str = "system",
        session_id: str | None = None,
        contract_id: str | None = None,
    ) -> str:
        """Directly invoke a specific agent.

        Args:
            agent_name: Name of the agent to invoke.
            prompt: The prompt to send.
            context: Optional context dict.
            user_id: User ID for tracing.
            session_id: Session ID for conversation grouping.
            contract_id: Contract ID for metadata.

        Returns:
            The agent's response text.
        """
        agent = self._agents.get(agent_name)
        if not agent:
            raise ValueError(f"Agent not found: {agent_name}")

        # Create Langfuse trace for user tracking
        trace = None
        if self.langfuse:
            try:
                trace = self.langfuse.trace(
                    name=f"invoke_{agent_name}",
                    user_id=user_id,
                    session_id=session_id,
                    metadata={
                        "agent_name": agent_name,
                        "contract_id": contract_id,
                    },
                )
            except Exception:
                pass

        messages = [{"role": "system", "content": agent.system_prompt}]

        if context:
            context_str = json.dumps(context, indent=2)
            messages.append({
                "role": "system",
                "content": f"Context:\n{context_str}",
            })

        messages.append({"role": "user", "content": prompt})

        response = await self.async_client.chat.completions.create(
            model=agent.model_id,
            messages=messages,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
        )

        result = response.choices[0].message.content or ""

        # Update trace with output
        if trace:
            try:
                trace.update(
                    output=result[:500],
                    metadata={"agent": agent_name, "success": True},
                )
            except Exception:
                pass

        return result

    async def health_check(self) -> dict[str, Any]:
        """Check health of OpenAI and Langfuse connections.

        Returns:
            Dictionary with health status of each service.
        """
        import asyncio

        health = {
            "openai": False,
            "langfuse": None,
            "agents_registered": len(self._agents),
        }

        # Run checks concurrently in thread pool to avoid blocking event loop
        async def check_openai():
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self.sync_client.models.list
                )
                return True
            except Exception:
                return False

        async def check_langfuse():
            if not self.langfuse:
                return None
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self.langfuse.auth_check
                )
                return True
            except Exception:
                return False

        openai_result, langfuse_result = await asyncio.gather(
            check_openai(), check_langfuse()
        )
        health["openai"] = openai_result
        health["langfuse"] = langfuse_result

        return health

    def flush(self) -> None:
        """Flush Langfuse events (call before shutdown)."""
        if self.langfuse:
            try:
                self.langfuse.flush()
            except Exception:
                pass


# Singleton instance
_orchestrator_service: OrchestratorService | None = None


def get_orchestrator() -> OrchestratorService:
    """Get the orchestrator service singleton."""
    global _orchestrator_service
    if _orchestrator_service is None:
        _orchestrator_service = OrchestratorService()
    return _orchestrator_service


def initialize_default_agents() -> None:
    """Initialize default agents for the orchestrator.

    Call this at application startup.
    """
    orchestrator = get_orchestrator()

    # Register Contract Q&A Agent (default)
    orchestrator.register_agent(
        name="contract_qa",
        description="""You answer questions about contracts using RAG-retrieved context.
        Use this agent for: general contract questions, finding specific clauses,
        understanding contract terms, comparing contracts.""",
        system_prompt="""You are a Contract Q&A specialist. Answer questions about contracts
        based on the provided context. Always cite the source contract and section when possible.
        If you cannot find the answer in the context, say so clearly.""",
        temperature=0.1,
        max_tokens=2000,
    )

    # Register Metadata Extraction Agent
    orchestrator.register_agent(
        name="metadata_extraction",
        description="""You extract structured metadata from contract text.
        Use this agent for: extracting parties, dates, values, contract types,
        jurisdictions, and other structured fields.""",
        system_prompt="""You are a contract metadata extraction specialist.
        Extract structured information from contract text and return it in JSON format.
        Fields to extract: contract_type, counterparty, effective_date, expiration_date,
        contract_value, currency, jurisdiction.""",
        temperature=0.0,
        max_tokens=1000,
    )

    # Register Risk Assessment Agent
    orchestrator.register_agent(
        name="risk_assessment",
        description="""You assess contractual risks and identify problematic clauses.
        Use this agent for: risk scoring, identifying unfavorable terms,
        liability analysis, compliance risks.""",
        system_prompt="""You are a contract risk assessment specialist.
        Analyze contract clauses for risks including: unlimited liability,
        broad indemnification, weak termination rights, auto-renewal traps,
        unfavorable IP terms, and regulatory compliance issues.
        Provide a risk score (0-100) and detailed explanations.""",
        temperature=0.1,
        max_tokens=2000,
    )
