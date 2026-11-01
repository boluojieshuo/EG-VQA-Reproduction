"""Analyze substitute-baseline predictions with the official per-sample metric output.

Joins predictions (for question type and raw response) with evidence_metrics
per-sample results, then reports per-type averages, parse health, and the
worst-grounded examples.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze EG-VQA predictions against official metrics.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-errors", type=int, default=10)
    args = parser.parse_args()

    predictions = load_json(args.predictions)
    metrics = load_json(args.metrics)
    by_id = {item["question_id"]: item for item in predictions}
    eg_key = next(iter(metrics["eg_f1"]["metrics_by_threshold"]))
    iou_keys = list(metrics["iou_f1"]["metrics_by_threshold"])

    rows: List[Dict[str, Any]] = []
    for sample in metrics["eg_f1"]["per_sample_results"]:
        pred = by_id.get(sample["question_id"], {})
        parsed = pred.get("parsed_response") or {}
        rows.append(
            {
                "question_id": sample["question_id"],
                "video_id": sample["video_id"],
                "type": pred.get("type", "unknown"),
                "n_gt": sample["n_gt"],
                "n_pred": sample["n_pred"],
                "n_pred_valid": sample["n_pred_valid"],
                "eg_f1": sample["thresholds"][eg_key]["f1"],
                "iou_f1": sample["thresholds_iou"] if "thresholds_iou" in sample else None,
                "has_evidence_block": bool(parsed.get("evidence")),
                "has_think_block": bool(parsed.get("think")),
                "has_answer_block": bool(parsed.get("answer")),
                "error": pred.get("error"),
            }
        )

    per_type: Dict[str, Dict[str, Any]] = {}
    grouped = collections.defaultdict(list)
    for row in rows:
        grouped[row["type"]].append(row)
    for question_type, items in sorted(grouped.items()):
        per_type[question_type] = {
            "num_questions": len(items),
            "avg_eg_f1": round(sum(item["eg_f1"] for item in items) / len(items), 4),
            "num_with_evidence": sum(1 for item in items if item["has_evidence_block"]),
            "num_invalid_predictions": sum(item["n_pred"] - item["n_pred_valid"] for item in items),
            "num_errors": sum(1 for item in items if item["error"]),
        }

    # IoU-F1 per sample is stored under the iou_f1 structure; join to compute per-type IoU too.
    iou_by_id = {
        sample["question_id"]: sample for sample in metrics["iou_f1"]["per_sample_results"]
    }
    for question_type, items in grouped.items():
        values = [
            iou_by_id[item["question_id"]]["thresholds"]["0.3"]["f1"]
            for item in items
            if item["question_id"] in iou_by_id
        ]
        if values:
            per_type[question_type]["avg_iou_f1@0.3"] = round(sum(values) / len(values), 4)

    errors = sorted(rows, key=lambda row: (row["eg_f1"], -row["n_gt"]))[: args.top_errors]
    summary = {
        "num_questions": len(rows),
        "eg_threshold_used": eg_key,
        "overall_avg_eg_f1": round(sum(row["eg_f1"] for row in rows) / len(rows), 4) if rows else 0.0,
        "num_with_evidence_block": sum(1 for row in rows if row["has_evidence_block"]),
        "num_with_think_block": sum(1 for row in rows if row["has_think_block"]),
        "num_with_answer_block": sum(1 for row in rows if row["has_answer_block"]),
        "num_errors": sum(1 for row in rows if row["error"]),
        "total_invalid_predictions": sum(row["n_pred"] - row["n_pred_valid"] for row in rows),
        "per_type": per_type,
        "worst_examples": [
            {
                "question_id": row["question_id"],
                "type": row["type"],
                "eg_f1": row["eg_f1"],
                "n_gt": row["n_gt"],
                "n_pred": row["n_pred"],
                "n_pred_valid": row["n_pred_valid"],
            }
            for row in errors
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
