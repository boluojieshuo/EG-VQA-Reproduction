"""Paired comparison of two runs that differ only in max_new_tokens."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "official_repo" / "evaluation"))

import evidence_metrics as em  # noqa: E402


def load_run(predictions: Path, metrics: Path):
    preds = json.loads(predictions.read_text(encoding="utf-8"))
    stored = json.loads(metrics.read_text(encoding="utf-8"))
    per_sample = {s["question_id"]: s for s in stored["eg_f1"]["per_sample_results"]}
    return {p["question_id"]: p for p in preds}, stored, per_sample


def completeness(row: dict) -> dict:
    raw = (row.get("model_response_raw") or "").lower()
    parsed = row.get("parsed_response") or {}
    return {
        "closing_tags_complete": all(tag in raw for tag in ("</evidence>", "</think>", "</answer>")),
        "parsed_answer_present": bool(parsed.get("answer")),
        "parsed_evidence_present": bool(parsed.get("evidence")),
        "hit_cap": bool(row.get("hit_token_cap")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Paired comparison across token limits.")
    parser.add_argument("--low-pred", type=Path, required=True)
    parser.add_argument("--low-metrics", type=Path, required=True)
    parser.add_argument("--high-pred", type=Path, required=True)
    parser.add_argument("--high-metrics", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    low, low_stored, low_per = load_run(args.low_pred, args.low_metrics)
    high, high_stored, high_per = load_run(args.high_pred, args.high_metrics)
    shared = sorted(set(low) & set(high))
    if set(low) != set(high):
        print(f"[warn] question sets differ: {len(shared)} shared", file=sys.stderr)

    key = "iou@0.3_sim@0.5"
    deltas = [high_per[q]["thresholds"][key]["f1"] - low_per[q]["thresholds"][key]["f1"] for q in shared]

    def completeness_stats(rows):
        flags = [completeness(rows[q]) for q in shared]
        return {
            "closing_tags_complete": sum(f["closing_tags_complete"] for f in flags),
            "parsed_answer_present": sum(f["parsed_answer_present"] for f in flags),
            "parsed_evidence_present": sum(f["parsed_evidence_present"] for f in flags),
            "hit_cap": sum(f["hit_cap"] for f in flags),
            "num_questions": len(flags),
        }

    low_complete = [q for q in shared if "</answer>" in (low[q].get("model_response_raw") or "").lower()]
    identical = sum(1 for q in low_complete if low[q].get("model_response_raw") == high[q].get("model_response_raw"))

    def timing(rows):
        values = [rows[q].get("processing_time", 0) for q in shared]
        tokens = [rows[q].get("output_tokens") for q in shared if rows[q].get("output_tokens") is not None]
        return {
            "mean_seconds": round(statistics.mean(values), 2),
            "total_seconds": round(sum(values), 1),
            "mean_output_tokens": round(statistics.mean(tokens), 1) if tokens else None,
            "output_tokens_recorded": bool(tokens),
        }

    improved = sum(1 for d in deltas if d > 1e-12)
    worsened = sum(1 for d in deltas if d < -1e-12)
    p_value = None
    nonzero = [d for d in deltas if abs(d) > 1e-12]
    if len(nonzero) >= 5:
        try:
            from scipy.stats import wilcoxon

            p_value = round(float(wilcoxon(nonzero).pvalue), 4)
        except Exception:
            p_value = None

    result = {
        "shared_questions": len(shared),
        "official_low": {
            "eg_f1": low_stored["eg_f1"]["metrics_by_threshold"],
            "iou_f1": low_stored["iou_f1"]["metrics_by_threshold"],
        },
        "official_high": {
            "eg_f1": high_stored["eg_f1"]["metrics_by_threshold"],
            "iou_f1": high_stored["iou_f1"]["metrics_by_threshold"],
        },
        "paired_eg_f1_delta": {
            "mean": round(statistics.mean(deltas), 4) if deltas else None,
            "improved": improved,
            "worsened": worsened,
            "unchanged": len(deltas) - improved - worsened,
            "wilcoxon_p": p_value,
        },
        "completeness_low": completeness_stats(low),
        "completeness_high": completeness_stats(high),
        "responses_identical_on_low_complete": {"identical": identical, "compared": len(low_complete)},
        "timing_low": timing(low),
        "timing_high": timing(high),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
