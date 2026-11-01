"""Build a stratified evaluation subset from real test questions.

Selection is by question type only, with a fixed seed; the official test
annotations are never modified. Every selected question must belong to a video
whose frames are already extracted locally.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Stratified sample of EG-VQA test questions.")
    parser.add_argument("--annotations", type=Path, default=REPO_ROOT / "official_repo/data/test.json")
    parser.add_argument("--frames-root", type=Path, default=REPO_ROOT / "official_repo/data/frames/test")
    parser.add_argument("--total", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20261030)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "experiments/ablation/expanded_questions.json")
    parser.add_argument("--allow-fewer", action="store_true",
                        help="Allow fewer than --total questions (default: fail).")
    args = parser.parse_args()

    data = json.loads(args.annotations.read_text(encoding="utf-8"))
    by_type: dict[str, list[dict]] = collections.defaultdict(list)
    available_videos = {p.name for p in args.frames_root.iterdir() if p.is_dir()}
    for video in data:
        if video["video_id"] not in available_videos:
            continue
        for question in video.get("questions") or []:
            by_type[question["type"]].append(
                {
                    "video_id": video["video_id"],
                    "question_id": question["question_id"],
                    "type": question["type"],
                    "question": question["question"],
                    "answer": question["answer"],
                    "evidence": question["evidence"],
                    "duration": video["duration"],
                    "data_source": video["data_source"],
                    "metadata": video.get("metadata") or {},
                }
            )

    types = sorted(by_type)
    per_type = args.total // len(types)
    remainder = args.total - per_type * len(types)
    rng = random.Random(args.seed)
    selected: list[dict] = []
    for index, question_type in enumerate(types):
        pool = sorted(by_type[question_type], key=lambda q: q["question_id"])
        quota = per_type + (1 if index < remainder else 0)
        quota = min(quota, len(pool))
        selected.extend(rng.sample(pool, quota))

    selected.sort(key=lambda q: q["question_id"])
    if len(selected) < args.total and not args.allow_fewer:
        print(
            f"error: only {len(selected)} of {args.total} questions are available; "
            "extract frames for more videos or pass --allow-fewer",
            file=sys.stderr,
        )
        return 2
    video_counts = collections.Counter(q["video_id"] for q in selected)
    summary = {
        "seed": args.seed,
        "requested_total": args.total,
        "selected_total": len(selected),
        "available_pool_by_type": {t: len(v) for t, v in sorted(by_type.items())},
        "selected_by_type": dict(sorted(collections.Counter(q["type"] for q in selected).items())),
        "selected_by_source": dict(sorted(collections.Counter(q["data_source"] for q in selected).items())),
        "num_videos": len(video_counts),
        "max_questions_per_video": max(video_counts.values()) if video_counts else 0,
        "sampling": "stratified by question type, uniform random within type (random.Random(seed).sample), sorted by question_id",
    }
    payload = {"summary": summary, "questions": selected}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
