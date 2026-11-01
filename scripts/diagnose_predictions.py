"""Compute official and custom diagnostic metrics for one prediction file.

Official metrics are read verbatim from the file produced by
official_repo/evaluation/evidence_metrics.py. Everything under
"custom_diagnostics" is our own and is not a paper metric.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "official_repo" / "evaluation"))

import evidence_metrics as em  # noqa: E402


def median(values: List[float]):
    return round(statistics.median(values), 3) if values else None


def mean(values: List[float]):
    return round(statistics.mean(values), 3) if values else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Official + custom diagnostics for one run.")
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--meta", type=Path, default=None)
    parser.add_argument("--label", default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    items = em.load_items(args.predictions)
    stored = json.loads(args.metrics.read_text(encoding="utf-8"))
    meta = json.loads(args.meta.read_text(encoding="utf-8")) if args.meta and args.meta.is_file() else {}
    predictions_by_id = {item["question_id"]: item for item in items}

    start_errors: List[float] = []
    end_errors: List[float] = []
    per_type: Dict[str, List[float]] = {}
    per_question = []
    counts = {"predictions": 0, "invalid": 0, "empty": 0, "end_beyond_duration": 0, "start_negative": 0,
              "no_temporal_overlap": 0, "max_iou_ge_0.1": 0}
    max_ious: List[float] = []
    early_questions = 0
    with_predictions = 0

    for sample in stored["eg_f1"]["per_sample_results"]:
        item = predictions_by_id[sample["question_id"]]
        gts = em.ground_truth_evidence(item)
        preds = em.predicted_evidence(item)
        duration = float(item.get("duration") or 0.0)
        valid_preds = [p for p in preds if p.is_valid]
        counts["predictions"] += len(preds)
        counts["invalid"] += sum(1 for p in preds if not p.is_valid)
        counts["empty"] += 1 if not preds else 0
        counts["end_beyond_duration"] += sum(1 for p in valid_preds if duration and p.end > duration + 1e-6)
        counts["start_negative"] += sum(1 for p in preds if p.start < 0)
        if valid_preds:
            with_predictions += 1
            if max(p.start for p in valid_preds) <= 30:
                early_questions += 1

        ious = em.iou_matrix(gts, valid_preds)
        if valid_preds:
            if gts:
                best_per_pred = ious.max(axis=0)
            else:
                best_per_pred = [0.0] * len(valid_preds)
            counts["no_temporal_overlap"] += sum(1 for value in best_per_pred if value == 0)
            counts["max_iou_ge_0.1"] += sum(1 for value in best_per_pred if value >= 0.1)
            max_ious.extend(float(value) for value in best_per_pred)
        matches = em.match_by_score(ious)
        sample_start, sample_end = [], []
        for gt_index, pred_index in matches:
            if ious[gt_index, pred_index] <= 0:
                continue
            gt, pred = gts[gt_index], valid_preds[pred_index]
            sample_start.append(abs(pred.start - gt.start))
            sample_end.append(abs(pred.end - gt.end))
        start_errors.extend(sample_start)
        end_errors.extend(sample_end)

        question_type = item.get("type", "unknown")
        f1 = sample["thresholds"]["iou@0.3_sim@0.5"]["f1"]
        per_type.setdefault(question_type, []).append(f1)
        per_question.append(
            {
                "question_id": sample["question_id"],
                "type": question_type,
                "time_start_mae_matched": mean(sample_start),
                "time_end_mae_matched": mean(sample_end),
            }
        )

    official = {
        "note": "computed by official_repo/evaluation/evidence_metrics.py; not modified here",
        "eg_f1": {k: round(v["avg_f1"], 4) for k, v in stored["eg_f1"]["metrics_by_threshold"].items()},
        "iou_f1": {k: round(v["avg_f1"], 4) for k, v in stored["iou_f1"]["metrics_by_threshold"].items()},
        "num_samples": len(items),
    }
    custom = {
        "note": "CUSTOM diagnostics, not official paper metrics",
        "start_abs_error_sec": {"mean": mean(start_errors), "median": median(start_errors), "matched_pairs": len(start_errors)},
        "end_abs_error_sec": {"mean": mean(end_errors), "median": median(end_errors), "matched_pairs": len(end_errors)},
        "fraction_questions_all_predictions_within_first_30s": round(early_questions / with_predictions, 4) if with_predictions else None,
        "predictions": counts,
        "invalid_rate": round(counts["invalid"] / counts["predictions"], 4) if counts["predictions"] else None,
        "no_temporal_overlap_rate": round(counts["no_temporal_overlap"] / counts["predictions"], 4) if counts["predictions"] else None,
        "predictions_with_max_iou_ge_0.1_rate": round(counts["max_iou_ge_0.1"] / counts["predictions"], 4) if counts["predictions"] else None,
        "mean_best_iou_per_prediction": round(statistics.mean(max_ious), 4) if max_ious else None,
        "empty_evidence_rate": round(counts["empty"] / len(items), 4) if items else None,
        "end_beyond_duration_rate": round(counts["end_beyond_duration"] / counts["predictions"], 4) if counts["predictions"] else None,
        "per_type_avg_eg_f1_iou@0.3_sim@0.5": {k: round(mean(v), 4) for k, v in sorted(per_type.items())},
        "per_type_counts": {k: len(v) for k, v in sorted(per_type.items())},
        "timing": {
            "mean_processing_sec": mean([r.get("processing_time", 0) for r in items]),
            "total_processing_sec": round(sum(r.get("processing_time", 0) for r in items), 1),
            "gpu_peak_gib": meta.get("gpu_peak_gib"),
            "load_seconds": meta.get("load_seconds"),
        },
        "format_health": {
            "with_evidence": sum(1 for r in items if (r.get("parsed_response") or {}).get("evidence")),
            "with_think": sum(1 for r in items if (r.get("parsed_response") or {}).get("think")),
            "with_answer": sum(1 for r in items if (r.get("parsed_response") or {}).get("answer")),
            "num_questions": len(items),
        },
    }

    output = {
        "label": args.label or args.predictions.stem,
        "predictions_file": str(args.predictions),
        "metrics_file": str(args.metrics),
        "config": {k: meta.get(k) for k in ("max_frames", "frame_selection", "prompt_variant", "dtype", "load_in_4bit", "gpu_peak_gib")},
        "official_metrics": official,
        "custom_diagnostics": custom,
        "per_question": per_question,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: output[k] for k in ("label", "official_metrics", "custom_diagnostics")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
