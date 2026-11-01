"""Describe the annotation distribution per split and question type."""

from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from pathlib import Path


def summarize(split_path: Path) -> dict:
    data = json.loads(split_path.read_text(encoding="utf-8"))
    per_type = collections.defaultdict(lambda: {"questions": 0, "evidence": 0, "span_seconds": [], "answer_words": [], "question_words": []})
    per_source = collections.Counter()
    durations = []
    for video in data:
        durations.append(video.get("duration"))
        per_source[video.get("data_source")] += 1
        for question in video.get("questions") or []:
            bucket = per_type[question.get("type")]
            bucket["questions"] += 1
            evidence = question.get("evidence") or []
            bucket["evidence"] += len(evidence)
            for span in evidence:
                start, end = span["timestamp"]
                bucket["span_seconds"].append(end - start)
            bucket["answer_words"].append(len(str(question.get("answer", "")).split()))
            bucket["question_words"].append(len(str(question.get("question", "")).split()))

    def stats(values):
        return {"mean": round(statistics.mean(values), 2), "median": round(statistics.median(values), 2)} if values else {}

    out = {
        "videos": len(data),
        "video_duration_seconds": stats(durations),
        "videos_by_source": dict(per_source),
        "by_type": {},
    }
    for name, bucket in sorted(per_type.items()):
        out["by_type"][name] = {
            "questions": bucket["questions"],
            "evidence_spans": bucket["evidence"],
            "evidence_per_question": round(bucket["evidence"] / bucket["questions"], 3),
            "evidence_span_seconds": stats(bucket["span_seconds"]),
            "answer_words": stats(bucket["answer_words"]),
            "question_words": stats(bucket["question_words"]),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Annotation distribution analysis.")
    parser.add_argument("--data-root", type=Path, default=Path("official_repo/data"))
    parser.add_argument("--output", type=Path, default=Path("experiments/annotation_stats.json"))
    args = parser.parse_args()
    result = {split: summarize(args.data_root / f"{split}.json") for split in ("train", "test")}
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
