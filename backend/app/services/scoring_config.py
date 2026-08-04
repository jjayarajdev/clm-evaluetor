"""Configurable scoring rules for At-Risk and Compliance metrics.

These used to be hardcoded (a contract "at risk" at >=2 overdue obligations or
>30% overdue; Compliance = obligations*0.6 + SLA*0.4). Now they're resolved per
request from a hierarchy that mirrors the rest of the platform config:

    DEFAULT  ->  tenant.config_overrides["scoring"]  ->  BU.config_overrides["scoring"]

Later (more specific) sources win. Anything a source doesn't set falls back to
the default, so partial overrides are safe.
"""

from copy import deepcopy


DEFAULT_SCORING_CONFIG: dict = {
    "at_risk": {
        # Which signal defines "at risk": obligation lateness, AI risk level, or both.
        "definition": "obligations",  # "obligations" | "risk_level" | "both"
        # Obligation-based: at risk if >= N overdue OR more than this fraction overdue.
        "overdue_count_threshold": 2,
        "overdue_ratio_threshold": 0.3,
        # Risk-level-based: which AI risk levels count as at risk.
        "risk_levels": ["high", "critical"],
    },
    "compliance": {
        # Overall compliance = weighted blend of the measured components.
        "obligation_weight": 0.6,
        "sla_weight": 0.4,
    },
    "vendor": {
        # Composite vendor score weights. Responsiveness and issue-rate are
        # reserved — those signals aren't measured anywhere yet, so the blend
        # only includes measured signals with their weights renormalized.
        "obligation_weight": 0.40,
        "sla_weight": 0.30,
        "responsiveness_weight": 0.20,
        "issue_rate_weight": 0.10,
        # Risk bands: score >= low_threshold -> low, >= medium_threshold ->
        # medium, >= high_threshold -> high, else critical.
        "low_threshold": 80,
        "medium_threshold": 60,
        "high_threshold": 40,
        # A vendor counts as "at risk" when its composite score is below this.
        "at_risk_threshold": 60,
    },
}

_NUMERIC_KEYS = {"overdue_count_threshold", "overdue_ratio_threshold",
                 "obligation_weight", "sla_weight",
                 "responsiveness_weight", "issue_rate_weight",
                 "low_threshold", "medium_threshold", "high_threshold",
                 "at_risk_threshold"}


def resolve_scoring_config(*override_sources: dict | None) -> dict:
    """Merge DEFAULT with each source's ``["scoring"]`` block (later sources win).

    Each source is a ``config_overrides`` dict (tenant, then BU) that MAY contain
    a ``"scoring"`` key. Only known keys with sane types are applied.
    """
    cfg = deepcopy(DEFAULT_SCORING_CONFIG)
    for src in override_sources:
        scoring = ((src or {}).get("scoring")) or {}
        if not isinstance(scoring, dict):
            continue
        for section in cfg:
            override = scoring.get(section)
            if not isinstance(override, dict):
                continue
            for k, v in override.items():
                if k not in cfg[section]:
                    continue
                if k in _NUMERIC_KEYS and not isinstance(v, (int, float)):
                    continue
                cfg[section][k] = v
    return cfg
