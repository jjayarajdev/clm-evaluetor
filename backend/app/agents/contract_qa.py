"""Contract Q&A Agent (SK-006).

RAG-based question answering with:
- Natural language queries
- Source citations
- Follow-up suggestions
- Conversation context
"""

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import (
    AgentConfig,
    ContractSearchTool,
    SourceCitation,
    inject_context,
)
from app.config import settings
from app.services.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)


class QAResponse(BaseModel):
    """Response from the Q&A agent."""

    answer: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    sources: list[SourceCitation] = []
    follow_up_questions: list[str] = []
    clarification_needed: bool = False
    clarification_prompt: str | None = None


CONTRACT_QA_PROMPT = """You are a Contract Q&A specialist with access to contract documents. Your role is to answer questions about contracts accurately and helpfully.

GUIDELINES:
1. Answer questions based ONLY on the provided contract context
2. Always cite specific sections and clauses when possible
3. If the answer cannot be found in the context, say so clearly
4. Provide confident, accurate answers without hedging unnecessarily
5. When appropriate, suggest follow-up questions the user might want to ask
6. If the question is ambiguous, ask for clarification

FORMAT YOUR RESPONSES:
- Give a clear, direct answer first
- Include relevant quotes from the contract
- Cite sources (contract ID, section, page)
- Suggest 2-3 follow-up questions when relevant

If you cannot find the information in the provided context:
- Clearly state that the information was not found
- Suggest what additional documents or clarifications might help
- Ask if the user wants to search for something specific

RESPONSE FORMAT:
Answer the question directly, then provide:
- **Sources**: List the specific sections you referenced
- **Confidence**: How confident you are (high/medium/low)
- **Follow-up Questions**: Related questions the user might ask"""


def get_contract_qa_config() -> AgentConfig:
    """Get configuration for the contract Q&A agent."""
    return AgentConfig(
        name="contract_qa",
        description="""Answer questions about contracts using RAG-based retrieval.
        Handles general queries, clause lookups, term explanations, and comparisons.
        This is the default agent for contract-related questions.""",
        system_prompt=CONTRACT_QA_PROMPT,
        temperature=0.2,
        max_tokens=2000,
        streaming=True,
    )


async def ask_question(
    question: str,
    user_id: str,
    session_id: str | None = None,
    contract_id: str | None = None,
    user_role: str | None = None,
    n_results: int = 10,
) -> QAResponse:
    """Ask a question about contracts using RAG.

    Args:
        question: The user's question.
        user_id: User ID for RBAC and tracking.
        session_id: Session ID for conversation context.
        contract_id: Optional contract ID to scope the search.
        user_role: User role for RBAC.
        n_results: Number of context chunks to retrieve.

    Returns:
        QAResponse with answer and sources.
    """
    orchestrator = get_orchestrator()

    # Create search tool with RBAC context
    search_tool = ContractSearchTool(
        user_id=user_id,
        user_role=user_role,
        contract_id=contract_id,
        n_results=n_results,
    )

    # Inject context into the query
    augmented_query = inject_context(question, search_tool)

    try:
        from app.services.orchestrator import AgentRequest

        response = await orchestrator.route_request(
            AgentRequest(
                query=augmented_query,
                user_id=user_id,
                session_id=session_id or f"qa_{user_id}",
                contract_id=contract_id,
                context={
                    "task": "contract_qa",
                    "original_question": question,
                },
            )
        )

        # Parse response for structured elements
        return _parse_qa_response(response.response, search_tool)

    except Exception as e:
        logger.exception(f"Error in Q&A: {e}")
        return QAResponse(
            answer="I apologize, but I encountered an error while processing your question. Please try again.",
            confidence=0.0,
            clarification_needed=True,
            clarification_prompt="Could you please rephrase your question?",
        )


def _parse_qa_response(response_text: str, search_tool: ContractSearchTool) -> QAResponse:
    """Parse the agent response into structured QAResponse.

    Args:
        response_text: Raw response from the agent.
        search_tool: Search tool used for context.

    Returns:
        Structured QAResponse.
    """
    # Extract sources from the search results
    results = search_tool.search("")  # Get cached results
    sources = []

    for idx, result in enumerate(results[:5]):  # Top 5 sources
        metadata = result.metadata or {}
        # Extract excerpt from the document content (first 200 chars)
        text = result.text or ""
        excerpt = text[:200] + "..." if len(text) > 200 else text
        sources.append(
            SourceCitation(
                contract_id=metadata.get("contract_id", "unknown"),
                filename=metadata.get("filename"),
                section_number=metadata.get("section_number"),
                page_start=metadata.get("page_number"),
                page_end=metadata.get("page_number"),
                relevance_score=1 - result.distance if result.distance else None,
                excerpt=excerpt,
                chunk_index=idx,
            )
        )

    # Extract follow-up questions from response
    follow_ups = _extract_follow_ups(response_text)

    # Detect clarification requests
    clarification_needed = any(
        phrase in response_text.lower()
        for phrase in [
            "could you clarify",
            "please clarify",
            "what do you mean",
            "could you specify",
            "more specific",
        ]
    )

    # Estimate confidence based on response content
    confidence = _estimate_confidence(response_text)

    return QAResponse(
        answer=response_text,
        confidence=confidence,
        sources=sources,
        follow_up_questions=follow_ups,
        clarification_needed=clarification_needed,
    )


def _extract_follow_ups(response: str) -> list[str]:
    """Extract suggested follow-up questions from response.

    Args:
        response: Agent response text.

    Returns:
        List of follow-up questions.
    """
    import re

    follow_ups = []

    # Look for bullet-pointed questions
    patterns = [
        r"[-•]\s*([^?\n]+\?)",
        r"\d+\.\s*([^?\n]+\?)",
        r"You might (?:also )?(?:want to )?ask[:\s]+([^?\n]+\?)",
        r"(?:Follow-up|Related) questions?:?\s*\n?(.*)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, response, re.IGNORECASE)
        for match in matches:
            if isinstance(match, str) and "?" in match:
                questions = [q.strip() + "?" for q in match.split("?") if q.strip()]
                follow_ups.extend(questions[:3])

    return follow_ups[:3]  # Max 3 follow-ups


def _estimate_confidence(response: str) -> float:
    """Estimate confidence based on response content.

    Args:
        response: Agent response text.

    Returns:
        Confidence score (0.0-1.0).
    """
    lower_response = response.lower()

    # High confidence indicators
    high_confidence = [
        "according to section",
        "the contract states",
        "specifically mentions",
        "clearly indicates",
        "as stated in",
    ]

    # Low confidence indicators
    low_confidence = [
        "not found",
        "cannot determine",
        "no mention",
        "unclear",
        "not specified",
        "could not find",
        "appears to",
        "might be",
    ]

    high_count = sum(1 for phrase in high_confidence if phrase in lower_response)
    low_count = sum(1 for phrase in low_confidence if phrase in lower_response)

    if low_count > high_count:
        return 0.3
    elif high_count > low_count:
        return 0.9
    else:
        return 0.6


async def suggest_questions(
    contract_id: str,
    user_id: str,
    user_role: str | None = None,
) -> list[str]:
    """Suggest relevant questions for a contract.

    Args:
        contract_id: Contract ID to analyze.
        user_id: User ID for RBAC.
        user_role: User role for RBAC.

    Returns:
        List of suggested questions.
    """
    # Default suggested questions for any contract
    suggestions = [
        "What are the key terms of this contract?",
        "When does this contract expire?",
        "What are the termination conditions?",
        "Are there any auto-renewal provisions?",
        "What are the payment terms?",
        "What are the indemnification obligations?",
        "What is the liability cap?",
        "What is the governing law?",
    ]

    # TODO: Customize based on contract type
    return suggestions


def register_contract_qa_agent() -> None:
    """Register the contract Q&A agent with the orchestrator."""
    config = get_contract_qa_config()
    orchestrator = get_orchestrator()

    if orchestrator.get_agent(config.name):
        return

    orchestrator.register_agent(
        name=config.name,
        description=config.description,
        system_prompt=config.system_prompt,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        streaming=config.streaming,
    )
