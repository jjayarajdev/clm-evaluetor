"""Contract type normalization.

The metadata agent returns contract types as free text ("Statement of Work
(SOW)", "Schedules of Work", ...). Stored raw, one concept fragments into
many values, which breaks type filters, schema lookup, and profile matching.
This module maps any phrasing to a canonical code via tiers:

1. exact alias match
2. parenthetical acronym ("Statement of Work (SOW)" → try "SOW" and base)
3. plural folding ("Statements of Work" → "Statement of Work")
4. whole-word substring against the longest aliases
"""

import re

# Canonical alias table (keys uppercase). Extend freely — longest keys win
# in the substring tier.
CONTRACT_TYPE_ALIASES: dict[str, str] = {
    # NDA variants
    "NDA": "nda",
    "NON-DISCLOSURE AGREEMENT": "nda",
    "NON DISCLOSURE AGREEMENT": "nda",
    "NONDISCLOSURE AGREEMENT": "nda",
    "MUTUAL NON-DISCLOSURE AGREEMENT": "nda",
    "MUTUAL NDA": "nda",
    "CONFIDENTIALITY AGREEMENT": "nda",
    "MUTUAL CONFIDENTIALITY AGREEMENT": "nda",
    "CONFIDENTIAL DISCLOSURE AGREEMENT": "nda",
    "CDA": "nda",
    # MSA variants
    "MSA": "msa",
    "MASTER SERVICES AGREEMENT": "msa",
    "MASTER SERVICE AGREEMENT": "msa",
    "MASTER AGREEMENT": "msa",
    "FRAMEWORK AGREEMENT": "msa",
    "SERVICES AGREEMENT": "msa",
    "SERVICE AGREEMENT": "msa",
    "PROFESSIONAL SERVICES AGREEMENT": "msa",
    "MANAGED SERVICES AGREEMENT": "msa",
    "MASTER PROFESSIONAL AND MANAGED SERVICES AGREEMENT": "msa",
    "CONSULTING AGREEMENT": "msa",
    "CONSULTING SERVICES AGREEMENT": "msa",
    "BUSINESS PROCESS OUTSOURCING AGREEMENT": "msa",
    "BPO AGREEMENT": "msa",
    "OUTSOURCING AGREEMENT": "msa",
    # SOW variants
    "SOW": "sow",
    "STATEMENT OF WORK": "sow",
    "SCHEDULE OF WORK": "sow",
    "SCOPE OF WORK": "sow",
    "WORK ORDER": "sow",
    "PURCHASE ORDER": "sow",
    "TASK ORDER": "sow",
    "PROJECT ORDER": "sow",
    "SCHEDULE": "sow",
    "SERVICE ORDER": "sow",
    "ORDER FORM": "sow",
    "CSOW": "sow",
    "CHANGE SOW": "sow",
    "CHANGE STATEMENT OF WORK": "sow",
    # Amendment variants
    "AMENDMENT": "amendment",
    "ADDENDUM": "amendment",
    "CONTRACT AMENDMENT": "amendment",
    "FIRST AMENDMENT": "amendment",
    "SECOND AMENDMENT": "amendment",
    "THIRD AMENDMENT": "amendment",
    "MODIFICATION": "amendment",
    "CONTRACT MODIFICATION": "amendment",
    "SUPPLEMENT": "amendment",
    "SUPPLEMENTAL AGREEMENT": "amendment",
    "CHANGE ORDER": "amendment",
    "SIDE LETTER": "amendment",
    "LETTER AMENDMENT": "amendment",
    # Vendor agreement variants
    "VENDOR": "vendor_agreement",
    "VENDOR_AGREEMENT": "vendor_agreement",
    "VENDOR AGREEMENT": "vendor_agreement",
    "SUPPLIER AGREEMENT": "vendor_agreement",
    "PROCUREMENT AGREEMENT": "vendor_agreement",
    "RESELLER AGREEMENT": "vendor_agreement",
    "DISTRIBUTION AGREEMENT": "vendor_agreement",
    "PARTNERSHIP AGREEMENT": "vendor_agreement",
    "JOINT VENTURE AGREEMENT": "vendor_agreement",
    # License / SaaS
    "LICENSE AGREEMENT": "license",
    "SOFTWARE LICENSE AGREEMENT": "license",
    "SAAS AGREEMENT": "license",
    "SAAS SUBSCRIPTION AGREEMENT": "license",
    "SUBSCRIPTION AGREEMENT": "license",
    # Lease
    "LEASE AGREEMENT": "lease",
    "LEASE": "lease",
    "RENTAL AGREEMENT": "lease",
    # Employment variants
    "EMPLOYMENT": "employment_contract",
    "EMPLOYMENT_CONTRACT": "employment_contract",
    "EMPLOYMENT CONTRACT": "employment_contract",
    "EMPLOYMENT AGREEMENT": "employment_contract",
    "OFFER LETTER": "employment_contract",
    "INDEPENDENT CONTRACTOR AGREEMENT": "employment_contract",
    "CONTRACTOR AGREEMENT": "employment_contract",
    "FREELANCE AGREEMENT": "employment_contract",
    "SEPARATION AGREEMENT": "employment_contract",
    "NON-COMPETE AGREEMENT": "employment_contract",
    "NON COMPETE AGREEMENT": "employment_contract",
    "NONCOMPETE AGREEMENT": "employment_contract",
    # Manufacturing types
    "SUPPLY AGREEMENT": "supply_agreement",
    "QUALITY AGREEMENT": "quality_agreement",
    "BLANKET PURCHASE ORDER": "blanket_po",
    "BLANKET PO": "blanket_po",
    "TOOLING AGREEMENT": "tooling_agreement",
    "TOLL MANUFACTURING AGREEMENT": "toll_manufacturing",
    # Pharma types
    "CLINICAL SUPPLY AGREEMENT": "csa",
    "CSA": "csa",
    "CMO AGREEMENT": "cmo_agreement",
    "CONTRACT MANUFACTURING AGREEMENT": "cmo_agreement",
    "CRO AGREEMENT": "cro_agreement",
    "CLINICAL RESEARCH AGREEMENT": "cro_agreement",
    "PHARMACOVIGILANCE AGREEMENT": "pharmacovigilance",
}

# Generic phrases that appear inside many DISTINCT types ("Network Services
# Agreement" is not an MSA) — excluded from the substring tier so it only
# fires on distinctive aliases.
_GENERIC_ALIASES = {
    "SERVICES AGREEMENT",
    "SERVICE AGREEMENT",
    "MASTER AGREEMENT",
    "SCHEDULE",
    "LEASE",
    "VENDOR",
    "EMPLOYMENT",
    "SUPPLEMENT",
    "MODIFICATION",
    "PURCHASE ORDER",
    "WORK ORDER",
    "SERVICE ORDER",
}

# Aliases sorted longest-first for the substring tier; skip very short and
# generic keys to avoid collapsing genuinely distinct types.
_SUBSTRING_ALIASES = sorted(
    (k for k in CONTRACT_TYPE_ALIASES if len(k) >= 3 and k not in _GENERIC_ALIASES),
    key=len,
    reverse=True,
)

_PAREN_RE = re.compile(r"\(([^)]*)\)")


def _clean(raw: str) -> str:
    """Uppercase, underscores/hyphens to spaces, collapse whitespace."""
    return re.sub(r"\s+", " ", raw.upper().replace("_", " ").replace("-", " ")).strip()


def _depluralize(text: str) -> str:
    """Fold simple plurals: 'STATEMENTS OF WORK' → 'STATEMENT OF WORK'."""
    words = []
    for w in text.split(" "):
        if len(w) > 3 and w.endswith("S") and not w.endswith("SS"):
            words.append(w[:-1])
        else:
            words.append(w)
    return " ".join(words)


def normalize_contract_type(raw: str | None) -> str | None:
    """Map a free-text contract type to its canonical code, or None."""
    if not raw or not raw.strip():
        return None

    cleaned = _clean(raw)

    # 1. Exact alias
    if cleaned in CONTRACT_TYPE_ALIASES:
        return CONTRACT_TYPE_ALIASES[cleaned]

    # 2. Parenthetical acronym: try the acronym, then the base text
    paren = _PAREN_RE.search(raw)
    if paren:
        inner = _clean(paren.group(1))
        if inner in CONTRACT_TYPE_ALIASES:
            return CONTRACT_TYPE_ALIASES[inner]
        base = _clean(_PAREN_RE.sub(" ", raw))
        if base in CONTRACT_TYPE_ALIASES:
            return CONTRACT_TYPE_ALIASES[base]
        cleaned = base or cleaned

    # 3. Plural folding
    folded = _depluralize(cleaned)
    if folded in CONTRACT_TYPE_ALIASES:
        return CONTRACT_TYPE_ALIASES[folded]

    # 4. Whole-word substring against the longest aliases. Amendment aliases
    # win first: "First Amendment to Master Services Agreement" is an
    # amendment, not an MSA, even though the parent type also appears.
    padded = f" {folded} "
    for alias in _SUBSTRING_ALIASES:
        if CONTRACT_TYPE_ALIASES[alias] == "amendment" and f" {alias} " in padded:
            return "amendment"
    for alias in _SUBSTRING_ALIASES:
        if f" {alias} " in padded:
            return CONTRACT_TYPE_ALIASES[alias]

    return None
