"""Risk Detection Agent (SK-004).

Identifies high-risk clauses and calculates overall contract risk scores.
Risk categories include:
- Unlimited liability
- Broad indemnification
- Weak termination rights
- Auto-renewal traps
- And more...
"""

import json
import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import (
    AgentConfig,
    extract_json_from_response,
)
from app.config import settings
from app.models.contract import Contract, RiskLevel
from app.services.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)


# Risk categories with weights for scoring
RISK_CATEGORIES = {
    "unlimited_liability": {
        "description": "No cap on liability exposure",
        "weight": 15,
        "severity": "HIGH",
    },
    "broad_indemnification": {
        "description": "Overly broad indemnification obligations",
        "weight": 12,
        "severity": "HIGH",
    },
    "weak_termination": {
        "description": "Limited or no termination for convenience rights",
        "weight": 10,
        "severity": "MEDIUM",
    },
    "auto_renewal_trap": {
        "description": "Auto-renewal with difficult opt-out",
        "weight": 10,
        "severity": "MEDIUM",
    },
    "unfavorable_ip": {
        "description": "Unfavorable intellectual property terms",
        "weight": 12,
        "severity": "HIGH",
    },
    "weak_confidentiality": {
        "description": "Inadequate confidentiality protections",
        "weight": 8,
        "severity": "MEDIUM",
    },
    "missing_limitation": {
        "description": "Missing limitation of liability clause",
        "weight": 15,
        "severity": "HIGH",
    },
    "one_sided_terms": {
        "description": "Significantly one-sided contractual terms",
        "weight": 10,
        "severity": "HIGH",
    },
    "regulatory_risk": {
        "description": "Potential regulatory compliance issues",
        "weight": 8,
        "severity": "MEDIUM",
    },
    "ambiguous_language": {
        "description": "Ambiguous or unclear language in key provisions",
        "weight": 5,
        "severity": "LOW",
    },
}

# Score thresholds for risk levels
RISK_THRESHOLDS = {
    "LOW": (0, 25),
    "MEDIUM": (26, 50),
    "HIGH": (51, 75),
    "CRITICAL": (76, 100),
}


class RiskFactor(BaseModel):
    """A single identified risk factor."""

    category: str
    description: str
    severity: str  # LOW, MEDIUM, HIGH
    score: int = Field(ge=0, le=100)
    clause_reference: str | None = None
    recommendation: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class RiskAssessmentResult(BaseModel):
    """Complete risk assessment for a contract."""

    risk_factors: list[RiskFactor] = []
    overall_score: int = Field(ge=0, le=100)
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    summary: str = ""
    top_recommendations: list[str] = []
    overall_confidence: float = 0.0


RISK_DETECTION_PROMPT = f"""You are a contract risk assessment specialist. Your task is to identify risks and provide a comprehensive risk score for the contract.

RISK CATEGORIES TO EVALUATE:
{json.dumps({k: v["description"] for k, v in RISK_CATEGORIES.items()}, indent=2)}

For each risk found, provide:
1. **category**: One of the risk categories above
2. **description**: Specific description of the risk in this contract
3. **severity**: LOW, MEDIUM, or HIGH based on potential impact
4. **score**: Risk contribution (0-100, weighted by category importance)
5. **clause_reference**: The specific clause or section containing the risk
6. **recommendation**: Actionable recommendation to mitigate
7. **confidence**: How confident you are in this assessment (0.0-1.0)

SCORING GUIDELINES:
- 0-25: Low Risk - Standard terms, well-balanced
- 26-50: Medium Risk - Some concerns, negotiation recommended
- 51-75: High Risk - Significant concerns, careful review needed
- 76-100: Critical Risk - Major red flags, legal review required

Respond ONLY with valid JSON:
```json
{{
  "risk_factors": [
    {{
      "category": "unlimited_liability",
      "description": "No cap on liability in Section 8",
      "severity": "HIGH",
      "score": 15,
      "clause_reference": "Section 8.1",
      "recommendation": "Negotiate a liability cap equal to contract value",
      "confidence": 0.95
    }}
  ],
  "overall_score": 65,
  "risk_level": "HIGH",
  "summary": "This contract contains several high-risk provisions...",
  "top_recommendations": [
    "Negotiate liability cap",
    "Clarify indemnification scope"
  ]
}}
```"""


def get_risk_detection_config() -> AgentConfig:
    """Get configuration for the risk detection agent."""
    return AgentConfig(
        name="risk_detection",
        description="""Assess contract risks including liability, indemnification, termination,
        IP, and regulatory concerns. Provides risk scores and recommendations.""",
        system_prompt=RISK_DETECTION_PROMPT,
        temperature=0.1,
        max_tokens=4000,  # Increased for comprehensive risk extraction
    )


def _split_text_for_processing(text: str, chunk_size: int = 30000, overlap: int = 2000) -> list[str]:
    """Split large text into overlapping chunks for processing.

    Args:
        text: Full contract text.
        chunk_size: Maximum size per chunk.
        overlap: Overlap between chunks to avoid missing risks at boundaries.

    Returns:
        List of text chunks.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        # Try to break at a paragraph boundary
        if end < len(text):
            # Look for paragraph break within last 1000 chars
            break_point = text.rfind('\n\n', start + chunk_size - 1000, end)
            if break_point > start:
                end = break_point
        chunks.append(text[start:end])
        start = end - overlap if end < len(text) else end

    return chunks


async def assess_risk(
    contract_text: str,
    contract_id: str | None = None,
    user_id: str | None = None,
) -> RiskAssessmentResult:
    """Assess risk in contract text using the AI agent.

    Processes full contract by splitting into chunks and aggregating results.

    Args:
        contract_text: The contract text to assess.
        contract_id: Optional contract ID for context.
        user_id: User ID for tracking.

    Returns:
        RiskAssessmentResult with risk factors and overall score.
    """
    orchestrator = get_orchestrator()

    # Split large contracts into chunks for complete processing
    chunks = _split_text_for_processing(contract_text, chunk_size=30000, overlap=2000)
    logger.info(f"Processing contract in {len(chunks)} chunk(s) for risk assessment")

    all_risk_factors: list[RiskFactor] = []
    chunk_scores: list[int] = []

    for chunk_idx, chunk_text in enumerate(chunks):
        chunk_label = f"[Part {chunk_idx + 1}/{len(chunks)}]" if len(chunks) > 1 else ""

        query = f"""Assess the risks in this contract {chunk_label}:

---
{chunk_text}
---

Identify all risk factors and calculate an overall risk score for this section."""

        try:
            from app.services.orchestrator import AgentRequest

            response = await orchestrator.route_request(
                AgentRequest(
                    query=query,
                    user_id=user_id or "system",
                    session_id=f"risk_{contract_id or 'unknown'}_{chunk_idx}",
                    contract_id=contract_id,
                    context={"task": "risk_detection", "chunk": chunk_idx},
                )
            )

            json_data = extract_json_from_response(response.response)
            if json_data:
                chunk_result = _parse_risk_response(json_data)
                all_risk_factors.extend(chunk_result.risk_factors)
                chunk_scores.append(chunk_result.overall_score)

        except Exception as e:
            logger.warning(f"Error processing chunk {chunk_idx} for risk: {e}")
            continue

    if not all_risk_factors:
        logger.warning("No risk factors found in any chunk")
        return RiskAssessmentResult(overall_score=0, risk_level="LOW")

    # Deduplicate risk factors by category and description similarity
    unique_factors = _deduplicate_risk_factors(all_risk_factors)

    # Calculate overall score as weighted average with max consideration
    if chunk_scores:
        avg_score = sum(chunk_scores) / len(chunk_scores)
        max_score = max(chunk_scores)
        # Use weighted combination: 60% max (capture worst risks) + 40% average
        overall_score = int(0.6 * max_score + 0.4 * avg_score)
    else:
        overall_score = sum(f.score for f in unique_factors) // max(len(unique_factors), 1)

    overall_score = min(100, overall_score)  # Cap at 100

    risk_level = _calculate_risk_level(overall_score)

    avg_confidence = (
        sum(f.confidence for f in unique_factors) / len(unique_factors)
        if unique_factors
        else 0.0
    )

    # Generate summary and recommendations
    top_recs = []
    for factor in sorted(unique_factors, key=lambda x: x.score, reverse=True)[:5]:
        if factor.recommendation:
            top_recs.append(factor.recommendation)

    summary = f"Contract analyzed in {len(chunks)} section(s). Found {len(unique_factors)} risk factors. "
    high_risks = [f for f in unique_factors if f.severity == "HIGH"]
    if high_risks:
        summary += f"High-severity risks: {', '.join(f.category for f in high_risks[:3])}."

    return RiskAssessmentResult(
        risk_factors=unique_factors,
        overall_score=overall_score,
        risk_level=risk_level,
        summary=summary,
        top_recommendations=top_recs[:5],
        overall_confidence=avg_confidence,
    )


def _deduplicate_risk_factors(factors: list[RiskFactor]) -> list[RiskFactor]:
    """Deduplicate risk factors by category, keeping highest-scoring instances.

    Args:
        factors: List of risk factors from multiple chunks.

    Returns:
        Deduplicated list of risk factors.
    """
    # Group by category
    by_category: dict[str, list[RiskFactor]] = {}
    for factor in factors:
        if factor.category not in by_category:
            by_category[factor.category] = []
        by_category[factor.category].append(factor)

    # For each category, keep the factor with highest score and merge info
    unique = []
    for category, cat_factors in by_category.items():
        # Sort by score descending
        cat_factors.sort(key=lambda x: x.score, reverse=True)
        best = cat_factors[0]

        # If multiple factors in same category, boost score slightly and merge recommendations
        if len(cat_factors) > 1:
            # Found in multiple places - likely significant
            merged_score = min(100, int(best.score * 1.1))
            merged_refs = [f.clause_reference for f in cat_factors if f.clause_reference]
            merged_ref = "; ".join(merged_refs[:3]) if merged_refs else best.clause_reference

            unique.append(RiskFactor(
                category=best.category,
                description=best.description,
                severity=best.severity,
                score=merged_score,
                clause_reference=merged_ref,
                recommendation=best.recommendation,
                confidence=max(f.confidence for f in cat_factors),
            ))
        else:
            unique.append(best)

    return sorted(unique, key=lambda x: x.score, reverse=True)


def _parse_risk_response(data: dict[str, Any]) -> RiskAssessmentResult:
    """Parse the JSON response into RiskAssessmentResult."""
    factors = []

    for factor_data in data.get("risk_factors", []):
        try:
            category = factor_data.get("category", "ambiguous_language")
            if category not in RISK_CATEGORIES:
                category = "ambiguous_language"

            factors.append(
                RiskFactor(
                    category=category,
                    description=factor_data.get("description", ""),
                    severity=factor_data.get("severity", "MEDIUM").upper(),
                    score=int(factor_data.get("score", 5)),
                    clause_reference=factor_data.get("clause_reference"),
                    recommendation=factor_data.get("recommendation"),
                    confidence=float(factor_data.get("confidence", 0.5)),
                )
            )
        except Exception as e:
            logger.warning(f"Error parsing risk factor: {e}")

    overall_score = int(data.get("overall_score", 0))
    risk_level = data.get("risk_level", "LOW").upper()

    # Validate risk level
    if risk_level not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
        risk_level = _calculate_risk_level(overall_score)

    avg_confidence = (
        sum(f.confidence for f in factors) / len(factors)
        if factors
        else 0.0
    )

    return RiskAssessmentResult(
        risk_factors=factors,
        overall_score=overall_score,
        risk_level=risk_level,
        summary=data.get("summary", ""),
        top_recommendations=data.get("top_recommendations", []),
        overall_confidence=avg_confidence,
    )


def _calculate_risk_level(score: int) -> str:
    """Calculate risk level from score."""
    for level, (low, high) in RISK_THRESHOLDS.items():
        if low <= score <= high:
            return level
    return "CRITICAL" if score > 75 else "LOW"


async def update_contract_risk(
    db: AsyncSession,
    contract: Contract,
    result: RiskAssessmentResult,
) -> Contract:
    """Update contract with risk assessment results.

    Args:
        db: Database session.
        contract: Contract to update.
        result: Risk assessment result.

    Returns:
        Updated contract.
    """
    contract.risk_score = result.overall_score

    level_map = {
        "LOW": RiskLevel.LOW,
        "MEDIUM": RiskLevel.MEDIUM,
        "HIGH": RiskLevel.HIGH,
        "CRITICAL": RiskLevel.CRITICAL,
    }
    contract.risk_level = level_map.get(result.risk_level, RiskLevel.LOW)

    await db.flush()
    return contract


def register_risk_detection_agent() -> None:
    """Register the risk detection agent with the orchestrator."""
    config = get_risk_detection_config()
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
