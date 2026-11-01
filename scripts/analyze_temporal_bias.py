"""Quantify where predicted evidence falls in time vs where ground truth falls."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "official_repo" / "evaluation"))
import evidence_metrics as em  # noqa: E402


def starts(preds: List[em.Evidence], gts: List[em.Evidence]) -> Dict[str, Any]:
    return {
        "pred_starts": [p.start for p in preds if p.is_valid],
        "gt_starts": [g.start for g in gts],
    }


def dist(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {}
    return {
        "n": len(values),
        "mean": round(statistics.mean(values), 2),
        "median": round(statistics.median(values), 2),
        "p25": round(sorted(values)[len(values) // 4], 2),
        "p75": round(sorted(values)[3 * len(values) // 4], 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Temporal bias of predicted evidence.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    items = em.load_items(args.predictions)
    all_pred: List[float] = []
    all_gt: List[float] = []
    per_question = []
    early_all = 0
    early_any = 0
    for item in items:
        preds = em.predicted_evidence(item)
        gts = em.ground_truth_evidence(item)
        pred_starts = [p.start for p in preds if p.is_valid]
        gt_starts = [g.start for g in gts]
        all_pred.extend(pred_starts)
        all_gt.extend(gt_starts)
        if pred_starts:
            if max(pred_starts) <= 30:
                early_all += 1
            if min(pred_starts) <= 30:
                early_any += 1
        per_question.append(
            {
                "question_id": item.get("question_id"),
                "pred_start_median": round(statistics.median(pred_starts), 2) if pred_starts else None,
                "gt_start_median": round(statistics.median(gt_starts), 2) if gt_starts else None,
            }
        )

    n_with_pred = sum(1 for row in per_question if row["pred_start_median"] is not None)
    result = {
        "num_questions": len(items),
        "num_questions_with_predictions": n_with_pred,
        "predicted_span_start_seconds": dist(all_pred),
        "ground_truth_span_start_seconds": dist(all_gt),
        "questions_whose_predictions_all_start_within_30s": early_all,
        "questions_with_at_least_one_prediction_within_30s": early_any,
        "fraction_all_within_30s": round(early_all / n_with_pred, 4) if n_with_pred else None,
        "per_question": per_question,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "per_question"}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
