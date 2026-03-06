"""Intent router for contract Q&A.

Detects whether a question should be answered from structured data (PostgreSQL)
or from document content (ChromaDB RAG). Routes accordingly and formats
human-readable responses with LLM-generated visualizations and follow-ups.
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

_ENHANCE_PROMPT = """You are a contract analytics assistant. Given a structured query result,
generate contextual follow-up questions and visualization specifications.

AVAILABLE CHART TYPES (use the exact data format shown):

1. stat_cards — Headline KPI cards (always include as first visualization)
   data: {"cards": [{"label": "Label", "value": "42", "color": "#hex"}]}
   Use for: key summary numbers the user should see at a glance

2. pie — Donut chart for proportional composition
   data: [{"name": "Segment", "value": 10}]
   Use for: showing how a whole breaks down (contract types, risk distribution)
   Best when: 2-7 segments, user cares about relative proportions

3. bar — Horizontal bar chart for comparisons
   data: [{"name": "Category", "count": 5, "fill": "#hex"}]
   Use for: comparing quantities, rankings, ordered categories
   Best when: order matters (urgency levels, rankings by count)

COLOR SEMANTICS:
- Red (#ef4444): danger, critical, expired, overdue
- Orange (#f97316): warning, high risk, urgent
- Yellow (#eab308): caution, medium risk, upcoming
- Green (#22c55e): safe, low risk, compliant, later
- Blue (#3b82f6): neutral, informational, totals
- Purple (#8b5cf6): categories, types
- Teal (#06b6d4): secondary metrics

RULES:
- Generate exactly 3 follow-up questions that are specific to the data shown
  (reference actual contract names, counterparties, risk levels, deadlines when relevant)
- Follow-ups should lead to DIFFERENT types of analysis (not repeat the same query)
- Include 2-3 visualizations maximum (always start with stat_cards)
- Pick chart types that best represent the data shape — do NOT default to bar charts
- For distributions/composition → use pie
- For ordered comparisons/rankings → use bar
- Keep stat card values short (numbers, percentages, dollar amounts)

Respond with ONLY valid JSON (no markdown, no explanation):
{
  "follow_up_questions": ["question1", "question2", "question3"],
  "visualizations": [
    {"chart_type": "stat_cards|bar|pie", "title": "...", "data": ...}
  ]
}"""


async def _enhance_with_llm(
    intent: str,
    question: str,
    answer: str,
    data_summary: dict,
) -> tuple[list[str], list[dict]]:
    """Use LLM to generate contextual follow-ups and adaptive visualizations.

    Args:
        intent: The detected intent category.
        question: The user's original question.
        answer: The formatted text answer.
        data_summary: Condensed data summary for the LLM.

    Returns:
        Tuple of (follow_up_questions, visualizations).
    """
    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        user_message = (
            f"Intent: {intent}\n"
            f"User question: {question}\n\n"
            f"Answer provided:\n{answer[:1500]}\n\n"
            f"Data summary:\n{json.dumps(data_summary, indent=2, default=str)[:2000]}"
        )

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _ENHANCE_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        follow_ups = result.get("follow_up_questions", [])[:3]
        visualizations = result.get("visualizations", [])[:3]

        # Validate visualization structure
        valid_viz = []
        for viz in visualizations:
            if (
                isinstance(viz, dict)
                and "chart_type" in viz
                and "title" in viz
                and "data" in viz
                and viz["chart_type"] in ("stat_cards", "bar", "pie")
            ):
                valid_viz.append(viz)

        if not valid_viz or not follow_ups:
            logger.warning("LLM enhancement returned incomplete results, using fallback")
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
    # Simple follow-ups per intent
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

    # Simple heuristic visualizations
    viz = []
    counts = data_summary.get("counts", {})
    if counts:
        # Stat cards from counts
        cards = []
        colors = ["#3b82f6", "#8b5cf6", "#ef4444", "#22c55e", "#f97316", "#06b6d4"]
        for i, (label, value) in enumerate(list(counts.items())[:4]):
            cards.append({"label": label, "value": str(value), "color": colors[i % len(colors)]})
        if cards:
            viz.append({"chart_type": "stat_cards", "title": "Summary", "data": {"cards": cards}})

    distribution = data_summary.get("distribution", {})
    if distribution:
        # Use pie for distributions
        pie_data = [{"name": k, "value": v} for k, v in distribution.items() if v > 0]
        if pie_data:
            viz.append({"chart_type": "pie", "title": "Distribution", "data": pie_data})

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
    """Query contracts up for renewal with actionable deadlines."""
    today = date.today()

    # Check if question is specifically about auto-renewal
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

    # Categorize
    expired, urgent, upcoming, later = [], [], [], []
    auto_renewal_count = 0
    total_value_at_risk = 0.0

    for c in contracts:
        exp = c.expiration_date
        if not exp:
            continue

        notice_date = None
        if c.notice_period_days:
            notice_date = exp - timedelta(days=c.notice_period_days)

        risk_level = (c.risk_level.value if hasattr(c.risk_level, "value") else str(c.risk_level or "")).lower()
        counterparty = _clean_counterparty(c.counterparty, c.filename)

        entry = {
            "filename": c.filename,
            "counterparty": counterparty,
            "type": c.contract_type or "Unknown",
            "expiration": str(exp),
            "auto_renewal": c.auto_renewal,
            "notice_period_days": c.notice_period_days,
            "notice_deadline": str(notice_date) if notice_date else None,
            "notice_passed": notice_date < today if notice_date else None,
            "value": f"{c.contract_value:,.2f} {c.currency or 'USD'}" if c.contract_value else None,
            "risk_level": risk_level,
            "risk_score": c.risk_score,
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

    # Build natural language answer
    parts = []
    if auto_renewal_filter:
        parts.append(f"**Contracts with Auto-Renewal Clauses** (as of {today.strftime('%B %d, %Y')}):\n")
    else:
        parts.append(f"As of {today.strftime('%B %d, %Y')}, here is your renewal status:\n")

    if expired:
        parts.append(f"**EXPIRED ({len(expired)}):**")
        for e in expired:
            risk = _risk_badge(e.get("risk_level"))
            parts.append(
                f"  - **{e['filename']}** ({e['counterparty']}){risk}"
                f" — expired {e['expiration']} ({abs(e['days_left'])} days ago)"
            )

    if urgent:
        parts.append(f"\n**URGENT — Expiring within 90 days ({len(urgent)}):**")
        for e in urgent:
            notice_warning = ""
            if e["notice_deadline"] and e["notice_passed"]:
                notice_warning = f" **Notice deadline PASSED ({e['notice_deadline']})**"
            elif e["notice_deadline"]:
                notice_warning = f" Notice due by {e['notice_deadline']}"
            auto = " (auto-renews)" if e["auto_renewal"] else ""
            value = f" — {e['value']}" if e["value"] else ""
            risk = _risk_badge(e.get("risk_level"))
            parts.append(
                f"  - **{e['filename']}** ({e['counterparty']}){risk}"
                f" — expires {e['expiration']} ({e['days_left']} days){auto}{value}{notice_warning}"
            )

    if upcoming:
        parts.append(f"\n**UPCOMING — Expiring in 90-180 days ({len(upcoming)}):**")
        for e in upcoming:
            auto = " (auto-renews)" if e["auto_renewal"] else ""
            value = f" — {e['value']}" if e["value"] else ""
            notice_info = f" Notice due by {e['notice_deadline']}" if e["notice_deadline"] else ""
            risk = _risk_badge(e.get("risk_level"))
            parts.append(
                f"  - **{e['filename']}** ({e['counterparty']}){risk}"
                f" — expires {e['expiration']} ({e['days_left']} days){auto}{value}{notice_info}"
            )

    if later:
        parts.append(f"\n**LATER — Beyond 180 days ({len(later)}):**")
        for e in later:
            auto = " (auto-renews)" if e["auto_renewal"] else ""
            risk = _risk_badge(e.get("risk_level"))
            parts.append(f"  - {e['filename']}{risk} — expires {e['expiration']}{auto}")

    if not expired and not urgent and not upcoming and not later:
        if auto_renewal_filter:
            parts.append("No contracts with auto-renewal clauses found.")
        else:
            parts.append("No contracts with expiration dates found.")

    # Action items
    if urgent or expired:
        parts.append("\n**Recommended actions:**")
        if expired:
            parts.append(f"  1. Review {len(expired)} expired contract(s) — decide whether to renegotiate or terminate")
        if urgent:
            for e in urgent:
                if e.get("notice_passed"):
                    parts.append(f"  - {e['filename']}: Notice deadline has passed — contact {e['counterparty']} immediately")
                elif e.get("notice_deadline"):
                    parts.append(f"  - {e['filename']}: Send renewal notice by {e['notice_deadline']}")

    # Data summary for LLM enhancement
    data_summary = {
        "counts": {
            "Expired": len(expired),
            "Urgent (≤90 days)": len(urgent),
            "Upcoming (90-180 days)": len(upcoming),
            "Later (>180 days)": len(later),
            "Auto-renewal": auto_renewal_count,
            "Total contracts": len(contracts),
        },
        "distribution": {
            "Expired": len(expired),
            "Urgent": len(urgent),
            "Upcoming": len(upcoming),
            "Later": len(later),
        },
        "value_at_risk_urgent": total_value_at_risk,
        "urgent_contracts": [
            {"name": e["filename"], "counterparty": e["counterparty"],
             "days_left": e["days_left"], "risk": e["risk_level"]}
            for e in urgent
        ],
        "expired_contracts": [
            {"name": e["filename"], "counterparty": e["counterparty"]}
            for e in expired
        ],
    }

    return {
        "answer": "\n".join(parts),
        "data": {"expired": expired, "urgent": urgent, "upcoming": upcoming, "later": later},
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
    """Query obligations with deadlines and status."""
    today = date.today()

    query = (
        select(Obligation, Contract.filename, Contract.tenant_id)
        .join(Contract, Obligation.contract_id == Contract.id)
        .order_by(Obligation.deadline.asc().nulls_last())
    )
    if tenant_id:
        query = query.where(Contract.tenant_id == tenant_id)
    if contract_id:
        query = query.where(Obligation.contract_id == contract_id)

    result = await db.execute(query)
    rows = result.all()

    # Deduplicate by description + contract filename
    seen = set()
    obligations = []
    for row in rows:
        o = row[0]
        fname = row[1]
        key = (o.description[:80] if o.description else "", fname)
        if key not in seen:
            seen.add(key)
            obligations.append(o)

    overdue, due_soon, upcoming = [], [], []
    by_party: dict[str, int] = defaultdict(int)
    by_type: dict[str, int] = defaultdict(int)
    critical_count = 0

    for o in obligations:
        party = o.obligated_party or "Unknown"
        by_party[party] += 1
        by_type[o.obligation_type or "unclassified"] += 1
        if o.is_critical:
            critical_count += 1

        entry = {
            "description": o.description[:120] if o.description else "No description",
            "status": o.status or "unknown",
            "deadline": str(o.deadline) if o.deadline else "No deadline",
            "obligated_party": party,
            "priority": o.priority or "normal",
            "is_critical": o.is_critical,
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

    parts = []
    parts.append(f"**Obligation Summary** (as of {today.strftime('%B %d, %Y')}):\n")

    if overdue:
        parts.append(f"**OVERDUE ({len(overdue)}):**")
        for o in overdue:
            critical = " [CRITICAL]" if o["is_critical"] else ""
            parts.append(
                f"  - {o['description']} — due {o['deadline']}"
                f" ({abs(o['days_left'])} days overdue){critical}"
            )

    if due_soon:
        parts.append(f"\n**DUE WITHIN 30 DAYS ({len(due_soon)}):**")
        for o in due_soon:
            parts.append(f"  - {o['description']} — due {o['deadline']} ({o['days_left']} days)")

    if upcoming:
        parts.append(f"\n**UPCOMING ({len(upcoming)}):**")
        for o in upcoming[:10]:
            parts.append(f"  - {o['description']} — {o['deadline']}")
        if len(upcoming) > 10:
            parts.append(f"  ... and {len(upcoming) - 10} more")

    if not obligations:
        parts.append("No obligations found.")

    # Data summary for LLM
    data_summary = {
        "counts": {
            "Total Obligations": len(obligations),
            "Overdue": len(overdue),
            "Due within 30 days": len(due_soon),
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
    }

    return {
        "answer": "\n".join(parts),
        "data": {"overdue": overdue, "due_soon": due_soon, "upcoming": upcoming},
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
    """Query contracts by risk level."""
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
            "value": f"{c.contract_value:,.2f} {c.currency or 'USD'}" if c.contract_value else None,
        }
        if level in by_level:
            by_level[level].append(entry)
        else:
            by_level["low"].append(entry)

        if c.contract_value:
            total_value += float(c.contract_value)
            if level in ("critical", "high"):
                high_risk_value += float(c.contract_value)

    parts = []
    parts.append("**Contract Risk Overview:**\n")

    for level in ["critical", "high", "medium", "low"]:
        items = by_level[level]
        if items:
            label = level.upper()
            parts.append(f"**{label} RISK ({len(items)}):**")
            for e in items:
                score = f" (score: {e['risk_score']})" if e["risk_score"] else ""
                value = f" — {e['value']}" if e["value"] else ""
                parts.append(f"  - {e['filename']} with {e['counterparty']}{score}{value}")

    total = len(contracts)
    high_count = len(by_level["critical"]) + len(by_level["high"])
    if high_count > 0:
        parts.append(f"\n**{high_count} out of {total} contracts** require attention due to elevated risk.")

    if not contracts:
        parts.append("No contracts with risk assessments found.")

    # Data summary for LLM
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
        "high_risk_contracts": [
            {"name": e["filename"], "counterparty": e["counterparty"],
             "score": e["risk_score"], "value": e["value"]}
            for e in (by_level["critical"] + by_level["high"])
        ],
    }

    return {
        "answer": "\n".join(parts),
        "data": by_level,
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
    """Portfolio-level summary."""
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
        (c.contract_type.value if hasattr(c.contract_type, "value") else str(c.contract_type or "unclassified"))
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

    parts = []
    parts.append("**Contract Portfolio Summary:**\n")
    parts.append(f"**Total contracts:** {total}")
    parts.append(f"**Total portfolio value:** ${total_value:,.2f}\n")

    parts.append("**By type:**")
    for t, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
        parts.append(f"  - {t}: {count}")

    parts.append("\n**By status:**")
    for s, count in sorted(by_status.items(), key=lambda x: x[1], reverse=True):
        parts.append(f"  - {s}: {count}")

    parts.append("\n**By risk level:**")
    for r, count in sorted(by_risk.items()):
        parts.append(f"  - {r}: {count}")

    # Data summary for LLM
    data_summary = {
        "counts": {
            "Total Contracts": total,
            "Portfolio Value": f"${total_value:,.0f}",
            "Contract Types": len(by_type),
            "High/Critical Risk": by_risk.get("critical", 0) + by_risk.get("high", 0),
        },
        "by_type": by_type,
        "by_status": by_status,
        "by_risk": by_risk,
        "total_value": total_value,
    }

    return {
        "answer": "\n".join(parts),
        "data": {"total": total, "total_value": total_value, "by_type": by_type, "by_status": by_status, "by_risk": by_risk},
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
    """Query SLA metrics from knowledge graph entities."""
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
            "source": e.source_text[:100] if e.source_text else None,
        })

    parts = []
    parts.append("**SLA Metrics Across Your Contracts:**\n")

    if by_contract:
        for fname, metrics in sorted(by_contract.items()):
            parts.append(f"**{fname}:**")
            for m in metrics:
                target = f" — Target: {m['target']}" if m["target"] else ""
                parts.append(f"  - {m['metric']}{target}")
    else:
        parts.append("No SLA metrics found in your contracts.")

    total_slas = sum(len(m) for m in by_contract.values())

    # Data summary for LLM
    data_summary = {
        "counts": {
            "Total SLA Metrics": total_slas,
            "Contracts with SLAs": len(by_contract),
            "With Targets Defined": with_targets,
            "Missing Targets": total_slas - with_targets,
        },
        "sla_per_contract": {fname: len(metrics) for fname, metrics in by_contract.items()},
        "sample_metrics": [
            {"contract": fname, "metric": m["metric"], "target": m["target"]}
            for fname, metrics in list(by_contract.items())[:3]
            for m in metrics[:2]
        ],
    }

    return {
        "answer": "\n".join(parts),
        "data": {"by_contract": dict(by_contract)},
        "data_summary": data_summary,
        "intent": "sla",
    }
