"""Plot the metric-sensitivity study from its JSON output (real data only)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Plot EG-F1 / IoU-F1 vs temporal jitter.")
    parser.add_argument("--input", type=Path, default=Path("experiments/metric_sensitivity/summary.json"))
    parser.add_argument("--output", type=Path, default=Path("experiments/metric_sensitivity/sensitivity.png"))
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    keys = sorted(data["temporal_shift"], key=float)
    sigmas = [float(k) for k in keys]

    def series(key):
        return [data["temporal_shift"][k][key] for k in keys]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    eg_keys = [("EG-F1_iou@0.3_sim@0.5", "EG-F1 (0.3,0.5)"), ("EG-F1_iou@0.3_sim@0.75", "EG-F1 (0.3,0.75)"),
               ("EG-F1_iou@0.5_sim@0.75", "EG-F1 (0.5,0.75)")]
    iou_keys = [(f"IoU-F1_{t}", f"IoU-F1 @{t}") for t in ("0.1", "0.3", "0.5", "0.7")]

    for key, label in eg_keys:
        axes[0].plot(sigmas, series(key), marker="o", label=label)
    axes[0].set_title("EG-F1 vs temporal jitter")
    axes[0].set_xlabel("uniform jitter bound on each boundary (s)")
    axes[0].set_ylabel("score")
    axes[0].grid(alpha=0.3)
    axes[0].legend(fontsize=8)

    for key, label in iou_keys:
        axes[1].plot(sigmas, series(key), marker="o", label=label)
    axes[1].set_title("IoU-F1 vs temporal jitter")
    axes[1].set_xlabel("uniform jitter bound on each boundary (s)")
    axes[1].grid(alpha=0.3)
    axes[1].legend(fontsize=8)

    n = data["num_questions"]
    fig.suptitle(f"Metric sensitivity on {n} real test questions (ground-truth timestamps perturbed)", fontsize=10)
    fig.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=150)
    print(f"Saved {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
