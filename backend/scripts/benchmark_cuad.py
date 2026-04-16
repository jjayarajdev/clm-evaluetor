"""Benchmark Evaluetor's clause extraction against CUAD ground truth.

Runs our clause extractor on CUAD contracts and compares results against
the lawyer-verified labels to produce precision, recall, and F1 scores.

Usage:
    uv run python -m scripts.benchmark_cuad                  # Benchmark all
    uv run python -m scripts.benchmark_cuad --limit 20       # First 20 contracts
    uv run python -m scripts.benchmark_cuad --from-db        # Use already-imported CUAD contracts
    uv run python -m scripts.benchmark_cuad --output report  # Save detailed report
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# Re-use CUAD parsing from import script
from scripts.import_cuad import (
    download_cuad,
    parse_cuad_contract,
    CUAD_CLAUSE_MAP,
)

REPORT_DIR = Path("data/cuad/benchmark_reports")


# ═══════════════════════════════════════════════════════════════════
# Extraction
# ═══════════════════════════════════════════════════════════════════

async def run_extraction(contract_text: str, contract_id: str, user_id: str = "benchmark") -> list[dict]:
    """Run our clause extractor on a contract and return results.

    Returns:
        List of {clause_type, text} dicts.
    """
    from app.agents.clause_extraction import extract_clauses
    from app.agents import register_all_agents
    from app.services.orchestrator import initialize_default_agents

    initialize_default_agents()
    register_all_agents()

    result = await extract_clauses(
        contract_text=contract_text,
        contract_id=contract_id,
        user_id=user_id,
    )

    if not result or not result.extracted_clauses:
        return []

    return [
        {
            "clause_type": c.clause_type,
            "text": c.text[:500] if c.text else "",
            "confidence": c.confidence,
        }
        for c in result.extracted_clauses
    ]


# ═══════════════════════════════════════════════════════════════════
# Matching & Scoring
# ═══════════════════════════════════════════════════════════════════

def compute_text_overlap(predicted_text: str, gold_text: str) -> float:
    """Compute token-level overlap between predicted and gold text.

    Returns:
        Overlap ratio (0-1).
    """
    pred_tokens = set(predicted_text.lower().split())
    gold_tokens = set(gold_text.lower().split())

    if not gold_tokens:
        return 0.0

    overlap = len(pred_tokens & gold_tokens)
    return overlap / len(gold_tokens)


def match_extractions(
    predicted: list[dict],
    gold: list[dict],
    overlap_threshold: float = 0.3,
) -> dict:
    """Match predicted clauses against gold labels.

    Args:
        predicted: List of {clause_type, text} from our extractor.
        gold: List of {clause_type, spans} from CUAD.
        overlap_threshold: Min token overlap to consider a match.

    Returns:
        Dict with tp, fp, fn, matches.
    """
    matched_gold = set()
    matched_pred = set()
    matches = []

    for pi, pred in enumerate(predicted):
        best_overlap = 0.0
        best_gi = -1

        for gi, g in enumerate(gold):
            if gi in matched_gold:
                continue

            # Type must match
            if pred["clause_type"] != g["clause_type"]:
                continue

            # Check text overlap against any gold span
            for span in g["spans"]:
                overlap = compute_text_overlap(pred["text"], span["text"])
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_gi = gi

        if best_overlap >= overlap_threshold and best_gi >= 0:
            matched_gold.add(best_gi)
            matched_pred.add(pi)
            matches.append({
                "predicted": pred,
                "gold": gold[best_gi],
                "overlap": best_overlap,
            })

    tp = len(matches)
    fp = len(predicted) - tp
    fn = len(gold) - tp

    return {"tp": tp, "fp": fp, "fn": fn, "matches": matches}


def compute_metrics(tp: int, fp: int, fn: int) -> dict:
    """Compute precision, recall, F1."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


# ═══════════════════════════════════════════════════════════════════
# Benchmark Runner
# ═══════════════════════════════════════════════════════════════════

async def benchmark(entries: list[dict], save_report: bool = False) -> dict:
    """Run benchmark on CUAD entries.

    Args:
        entries: Parsed CUAD contract data.
        save_report: Whether to save detailed report.

    Returns:
        Aggregate metrics dict.
    """
    overall_tp = 0
    overall_fp = 0
    overall_fn = 0

    per_type_tp: dict[str, int] = defaultdict(int)
    per_type_fp: dict[str, int] = defaultdict(int)
    per_type_fn: dict[str, int] = defaultdict(int)

    contract_results = []
    errors = 0

    for i, parsed in enumerate(entries):
        title = parsed["title"]
        gold_clauses = parsed["clauses"]

        if not gold_clauses:
            continue

        logger.info(f"[{i+1}/{len(entries)}] {title} ({len(gold_clauses)} gold clauses)")

        try:
            start = time.time()
            predicted = await run_extraction(
                contract_text=parsed["text"],
                contract_id=f"cuad_benchmark_{i}",
            )
            elapsed = time.time() - start

            result = match_extractions(predicted, gold_clauses)

            overall_tp += result["tp"]
            overall_fp += result["fp"]
            overall_fn += result["fn"]

            # Per-type breakdown
            for match in result["matches"]:
                ct = match["predicted"]["clause_type"]
                per_type_tp[ct] += 1

            for pi, pred in enumerate(predicted):
                if pi not in {m["predicted"] for m in result["matches"]}:
                    per_type_fp[pred["clause_type"]] += 1

            for gi, g in enumerate(gold_clauses):
                if gi not in {gold_clauses.index(m["gold"]) for m in result["matches"]}:
                    per_type_fn[g["clause_type"]] += 1

            metrics = compute_metrics(result["tp"], result["fp"], result["fn"])

            contract_results.append({
                "title": title,
                "gold_count": len(gold_clauses),
                "predicted_count": len(predicted),
                "tp": result["tp"],
                "fp": result["fp"],
                "fn": result["fn"],
                **metrics,
                "elapsed_s": round(elapsed, 1),
            })

            logger.info(
                f"  P={metrics['precision']:.0%} R={metrics['recall']:.0%} "
                f"F1={metrics['f1']:.0%} (TP={result['tp']} FP={result['fp']} "
                f"FN={result['fn']}) [{elapsed:.1f}s]"
            )

        except Exception as e:
            logger.warning(f"  Error: {e}")
            errors += 1

    # Aggregate metrics
    overall = compute_metrics(overall_tp, overall_fp, overall_fn)

    # Per-type metrics
    all_types = set(per_type_tp) | set(per_type_fp) | set(per_type_fn)
    per_type_metrics = {}
    for ct in sorted(all_types):
        tp = per_type_tp[ct]
        fp = per_type_fp[ct]
        fn = per_type_fn[ct]
        per_type_metrics[ct] = {
            "tp": tp, "fp": fp, "fn": fn,
            **compute_metrics(tp, fp, fn),
        }

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "contracts_evaluated": len(contract_results),
        "contracts_with_errors": errors,
        "overall": {
            "tp": overall_tp,
            "fp": overall_fp,
            "fn": overall_fn,
            **overall,
        },
        "per_type": per_type_metrics,
        "contract_results": contract_results,
    }

    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info(f"CUAD Benchmark Results")
    logger.info(f"{'='*60}")
    logger.info(f"Contracts evaluated:  {len(contract_results)}")
    logger.info(f"Errors:               {errors}")
    logger.info(f"")
    logger.info(f"Overall:")
    logger.info(f"  Precision:  {overall['precision']:.1%}")
    logger.info(f"  Recall:     {overall['recall']:.1%}")
    logger.info(f"  F1 Score:   {overall['f1']:.1%}")
    logger.info(f"  TP={overall_tp}  FP={overall_fp}  FN={overall_fn}")
    logger.info(f"")
    logger.info(f"Per Clause Type:")
    logger.info(f"  {'Type':30s}  {'P':>6s}  {'R':>6s}  {'F1':>6s}  {'TP':>4s}  {'FP':>4s}  {'FN':>4s}")
    logger.info(f"  {'-'*30}  {'-'*6}  {'-'*6}  {'-'*6}  {'-'*4}  {'-'*4}  {'-'*4}")
    for ct, m in sorted(per_type_metrics.items(), key=lambda x: -x[1]["f1"]):
        logger.info(
            f"  {ct:30s}  {m['precision']:5.1%}  {m['recall']:5.1%}  "
            f"{m['f1']:5.1%}  {m['tp']:4d}  {m['fp']:4d}  {m['fn']:4d}"
        )

    # Save report
    if save_report:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORT_DIR / f"benchmark_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(f"\nReport saved: {report_path}")

    return report


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(description="Benchmark clause extraction against CUAD")
    parser.add_argument("--limit", type=int, default=None, help="Max contracts to benchmark")
    parser.add_argument("--from-db", action="store_true", help="Use imported CUAD contracts from DB")
    parser.add_argument("--output", choices=["report", "console"], default="console", help="Output format")
    args = parser.parse_args()

    # Load CUAD data
    cuad_data = await download_cuad()
    entries = cuad_data.get("data", [])
    logger.info(f"CUAD dataset: {len(entries)} contracts")

    # Parse
    parsed = [parse_cuad_contract(e) for e in entries]
    parsed = [p for p in parsed if p["text"] and p["clauses"]]
    logger.info(f"Contracts with clause labels: {len(parsed)}")

    if args.limit:
        parsed = parsed[:args.limit]
        logger.info(f"Limited to {len(parsed)} contracts")

    total_labels = sum(len(p["clauses"]) for p in parsed)
    logger.info(f"Total clause labels: {total_labels}")

    # Run benchmark
    await benchmark(parsed, save_report=(args.output == "report"))


if __name__ == "__main__":
    asyncio.run(main())
