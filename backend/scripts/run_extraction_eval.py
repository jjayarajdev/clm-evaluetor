"""Extraction pipeline evaluation harness.

Modes:
  bootstrap  — Run extraction on golden contracts, save output as draft ground truth
  eval       — Run extraction, compare to ground truth labels, score results
  score-only — Score existing results against ground truth (no re-extraction)

Usage:
  cd backend
  uv run python -m scripts.run_extraction_eval bootstrap          # Generate draft labels
  uv run python -m scripts.run_extraction_eval bootstrap --limit 5 # First 5 contracts only
  uv run python -m scripts.run_extraction_eval eval               # Full eval
  uv run python -m scripts.run_extraction_eval score-only         # Score without re-running
  uv run python -m scripts.run_extraction_eval eval --ids nov-msa-docx,ing-msa  # Specific contracts
"""

import argparse
import asyncio
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
EVAL_DIR = Path(__file__).resolve().parent.parent / "data" / "eval"
GOLDEN_MANIFEST = EVAL_DIR / "golden_contracts.json"
LABELS_DIR = EVAL_DIR / "labels"
RESULTS_DIR = EVAL_DIR / "results"

LABELS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Contract manifest loader
# ---------------------------------------------------------------------------

def load_manifest() -> dict:
    with open(GOLDEN_MANIFEST) as f:
        return json.load(f)


def resolve_path(contract: dict, sources: dict) -> Path:
    """Resolve a contract entry to its absolute file path."""
    source = sources[contract["source"]]
    base = (EVAL_DIR / source["base_path"]).resolve()
    return base / contract["filename"]


# ---------------------------------------------------------------------------
# Extraction runner  (imports deferred to avoid import-time side effects)
# ---------------------------------------------------------------------------

_orchestrator_initialized = False


def _ensure_orchestrator():
    """Initialize the agent orchestrator (once)."""
    global _orchestrator_initialized
    if _orchestrator_initialized:
        return
    from app.services.orchestrator import initialize_default_agents
    from app.agents import register_all_agents
    initialize_default_agents()
    register_all_agents()
    _orchestrator_initialized = True


async def run_extraction(file_path: Path) -> dict:
    """Run the full extraction pipeline on a single file and return structured results."""
    _ensure_orchestrator()
    from app.services.parser import get_parser

    parser = get_parser()
    parsed = parser.parse_file(str(file_path))
    full_text = parsed.full_text
    page_count = parsed.page_count

    if not full_text or len(full_text.strip()) < 50:
        return {"error": "Parsed text too short", "char_count": len(full_text) if full_text else 0}

    results: dict[str, Any] = {
        "parse": {
            "char_count": len(full_text),
            "page_count": page_count,
        },
        "metadata": {},
        "clauses": [],
        "obligations": [],
        "slas": [],
        "renewal": {},
    }

    contract_id = file_path.stem  # Use filename as contract ID for standalone eval

    # --- Metadata extraction ---
    try:
        from app.agents.metadata_extraction import extract_metadata
        meta = await extract_metadata(full_text, contract_id=contract_id)
        results["metadata"] = _serialize_metadata(meta)
    except Exception as e:
        results["metadata"] = {"error": str(e)}

    # --- Clause extraction ---
    try:
        from app.agents.clause_extraction import extract_clauses
        clause_result = await extract_clauses(full_text, contract_id=contract_id)
        results["clauses"] = _serialize_clauses(clause_result)
    except Exception as e:
        results["clauses"] = {"error": str(e)}

    # --- Obligation extraction ---
    try:
        from app.agents.obligation_tracking import extract_obligations
        obl_result = await extract_obligations(full_text, contract_id=contract_id)
        results["obligations"] = _serialize_obligations(obl_result)
    except Exception as e:
        results["obligations"] = {"error": str(e)}

    # --- SLA extraction ---
    try:
        from app.agents.sla_extraction import extract_slas
        sla_result = await extract_slas(full_text, contract_id=contract_id, user_id="eval-harness")
        results["slas"] = _serialize_slas(sla_result)
    except Exception as e:
        results["slas"] = {"error": str(e)}

    # --- Renewal detection ---
    try:
        from app.agents.renewal_monitoring import analyze_renewal_terms
        renewal_result = await analyze_renewal_terms(full_text, contract_id=contract_id)
        results["renewal"] = _serialize_renewal(renewal_result)
    except Exception as e:
        results["renewal"] = {"error": str(e)}

    return results


# ---------------------------------------------------------------------------
# Serializers — convert agent output objects to plain dicts for JSON storage
# ---------------------------------------------------------------------------

def _safe_val(v: Any) -> Any:
    """Convert non-JSON-serializable values."""
    if v is None:
        return None
    if isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, dict):
        return {k: _safe_val(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return [_safe_val(item) for item in v]
    return str(v)


def _field_val(field: Any) -> dict | None:
    """Extract value from MetadataField or plain value."""
    if field is None:
        return None
    if isinstance(field, dict):
        return {
            "value": _safe_val(field.get("value")),
            "confidence": field.get("confidence"),
        }
    if hasattr(field, "value"):
        return {
            "value": _safe_val(field.value),
            "confidence": getattr(field, "confidence", None),
        }
    return {"value": _safe_val(field), "confidence": None}


def _serialize_metadata(meta: Any) -> dict:
    if isinstance(meta, dict):
        result = {}
        for key in ["contract_type", "counterparty", "effective_date", "expiration_date",
                     "contract_value", "currency", "jurisdiction"]:
            result[key] = _field_val(meta.get(key))
        result["parties"] = _safe_val(meta.get("parties", []))
        result["overall_confidence"] = meta.get("overall_confidence")
        return result
    # Object with attributes
    result = {}
    for key in ["contract_type", "counterparty", "effective_date", "expiration_date",
                 "contract_value", "currency", "jurisdiction"]:
        result[key] = _field_val(getattr(meta, key, None))
    result["parties"] = _safe_val(getattr(meta, "parties", []))
    result["overall_confidence"] = getattr(meta, "overall_confidence", None)
    return result


def _serialize_clauses(result: Any) -> list[dict]:
    clauses = result if isinstance(result, list) else getattr(result, "extracted_clauses", result)
    if isinstance(clauses, dict) and "error" in clauses:
        return clauses
    items = []
    for c in (clauses or []):
        if isinstance(c, dict):
            items.append({
                "clause_type": c.get("clause_type"),
                "text": (c.get("text", "") or "")[:500],
                "section_number": c.get("section_number"),
                "page_number": c.get("page_number"),
                "risk_level": c.get("risk_level"),
                "confidence": c.get("confidence"),
                "key_terms": c.get("key_terms", []),
            })
        else:
            items.append({
                "clause_type": getattr(c, "clause_type", None),
                "text": (getattr(c, "text", "") or "")[:500],
                "section_number": getattr(c, "section_number", None),
                "page_number": getattr(c, "page_number", None),
                "risk_level": getattr(c, "risk_level", None),
                "confidence": getattr(c, "confidence", None),
                "key_terms": getattr(c, "key_terms", []),
            })
    return items


def _serialize_obligations(result: Any) -> list[dict]:
    obls = result if isinstance(result, list) else getattr(result, "obligations", result)
    if isinstance(obls, dict) and "error" in obls:
        return obls
    items = []
    for o in (obls or []):
        if isinstance(o, dict):
            items.append({
                "description": (o.get("description", "") or "")[:500],
                "obligation_type": o.get("obligation_type"),
                "obligated_party": o.get("obligated_party"),
                "beneficiary_party": o.get("beneficiary_party"),
                "deadline_type": o.get("deadline_type"),
                "deadline_date": o.get("deadline_date"),
                "recurrence_pattern": o.get("recurrence_pattern"),
                "consequences": o.get("consequences"),
                "section_number": o.get("section_number"),
                "source_quote": (o.get("source_quote", "") or "")[:500],
                "confidence": o.get("confidence"),
            })
        else:
            items.append({
                "description": (getattr(o, "description", "") or "")[:500],
                "obligation_type": getattr(o, "obligation_type", None),
                "obligated_party": getattr(o, "obligated_party", None),
                "beneficiary_party": getattr(o, "beneficiary_party", None),
                "deadline_type": getattr(o, "deadline_type", None),
                "deadline_date": getattr(o, "deadline_date", None),
                "recurrence_pattern": getattr(o, "recurrence_pattern", None),
                "consequences": getattr(o, "consequences", None),
                "section_number": getattr(o, "section_number", None),
                "source_quote": (getattr(o, "source_quote", "") or "")[:500],
                "confidence": getattr(o, "confidence", None),
            })
    return items


def _serialize_slas(result: Any) -> list[dict]:
    slas = result if isinstance(result, list) else getattr(result, "slas", result)
    if isinstance(slas, dict) and "error" in slas:
        return slas
    items = []
    for s in (slas or []):
        if isinstance(s, dict):
            items.append({
                "sla_name": s.get("sla_name"),
                "metric_type": s.get("metric_type"),
                "metric_unit": s.get("metric_unit"),
                "target_value": _safe_val(s.get("target_value")),
                "severity": s.get("severity"),
                "has_penalty": s.get("has_penalty"),
                "penalty_type": s.get("penalty_type"),
                "penalty_value": _safe_val(s.get("penalty_value")),
                "measurement_period": s.get("measurement_period"),
                "section_reference": s.get("section_reference"),
                "source_text": (s.get("source_text", "") or "")[:500],
                "confidence": s.get("confidence"),
            })
        else:
            items.append({
                "sla_name": getattr(s, "sla_name", None),
                "metric_type": getattr(s, "metric_type", None),
                "metric_unit": getattr(s, "metric_unit", None),
                "target_value": _safe_val(getattr(s, "target_value", None)),
                "severity": getattr(s, "severity", None),
                "has_penalty": getattr(s, "has_penalty", None),
                "penalty_type": getattr(s, "penalty_type", None),
                "penalty_value": _safe_val(getattr(s, "penalty_value", None)),
                "measurement_period": getattr(s, "measurement_period", None),
                "section_reference": getattr(s, "section_reference", None),
                "source_text": (getattr(s, "source_text", "") or "")[:500],
                "confidence": getattr(s, "confidence", None),
            })
    return items


def _serialize_renewal(result: Any) -> dict:
    if isinstance(result, dict):
        terms = result.get("terms", result)
    else:
        terms = getattr(result, "terms", result)

    if isinstance(terms, dict):
        return {
            "has_auto_renewal": terms.get("has_auto_renewal"),
            "auto_renewal_term_months": terms.get("auto_renewal_term_months"),
            "notice_period_days": terms.get("notice_period_days"),
            "notice_deadline": terms.get("notice_deadline"),
            "expiration_date": terms.get("expiration_date"),
            "initial_term_months": terms.get("initial_term_months"),
            "termination_for_convenience": terms.get("termination_for_convenience"),
            "confidence": terms.get("confidence"),
        }
    return {
        "has_auto_renewal": getattr(terms, "has_auto_renewal", None),
        "auto_renewal_term_months": getattr(terms, "auto_renewal_term_months", None),
        "notice_period_days": getattr(terms, "notice_period_days", None),
        "notice_deadline": getattr(terms, "notice_deadline", None),
        "expiration_date": getattr(terms, "expiration_date", None),
        "initial_term_months": getattr(terms, "initial_term_months", None),
        "termination_for_convenience": getattr(terms, "termination_for_convenience", None),
        "confidence": getattr(terms, "confidence", None),
    }


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------

def score_metadata(extracted: dict, ground_truth: dict) -> dict:
    """Score metadata extraction against ground truth."""
    fields = ["contract_type", "counterparty", "effective_date", "expiration_date",
              "contract_value", "currency", "jurisdiction"]
    scores = {}
    correct = 0
    total = 0

    for field in fields:
        gt = ground_truth.get(field)
        ex = extracted.get(field)
        if gt is None:
            continue

        gt_val = gt.get("value") if isinstance(gt, dict) else gt
        ex_val = ex.get("value") if isinstance(ex, dict) else ex
        if gt_val is None:
            continue

        total += 1
        match_type = gt.get("match_type", "exact") if isinstance(gt, dict) else "exact"

        if match_type == "exact":
            matched = _normalize(str(ex_val)) == _normalize(str(gt_val))
        elif match_type == "normalized":
            matched = _normalize_date_or_value(ex_val) == _normalize_date_or_value(gt_val)
        elif match_type == "contains":
            matched = str(gt_val).lower() in str(ex_val).lower()
        else:
            matched = str(ex_val) == str(gt_val)

        if matched:
            correct += 1
        scores[field] = {
            "expected": _safe_val(gt_val),
            "extracted": _safe_val(ex_val),
            "match": matched,
            "match_type": match_type,
        }

    accuracy = correct / total if total > 0 else 0
    return {"fields": scores, "accuracy": accuracy, "correct": correct, "total": total}


def score_list_extraction(
    extracted: list[dict],
    ground_truth: list[dict],
    key_field: str,
    match_fields: list[str],
) -> dict:
    """Score list-based extraction (clauses, obligations, SLAs) against ground truth.

    Uses fuzzy matching on key_field to pair extracted items with ground truth,
    then checks match_fields for each pair.
    """
    if isinstance(extracted, dict) and "error" in extracted:
        return {"error": extracted["error"], "precision": 0, "recall": 0, "f1": 0}
    if isinstance(ground_truth, dict) and "error" in ground_truth:
        return {"error": "Ground truth has error", "precision": 0, "recall": 0, "f1": 0}

    gt_matched = set()
    ex_matched = set()
    field_scores: list[dict] = []

    for ei, ex_item in enumerate(extracted):
        best_match = -1
        best_score = 0.0

        ex_key = str(ex_item.get(key_field, "")).lower().strip()
        if not ex_key:
            continue

        for gi, gt_item in enumerate(ground_truth):
            if gi in gt_matched:
                continue
            gt_key = str(gt_item.get(key_field, "")).lower().strip()
            sim = _text_similarity(ex_key, gt_key)
            if sim > best_score and sim > 0.3:
                best_score = sim
                best_match = gi

        if best_match >= 0:
            gt_matched.add(best_match)
            ex_matched.add(ei)
            gt_item = ground_truth[best_match]
            match_detail = {"extracted_key": ex_key, "gt_key": str(gt_item.get(key_field, "")).lower()}
            for mf in match_fields:
                ex_val = _safe_val(ex_item.get(mf))
                gt_val = _safe_val(gt_item.get(mf))
                match_detail[mf] = {
                    "extracted": ex_val,
                    "expected": gt_val,
                    "match": _normalize(str(ex_val)) == _normalize(str(gt_val)) if gt_val is not None else None,
                }
            field_scores.append(match_detail)

    tp = len(gt_matched)
    fp = len(extracted) - len(ex_matched)
    fn = len(ground_truth) - len(gt_matched)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "extracted_count": len(extracted),
        "ground_truth_count": len(ground_truth),
        "match_details": field_scores,
    }


def _normalize(s: str) -> str:
    return s.lower().strip().replace(" ", "").replace("-", "").replace("_", "")


def _normalize_date_or_value(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    # Try to normalize dates
    for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%d %B %Y"]:
        try:
            from datetime import datetime as dt
            d = dt.strptime(s, fmt)
            return d.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue
    return _normalize(s)


def _text_similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity (Jaccard)."""
    if not a or not b:
        return 0.0
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------

def generate_report(all_scores: list[dict], output_path: Path) -> None:
    """Generate a human-readable eval report."""
    lines = [
        "# Extraction Eval Report",
        f"Generated: {datetime.utcnow().isoformat()}",
        f"Contracts evaluated: {len(all_scores)}",
        "",
    ]

    # Aggregate metadata accuracy
    meta_accs = [s["metadata"]["accuracy"] for s in all_scores
                 if "metadata" in s and "accuracy" in s.get("metadata", {})]
    if meta_accs:
        lines.append(f"## Metadata Accuracy: {sum(meta_accs)/len(meta_accs)*100:.1f}%")
        lines.append("")

    # Aggregate list extraction scores
    for domain in ["clauses", "obligations", "slas"]:
        precisions = []
        recalls = []
        f1s = []
        for s in all_scores:
            d = s.get(domain, {})
            if "precision" in d:
                precisions.append(d["precision"])
                recalls.append(d["recall"])
                f1s.append(d["f1"])
        if precisions:
            lines.append(f"## {domain.title()}")
            lines.append(f"  Precision: {sum(precisions)/len(precisions)*100:.1f}%")
            lines.append(f"  Recall:    {sum(recalls)/len(recalls)*100:.1f}%")
            lines.append(f"  F1:        {sum(f1s)/len(f1s)*100:.1f}%")
            lines.append("")

    # Per-contract details
    lines.append("## Per-Contract Results")
    lines.append("")
    for s in all_scores:
        cid = s["contract_id"]
        lines.append(f"### {cid}")
        if "error" in s:
            lines.append(f"  ERROR: {s['error']}")
            continue

        meta = s.get("metadata", {})
        if "accuracy" in meta:
            lines.append(f"  Metadata accuracy: {meta['accuracy']*100:.0f}% ({meta['correct']}/{meta['total']})")
            for field, detail in meta.get("fields", {}).items():
                status = "OK" if detail["match"] else "MISS"
                lines.append(f"    {field}: {status} (expected={detail['expected']}, got={detail['extracted']})")

        for domain in ["clauses", "obligations", "slas"]:
            d = s.get(domain, {})
            if "f1" in d:
                lines.append(f"  {domain.title()}: P={d['precision']:.2f} R={d['recall']:.2f} F1={d['f1']:.2f}"
                             f" (extracted={d['extracted_count']}, gt={d['ground_truth_count']})")
        lines.append("")

    report = "\n".join(lines)
    output_path.write_text(report)
    print(f"\nReport written to {output_path}")
    print(report)


# ---------------------------------------------------------------------------
# Main commands
# ---------------------------------------------------------------------------

async def cmd_bootstrap(args: argparse.Namespace) -> None:
    """Run extraction on golden contracts and save output as draft ground truth."""
    manifest = load_manifest()
    sources = manifest["sources"]
    contracts = manifest["contracts"]

    if args.ids:
        ids = set(args.ids.split(","))
        contracts = [c for c in contracts if c["id"] in ids]

    if args.limit:
        contracts = contracts[:args.limit]

    print(f"Bootstrapping ground truth for {len(contracts)} contracts...")
    print(f"Labels will be saved to {LABELS_DIR}/")
    print()

    for i, contract in enumerate(contracts):
        cid = contract["id"]
        file_path = resolve_path(contract, sources)
        label_path = LABELS_DIR / f"{cid}.json"

        if label_path.exists() and not args.overwrite:
            print(f"[{i+1}/{len(contracts)}] SKIP {cid} (label exists, use --overwrite)")
            continue

        print(f"[{i+1}/{len(contracts)}] Extracting {cid}: {contract['filename']}")

        if not file_path.exists():
            print(f"  ERROR: File not found: {file_path}")
            continue

        t0 = time.time()
        try:
            results = await run_extraction(file_path)
            elapsed = time.time() - t0

            label = {
                "contract_id": cid,
                "source": contract["source"],
                "filename": contract["filename"],
                "doc_type": contract["doc_type"],
                "generated_at": datetime.utcnow().isoformat(),
                "extraction_time_seconds": round(elapsed, 1),
                "is_draft": True,
                "reviewed": False,
                "metadata": results.get("metadata", {}),
                "clauses": results.get("clauses", []),
                "obligations": results.get("obligations", []),
                "slas": results.get("slas", []),
                "renewal": results.get("renewal", {}),
                "parse": results.get("parse", {}),
            }

            with open(label_path, "w") as f:
                json.dump(label, f, indent=2, default=str)

            # Summary
            meta = results.get("metadata", {})
            n_clauses = len(results.get("clauses", [])) if isinstance(results.get("clauses"), list) else 0
            n_obls = len(results.get("obligations", [])) if isinstance(results.get("obligations"), list) else 0
            n_slas = len(results.get("slas", [])) if isinstance(results.get("slas"), list) else 0
            counterparty = meta.get("counterparty", {})
            cp_val = counterparty.get("value") if isinstance(counterparty, dict) else counterparty
            print(f"  {elapsed:.1f}s | counterparty={cp_val} | "
                  f"clauses={n_clauses} obls={n_obls} slas={n_slas}")

        except Exception as e:
            elapsed = time.time() - t0
            print(f"  ERROR ({elapsed:.1f}s): {e}")
            traceback.print_exc()

    print(f"\nDone. Labels saved to {LABELS_DIR}/")
    print("Review and correct the labels, then set 'is_draft': false and 'reviewed': true")


async def cmd_eval(args: argparse.Namespace) -> None:
    """Run extraction and score against ground truth labels."""
    manifest = load_manifest()
    sources = manifest["sources"]
    contracts = manifest["contracts"]

    if args.ids:
        ids = set(args.ids.split(","))
        contracts = [c for c in contracts if c["id"] in ids]

    if args.limit:
        contracts = contracts[:args.limit]

    all_scores = []
    for i, contract in enumerate(contracts):
        cid = contract["id"]
        file_path = resolve_path(contract, sources)
        label_path = LABELS_DIR / f"{cid}.json"

        if not label_path.exists():
            print(f"[{i+1}/{len(contracts)}] SKIP {cid} (no ground truth label)")
            continue

        with open(label_path) as f:
            ground_truth = json.load(f)

        print(f"[{i+1}/{len(contracts)}] Evaluating {cid}...")

        if not file_path.exists():
            all_scores.append({"contract_id": cid, "error": f"File not found: {file_path}"})
            continue

        t0 = time.time()
        try:
            results = await run_extraction(file_path)
            elapsed = time.time() - t0

            # Save raw results
            result_path = RESULTS_DIR / f"{cid}.json"
            with open(result_path, "w") as f:
                json.dump({"contract_id": cid, "extraction_time": elapsed, **results}, f, indent=2, default=str)

            # Score
            scores = _score_contract(cid, results, ground_truth)
            scores["extraction_time"] = round(elapsed, 1)
            all_scores.append(scores)

            meta_acc = scores.get("metadata", {}).get("accuracy", 0)
            clause_f1 = scores.get("clauses", {}).get("f1", 0)
            obl_f1 = scores.get("obligations", {}).get("f1", 0)
            sla_f1 = scores.get("slas", {}).get("f1", 0)
            print(f"  {elapsed:.1f}s | meta={meta_acc*100:.0f}% | "
                  f"clause_f1={clause_f1:.2f} obl_f1={obl_f1:.2f} sla_f1={sla_f1:.2f}")

        except Exception as e:
            print(f"  ERROR: {e}")
            traceback.print_exc()
            all_scores.append({"contract_id": cid, "error": str(e)})

    # Generate report
    report_path = EVAL_DIR / "EVAL_REPORT.md"
    scores_path = EVAL_DIR / "eval_scores.json"
    with open(scores_path, "w") as f:
        json.dump(all_scores, f, indent=2, default=str)
    generate_report(all_scores, report_path)


def cmd_score_only(args: argparse.Namespace) -> None:
    """Score existing results against ground truth without re-extraction."""
    manifest = load_manifest()
    contracts = manifest["contracts"]

    if args.ids:
        ids = set(args.ids.split(","))
        contracts = [c for c in contracts if c["id"] in ids]

    all_scores = []
    for contract in contracts:
        cid = contract["id"]
        result_path = RESULTS_DIR / f"{cid}.json"
        label_path = LABELS_DIR / f"{cid}.json"

        if not result_path.exists() or not label_path.exists():
            continue

        with open(result_path) as f:
            results = json.load(f)
        with open(label_path) as f:
            ground_truth = json.load(f)

        scores = _score_contract(cid, results, ground_truth)
        all_scores.append(scores)

    report_path = EVAL_DIR / "EVAL_REPORT.md"
    scores_path = EVAL_DIR / "eval_scores.json"
    with open(scores_path, "w") as f:
        json.dump(all_scores, f, indent=2, default=str)
    generate_report(all_scores, report_path)


def _score_contract(cid: str, results: dict, ground_truth: dict) -> dict:
    """Score a single contract's extraction results against ground truth."""
    scores: dict[str, Any] = {"contract_id": cid}

    # Metadata
    if results.get("metadata") and ground_truth.get("metadata"):
        scores["metadata"] = score_metadata(results["metadata"], ground_truth["metadata"])

    # Clauses
    ex_clauses = results.get("clauses", [])
    gt_clauses = ground_truth.get("clauses", [])
    if isinstance(ex_clauses, list) and isinstance(gt_clauses, list) and gt_clauses:
        scores["clauses"] = score_list_extraction(
            ex_clauses, gt_clauses,
            key_field="clause_type",
            match_fields=["risk_level"],
        )

    # Obligations
    ex_obls = results.get("obligations", [])
    gt_obls = ground_truth.get("obligations", [])
    if isinstance(ex_obls, list) and isinstance(gt_obls, list) and gt_obls:
        scores["obligations"] = score_list_extraction(
            ex_obls, gt_obls,
            key_field="description",
            match_fields=["obligation_type", "obligated_party"],
        )

    # SLAs
    ex_slas = results.get("slas", [])
    gt_slas = ground_truth.get("slas", [])
    if isinstance(ex_slas, list) and isinstance(gt_slas, list) and gt_slas:
        scores["slas"] = score_list_extraction(
            ex_slas, gt_slas,
            key_field="sla_name",
            match_fields=["metric_type", "target_value", "severity"],
        )

    return scores


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Extraction pipeline eval harness")
    sub = parser.add_subparsers(dest="command", required=True)

    # bootstrap
    p_boot = sub.add_parser("bootstrap", help="Run extraction and save as draft ground truth")
    p_boot.add_argument("--limit", type=int, help="Process only first N contracts")
    p_boot.add_argument("--ids", type=str, help="Comma-separated contract IDs to process")
    p_boot.add_argument("--overwrite", action="store_true", help="Overwrite existing labels")

    # eval
    p_eval = sub.add_parser("eval", help="Run extraction and score against ground truth")
    p_eval.add_argument("--limit", type=int, help="Process only first N contracts")
    p_eval.add_argument("--ids", type=str, help="Comma-separated contract IDs to process")

    # score-only
    p_score = sub.add_parser("score-only", help="Score existing results (no re-extraction)")
    p_score.add_argument("--ids", type=str, help="Comma-separated contract IDs to score")

    args = parser.parse_args()

    if args.command == "bootstrap":
        asyncio.run(cmd_bootstrap(args))
    elif args.command == "eval":
        asyncio.run(cmd_eval(args))
    elif args.command == "score-only":
        cmd_score_only(args)  # score-only is sync (no extraction)


if __name__ == "__main__":
    main()
