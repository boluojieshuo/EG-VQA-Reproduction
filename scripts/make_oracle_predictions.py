"""Build an evaluate.py-compatible result file whose predictions are the ground truth.

Purpose: validate the official evidence-metric pipeline end to end on real
annotations without any model. This is an oracle sanity check, NOT model
performance. The output keeps the official schema so
`evaluation/evidence_metrics.py` reads it unmodified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build(annotation_path: Path, limit: int = 0) -> list:
    data = json.loads(annotation_path.read_text(encoding="utf-8"))
    samples = []
    for video in data:
        if len(samples) >= limit > 0:
            break
        for question in video.get("questions") or []:
            if len(samples) >= limit > 0:
                break
            evidence = question.get("evidence") or []
            samples.append(
                {
                    "video_id": video.get("video_id"),
                    "question_id": question.get("question_id"),
                    "video_path": video.get("video_path"),
                    "duration": video.get("duration"),
                    "data_source": video.get("data_source"),
                    "metadata": video.get("metadata") or {},
                    "question": question.get("question", ""),
                    "type": question.get("type"),
                    "answer": question.get("answer", ""),
                    "evidence": evidence,
                    "model_response_raw": None,
                    "parsed_response": {"evidence": evidence, "think": None, "answer": question.get("answer", "")},
                    "is_oracle": True,
                }
            )
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an oracle prediction file for metric validation.")
    parser.add_argument("--annotations", type=Path, default=Path("official_repo/data/test.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0, help="Keep only the first N questions.")
    args = parser.parse_args()

    samples = build(args.annotations, args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(samples, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {len(samples)} oracle samples to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
