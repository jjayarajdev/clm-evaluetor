"""Intent router for contract Q&A.

Detects whether a question should be answered from structured data (PostgreSQL)
or from document content (ChromaDB RAG). Routes accordingly and formats
concise executive summaries with rich LLM-generated visualizations.
"""

import json
import logging
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.contract import Contract
from app.models.obligation import Obligation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Counterparty cleanup helpers
# ---------------------------------------------------------------------------

_GARBAGE_COUNTERPARTY_PATTERNS = [
    "the terms of", "the ones in", "attached hereto", "as exhibit",
    "pursuant to", "in accordance", "as defined in", "set forth",
]


def _clean_counterparty(raw: str | None, filename: str) -> str:
    """Sanitize counterparty, falling back to filename-derived name."""
    if not raw:
        return _counterparty_from_filename(filename)
    if len(raw) > 50:
        return _counterparty_from_filename(filename)
    lower = raw.lower()
    if any(p in lower for p in _GARBAGE_COUNTERPARTY_PATTERNS):
        return _counterparty_from_filename(filename)
    return raw


def _counterparty_from_filename(filename: str) -> str:
    """Extract a reasonable counterparty name from a filename."""
    name = filename.rsplit(".", 1)[0]
    for prefix in [
        "MSA_", "SOW_", "NDA_", "SLA_", "Amendment_",
        "Vendor_Agreement_", "Employment_Contract_",
    ]:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return name.replace("_", " ")


# ---------------------------------------------------------------------------
# Risk badge helper
# ---------------------------------------------------------------------------

_RISK_LABELS = {
    "critical": " [CRITICAL RISK]",
    "high": " [HIGH RISK]",
    "medium": " [MEDIUM RISK]",
    "low": "",
}


def _risk_badge(risk_level: str | None) -> str:
    if not risk_level:
        return ""
    return _RISK_LABELS.get(risk_level.lower(), "")


# ---------------------------------------------------------------------------
# Deduplication helper
# ---------------------------------------------------------------------------

def _dedup_contracts(contracts: list) -> list:
    """Deduplicate contracts by filename + tenant_id."""
    seen = set()
    result = []
    for c in contracts:
        key = (c.filename, str(c.tenant_id))
        if key not in seen:
            seen.add(key)
            result.append(c)
    return result


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

STRUCTURED_INTENTS = {
    "renewals": [
        "renewal", "renew", "expiring", "expiration", "expire", "auto-renewal",
        "auto renewal", "up for renewal", "notice period", "notice deadline",
    ],
    "obligations": [
        "obligation", "obligations due", "upcoming deadline", "overdue",
        "compliance", "what do i owe", "what must", "deliverable",
    ],
    "risk": [
        "high risk", "risky", "risk summary", "risk score", "risk level",
        "most risky", "risk assessment", "risk overview",
    ],
    "portfolio": [
        "how many contracts", "total contracts", "contract summary",
        "portfolio", "total value", "contract count", "overview",
        "all contracts", "list contracts", "my contracts",
    ],
    "sla": [
        "sla performance", "service level", "breached sla", "sla breach",
        "sla status", "sla metric", "what are my sla",
    ],
}


def detect_intent(question: str) -> str:
    """Detect whether a question maps to a structured query or needs RAG."""
    q = question.lower().strip()

    # Clause analysis requests should always go to document Q&A (RAG),
    # not structured queries — even if the clause text contains keywords
    # like "obligation" or "renewal"
    if q.startswith("[clause analysis]") or '"' in q and len(q) > 300:
        return "document_qa"

    scores: dict[str, int] = {}
    for intent, keywords in STRUCTURED_INTENTS.items():
        score = sum(1 for kw in keywords if kw in q)
        if score > 0:
            scores[intent] = score

    if scores:
        return max(scores, key=scores.get)
    return "document_qa"


# ---------------------------------------------------------------------------
# LLM enhancement: follow-ups + adaptive visualizations
# ---------------------------------------------------------------------------

_ENHANCE_PROMPT = """You are a contract analytics assistant. Given structured query results,
generate contextual follow-up questions and RICH visualization specifications.

The user wants VISUAL answers — charts and cards — not walls of text.
Your job is to generate comprehensive visualizations that tell the full data story.

AVAILABLE CHART TYPES (use EXACT data formats):

1. stat_cards — Headline KPI cards (ALWAYS include as first visualization)
   data: {"cards": [{"label": "Label", "value": "42", "color": "#hex"}]}
   Use for: 3-5 key numbers the user should see at a glance

2. pie — Donut chart for proportional breakdowns
   data: [{"name": "Segment", "value": 10}]
   Use when: showing how a whole breaks down into parts (2-7 segments)

3. bar — Horizontal bar chart for comparisons/rankings
   data: [{"name": "Category", "count": 5, "fill": "#hex"}]
   Use when: comparing quantities, showing rankings, ordered categories

4. table — Data table for detailed item listings
   data: {"columns": ["Col1", "Col2", "Col3"], "rows": [["val1", "val2", "val3"]]}
   Use when: showing specific items with multiple attributes (contracts, obligations, deadlines)
   Keep to 5-8 rows maximum. Keep cell values SHORT (truncate long text).

COLOR SEMANTICS:
- Red (#ef4444): danger, critical, expired, overdue
- Orange (#f97316): warning, high risk, urgent
- Yellow (#eab308): caution, medium risk, upcoming
- Green (#22c55e): safe, low risk, compliant, on track
- Blue (#3b82f6): neutral, informational, totals
- Purple (#8b5cf6): categories, types, highlights
- Teal (#06b6d4): secondary metrics

RULES:
- Generate exactly 3 follow-up questions specific to the actual data
  (reference contract names, counterparties, deadlines, numbers when relevant)
- Follow-ups should lead to DIFFERENT types of analysis
- Generate 3-4 visualizations:
  1. ALWAYS start with stat_cards for headline KPIs
  2. Add 1-2 charts (pie for distributions, bar for rankings/comparisons)
  3. Add a table for the most important detail items (top obligations, contracts at risk, etc.)
- Pick chart types that best represent the data shape
- For distributions/composition → use pie
- For ordered comparisons/rankings → use bar
- For detailed item listings → use table
- Keep stat card values short (numbers, "$1.2M", "85%", not full sentences)
- Table column headers should be short (1-2 words)
- Table cell values should be concise

Respond with ONLY valid JSON:
{
  "follow_up_questions": ["question1", "question2", "question3"],
  "visualizations": [
    {"chart_type": "stat_cards|bar|pie|table", "title": "...", "data": ...}
  ]
}"""


async def _enhance_with_llm(
    intent: str,
    question: str,
    answer: str,
    data_summary: dict,
) -> tuple[list[str], list[dict]]:
    """Use LLM to generate contextual follow-ups and adaptive visualizations."""
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        user_message = (
            f"Intent: {intent}\n"
            f"User question: {question}\n\n"
            f"Short answer: {answer[:500]}\n\n"
            f"Full data summary (use this to build visualizations):\n"
            f"{json.dumps(data_summary, indent=2, default=str)[:3000]}"
        )

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _ENHANCE_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        follow_ups = result.get("follow_up_questions", [])[:3]
        visualizations = result.get("visualizations", [])[:4]

        # Validate visualization structure
        valid_viz = []
        for viz in visualizations:
            if (
                isinstance(viz, dict)
                and "chart_type" in viz
                and "title" in viz
                and "data" in viz
                and viz["chart_type"] in ("stat_cards", "bar", "pie", "table")
            ):
                valid_viz.append(viz)

        if not valid_viz or not follow_ups:
            logger.warning("LLM enhancement incomplete, using fallback")
            return _fallback_enhancement(intent, data_summary)

        return follow_ups, valid_viz

    except Exception as e:
        logger.warning(f"LLM enhancement failed, using fallback: {e}")
        return _fallback_enhancement(intent, data_summary)


def _fallback_enhancement(
    intent: str,
    data_summary: dict,
) -> tuple[list[str], list[dict]]:
    """Heuristic fallback when LLM is unavailable."""
    fallback_followups = {
        "renewals": [
            "Which contracts have auto-renewal clauses?",
            "What obligations do we have?",
            "Show me my high risk contracts",
        ],
        "obligations": [
            "Which obligations are critical?",
            "How many contracts do I have?",
            "What are my SLAs?",
        ],
        "risk": [
            "What are my contracts up for renewal?",
            "What obligations do we have?",
            "How many contracts do I have?",
        ],
        "portfolio": [
            "What are my contracts up for renewal?",
            "Show me my high risk contracts",
            "What are my SLAs?",
        ],
        "sla": [
            "What penalties apply for SLA misses?",
            "What obligations do we have?",
            "Show me my high risk contracts",
        ],
    }

    viz = []
    counts = data_summary.get("counts", {})
    if counts:
        cards = []
        colors = ["#3b82f6", "#8b5cf6", "#ef4444", "#22c55e", "#f97316", "#06b6d4"]
        for i, (label, value) in enumerate(list(counts.items())[:4]):
            cards.append({"label": label, "value": str(value), "color": colors[i % len(colors)]})
        if cards:
            viz.append({"chart_type": "stat_cards", "title": "Summary", "data": {"cards": cards}})

    distribution = data_summary.get("distribution", {})
    if distribution:
        pie_data = [{"name": k, "value": v} for k, v in distribution.items() if v > 0]
        if pie_data:
            viz.append({"chart_type": "pie", "title": "Distribution", "data": pie_data})

    # Add table from detail_rows if available
    detail = data_summary.get("detail_rows")
    if detail and detail.get("columns") and detail.get("rows"):
        viz.append({"chart_type": "table", "title": "Details", "data": detail})

    return fallback_followups.get(intent, []), viz


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

async def handle_structured_query(
    intent: str,
    question: str,
    db: AsyncSession,
    tenant_id: str | None = None,
    contract_id: str | None = None,
) -> dict[str, Any] | None:
    """Execute a structured database query and enhance with LLM."""
    handlers = {
        "renewals": _handle_renewals,
        "obligations": _handle_obligations,
        "risk": _handle_risk,
        "portfolio": _handle_portfolio,
        "sla": _handle_sla,
    }

    handler = handlers.get(intent)
    if not handler:
        return None

    try:
        result = await handler(db, tenant_id, contract_id, question)
    except Exception as e:
        logger.warning(f"Structured query failed for intent '{intent}': {e}")
        return None

    # Enhance with LLM-generated follow-ups and visualizations
    follow_ups, visualizations = await _enhance_with_llm(
        intent=intent,
        question=question,
        answer=result["answer"],
        data_summary=result.get("data_summary", result.get("data", {})),
    )

    result["visualizations"] = visualizations
    result["follow_up_questions"] = follow_ups
    return result


# ---------------------------------------------------------------------------
# Handler: Renewals
# ---------------------------------------------------------------------------

async def _handle_renewals(
    db: AsyncSession,
    tenant_id: str | None,
    contract_id: str | None,
    question: str,
) -> dict[str, Any]:
    """Query contracts up for renewal — concise summary + rich data."""
    today = date.today()

    q_lower = question.lower()
    auto_renewal_filter = any(
        kw in q_lower for kw in ["auto-renewal", "auto renewal", "auto renew", "auto-renew"]
    )

    query = (
        select(Contract)
        .where(Contract.expiration_date.isnot(None))
        .order_by(Contract.expiration_date.asc())
    )
    if tenant_id:
        query = query.where(Contract.tenant_id == tenant_id)
    if auto_renewal_filter:
        query = query.where(Contract.auto_renewal == True)

    result = await db.execute(query)
    contracts = _dedup_contracts(result.scalars().all())

    expired, urgent, upcoming, later = [], [], [], []
    auto_renewal_count = 0
    total_value_at_risk = 0.0

    for c in contracts:
        exp = c.expiration_date
        if not exp:
            continue

        risk_level = (c.risk_level.value if hasattr(c.risk_level, "value") else str(c.risk_level or "")).lower()
        counterparty = _clean_counterparty(c.counterparty, c.filename)

        notice_date = None
        if c.notice_period_days:
            notice_date = exp - timedelta(days=c.notice_period_days)

        entry = {
            "filename": c.filename,
            "counterparty": counterparty,
            "type": c.contract_type or "Unknown",
            "expiration": str(exp),
            "auto_renewal": c.auto_renewal,
            "notice_period_days": c.notice_period_days,
            "notice_deadline": str(notice_date) if notice_date else None,
            "notice_passed": notice_date < today if notice_date else None,
            "value": f"{c.contract_value:,.0f}" if c.contract_value else None,
            "risk_level": risk_level,
        }

        if c.auto_renewal:
            auto_renewal_count += 1

        days_left = (exp - today).days
        entry["days_left"] = days_left

        if days_left < 0:
            expired.append(entry)
        elif days_left <= 90:
            urgent.append(entry)
            if c.contract_value:
                total_value_at_risk += float(c.contract_value)
        elif days_left <= 180:
            upcoming.append(entry)
        else:
            later.append(entry)

    # SHORT executive summary — not a list of every contract
    total = len(contracts)
    parts = []
    if auto_renewal_filter:
        parts.append(f"You have **{auto_renewal_count} contracts with auto-renewal clauses** across your portfolio.")
    else:
        parts.append(f"You have **{total} contracts** with expiration dates.")

    highlights = []
    if expired:
        highlights.append(f"**{len(expired)} expired**")
    if urgent:
        highlights.append(f"**{len(urgent)} expiring within 90 days**")
    if upcoming:
        highlights.append(f"**{len(upcoming)} due in 90–180 days**")
    if later:
        highlights.append(f"**{len(later)} beyond 180 days**")

    if highlights:
        parts.append(f"Breakdown: {', '.join(highlights)}.")

    if urgent and total_value_at_risk > 0:
        parts.append(f"Total value at risk in the next 90 days: **${total_value_at_risk:,.0f}**.")

    if expired:
        parts.append(f"\n⚠ {len(expired)} contract(s) have already expired and need immediate review.")

    # Build detail rows for table visualization
    detail_rows = []
    for e in (expired + urgent + upcoming + later):
        status = "Expired" if e["days_left"] < 0 else f"{e['days_left']}d left"
        auto = "Yes" if e["auto_renewal"] else "No"
        detail_rows.append([
            e["counterparty"][:25],
            e["type"],
            e["expiration"],
            status,
            auto,
        ])

    data_summary = {
        "counts": {
            "Total": total,
            "Expired": len(expired),
            "Urgent (≤90d)": len(urgent),
            "Upcoming (90-180d)": len(upcoming),
            "Later (>180d)": len(later),
            "Auto-Renewal": auto_renewal_count,
        },
        "distribution": {
            "Expired": len(expired),
            "Urgent": len(urgent),
            "Upcoming": len(upcoming),
            "Later": len(later),
        },
        "value_at_risk_urgent": total_value_at_risk,
        "detail_rows": {
            "columns": ["Counterparty", "Type", "Expires", "Status", "Auto-Renew"],
            "rows": detail_rows[:10],
        },
        "urgent_contracts": [
            {"name": e["counterparty"], "days_left": e["days_left"], "risk": e["risk_level"]}
            for e in urgent
        ],
        "expired_contracts": [
            {"name": e["counterparty"], "expired": e["expiration"]}
            for e in expired
        ],
    }

    return {
        "answer": "\n".join(parts),
        "data_summary": data_summary,
        "intent": "renewals",
    }


# ---------------------------------------------------------------------------
# Handler: Obligations
# ---------------------------------------------------------------------------

async def _handle_obligations(
    db: AsyncSession,
    tenant_id: str | None,
    contract_id: str | None,
    question: str,
) -> dict[str, Any]:
    """Query obligations — concise summary + rich data for visualization."""
    today = date.today()

    query = (
        select(Obligation, Contract.filename, Contract.counterparty, Contract.tenant_id)
        .join(Contract, Obligation.contract_id == Contract.id)
        .order_by(Obligation.deadline.asc().nulls_last())
    )
    if tenant_id:
        query = query.where(Contract.tenant_id == tenant_id)
    if contract_id:
        query = query.where(Obligation.contract_id == contract_id)

    result = await db.execute(query)
    rows = result.all()

    # Deduplicate
    seen = set()
    obligations = []
    fname_map = {}
    cp_map = {}
    for row in rows:
        o = row[0]
        fname = row[1]
        cp_raw = row[2]
        key = (o.description[:80] if o.description else "", fname)
        if key not in seen:
            seen.add(key)
            obligations.append(o)
            fname_map[o.id] = fname
            cp_map[o.id] = _clean_counterparty(cp_raw, fname)

    overdue, due_soon, upcoming = [], [], []
    by_party: dict[str, int] = defaultdict(int)
    by_type: dict[str, int] = defaultdict(int)
    by_status: dict[str, int] = defaultdict(int)
    critical_count = 0

    for o in obligations:
        party = o.obligated_party or "Unknown"
        by_party[party] += 1
        by_type[o.obligation_type or "Unclassified"] += 1
        by_status[o.status or "unknown"] += 1
        if o.is_critical:
            critical_count += 1

        entry = {
            "description": o.description[:80] if o.description else "No description",
            "full_description": o.description[:120] if o.description else "No description",
            "status": o.status or "unknown",
            "deadline": str(o.deadline) if o.deadline else "No deadline",
            "obligated_party": party,
            "contract": cp_map.get(o.id, "Unknown"),
            "type": o.obligation_type or "Unclassified",
            "is_critical": o.is_critical,
            "source_text": o.source_text or "",
            "section_reference": o.section_reference or "",
        }

        if o.deadline:
            days_left = (o.deadline - today).days
            entry["days_left"] = days_left
            if days_left < 0 and o.status not in ("completed", "fulfilled"):
                overdue.append(entry)
            elif days_left <= 30:
                due_soon.append(entry)
            else:
                upcoming.append(entry)
        else:
            upcoming.append(entry)

    # SHORT executive summary
    total = len(obligations)
    parts = []
    parts.append(f"You have **{total} obligations** across your contracts.")

    highlights = []
    if overdue:
        highlights.append(f"**{len(overdue)} overdue**")
    if due_soon:
        highlights.append(f"**{len(due_soon)} due within 30 days**")
    if critical_count:
        highlights.append(f"**{critical_count} marked critical**")

    if highlights:
        parts.append(f"Status: {', '.join(highlights)}.")

    if overdue:
        parts.append(f"\n⚠ **{len(overdue)} obligation(s) are past deadline** and require immediate attention.")
        # Include source text for overdue obligations so AI can answer "show me the original text"
        for e in overdue[:5]:
            src = e.get("source_text", "")
            sec = e.get("section_reference", "")
            if src:
                sec_label = f" (Section {sec})" if sec else ""
                parts.append(f"\n**{e['contract']}** — {e['description']}{sec_label}:")
                parts.append(f"> {src[:500]}")

    if not obligations:
        parts = ["No obligations found in your contracts."]

    # Build detail rows for table
    detail_rows = []
    for e in (overdue + due_soon + upcoming):
        status_label = e["status"]
        if "days_left" in e:
            if e["days_left"] < 0:
                status_label = f"Overdue ({abs(e['days_left'])}d)"
            else:
                status_label = f"{e['days_left']}d left"
        detail_rows.append([
            e["description"][:40],
            e["contract"][:20],
            e["type"][:15],
            e["deadline"],
            status_label,
        ])

    data_summary = {
        "counts": {
            "Total Obligations": total,
            "Overdue": len(overdue),
            "Due Within 30 Days": len(due_soon),
            "Upcoming": len(upcoming),
            "Critical": critical_count,
        },
        "distribution": {
            "Overdue": len(overdue),
            "Due Soon": len(due_soon),
            "Upcoming": len(upcoming),
        },
        "by_party": dict(by_party),
        "by_type": dict(by_type),
        "by_status": dict(by_status),
        "detail_rows": {
            "columns": ["Obligation", "Contract", "Type", "Deadline", "Status"],
            "rows": detail_rows[:8],
        },
        "overdue_items": [
            {"obligation": e["description"][:50], "contract": e["contract"],
             "deadline": e["deadline"], "days_overdue": abs(e.get("days_left", 0)),
             "source_text": e.get("source_text", ""),
             "section_reference": e.get("section_reference", "")}
            for e in overdue[:5]
        ],
    }

    return {
        "answer": "\n".join(parts),
        "data_summary": data_summary,
        "intent": "obligations",
    }


# ---------------------------------------------------------------------------
# Handler: Risk
# ---------------------------------------------------------------------------

async def _handle_risk(
    db: AsyncSession,
    tenant_id: str | None,
    contract_id: str | None,
    question: str,
) -> dict[str, Any]:
    """Query contracts by risk level — concise summary + rich data."""
    query = (
        select(Contract)
        .where(Contract.risk_level.isnot(None))
        .order_by(Contract.risk_score.desc().nulls_last())
    )
    if tenant_id:
        query = query.where(Contract.tenant_id == tenant_id)

    result = await db.execute(query)
    contracts = _dedup_contracts(result.scalars().all())

    by_level: dict[str, list] = {"critical": [], "high": [], "medium": [], "low": []}
    total_value = 0.0
    high_risk_value = 0.0

    for c in contracts:
        level = (c.risk_level.value if hasattr(c.risk_level, "value") else str(c.risk_level or "low")).lower()
        counterparty = _clean_counterparty(c.counterparty, c.filename)
        entry = {
            "filename": c.filename,
            "counterparty": counterparty,
            "risk_level": level,
            "risk_score": c.risk_score,
            "value": f"${c.contract_value:,.0f}" if c.contract_value else "N/A",
        }
        if level in by_level:
            by_level[level].append(entry)
        else:
            by_level["low"].append(entry)

        if c.contract_value:
            total_value += float(c.contract_value)
            if level in ("critical", "high"):
                high_risk_value += float(c.contract_value)

    total = len(contracts)
    high_count = len(by_level["critical"]) + len(by_level["high"])

    # SHORT executive summary
    parts = []
    parts.append(f"**{total} contracts** have been risk-assessed.")

    if high_count > 0:
        parts.append(f"**{high_count}** are at elevated risk (critical or high).")
        if high_risk_value > 0:
            parts.append(f"Combined value at risk: **${high_risk_value:,.0f}**.")
    else:
        parts.append("No contracts are at critical or high risk.")

    if not contracts:
        parts = ["No contracts with risk assessments found."]

    # Detail rows for table
    detail_rows = []
    for level in ["critical", "high", "medium", "low"]:
        for e in by_level[level]:
            score_str = str(e["risk_score"]) if e["risk_score"] else "—"
            detail_rows.append([
                e["counterparty"][:25],
                level.capitalize(),
                score_str,
                e["value"],
            ])

    data_summary = {
        "counts": {
            "Total Assessed": total,
            "Critical": len(by_level["critical"]),
            "High Risk": len(by_level["high"]),
            "Medium Risk": len(by_level["medium"]),
            "Low Risk": len(by_level["low"]),
        },
        "distribution": {
            "Critical": len(by_level["critical"]),
            "High": len(by_level["high"]),
            "Medium": len(by_level["medium"]),
            "Low": len(by_level["low"]),
        },
        "total_portfolio_value": total_value,
        "high_risk_value": high_risk_value,
        "detail_rows": {
            "columns": ["Contract", "Risk Level", "Score", "Value"],
            "rows": detail_rows[:8],
        },
        "high_risk_contracts": [
            {"name": e["counterparty"], "score": e["risk_score"], "value": e["value"]}
            for e in (by_level["critical"] + by_level["high"])
        ],
    }

    return {
        "answer": "\n".join(parts),
        "data_summary": data_summary,
        "intent": "risk",
    }


# ---------------------------------------------------------------------------
# Handler: Portfolio
# ---------------------------------------------------------------------------

async def _handle_portfolio(
    db: AsyncSession,
    tenant_id: str | None,
    contract_id: str | None,
    question: str,
) -> dict[str, Any]:
    """Portfolio-level summary — concise + rich data."""
    base_filter = []
    if tenant_id:
        base_filter.append(Contract.tenant_id == tenant_id)

    q = select(Contract)
    if base_filter:
        q = q.where(*base_filter)
    all_rows = (await db.execute(q)).scalars().all()
    contracts = _dedup_contracts(all_rows)

    total = len(contracts)
    by_type = dict(Counter(
        str(c.contract_type or "unclassified")
        for c in contracts
    ))
    by_status = dict(Counter(
        (c.status.value if hasattr(c.status, "value") else str(c.status or "unknown"))
        for c in contracts
    ))
    total_value = sum(c.contract_value or 0 for c in contracts)
    by_risk = dict(Counter(
        (c.risk_level.value if hasattr(c.risk_level, "value") else str(c.risk_level or "unassessed"))
        for c in contracts
    ))

    # Count expiring soon
    today = date.today()
    expiring_90d = sum(
        1 for c in contracts
        if c.expiration_date and 0 < (c.expiration_date - today).days <= 90
    )

    # SHORT executive summary
    parts = []
    parts.append(f"Your portfolio contains **{total} contracts** worth **${total_value:,.0f}** total.")

    type_top = sorted(by_type.items(), key=lambda x: x[1], reverse=True)[:3]
    if type_top:
        type_str = ", ".join(f"{t} ({c})" for t, c in type_top)
        parts.append(f"Top types: {type_str}.")

    high_risk = by_risk.get("critical", 0) + by_risk.get("high", 0)
    if high_risk:
        parts.append(f"**{high_risk}** at elevated risk.")
    if expiring_90d:
        parts.append(f"**{expiring_90d}** expiring within 90 days.")

    if not contracts:
        parts = ["No contracts found in your portfolio."]

    # Detail rows
    detail_rows = []
    for c in contracts:
        ctype = str(c.contract_type or "—")
        risk = c.risk_level.value if hasattr(c.risk_level, "value") else str(c.risk_level or "—")
        cp = _clean_counterparty(c.counterparty, c.filename)
        val = f"${c.contract_value:,.0f}" if c.contract_value else "—"
        detail_rows.append([cp[:25], ctype, risk.capitalize(), val])

    data_summary = {
        "counts": {
            "Total Contracts": total,
            "Portfolio Value": f"${total_value:,.0f}",
            "Contract Types": len(by_type),
            "Expiring (90d)": expiring_90d,
        },
        "by_type": by_type,
        "by_status": by_status,
        "by_risk": by_risk,
        "total_value": total_value,
        "detail_rows": {
            "columns": ["Counterparty", "Type", "Risk", "Value"],
            "rows": detail_rows[:8],
        },
    }

    return {
        "answer": "\n".join(parts),
        "data_summary": data_summary,
        "intent": "portfolio",
    }


# ---------------------------------------------------------------------------
# Handler: SLA
# ---------------------------------------------------------------------------

async def _handle_sla(
    db: AsyncSession,
    tenant_id: str | None,
    contract_id: str | None,
    question: str,
) -> dict[str, Any]:
    """Query SLA metrics — concise summary + rich data."""
    from app.models.knowledge_graph import KGEntity, KGEntityType

    query = select(KGEntity).where(KGEntity.entity_type == KGEntityType.SLA_METRIC)
    if tenant_id:
        query = query.where(KGEntity.tenant_id == tenant_id)
    if contract_id:
        query = query.where(KGEntity.contract_id == contract_id)

    result = await db.execute(query)
    sla_entities = result.scalars().all()

    by_contract: dict[str, list] = defaultdict(list)

    contract_ids = {str(e.contract_id) for e in sla_entities}
    if contract_ids:
        c_result = await db.execute(
            select(Contract.id, Contract.filename)
            .where(Contract.id.in_([e.contract_id for e in sla_entities]))
        )
        id_to_name = {str(row[0]): row[1] for row in c_result.all()}
    else:
        id_to_name = {}

    with_targets = 0
    for e in sla_entities:
        fname = id_to_name.get(str(e.contract_id), "Unknown")
        props = e.properties or {}
        target = props.get("target") or props.get("target_value")
        if target:
            with_targets += 1
        by_contract[fname].append({
            "metric": e.name,
            "target": target,
            "source": e.source_text[:80] if e.source_text else None,
        })

    total_slas = sum(len(m) for m in by_contract.values())

    # SHORT executive summary
    parts = []
    if total_slas > 0:
        parts.append(f"Found **{total_slas} SLA metrics** across **{len(by_contract)} contracts**.")
        if with_targets:
            parts.append(f"**{with_targets}** have defined targets, **{total_slas - with_targets}** are missing targets.")
    else:
        parts.append("No SLA metrics found in your contracts.")

    # Detail rows
    detail_rows = []
    for fname, metrics in sorted(by_contract.items()):
        for m in metrics:
            detail_rows.append([
                fname.rsplit(".", 1)[0][:25],
                m["metric"][:30],
                str(m["target"])[:20] if m["target"] else "Not defined",
            ])

    data_summary = {
        "counts": {
            "Total SLA Metrics": total_slas,
            "Contracts with SLAs": len(by_contract),
            "With Targets": with_targets,
            "Missing Targets": total_slas - with_targets,
        },
        "sla_per_contract": {fname: len(metrics) for fname, metrics in by_contract.items()},
        "detail_rows": {
            "columns": ["Contract", "Metric", "Target"],
            "rows": detail_rows[:8],
        },
        "sample_metrics": [
            {"contract": fname, "metric": m["metric"], "target": m["target"]}
            for fname, metrics in list(by_contract.items())[:3]
            for m in metrics[:2]
        ],
    }

    return {
        "answer": "\n".join(parts),
        "data_summary": data_summary,
        "intent": "sla",
    }
