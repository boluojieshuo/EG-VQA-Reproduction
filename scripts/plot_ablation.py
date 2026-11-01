"""Plot ablation results from experiments/ablation/summary.json."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "experiments" / "ablation" / "summary.json"
OUT = ROOT / "experiments" / "ablation" / "ablation_summary.png"

ORDER = ["A_legacy_8_first", "A2_uniform_8", "B_uniform_16", "C_uniform_32", "D_uniform_8_timestamp"]
LABELS = {
    "A_legacy_8_first": "A: 8f first",
    "A2_uniform_8": "A2: 8f uniform",
    "B_uniform_16": "B: 16f uniform",
    "C_uniform_32": "C: 32f uniform",
    "D_uniform_8_timestamp": "D: 8f + timestamp prompt",
}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Plot ablation results from a summary.json.")
    parser.add_argument("--input", type=Path, default=SUMMARY)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    rows_list = payload.get("ablation_rows", payload.get("rows"))
    if not rows_list:
        raise SystemExit(f"no ablation rows found in {args.input}")
    rows = {row["config"]: row for row in rows_list}
    configs = [c for c in ORDER if c in rows]
    labels = [LABELS[c] for c in configs]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))

    x = range(len(configs))
    axes[0].bar([i - 0.2 for i in x], [rows[c]["eg_f1_0.3_0.5"] for c in configs], width=0.4, label="EG-F1 (0.3,0.5)")
    axes[0].bar([i + 0.2 for i in x], [rows[c]["iou_f1_0.1"] for c in configs], width=0.4, label="IoU-F1 @0.1")
    axes[0].set_xticks(list(x))
    axes[0].set_xticklabels(labels, rotation=20, ha="right", fontsize=8)
    axes[0].set_ylabel("score")
    axes[0].set_title("Official metrics on the same 92 questions")
    axes[0].legend(fontsize=8)
    axes[0].grid(axis="y", alpha=0.3)

    uniform = [("8", rows["A2_uniform_8"]), ("16", rows["B_uniform_16"]), ("32", rows["C_uniform_32"])]
    axes[1].plot([int(f) for f, _ in uniform], [r["eg_f1_0.3_0.5"] for _, r in uniform], marker="o", label="EG-F1 (0.3,0.5)")
    axes[1].plot([int(f) for f, _ in uniform], [r["iou_f1_0.1"] for _, r in uniform], marker="s", label="IoU-F1 @0.1")
    axes[1].set_xlabel("frames (uniform sampling from 32 extracted)")
    axes[1].set_title("Frame count is the main lever")
    axes[1].grid(alpha=0.3)
    axes[1].legend(fontsize=8)

    axes[2].bar(labels, [rows[c]["with_answer"] for c in configs], color="#c44e52")
    axes[2].set_ylim(0, 92)
    axes[2].set_ylabel("questions with complete think+answer (of 92)")
    axes[2].set_title("Output completeness degrades with more frames")
    axes[2].tick_params(axis="x", labelrotation=20, labelsize=8)
    axes[2].grid(axis="y", alpha=0.3)

    fig.suptitle("Substitute baseline (Qwen2.5-VL-3B, 4-bit) — real measured results, not EG-Reasoner", fontsize=10)
    fig.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=150)
    print(f"Saved {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
