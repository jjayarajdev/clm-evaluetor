"""AI-assisted industry profile generation.

Drafts a complete IndustryProfile configuration (contract types, clause
types, risk categories, SLA metrics, field definitions, extraction hints,
UI config) for a new industry vertical using GPT-4o, with an existing
seeded profile as a few-shot example. The draft is returned for human
review — nothing is persisted here.
"""

import json
import logging

from openai import AsyncOpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.industry_profile import IndustryProfile

logger = logging.getLogger(__name__)

MAX_SAMPLE_CHARS = 8000

SYSTEM_PROMPT = """You are a contract lifecycle management (CLM) domain expert. \
You design industry vertical configurations for a CLM platform.

Given an industry name and description, produce a COMPLETE industry profile as a \
single JSON object with EXACTLY these keys:

- "description": one-paragraph summary of the vertical (string)
- "contract_types": 6-12 items, each {"code", "label", "description", "icon"}. \
codes are snake_case. icon is a lucide icon name (e.g. "truck", "file-text", "shield").
- "clause_types": 10-17 items, each {"code", "label", "category", "risk_weight", "description"}. \
risk_weight is an integer 0-15 reflecting how much a problematic version of this clause \
contributes to contract risk. category groups clauses for the UI (e.g. "commercial", "liability").
- "risk_categories": 8-10 items, each {"code", "label", "severity", "weight", "description"}. \
severity is one of low|medium|high|critical. weight is an integer 0-30.
- "sla_metrics": 5-10 items, each {"code", "label", "unit", "direction", "default_target", "description"}. \
direction is "lower_is_better" or "higher_is_better". default_target is a number.
- "field_definitions": object keyed by contract_type code (cover at least the 3 most important \
contract types), each value a list of {"section": str, "fields": [{"key", "label", "type"}]} \
where type is one of: text, date, currency, percentage, number, table, boolean.
- "extraction_hints": object with EXACTLY the keys "metadata", "clauses", "risks", "slas", \
"obligations". Each value is a 2-4 sentence instruction telling an AI extraction agent what \
industry-specific things to look for.
- "ui_config": object with "table_columns" (4-6 of {"key", "label", "width"?, "format"?}), \
"dashboard_widgets" (3-5 of {"key", "label", "color"}), "detail_tabs" (list of {"id", "label"}, \
always include overview/review/documents/sharing plus 1-2 industry tabs), "filters" (list of \
strings), and "labels" (object remapping generic terms like "counterparty" to industry language).

Ground every choice in real practices of the target industry. Use the example profile for \
structure and level of detail only — do NOT copy its domain content.

Return ONLY the JSON object, no markdown fences, no commentary."""


async def _load_example_profile(db: AsyncSession) -> dict | None:
    """Load one existing profile as a few-shot structural example."""
    result = await db.execute(
        select(IndustryProfile)
        .where(IndustryProfile.is_active.is_(True))
        .order_by(IndustryProfile.created_at)
        .limit(1)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        return None
    return {
        "description": profile.description,
        "contract_types": profile.contract_types,
        "clause_types": profile.clause_types,
        "risk_categories": profile.risk_categories,
        "sla_metrics": profile.sla_metrics,
        "field_definitions": profile.field_definitions,
        "extraction_hints": profile.extraction_hints,
        "ui_config": profile.ui_config,
    }


async def generate_profile_draft(
    db: AsyncSession,
    name: str,
    description: str,
    sample_contract_text: str | None = None,
) -> dict:
    """Generate a draft industry profile config via GPT-4o.

    Returns the raw config dict (without name/slug). Raises ValueError if
    the model response cannot be parsed as JSON.
    """
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    user_parts = [
        f"Target industry: {name}",
        f"Description: {description}",
    ]

    example = await _load_example_profile(db)
    if example:
        user_parts.append(
            "Example profile from another industry (structure reference only):\n"
            + json.dumps(example, default=str)
        )

    if sample_contract_text:
        user_parts.append(
            "Representative contract excerpt from this industry:\n"
            + sample_contract_text[:MAX_SAMPLE_CHARS]
        )

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "\n\n".join(user_parts)},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
    except OpenAIError as e:
        logger.error(f"Profile generation OpenAI call failed: {e}")
        raise ValueError(f"AI generation failed: {e}") from e

    content = response.choices[0].message.content or ""
    try:
        draft = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Profile generation returned invalid JSON: {e}")
        raise ValueError("AI generation returned invalid JSON — please retry") from e

    logger.info(
        f"Generated industry profile draft for '{name}': "
        f"{len(draft.get('contract_types', []))} contract types, "
        f"{len(draft.get('clause_types', []))} clause types"
    )
    return draft
