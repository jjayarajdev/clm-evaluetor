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
    get_kg_context_for_query,
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
    visualizations: list[dict] = []
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
    tenant_id: str | None = None,
    n_results: int = 10,
    language: str = "en",
) -> QAResponse:
    """Ask a question about contracts using intent routing + RAG.

    First detects whether the question maps to a structured database query
    (renewals, obligations, risk, portfolio, SLAs). If so, queries PostgreSQL
    directly for accurate, complete answers. Otherwise falls through to
    RAG-based document Q&A.

    Args:
        question: The user's question.
        user_id: User ID for RBAC and tracking.
        session_id: Session ID for conversation context.
        contract_id: Optional contract ID to scope the search.
        user_role: User role for RBAC.
        tenant_id: Tenant ID for isolation.
        n_results: Number of context chunks to retrieve.

    Returns:
        QAResponse with answer and sources.
    """
    from app.agents.intent_router import detect_intent, handle_structured_query

    # Step 1: Detect intent
    intent = detect_intent(question)
    logger.info(f"Q&A intent detected: '{intent}' for question: {question[:80]}")

    # Step 2: Try structured query for non-document intents.
    # When the user has scoped the chat to a specific document, always use
    # RAG on that document — portfolio-level dashboards would answer about
    # other contracts and ignore the selection.
    if intent != "document_qa" and not contract_id:
        try:
            from app.database import async_session_maker

            async with async_session_maker() as db:
                result = await handle_structured_query(
                    intent=intent,
                    question=question,
                    db=db,
                    tenant_id=tenant_id,
                    contract_id=contract_id,
                    language=language,
                )

                if result and result.get("answer"):
                    logger.info(f"Structured query answered intent '{intent}' successfully")
                    return QAResponse(
                        answer=result["answer"],
                        confidence=0.95,
                        sources=[],
                        follow_up_questions=result.get("follow_up_questions", []),
                        visualizations=result.get("visualizations", []),
                    )
        except Exception as e:
            logger.warning(f"Structured query failed, falling back to RAG: {e}")

    # Step 3: Fall through to RAG-based document Q&A
    orchestrator = get_orchestrator()

    # Create search tool with RBAC context
    search_tool = ContractSearchTool(
        user_id=user_id,
        user_role=user_role,
        contract_id=contract_id,
        tenant_id=tenant_id,
        n_results=n_results,
    )

    # Get knowledge graph context if contract_id is specified
    kg_context = None
    if contract_id and tenant_id:
        try:
            kg_context = await get_kg_context_for_query(question, contract_id, tenant_id)
        except Exception as e:
            logger.warning(f"Failed to get KG context: {e}")

    # Inject context into the query (includes KG context if available)
    augmented_query = inject_context(question, search_tool, kg_context=kg_context)

    if language == "fr":
        augmented_query += (
            "\n\nIMPORTANT: Réponds entièrement en français — la réponse, "
            "les commentaires sur les sources et les questions de suivi."
        )

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
        if language == "fr":
            return QAResponse(
                answer="Je suis désolé, une erreur s'est produite lors du traitement de votre question. Veuillez réessayer.",
                confidence=0.0,
                clarification_needed=True,
                clarification_prompt="Pourriez-vous reformuler votre question ?",
            )
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
    tenant_id: str | None = None,
    language: str = "en",
) -> list[str]:
    """Suggest relevant questions for a contract.

    Args:
        contract_id: Contract ID to analyze.
        user_id: User ID for RBAC.
        user_role: User role for RBAC.
        tenant_id: Tenant ID for isolation.

    Returns:
        List of suggested questions.
    """
    # Default suggested questions for any contract
    if language == "fr":
        suggestions = [
            "Quelles sont les conditions clés de ce contrat ?",
            "Quand ce contrat expire-t-il ?",
            "Quelles sont les conditions de résiliation ?",
            "Y a-t-il des clauses de renouvellement automatique ?",
            "Quelles sont les conditions de paiement ?",
            "Quelles sont les obligations d'indemnisation ?",
            "Quel est le plafond de responsabilité ?",
            "Quel est le droit applicable ?",
        ]
    else:
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
