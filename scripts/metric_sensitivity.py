"""Measure how official evidence metrics respond to controlled perturbations.

Ground-truth evidence is perturbed in two ways:
  * temporal shift: both boundaries move by an independent uniform offset;
  * description swap: timestamps stay exact, descriptions are replaced by
    descriptions from other samples (semantic gate stress test).

This is a metric-sensitivity study, NOT a model evaluation.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "official_repo" / "evaluation"))

import evidence_metrics as em  # noqa: E402


def load_items(annotation_path: Path, limit: int) -> List[Dict[str, Any]]:
    data = json.loads(annotation_path.read_text(encoding="utf-8"))
    items = []
    for video in data:
        for question in video.get("questions") or []:
            if limit and len(items) >= limit:
                return items
            items.append(
                {
                    "video_id": video.get("video_id"),
                    "question_id": question.get("question_id"),
                    "question": question.get("question", ""),
                    "evidence": question.get("evidence") or [],
                }
            )
    return items


def with_predictions(items: List[Dict[str, Any]], predictions_by_id: Dict[str, List[dict]]) -> List[Dict[str, Any]]:
    out = []
    for item in items:
        copy = dict(item)
        copy["parsed_response"] = {"evidence": predictions_by_id[item["question_id"]]}
        out.append(copy)
    return out


def shift_time(items: List[Dict[str, Any]], sigma: float, rng: random.Random) -> Dict[str, List[dict]]:
    predictions = {}
    for item in items:
        spans = []
        for span in item["evidence"]:
            start, end = span["timestamp"]
            new_start = max(0.0, start + rng.uniform(-sigma, sigma))
            new_end = max(new_start + 0.5, end + rng.uniform(-sigma, sigma))
            spans.append({"timestamp": [round(new_start, 2), round(new_end, 2)], "description": span["description"]})
        predictions[item["question_id"]] = spans
    return predictions


def swap_descriptions(items: List[Dict[str, Any]], seed: int) -> Dict[str, List[dict]]:
    pool = [span["description"] for item in items for span in item["evidence"]]
    rng = random.Random(seed)
    predictions = {}
    cursor = 0
    for item in items:
        spans = []
        for span in item["evidence"]:
            other = pool[(cursor + len(item["evidence"])) % len(pool)]
            cursor += 1
            spans.append({"timestamp": list(span["timestamp"]), "description": other})
        predictions[item["question_id"]] = spans
    return predictions


def summarize(result: Dict[str, Any]) -> Dict[str, float]:
    return {
        **{f"EG-F1_{key}": round(value["avg_f1"], 4) for key, value in result["eg_f1"]["metrics_by_threshold"].items()},
        **{f"IoU-F1_{key}": round(value["avg_f1"], 4) for key, value in result["iou_f1"]["metrics_by_threshold"].items()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Metric sensitivity to temporal jitter and description swaps.")
    parser.add_argument("--annotations", type=Path, default=REPO_ROOT / "official_repo" / "data" / "test.json")
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--sigmas", nargs="*", type=float, default=[0, 2, 5, 10, 20, 30])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--semantic-dir", type=Path, default=REPO_ROOT / "official_repo" / "EG-Reasoner" / "Science_Bert")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "experiments" / "metric_sensitivity" / "summary.json")
    args = parser.parse_args()

    items = load_items(args.annotations, args.limit)
    print(f"Loaded {len(items)} questions")
    encoder = em.SemanticEncoder(args.semantic_dir, args.device)
    eg_thresholds = em.parse_threshold_pairs(em.DEFAULT_EG_THRESHOLDS)
    iou_thresholds = em.parse_float_list(em.DEFAULT_IOU_THRESHOLDS)

    results: Dict[str, Any] = {"num_questions": len(items), "temporal_shift": {}, "description_swap": {}}
    for sigma in args.sigmas:
        rng = random.Random(args.seed + int(sigma * 100))
        preds = shift_time(items, sigma, rng)
        perturbed = with_predictions(items, preds)
        result = {"eg_f1": em.evaluate_eg(perturbed, eg_thresholds, encoder), "iou_f1": em.evaluate_iou(perturbed, iou_thresholds)}
        results["temporal_shift"][str(sigma)] = summarize(result)
        print(f"sigma={sigma}s: {results['temporal_shift'][str(sigma)]}")

    swapped = with_predictions(items, swap_descriptions(items, args.seed))
    result = {"eg_f1": em.evaluate_eg(swapped, eg_thresholds, encoder), "iou_f1": em.evaluate_iou(swapped, iou_thresholds)}
    results["description_swap"]["summary"] = summarize(result)
    print(f"description swap: {results['description_swap']['summary']}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Saved to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
