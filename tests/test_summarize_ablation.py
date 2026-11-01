"""Tests for scripts/summarize_ablation.py layout and subset separation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import summarize_ablation as sa  # noqa: E402


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_run(base: Path, name: str, qids, values, frames=8, with_diagnostics=True,
             with_config=True, with_meta=False):
    metrics = {
        "eg_f1": {
            "metrics_by_threshold": {
                sa.EG_KEY: {"avg_f1": sum(values) / len(values)},
                "iou@0.3_sim@0.75": {"avg_f1": 0.01},
                "iou@0.5_sim@0.75": {"avg_f1": 0.005},
            },
            "per_sample_results": [
                {"question_id": qid, "thresholds": {sa.EG_KEY: {"f1": value}}}
                for qid, value in zip(qids, values)
            ],
        },
        "iou_f1": {"metrics_by_threshold": {k: {"avg_f1": 0.1} for k in ("0.1", "0.3", "0.5", "0.7")}},
    }
    diagnostics = {
        "config": {"max_frames": frames, "frame_selection": "uniform", "prompt_variant": "official"},
        "official_metrics": {
            "num_samples": len(qids),
            "eg_f1": {"iou@0.3_sim@0.5": sum(values) / len(values),
                      "iou@0.3_sim@0.75": 0.01, "iou@0.5_sim@0.75": 0.005},
            "iou_f1": {k: 0.1 for k in ("0.1", "0.3", "0.5", "0.7")},
        },
        "custom_diagnostics": {
            "start_abs_error_sec": {"mean": 1.0, "matched_pairs": 1},
            "end_abs_error_sec": {"mean": 2.0},
            "fraction_questions_all_predictions_within_first_30s": 0.5,
            "no_temporal_overlap_rate": 0.5,
            "mean_best_iou_per_prediction": 0.1,
            "invalid_rate": 0.0,
            "empty_evidence_rate": 0.0,
            "end_beyond_duration_rate": 0.0,
            "timing": {"mean_processing_sec": 1.0, "gpu_peak_gib": 3.0},
            "format_health": {"with_evidence": len(qids), "with_answer": len(qids)},
            "per_type_avg_eg_f1_iou@0.3_sim@0.5": {
                "causal": 0.1, "counterfactual": 0.1, "descriptive": 0.1, "temporal": 0.1,
            },
        },
    }
    write_json(base / "metrics" / f"{name}_evidence_metrics.json", metrics)
    if with_diagnostics:
        write_json(base / "diagnostics" / f"{name}.json", diagnostics)
    if with_config:
        write_json(base / "configs" / f"{name}.json",
                   {"max_frames": frames, "frame_selection": "uniform", "prompt_variant": "official"})
    if with_meta:
        write_json(base / "meta" / f"{name}.meta.json",
                   {"max_frames": frames, "frame_selection": "uniform", "prompt_variant": "official"})


def args_for(base: Path):
    return [
        "--metrics-dir", str(base / "metrics"),
        "--diagnostics-dir", str(base / "diagnostics"),
        "--configs-dir", str(base / "configs"),
        "--meta-dir", str(base / "meta"),
        "--output-dir", str(base / "out"),
    ]


def test_reads_repository_layout_and_separates_subsets(tmp_path):
    qids = ["q1", "q2", "q3", "q4"]
    make_run(tmp_path, "A2_uniform_8", qids, [0.1, 0.1, 0.1, 0.1], frames=8)
    make_run(tmp_path, "B_uniform_16", qids, [0.2, 0.2, 0.2, 0.2], frames=16, with_meta=True)
    make_run(tmp_path, "expanded_C32", [f"e{i}" for i in range(6)], [0.3] * 6, frames=32)

    assert sa.main(args_for(tmp_path)) == 0
    payload = json.loads((tmp_path / "out" / "ablation_summary.json").read_text(encoding="utf-8"))
    names = [row["config"] for row in payload["ablation_rows"]]
    assert names == ["A2_uniform_8", "B_uniform_16"]
    assert payload["expanded_rows"][0]["config"] == "expanded_C32"
    assert payload["expanded_rows"][0]["pair_status"] == "different_sample_set"
    assert payload["expanded_rows"][0]["mean_delta"] is None
    b_row = next(row for row in payload["ablation_rows"] if row["config"] == "B_uniform_16")
    assert b_row["paired_vs_reference_n"] == 4
    assert b_row["mean_delta"] == pytest.approx(0.1)
    assert (tmp_path / "out" / "expanded_summary.csv").is_file()
    assert (tmp_path / "out" / "ablation_summary.md").is_file()


def test_same_count_different_questions_is_not_paired(tmp_path):
    make_run(tmp_path, "A2_uniform_8", ["a1", "a2", "a3", "a4"], [0.1] * 4)
    make_run(tmp_path, "other", ["b1", "b2", "b3", "b4"], [0.9] * 4)
    assert sa.main(args_for(tmp_path)) == 0
    payload = json.loads((tmp_path / "out" / "ablation_summary.json").read_text(encoding="utf-8"))
    assert [row["config"] for row in payload["ablation_rows"]] == ["A2_uniform_8"]
    other = payload["expanded_rows"][0]
    assert other["pair_status"] == "different_sample_set"
    assert other["paired_vs_reference_n"] == 0
    assert other["mean_delta"] is None


def test_missing_diagnostics_is_warned_not_silent(tmp_path, capsys):
    qids = ["q1", "q2"]
    make_run(tmp_path, "A2_uniform_8", qids, [0.1, 0.1])
    make_run(tmp_path, "B_uniform_16", qids, [0.2, 0.2], with_diagnostics=False)
    assert sa.main(args_for(tmp_path)) == 0
    payload = json.loads((tmp_path / "out" / "ablation_summary.json").read_text(encoding="utf-8"))
    assert [row["config"] for row in payload["ablation_rows"]] == ["A2_uniform_8"]
    err = capsys.readouterr().err
    assert "diagnostics missing" in err


def test_empty_metrics_directory_returns_nonzero(tmp_path, capsys):
    (tmp_path / "metrics").mkdir()
    assert sa.main(args_for(tmp_path)) == 2
    assert "no valid runs" in capsys.readouterr().err


def test_all_runs_missing_diagnostics_returns_nonzero(tmp_path):
    make_run(tmp_path, "A2_uniform_8", ["q1"], [0.1], with_diagnostics=False)
    assert sa.main(args_for(tmp_path)) == 2


def test_missing_reference_returns_nonzero(tmp_path):
    make_run(tmp_path, "B_uniform_16", ["q1"], [0.1])
    assert sa.main(args_for(tmp_path)) == 2
