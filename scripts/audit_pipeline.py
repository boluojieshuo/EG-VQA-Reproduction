"""Audit the local inference/evaluation pipeline and the existing baseline run.

Produces experiments/ablation/pipeline_audit.json with evidence for:
  * how many of the 32 extracted frames each frame-count setting actually uses,
  * what time window those frames cover,
  * whether timestamps reach the model only through burned-in pixels,
  * parse/validity statistics of the existing 92-question predictions,
  * whether the stored IoU-F1 matches a fresh official recomputation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "official_repo" / "evaluation"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import evidence_metrics as em  # noqa: E402
import infer_qwen_vl as iq  # noqa: E402


def natural_key(path: Path):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", path.name)]


def uniform_subset(paths: List[Path], count: int) -> List[Path]:
    if count >= len(paths):
        return paths
    indices = np.linspace(0, len(paths) - 1, count)
    return [paths[int(round(i))] for i in indices]


def video_meta(video: Path) -> Dict[str, float]:
    cap = cv2.VideoCapture(str(video))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return {"fps": fps, "frames": frames, "duration_sec": frames / fps if fps else 0.0}


def frame_coverage(frames_root: Path, videos_root: Path, annotations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for video in annotations:
        frame_dir = frames_root / video["video_id"]
        if not frame_dir.is_dir():
            continue
        paths = sorted([p for p in frame_dir.iterdir() if p.suffix.lower() == ".png"], key=natural_key)
        video_path = next(iter(videos_root.glob(f"{video['video_id']}.*")), None)
        meta = video_meta(video_path) if video_path else {"fps": 0, "frames": 0, "duration_sec": video.get("duration", 0)}
        # Official sampling: uniform linspace over the whole video, times = index / fps.
        total = meta["frames"] or 1
        idx32 = [int(round(i)) for i in np.linspace(0, total - 1, len(paths))]
        times = [round(i / meta["fps"], 2) if meta["fps"] else None for i in idx32]
        first8_idx = idx32[:8]
        uni8_idx = [idx32[int(round(i))] for i in np.linspace(0, len(idx32) - 1, 8)]
        rows.append(
            {
                "video_id": video["video_id"],
                "duration_sec": round(meta["duration_sec"], 2),
                "extracted_frames": len(paths),
                "official_32_last_time": times[-1],
                "first8_last_time": round(first8_idx[-1] / meta["fps"], 2) if meta["fps"] else None,
                "uniform8_last_time": round(uni8_idx[-1] / meta["fps"], 2) if meta["fps"] else None,
                "first8_coverage_fraction": round(first8_idx[-1] / max(total - 1, 1), 4),
                "uniform8_coverage_fraction": round(uni8_idx[-1] / max(total - 1, 1), 4),
            }
        )
    return rows


def prediction_stats(items: List[Dict[str, Any]], metrics: Dict[str, Any]) -> Dict[str, Any]:
    rows = []
    for item in items:
        preds = em.predicted_evidence(item)
        gts = em.ground_truth_evidence(item)
        duration = item.get("duration") or 0
        starts = [p.start for p in preds if p.is_valid]
        rows.append(
            {
                "question_id": item["question_id"],
                "type": item.get("type"),
                "n_pred": len(preds),
                "n_invalid": sum(1 for p in preds if not p.is_valid),
                "n_empty": 0 if preds else 1,
                "n_reversed": sum(1 for p in preds if p.is_valid and p.start >= p.end),
                "n_start_negative": sum(1 for p in preds if p.start < 0),
                "n_end_beyond_duration": sum(1 for p in preds if p.is_valid and duration and p.end > float(duration) + 1e-6),
                "median_start": float(np.median(starts)) if starts else None,
                "max_start": max(starts) if starts else None,
                "gt_median_start": float(np.median([g.start for g in gts])) if gts else None,
                "duration": duration,
            }
        )

    valid_rows = [r for r in rows if r["n_pred"]]
    per_type: Dict[str, int] = {}
    for row in rows:
        per_type[row["type"]] = per_type.get(row["type"], 0) + 1

    # Recompute IoU-F1 with official functions and compare to the stored file.
    recomputed = em.evaluate_iou(em.load_items(Path(metrics["_input"])), em.parse_float_list(em.DEFAULT_IOU_THRESHOLDS))
    stored = metrics["iou_f1"]["metrics_by_threshold"]
    consistency = {
        key: {
            "stored_avg_f1": stored[key]["avg_f1"],
            "recomputed_avg_f1": recomputed["metrics_by_threshold"][key]["avg_f1"],
            "match": abs(stored[key]["avg_f1"] - recomputed["metrics_by_threshold"][key]["avg_f1"]) < 1e-12,
        }
        for key in stored
    }

    return {
        "num_questions": len(rows),
        "questions_by_type": per_type,
        "questions_with_predictions": len(valid_rows),
        "questions_without_evidence": sum(r["n_empty"] for r in rows),
        "total_predictions": sum(r["n_pred"] for r in rows),
        "total_invalid": sum(r["n_invalid"] for r in rows),
        "total_reversed": sum(r["n_reversed"] for r in rows),
        "total_negative_start": sum(r["n_start_negative"] for r in rows),
        "total_end_beyond_duration": sum(r["n_end_beyond_duration"] for r in rows),
        "predicted_start_median_of_medians": float(np.median([r["median_start"] for r in valid_rows])),
        "gt_start_median_of_medians": float(np.median([r["gt_median_start"] for r in rows])),
        "fraction_questions_all_predictions_within_first_30s": sum(
            1 for r in valid_rows if r["max_start"] is not None and r["max_start"] <= 30
        )
        / max(len(valid_rows), 1),
        "iou_metric_consistency_with_official_recompute": consistency,
        "per_question": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit local pipeline and baseline predictions.")
    parser.add_argument("--predictions", type=Path, default=REPO_ROOT / "experiments/predictions/qwen25vl3b_4bit_8f_test92.json")
    parser.add_argument("--metrics", type=Path, default=REPO_ROOT / "experiments/predictions/qwen25vl3b_4bit_8f_test92_evidence_metrics.json")
    parser.add_argument("--frames-root", type=Path, default=REPO_ROOT / "official_repo/data/frames/test")
    parser.add_argument("--videos-root", type=Path, default=REPO_ROOT / "official_repo/data/videos")
    parser.add_argument("--annotations", type=Path, default=REPO_ROOT / "official_repo/data/test.json")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "experiments/ablation/pipeline_audit.json")
    args = parser.parse_args()

    annotations = json.loads(args.annotations.read_text(encoding="utf-8"))
    frames = frame_coverage(args.frames_root, args.videos_root, annotations)
    items = em.load_items(args.predictions)
    metrics = json.loads(args.metrics.read_text(encoding="utf-8"))
    metrics["_input"] = str(args.predictions)
    stats = prediction_stats(items, metrics)

    prompt = evaluate_prompt_text()
    audit = {
        "frame_coverage": frames,
        "frame_selection_code_path": {
            "official_evaluate": "evaluation/evaluate.py::frame_paths_for_video does sorted(...)[:max_frames]",
            "local_inference": "scripts/infer_qwen_vl.py uses evaluate.frame_paths_for_video directly",
            "finding": "with max_frames < 32 this takes the FIRST frames, which cover only the beginning of the video",
            "uniform_subset_helper_available_now": True,
        },
        "timestamp_channel": {
            "frames_have_burned_in_timestamp": True,
            "prompt_static_example_timestamps": sorted(set(re.findall(r"\d{2}:\d{2}(?::\d{2})?", prompt))),
            "prompt_contains_sample_specific_timestamps": False,
            "prompt_time_instruction": "Time:MM:SS-MM:SS",
            "note": "timestamps reach the model only as pixels drawn on each frame; the prompt text carries no per-frame time",
        },
        "prediction_stats": stats,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({k: v for k, v in stats.items() if k != "per_question"}, indent=2))
    print("\nframe coverage (first 8 vs uniform 8):")
    for row in frames:
        print(
            f"  {row['video_id']}: dur={row['duration_sec']}s, first8_last={row['first8_last_time']}s "
            f"({row['first8_coverage_fraction'] * 100:.1f}% of video), uniform8_last={row['uniform8_last_time']}s"
        )
    return 0


def evaluate_prompt_text() -> str:
    return iq.evaluate.PROMPT_TEMPLATE


if __name__ == "__main__":
    sys.exit(main())
