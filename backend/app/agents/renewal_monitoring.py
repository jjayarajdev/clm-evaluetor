"""Renewal Monitoring Agent (SK-005).

Extracts renewal terms and calculates notice deadlines:
- Auto-renewal detection
- Notice periods
- Expiration dates
- Termination for convenience
"""

import json
import logging
import uuid
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import (
    AgentConfig,
    extract_json_from_response,
)
from app.config import settings
from app.models.contract import Contract
from app.services.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)


class RenewalTerms(BaseModel):
    """Extracted renewal terms from a contract."""

    has_auto_renewal: bool = False
    auto_renewal_term_months: int | None = None
    notice_period_days: int | None = None
    notice_deadline: str | None = None  # Calculated from expiration
    expiration_date: str | None = None
    effective_date: str | None = None
    initial_term_months: int | None = None
    termination_for_convenience: bool = False
    termination_notice_days: int | None = None
    renewal_clause_text: str | None = None
    confidence: float = 0.0


class RenewalMonitoringResult(BaseModel):
    """Result of renewal monitoring analysis."""

    terms: RenewalTerms
    days_until_expiration: int | None = None
    days_until_notice_deadline: int | None = None
    urgency_level: str = "FUTURE"  # IMMEDIATE, SOON, UPCOMING, FUTURE
    action_required: str | None = None
    recommendations: list[str] = []


RENEWAL_MONITORING_PROMPT = """You are a contract renewal specialist. Your task is to identify all renewal and termination terms in the contract.

Extract the following information:
1. **has_auto_renewal**: Does the contract automatically renew?
2. **auto_renewal_term_months**: How long is each renewal period?
3. **notice_period_days**: How many days before expiration must notice be given?
4. **expiration_date**: When does the contract expire? (YYYY-MM-DD format)
5. **effective_date**: When did the contract start? (YYYY-MM-DD format)
6. **initial_term_months**: Length of the initial term
7. **termination_for_convenience**: Can either party terminate without cause?
8. **termination_notice_days**: Notice required for termination for convenience
9. **renewal_clause_text**: The exact text of the renewal clause
10. **confidence**: How confident you are in the extraction (0.0-1.0)

Look for:
- "This Agreement shall automatically renew..."
- "...shall continue for successive periods..."
- "...unless either party provides written notice..."
- "...within [X] days prior to expiration..."
- Termination provisions
- Notice requirements

Respond ONLY with valid JSON:
```json
{
  "has_auto_renewal": true,
  "auto_renewal_term_months": 12,
  "notice_period_days": 30,
  "expiration_date": "2025-12-31",
  "effective_date": "2024-01-01",
  "initial_term_months": 24,
  "termination_for_convenience": true,
  "termination_notice_days": 60,
  "renewal_clause_text": "This Agreement shall automatically renew for additional one-year periods unless either party provides written notice of non-renewal at least 30 days prior to the expiration of the then-current term.",
  "confidence": 0.9
}
```

If a field cannot be determined, set it to null."""


def get_renewal_monitoring_config() -> AgentConfig:
    """Get configuration for the renewal monitoring agent."""
    return AgentConfig(
        name="renewal_monitoring",
        description="""Extract renewal terms including auto-renewal, notice periods,
        expiration dates, and termination rights. Use for renewal tracking and alerts.""",
        system_prompt=RENEWAL_MONITORING_PROMPT,
        temperature=0.0,
        max_tokens=1500,
    )


async def analyze_renewal_terms(
    contract_text: str,
    contract_id: str | None = None,
    user_id: str | None = None,
    current_date: date | None = None,
) -> RenewalMonitoringResult:
    """Analyze renewal terms in contract text using the AI agent.

    Args:
        contract_text: The contract text to analyze.
        contract_id: Optional contract ID for context.
        user_id: User ID for tracking.
        current_date: Date to use for calculations (defaults to today).

    Returns:
        RenewalMonitoringResult with terms and urgency assessment.
    """
    orchestrator = get_orchestrator()

    if current_date is None:
        current_date = date.today()

    # Focus on the first part and any section mentioning "term" or "renewal"
    text_sample = contract_text[:15000]

    query = f"""Extract all renewal and termination terms from this contract:

---
{text_sample}
---

Identify auto-renewal clauses, notice periods, and expiration dates."""

    try:
        from app.services.orchestrator import AgentRequest

        response = await orchestrator.route_request(
            AgentRequest(
                query=query,
                user_id=user_id or "system",
                session_id=f"renewal_{contract_id or 'unknown'}",
                contract_id=contract_id,
                context={"task": "renewal_monitoring"},
            )
        )

        json_data = extract_json_from_response(response.response)
        if json_data:
            terms = _parse_renewal_response(json_data)
            return _calculate_urgency(terms, current_date)
        else:
            logger.warning("Could not parse renewal response")
            return RenewalMonitoringResult(terms=RenewalTerms())

    except Exception as e:
        logger.exception(f"Error analyzing renewal terms: {e}")
        return RenewalMonitoringResult(terms=RenewalTerms())


def _parse_renewal_response(data: dict[str, Any]) -> RenewalTerms:
    """Parse the JSON response into RenewalTerms."""
    return RenewalTerms(
        has_auto_renewal=bool(data.get("has_auto_renewal", False)),
        auto_renewal_term_months=data.get("auto_renewal_term_months"),
        notice_period_days=data.get("notice_period_days"),
        expiration_date=data.get("expiration_date"),
        effective_date=data.get("effective_date"),
        initial_term_months=data.get("initial_term_months"),
        termination_for_convenience=bool(data.get("termination_for_convenience", False)),
        termination_notice_days=data.get("termination_notice_days"),
        renewal_clause_text=data.get("renewal_clause_text"),
        confidence=float(data.get("confidence", 0.5)),
    )


def _calculate_urgency(terms: RenewalTerms, current_date: date) -> RenewalMonitoringResult:
    """Calculate urgency level and recommendations.

    Args:
        terms: Extracted renewal terms.
        current_date: Current date for calculations.

    Returns:
        RenewalMonitoringResult with urgency assessment.
    """
    result = RenewalMonitoringResult(terms=terms)

    # Parse expiration date
    expiration = None
    if terms.expiration_date:
        try:
            expiration = date.fromisoformat(terms.expiration_date)
        except ValueError:
            pass

    if expiration:
        result.days_until_expiration = (expiration - current_date).days

        # Calculate notice deadline
        if terms.notice_period_days:
            notice_deadline = expiration - timedelta(days=terms.notice_period_days)
            terms.notice_deadline = notice_deadline.isoformat()
            result.days_until_notice_deadline = (notice_deadline - current_date).days

            # Determine urgency
            if result.days_until_notice_deadline is not None:
                days = result.days_until_notice_deadline
                if days < 0:
                    result.urgency_level = "IMMEDIATE"
                    result.action_required = "Notice deadline has passed!"
                elif days < 7:
                    result.urgency_level = "IMMEDIATE"
                    result.action_required = f"Notice due in {days} days"
                elif days < 30:
                    result.urgency_level = "SOON"
                    result.action_required = f"Notice due in {days} days"
                elif days < 90:
                    result.urgency_level = "UPCOMING"
                else:
                    result.urgency_level = "FUTURE"

    # Generate recommendations
    recommendations = []

    if terms.has_auto_renewal:
        if result.urgency_level in ["IMMEDIATE", "SOON"]:
            recommendations.append(
                f"URGENT: Review contract and decide on renewal within {result.days_until_notice_deadline} days"
            )
        else:
            recommendations.append("Set calendar reminder for renewal decision")

    if not terms.termination_for_convenience:
        recommendations.append("Consider negotiating termination for convenience in next renewal")

    if terms.notice_period_days and terms.notice_period_days > 60:
        recommendations.append(f"Long notice period ({terms.notice_period_days} days) - plan ahead")

    result.recommendations = recommendations
    return result


async def update_contract_renewal(
    db: AsyncSession,
    contract: Contract,
    result: RenewalMonitoringResult,
) -> Contract:
    """Update contract with renewal monitoring results.

    Args:
        db: Database session.
        contract: Contract to update.
        result: Renewal monitoring result.

    Returns:
        Updated contract.
    """
    terms = result.terms

    contract.auto_renewal = terms.has_auto_renewal
    contract.notice_period_days = terms.notice_period_days
    contract.renewal_term_months = terms.auto_renewal_term_months

    if terms.expiration_date:
        try:
            contract.expiration_date = date.fromisoformat(terms.expiration_date)
        except ValueError:
            pass

    if terms.effective_date:
        try:
            contract.effective_date = date.fromisoformat(terms.effective_date)
        except ValueError:
            pass

    await db.flush()
    return contract


def register_renewal_monitoring_agent() -> None:
    """Register the renewal monitoring agent with the orchestrator."""
    config = get_renewal_monitoring_config()
    orchestrator = get_orchestrator()

    if orchestrator.get_agent(config.name):
        return

    orchestrator.register_agent(
        name=config.name,
        description=config.description,
        system_prompt=config.system_prompt,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )
