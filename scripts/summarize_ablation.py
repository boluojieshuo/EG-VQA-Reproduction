"""Aggregate ablation runs into JSON/CSV/Markdown tables.

Repository layout (default):
    results/metrics/<run>_evidence_metrics.json
    results/summaries/diagnostics/<run>.json
    configs/<run>.json          (optional; run meta is used as fallback)
    results/predictions/<run>.meta.json
    results/summaries/          (outputs)

Runs are split into two groups:
  * ablation: exactly the same question set as --reference (paired statistics);
  * expanded: any other sample set (reported separately, never paired).

A run with a different sample set is never compared with the reference; the
shared-question count is recorded for transparency only.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
EG_KEY = "iou@0.3_sim@0.5"

DEFAULT_METRICS = ROOT / "results" / "metrics"
DEFAULT_DIAGNOSTICS = ROOT / "results" / "summaries" / "diagnostics"
DEFAULT_CONFIGS = ROOT / "configs"
DEFAULT_META = ROOT / "results" / "predictions"
DEFAULT_OUTPUT = ROOT / "results" / "summaries"

ROW_ORDER = ["A_legacy_8_first", "A2_uniform_8", "B_uniform_16", "C_uniform_32", "D_uniform_8_timestamp"]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def discover_runs(metrics_dir: Path, diagnostics_dir: Path, configs_dir: Path,
                  meta_dir: Path, exclude: Sequence[str]) -> Tuple[List[Dict[str, Any]], List[str]]:
    runs: List[Dict[str, Any]] = []
    warnings: List[str] = []
    if not metrics_dir.is_dir():
        return [], [f"metrics directory not found: {metrics_dir}"]

    for metrics_path in sorted(metrics_dir.glob("*_evidence_metrics.json")):
        name = metrics_path.name.removesuffix("_evidence_metrics.json")
        if name in exclude:
            continue
        diagnostics_path = diagnostics_dir / f"{name}.json"
        if not diagnostics_path.is_file():
            warnings.append(f"skip {name}: diagnostics missing ({diagnostics_path})")
            continue
        diagnostics = load_json(diagnostics_path)
        metrics = load_json(metrics_path)

        config: Dict[str, Any] = {}
        config_source = None
        config_path = configs_dir / f"{name}.json"
        if config_path.is_file():
            config = load_json(config_path)
            config_source = str(config_path)
        else:
            meta_path = meta_dir / f"{name}.meta.json"
            if meta_path.is_file():
                config = load_json(meta_path)
                config_source = str(meta_path)
        if not config:
            warnings.append(f"{name}: no config or run metadata found; frame/prompt fields may be null")

        runs.append(
            {
                "name": name,
                "metrics": metrics,
                "diagnostics": diagnostics,
                "config": config,
                "config_source": config_source,
            }
        )
    return runs, warnings


def row_for(run: Dict[str, Any]) -> Dict[str, Any]:
    diag = run["diagnostics"]
    official = diag["official_metrics"]
    custom = diag["custom_diagnostics"]
    config = run["config"]
    return {
        "config": run["name"],
        "frames": diag["config"].get("max_frames") or config.get("max_frames"),
        "frame_selection": diag["config"].get("frame_selection") or config.get("frame_selection"),
        "prompt_variant": diag["config"].get("prompt_variant") or config.get("prompt_variant"),
        "num_questions": official["num_samples"],
        "eg_f1_0.3_0.5": official["eg_f1"].get(EG_KEY),
        "eg_f1_0.3_0.75": official["eg_f1"].get("iou@0.3_sim@0.75"),
        "eg_f1_0.5_0.75": official["eg_f1"].get("iou@0.5_sim@0.75"),
        "iou_f1_0.1": official["iou_f1"].get("0.1"),
        "iou_f1_0.3": official["iou_f1"].get("0.3"),
        "iou_f1_0.5": official["iou_f1"].get("0.5"),
        "iou_f1_0.7": official["iou_f1"].get("0.7"),
        "start_mae_sec": custom["start_abs_error_sec"]["mean"],
        "end_mae_sec": custom["end_abs_error_sec"]["mean"],
        "matched_pairs": custom["start_abs_error_sec"]["matched_pairs"],
        "first30_fraction": custom["fraction_questions_all_predictions_within_first_30s"],
        "no_overlap_rate": custom["no_temporal_overlap_rate"],
        "mean_best_iou": custom["mean_best_iou_per_prediction"],
        "invalid_rate": custom["invalid_rate"],
        "empty_rate": custom["empty_evidence_rate"],
        "oob_rate": custom["end_beyond_duration_rate"],
        "mean_seconds": custom["timing"]["mean_processing_sec"],
        "gpu_peak_gib": custom["timing"]["gpu_peak_gib"],
        "with_evidence": custom["format_health"]["with_evidence"],
        "with_answer": custom["format_health"]["with_answer"],
        "eg_causal": custom["per_type_avg_eg_f1_iou@0.3_sim@0.5"].get("causal"),
        "eg_counterfactual": custom["per_type_avg_eg_f1_iou@0.3_sim@0.5"].get("counterfactual"),
        "eg_descriptive": custom["per_type_avg_eg_f1_iou@0.3_sim@0.5"].get("descriptive"),
        "eg_temporal": custom["per_type_avg_eg_f1_iou@0.3_sim@0.5"].get("temporal"),
    }


def sample_f1s(run: Dict[str, Any]) -> Dict[str, float]:
    return {
        sample["question_id"]: sample["thresholds"][EG_KEY]["f1"]
        for sample in run["metrics"]["eg_f1"]["per_sample_results"]
    }


def pair_against_reference(
    reference_f1: Dict[str, float],
    other_f1: Dict[str, float],
    identical_sets: bool,
) -> Dict[str, Any]:
    shared = sorted(set(reference_f1) & set(other_f1))
    if not identical_sets:
        return {
            "pair_status": "different_sample_set",
            "paired_vs_reference_n": len(shared),
            "mean_delta": None,
            "improved": None,
            "worsened": None,
            "wilcoxon_p": None,
        }
    deltas = [other_f1[qid] - reference_f1[qid] for qid in shared]
    improved = sum(1 for d in deltas if d > 1e-12)
    worsened = sum(1 for d in deltas if d < -1e-12)
    nonzero = [d for d in deltas if abs(d) > 1e-12]
    p_value: Optional[float] = None
    if len(nonzero) >= 5:
        try:
            from scipy.stats import wilcoxon

            p_value = round(float(wilcoxon(nonzero).pvalue), 4)
        except Exception:
            p_value = None
    return {
        "pair_status": "same_sample_set",
        "paired_vs_reference_n": len(shared),
        "mean_delta": round(statistics.mean(deltas), 4),
        "improved": improved,
        "worsened": worsened,
        "wilcoxon_p": p_value,
    }


def sort_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(rows, key=lambda r: ROW_ORDER.index(r["config"]) if r["config"] in ROW_ORDER else 99)


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: List[Dict[str, Any]], columns: List[str]) -> None:
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(column)) for column in columns) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize ablation and expanded runs.")
    parser.add_argument("--reference", default="A2_uniform_8")
    parser.add_argument("--exclude", nargs="*", default=["C32_tok512"],
                        help="Runs reported separately elsewhere (e.g. token-limit experiment).")
    parser.add_argument("--metrics-dir", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--diagnostics-dir", type=Path, default=DEFAULT_DIAGNOSTICS)
    parser.add_argument("--configs-dir", type=Path, default=DEFAULT_CONFIGS)
    parser.add_argument("--meta-dir", type=Path, default=DEFAULT_META)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    runs, warnings = discover_runs(
        args.metrics_dir, args.diagnostics_dir, args.configs_dir, args.meta_dir, args.exclude
    )
    if not runs:
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        print("error: no valid runs found (metrics + diagnostics are required)", file=sys.stderr)
        return 2

    by_name = {run["name"]: run for run in runs}
    if args.reference not in by_name:
        print(f"error: reference run not found: {args.reference}", file=sys.stderr)
        return 2

    reference_f1 = sample_f1s(by_name[args.reference])
    reference_set = set(reference_f1)

    ablation_rows: List[Dict[str, Any]] = []
    expanded_rows: List[Dict[str, Any]] = []

    for run in runs:
        row = row_for(run)
        f1 = sample_f1s(run)
        identical = set(f1) == reference_set
        if run["name"] == args.reference:
            row.update(
                {
                    "pair_status": "reference",
                    "paired_vs_reference_n": len(reference_set),
                    "mean_delta": 0.0,
                    "improved": None,
                    "worsened": None,
                    "wilcoxon_p": None,
                }
            )
        else:
            row.update(pair_against_reference(reference_f1, f1, identical))
        if identical:
            ablation_rows.append(row)
        else:
            warnings.append(
                f"{run['name']}: {row['num_questions']} questions, different from reference set "
                f"({len(reference_set)}); reported separately, no paired statistics"
            )
            expanded_rows.append(row)

    ablation_rows = sort_rows(ablation_rows)
    expanded_rows = sort_rows(expanded_rows)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "reference": args.reference,
        "reference_num_questions": len(reference_set),
        "ablation_rows": ablation_rows,
        "expanded_rows": expanded_rows,
        "warnings": warnings,
    }
    (args.output_dir / "ablation_summary.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )

    ablation_columns = [
        "config", "num_questions", "frames", "frame_selection", "prompt_variant",
        "eg_f1_0.3_0.5", "eg_f1_0.3_0.75", "iou_f1_0.1",
        "pair_status", "paired_vs_reference_n", "mean_delta", "improved", "worsened", "wilcoxon_p",
        "mean_seconds", "gpu_peak_gib",
    ]
    write_csv(args.output_dir / "ablation_summary.csv", ablation_rows)
    write_markdown(args.output_dir / "ablation_summary.md", ablation_rows, ablation_columns)

    if expanded_rows:
        (args.output_dir / "expanded_summary.json").write_text(
            json.dumps({"note": "Different sample set from the ablation reference; no paired statistics.",
                        "rows": expanded_rows}, indent=2), encoding="utf-8"
        )
        expanded_columns = [
            "config", "num_questions", "frames", "frame_selection", "prompt_variant",
            "eg_f1_0.3_0.5", "eg_f1_0.3_0.75", "iou_f1_0.1",
            "no_overlap_rate", "first30_fraction", "mean_best_iou",
            "mean_seconds", "gpu_peak_gib",
        ]
        write_csv(args.output_dir / "expanded_summary.csv", expanded_rows)
        write_markdown(args.output_dir / "expanded_summary.md", expanded_rows, expanded_columns)

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(f"wrote {args.output_dir / 'ablation_summary.json'} ({len(ablation_rows)} runs)")
    if expanded_rows:
        print(f"wrote {args.output_dir / 'expanded_summary.json'} ({len(expanded_rows)} runs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
