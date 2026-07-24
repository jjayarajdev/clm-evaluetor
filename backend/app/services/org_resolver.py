"""Canonical organization resolution.

Counterparty is free text, so one organization fragments across variants
("ING", "ING Bank N.V.", "ING Group"). This maps any variant to a stable
canonical key by stripping legal suffixes and generic corporate descriptors
down to the distinctive core token(s). Equal keys = same organization.

Conservative by design: it only strips well-known suffixes/descriptors, so
distinct names ("Micro Focus" vs "Microsoft") keep distinct keys.
"""

import re

# Legal-entity suffixes (dot/space-insensitive), matched at the end.
_LEGAL_SUFFIXES = {
    "inc", "incorporated", "llc", "llp", "ltd", "limited", "corp",
    "corporation", "co", "company", "gmbh", "ag", "nv", "bv", "plc",
    "pvt", "private", "sa", "spa", "srl", "pte", "pty", "kg", "oy", "ab",
    "as", "sas", "sarl",
}

# Generic descriptors that don't distinguish one org from another.
_GENERIC_DESCRIPTORS = {
    "group", "holding", "holdings", "bank", "technologies", "technology",
    "services", "service", "solutions", "systems", "international",
    "global", "worldwide", "enterprises", "industries", "partners",
    "consulting", "supplier", "vendor", "the", "products", "product",
}


def _tokens(name: str) -> list[str]:
    # Split on non-alphanumerics, lowercase
    return [t for t in re.split(r"[^a-z0-9]+", (name or "").lower()) if t]


def canonical_org_key(name: str | None) -> str:
    """Distinctive core of an organization name, for grouping variants."""
    tokens = _tokens(name)
    if not tokens:
        return ""
    # Drop trailing legal suffixes and single-letter abbreviation fragments
    # ("N.V." -> n, v; "pvt ltd" -> two suffixes).
    while tokens and (tokens[-1] in _LEGAL_SUFFIXES or len(tokens[-1]) == 1):
        tokens.pop()
    # Drop generic descriptors anywhere
    core = [t for t in tokens if t not in _GENERIC_DESCRIPTORS]
    if not core:
        core = tokens  # everything was generic — keep original tokens
    return " ".join(core)


def choose_display_name(names: list[str]) -> str:
    """Pick the best human display name among variants of one organization.

    Prefers a name that carries a legal suffix (more official), then the
    longest — 'ING Bank N.V.' over 'ING'.
    """
    if not names:
        return ""
    def score(n: str) -> tuple[int, int]:
        toks = _tokens(n)
        has_suffix = 1 if toks and toks[-1] in _LEGAL_SUFFIXES else 0
        return (has_suffix, len(n))
    return max(names, key=score)


def group_by_organization(names: list[str]) -> dict[str, list[str]]:
    """Group counterparty strings by canonical key.

    Returns {canonical_key: [variant, ...]}. Empty-key names are grouped
    each under their own lowercased string (no safe canonical form).
    """
    groups: dict[str, list[str]] = {}
    for name in names:
        if not name:
            continue
        key = canonical_org_key(name) or name.strip().lower()
        groups.setdefault(key, []).append(name)
    return groups
