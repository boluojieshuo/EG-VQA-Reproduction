"""Analyze whether model outputs were cut off by max_new_tokens.

Token counts are recomputed from the saved raw responses with the same
tokenizer used for generation (no re-inference).
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def section_flags(text: str) -> dict:
    text = text or ""
    return {
        "has_evidence_close": "</evidence>" in text.lower(),
        "has_think_close": "</think>" in text.lower(),
        "has_answer_close": "</answer>" in text.lower(),
    }


def truncation_point(flags: dict) -> str:
    if flags["has_answer_close"]:
        return "complete"
    if flags["has_think_close"]:
        return "cut_in_answer"
    if flags["has_evidence_close"]:
        return "cut_in_think"
    return "cut_in_evidence"


def main() -> int:
    parser = argparse.ArgumentParser(description="Quantify output truncation.")
    parser.add_argument("--predictions", nargs="+", required=True, type=Path)
    parser.add_argument("--tokenizer", type=Path, default=REPO_ROOT / "models/Qwen2.5-VL-3B-Instruct")
    parser.add_argument("--cap", type=int, default=256)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "experiments/ablation/truncation_analysis.json")
    args = parser.parse_args()

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(args.tokenizer))
    report = {"tokenizer": str(args.tokenizer), "cap": args.cap, "runs": {}}

    for path in args.predictions:
        rows = json.loads(path.read_text(encoding="utf-8"))
        counts = []
        points = collections.Counter()
        group_counts: dict[str, list[int]] = collections.defaultdict(list)
        at_cap = 0
        for row in rows:
            raw = row.get("model_response_raw") or ""
            n_tokens = len(tokenizer(raw, add_special_tokens=False)["input_ids"])
            counts.append(n_tokens)
            flags = section_flags(raw)
            point = truncation_point(flags)
            points[point] += 1
            group_counts[point].append(n_tokens)
            if n_tokens >= args.cap - 2:
                at_cap += 1
        report["runs"][path.stem] = {
            "num_samples": len(rows),
            "cap": args.cap,
            "mean_output_tokens": round(statistics.mean(counts), 1) if counts else None,
            "median_output_tokens": statistics.median(counts) if counts else None,
            "max_output_tokens": max(counts) if counts else None,
            "outputs_at_or_near_cap": at_cap,
            "truncation_points": dict(points),
            "complete_rate": round(points["complete"] / len(rows), 4) if rows else None,
            "token_stats_by_truncation_point": {
                point: {
                    "count": len(values),
                    "mean_tokens": round(statistics.mean(values), 1),
                    "median_tokens": statistics.median(values),
                }
                for point, values in sorted(group_counts.items())
            },
        }
        print(f"{path.stem}: {report['runs'][path.stem]}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
