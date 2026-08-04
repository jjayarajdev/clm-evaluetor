"""Tests for extract_json_from_response — the JSON robustness layer that stands
between raw LLM output and the extraction agents.

These guard the silent-data-loss bugs: a truncated / edge-case JSON response
must never be turned into a None-that-looks-like-a-clean-"nothing found".
"""

import json

import pytest

from app.agents.base import (
    AgentResponseError,
    LLMTruncationError,
    extract_json_from_response,
)


def test_markdown_fence_object():
    resp = 'Here is the result:\n```json\n{"a": 1, "b": [2, 3]}\n```\nDone.'
    assert extract_json_from_response(resp) == {"a": 1, "b": [2, 3]}


def test_markdown_fence_no_language_tag():
    resp = "```\n{\"score\": 65, \"level\": \"HIGH\"}\n```"
    assert extract_json_from_response(resp) == {"score": 65, "level": "HIGH"}


def test_bare_object():
    resp = '{"risk_factors": [], "overall_score": 0}'
    assert extract_json_from_response(resp) == {"risk_factors": [], "overall_score": 0}


def test_bare_top_level_array():
    # The old greedy `\{...\}` regex could not parse a top-level array at all.
    resp = '[{"chunk": 1, "type": "SERVICE_LEVEL"}, {"chunk": 2, "type": "OTHER"}]'
    out = extract_json_from_response(resp)
    assert isinstance(out, list)
    assert out[0]["type"] == "SERVICE_LEVEL"
    assert len(out) == 2


def test_prose_wrapped_object():
    resp = (
        "Sure! Based on my analysis, here are the findings.\n\n"
        '{"slas": [{"sla_name": "Uptime", "target_value": 99.9}], '
        '"has_sla_section": true}\n\n'
        "Let me know if you need anything else."
    )
    out = extract_json_from_response(resp)
    assert out["has_sla_section"] is True
    assert out["slas"][0]["sla_name"] == "Uptime"


def test_prose_wrapped_array_before_object():
    # An array appears first in prose; scanner must pick it, not a later brace.
    resp = 'Answer: [1, 2, 3] and some note {not json here'
    out = extract_json_from_response(resp)
    assert out == [1, 2, 3]


def test_braces_inside_string_values_do_not_break_scan():
    resp = 'prefix {"desc": "cap set to {value} per {period}", "n": 5} suffix'
    out = extract_json_from_response(resp)
    assert out["n"] == 5
    assert out["desc"] == "cap set to {value} per {period}"


def test_ignores_trailing_second_block():
    resp = '{"first": 1}\n\n{"second": 2}'
    # Whole-string parse fails (two objects); scanner returns the first only.
    out = extract_json_from_response(resp)
    assert out == {"first": 1}


def test_truncated_array_salvages_complete_prefix():
    # Model hit max_tokens mid-array: last element is incomplete.
    truncated = (
        '[{"chunk": 1, "type": "SERVICE_LEVEL"}, '
        '{"chunk": 2, "type": "GOVERNANCE"}, '
        '{"chunk": 3, "type": "SERVI'
    )
    out = extract_json_from_response(truncated, finish_reason="length")
    assert isinstance(out, list)
    # The two complete elements survive; the truncated third is dropped.
    assert len(out) == 2
    assert out[0]["chunk"] == 1
    assert out[1]["type"] == "GOVERNANCE"


def test_truncated_object_with_complete_array_prefix_salvages():
    truncated = (
        '{"risk_factors": [{"category": "unlimited_liability", "score": 15}, '
        '{"category": "broad_indemnification", "score": 12}], '
        '"overall_score": 65, "summary": "This contract has serious iss'
    )
    out = extract_json_from_response(truncated, finish_reason="length")
    assert isinstance(out, dict)
    # The complete risk_factors array is recovered (the key point: high-risk
    # data is NOT silently lost).
    assert len(out["risk_factors"]) == 2
    assert out["risk_factors"][0]["category"] == "unlimited_liability"


def test_truncated_unsalvageable_raises_when_finish_reason_length():
    # Truncated so badly there is no complete prefix to recover, AND the call
    # was flagged as length-truncated -> must raise, never return a clean None.
    garbage = '{"risk_factors": [{"category": "unlimi'
    with pytest.raises(LLMTruncationError):
        extract_json_from_response(garbage, finish_reason="length")


def test_truncation_error_is_agent_response_error_subclass():
    # Callers catch AgentResponseError broadly.
    assert issubclass(LLMTruncationError, AgentResponseError)


def test_no_json_non_truncated_returns_none():
    # Genuinely no JSON and not truncated -> None is the correct, honest answer.
    assert extract_json_from_response("I could not find any SLAs.") is None
    assert extract_json_from_response("") is None


def test_no_json_but_truncated_raises():
    # No JSON at all but the model was cut off -> this is a failure, not empty.
    with pytest.raises(LLMTruncationError):
        extract_json_from_response("Let me analyze this contra", finish_reason="length")


def test_roundtrip_clean_json_unchanged():
    payload = {"a": [1, 2, {"nested": True}], "b": "x"}
    resp = json.dumps(payload)
    assert extract_json_from_response(resp) == payload
