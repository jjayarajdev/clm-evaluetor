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


# ── Display / filter / storage canonicalization ──────────────────────────────
#
# `normalize_contract_type` is deliberately strict: it returns None for anything
# it can't confidently map, and it feeds framework-linking, schema lookup, and
# profile matching (so it must not guess). But the UI needs EVERY contract to
# land in a small, controlled vocabulary — otherwise the raw AI-extracted type
# ("roles_and_responsibilities_matrix", "termination_charges", ...) leaks into
# filters and lists as dozens of one-off values.
#
# `canonical_contract_type` sits on top: it tries the strict normalizer first,
# then a permissive ordered keyword tier, and finally buckets the remainder as
# "other". It never returns a raw value and never returns None for a non-empty
# input — so the type dropdown always shows a tidy, finite set. Order matters
# (first match wins): amendments before the parent type, procedures before
# change-control, pricing schedules before generic "services".
_KEYWORD_BUCKETS: list[tuple[str, str]] = [
    # amendments to an existing agreement (win over the parent type)
    ("allonge", "amendment"),
    ("addendum", "amendment"),
    ("amendment", "amendment"),
    ("variation", "amendment"),
    # procedures / policies (before change-control, which is otherwise an amendment)
    ("procedural", "policy"),
    ("procedure", "policy"),
    ("policies", "policy"),
    ("policy", "policy"),
    ("compliance", "policy"),
    # change control notices / management = amendments to scope
    ("change control", "amendment"),
    ("change management", "amendment"),
    # leases (NL "huurovereenkomst" = office lease)
    ("huurovereenkomst", "lease"),
    ("lease", "lease"),
    # service level agreements
    ("service level", "sla"),
    ("sla", "sla"),
    # pricing / rate / financial schedules
    ("termination charge", "pricing"),
    ("pricing", "pricing"),
    ("tariff", "pricing"),
    ("rate card", "pricing"),
    ("cola", "pricing"),
    ("cost of living", "pricing"),
    ("financial provision", "pricing"),
    ("resource baseline", "pricing"),
    # governance / operating model / performance
    ("roles and responsibilit", "governance"),
    ("operating model", "governance"),
    ("governance", "governance"),
    ("continuous improvement", "governance"),
    ("benchmark", "governance"),
    # memoranda / letters of intent
    ("memorandum", "mou"),
    ("mou", "mou"),
    ("letter of intent", "mou"),
    # procurement / hardware / assets
    ("procurement", "order"),
    ("purchase order", "order"),
    ("asset inventory", "order"),
    ("hardware", "order"),
    # delivery / acceptance / structural schedules (NL "oplevering" = handover)
    ("oplevering", "schedule"),
    ("proces verbaal", "schedule"),
    ("acceptance", "schedule"),
    ("matrix", "schedule"),
    ("exhibit", "schedule"),
    ("appendix", "schedule"),
    ("attachment", "schedule"),
    ("annex", "schedule"),
    ("schedule", "schedule"),
    # generic services (broadest — checked last)
    ("service desk", "service_agreement"),
    ("managed voice", "service_agreement"),
    ("network service", "service_agreement"),
    ("server management", "service_agreement"),
    ("end user computing", "service_agreement"),
    ("service provider", "service_agreement"),
    ("local service", "service_agreement"),
    ("managed service", "service_agreement"),
    ("services", "service_agreement"),
    ("service", "service_agreement"),
]

# The full controlled vocabulary the UI can expect from canonicalization.
CANONICAL_CONTRACT_TYPES: tuple[str, ...] = (
    "msa", "sow", "sla", "service_agreement", "amendment", "lease", "nda",
    "license", "mou", "order", "pricing", "governance", "policy", "schedule",
    "supply_agreement", "vendor_agreement", "employment_contract", "csa",
    "quality_agreement", "cmo_agreement", "cro_agreement", "pharmacovigilance",
    "toll_manufacturing", "tooling_agreement", "blanket_po", "other",
)


def canonical_contract_type(raw: str | None) -> str | None:
    """Map any contract type to the controlled display vocabulary.

    Returns None only for empty input; otherwise always a canonical code
    (never a raw one-off value). Use this for filters, lists, and storage;
    use `normalize_contract_type` where a confident, possibly-None answer is
    needed (framework linking, schema lookup).
    """
    if not raw or not raw.strip():
        return None

    # Idempotent: an already-canonical code passes straight through. This also
    # avoids re-mapping codes whose spelled-out form is a strict alias for a
    # DIFFERENT concept (e.g. "service_agreement" → "SERVICE AGREEMENT" → msa).
    lowered = raw.strip().lower()
    if lowered in CANONICAL_CONTRACT_TYPES:
        return lowered

    strict = normalize_contract_type(raw)
    if strict:
        return strict

    # Substring match on the cleaned text — do NOT depluralize here, or keywords
    # like "policies"/"continuous improvement" get mangled ("policie"/"continuou").
    cleaned = _clean(raw).lower()
    for keyword, code in _KEYWORD_BUCKETS:
        if keyword in cleaned:
            return code

    return "other"


# Master contract types — the ones that anchor a family. A structural document
# (schedule, exhibit, allonge) mis-classified as one of these poisons family
# root selection and counterparty-master linking, so the pipeline downgrades it.
MASTER_CONTRACT_TYPES: frozenset[str] = frozenset(
    {"msa", "service_agreement", "supply_agreement", "vendor_agreement", "csa"}
)

# Decisive filename signals. A file named "…allonge #1…" IS an amendment; a file
# named "Schedule 13 …" IS a schedule — no matter what the model guessed. Anchored
# to the start (or a word boundary for amendments) to stay high-precision.
_FILENAME_AMENDMENT_RE = re.compile(
    r"\b(allonge|avenant|addend(?:um|a)|amendment|wijziging|nachtrag)\b",
    re.IGNORECASE,
)
_FILENAME_SOW_RE = re.compile(
    # c?sow\d* so a fused document number (CSOW0004949) still matches.
    r"^\s*(c?sow\d*|statement\s+of\s+work|change\s+order|work\s+order)\b",
    re.IGNORECASE,
)
_FILENAME_ATTACHMENT_RE = re.compile(
    r"^\s*(schedules?|exhibits?|attachments?|annex(?:es|ure)?|appendix|appendices)\b",
    re.IGNORECASE,
)


def structural_contract_type_from_filename(
    filename: str | None, current_type: str | None = None
) -> str | None:
    """Correct a contract type from a decisive filename signal, else None.

    Two high-precision corrections that keep families well-formed:

    * A filename naming an amendment/allonge/addendum/avenant → ``amendment``
      (a document named that simply *is* an amendment).
    * A filename naming a schedule/exhibit/attachment/SOW, when the model typed
      the document as a MASTER agreement → the structural type. Only the harmful
      master mis-classification is overridden; a correct specific type the model
      already assigned (pricing, governance, sla, ...) is left untouched.

    Returns the corrected canonical type, or None to keep ``current_type``.
    Idempotent — re-running never changes an already-corrected value.
    """
    if not filename or not filename.strip():
        return None
    name = filename.strip()
    current = (current_type or "").strip().lower()

    if _FILENAME_AMENDMENT_RE.search(name) and current != "amendment":
        return "amendment"

    if current in MASTER_CONTRACT_TYPES:
        if _FILENAME_SOW_RE.match(name):
            return "sow"
        if _FILENAME_ATTACHMENT_RE.match(name):
            return "schedule"

    return None


def looks_like_subordinate_filename(filename: str | None) -> bool:
    """True when the filename itself marks the document as a subordinate part of
    a family — a schedule/exhibit/attachment/annex/appendix, a SOW, or an
    amendment/allonge. Such a document is a poor family root regardless of its
    (frequently missing or mis-extracted) contract_type, so root selection uses
    this as a strong, type-independent signal.
    """
    if not filename or not filename.strip():
        return False
    name = filename.strip()
    return bool(
        _FILENAME_ATTACHMENT_RE.match(name)
        or _FILENAME_SOW_RE.match(name)
        or _FILENAME_AMENDMENT_RE.search(name)
    )
