"""Contract language detection and language-aware prompt instructions.

The extraction pipeline was built assuming English documents: agent prompts
are English and the LLM answers in English regardless of the source text,
so a French contract gets English summaries/descriptions. This module gives
the pipeline language awareness:

  * detect_language() — dependency-free stopword heuristic over the extracted
    text, returning an ISO 639-1 code. Deterministic and cheap (no LLM call);
    contracts are long enough that function-word counts are a reliable signal.
  * language_instruction() — a prompt block instructing agents to write all
    free-text output (summaries, descriptions, recommendations) in the
    document's language while keeping enum/code values in English.
  * apply_language_to_hints() — appends that block to the per-agent
    extraction-hints dict so every agent call site picks it up without
    signature changes.
"""

import re

# Distinctive function words per language. Words shared across languages
# (e.g. "la" in fr/es/it, "de" in fr/es/nl/pt) are deliberately excluded —
# only words that strongly indicate one language are listed.
_STOPWORDS: dict[str, frozenset[str]] = {
    "en": frozenset({
        "the", "and", "of", "to", "shall", "agreement", "party", "parties",
        "with", "this", "will", "any", "such", "hereby", "pursuant",
    }),
    "fr": frozenset({
        "le", "les", "des", "une", "est", "sont", "dans", "pour", "par",
        "être", "cette", "aux", "ainsi", "dont", "présent", "présente",
        "contrat", "entre", "chaque", "doit", "peut", "sera", "ont",
    }),
    "de": frozenset({
        "der", "die", "das", "und", "ist", "nicht", "mit", "für", "von",
        "dem", "den", "eine", "werden", "wird", "oder", "vertrag", "sowie",
    }),
    "es": frozenset({
        "el", "los", "las", "una", "es", "son", "en", "para", "por",
        "este", "esta", "del", "con", "según", "contrato", "deberá", "podrá",
    }),
    "it": frozenset({
        "il", "gli", "delle", "della", "è", "sono", "nel", "per", "con",
        "questo", "questa", "del", "che", "contratto", "dovrà", "può",
    }),
    "nl": frozenset({
        "de", "het", "een", "van", "en", "is", "niet", "met", "voor",
        "deze", "wordt", "worden", "zal", "overeenkomst", "partijen", "zijn",
    }),
    "pt": frozenset({
        "uma", "é", "são", "em", "para", "por", "não", "ao", "às",
        "este", "esta", "do", "da", "com", "contrato", "deverá", "poderá",
    }),
}

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "nl": "Dutch",
    "pt": "Portuguese",
}

_WORD_RE = re.compile(r"[a-zà-ÿœæ]+", re.IGNORECASE)

# Keys in the extraction-hints dict whose agents produce free-text output.
_LANGUAGE_HINT_KEYS = ("metadata", "clauses", "obligations", "slas", "risks")


def detect_language(text: str | None, sample_size: int = 20000) -> str | None:
    """Detect the dominant language of a document. Returns ISO 639-1 or None.

    Conservative: returns None (treated as English downstream) when the
    signal is weak or ambiguous — a missing instruction is harmless, a wrong
    one is not.
    """
    if not text:
        return None
    words = _WORD_RE.findall(text[:sample_size].lower())
    if len(words) < 50:
        return None

    scores = {
        lang: sum(1 for w in words if w in stopwords)
        for lang, stopwords in _STOPWORDS.items()
    }
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_lang, best = ranked[0]
    runner_up = ranked[1][1]

    # Require a real signal (≥2% of words) and a clear margin over the runner-up.
    if best < max(10, len(words) // 50):
        return None
    if runner_up and best < runner_up * 1.3:
        return None
    return best_lang


def language_instruction(language: str | None) -> str:
    """Prompt block for non-English documents; empty string for English/unknown."""
    if not language or language == "en":
        return ""
    name = LANGUAGE_NAMES.get(language, language)
    return (
        f"DOCUMENT LANGUAGE: This contract is written in {name}. "
        f"Write ALL free-text output fields (summaries, descriptions, titles, "
        f"reasons, consequences, recommendations, notes) in {name}, matching "
        f"the document's language. Keep quoted source text verbatim. "
        f"Keep enumerated/coded values exactly as the schema specifies "
        f"(category codes, type codes, ISO dates, currency codes, risk levels "
        f"remain in English)."
    )


def apply_language_to_hints(
    hints: dict[str, str] | None, language: str | None
) -> dict[str, str]:
    """Append the language instruction to every free-text-producing agent hint.

    Agents inject their hint under an "INDUSTRY-SPECIFIC GUIDANCE" header, so
    appending here reaches every agent without changing call signatures.
    """
    instruction = language_instruction(language)
    merged = dict(hints or {})
    if not instruction:
        return merged
    for key in _LANGUAGE_HINT_KEYS:
        existing = merged.get(key, "") or ""
        merged[key] = (existing + "\n\n" + instruction).strip() if existing else instruction
    return merged
