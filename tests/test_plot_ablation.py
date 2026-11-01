"""Tests for scripts/plot_ablation.py --output handling."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import plot_ablation  # noqa: E402


def row(name, frames, eg, eg75, iou, overlap, complete):
    return {
        "config": name,
        "frames": frames,
        "frame_selection": "uniform",
        "prompt_variant": "official",
        "eg_f1_0.3_0.5": eg,
        "eg_f1_0.3_0.75": eg75,
        "iou_f1_0.1": iou,
        "no_overlap_rate": overlap,
        "with_answer": complete,
    }


def test_output_path_is_used_and_parent_created(tmp_path, monkeypatch):
    summary = {
        "reference": "A2_uniform_8",
        "ablation_rows": [
            row("A2_uniform_8", 8, 0.02, 0.01, 0.05, 0.75, 85),
            row("B_uniform_16", 16, 0.04, 0.02, 0.11, 0.69, 72),
            row("C_uniform_32", 32, 0.06, 0.02, 0.15, 0.53, 45),
        ],
        "expanded_rows": [],
        "warnings": [],
    }
    input_path = tmp_path / "summary.json"
    input_path.write_text(json.dumps(summary), encoding="utf-8")
    output = tmp_path / "nested" / "figure.png"

    monkeypatch.setattr(sys, "argv", ["plot_ablation.py", "--input", str(input_path), "--output", str(output)])
    assert plot_ablation.main() == 0
    assert output.is_file() and output.stat().st_size > 0


def test_legacy_rows_key_still_accepted(tmp_path, monkeypatch):
    summary = {"rows": [
        row("A2_uniform_8", 8, 0.02, 0.01, 0.05, 0.75, 85),
        row("B_uniform_16", 16, 0.04, 0.02, 0.11, 0.69, 72),
        row("C_uniform_32", 32, 0.06, 0.02, 0.15, 0.53, 45),
    ]}
    input_path = tmp_path / "summary.json"
    input_path.write_text(json.dumps(summary), encoding="utf-8")
    output = tmp_path / "figure.png"
    monkeypatch.setattr(sys, "argv", ["plot_ablation.py", "--input", str(input_path), "--output", str(output)])
    assert plot_ablation.main() == 0
    assert output.is_file()


def test_empty_summary_fails(tmp_path, monkeypatch):
    input_path = tmp_path / "summary.json"
    input_path.write_text(json.dumps({"ablation_rows": []}), encoding="utf-8")
    output = tmp_path / "figure.png"
    monkeypatch.setattr(sys, "argv", ["plot_ablation.py", "--input", str(input_path), "--output", str(output)])
    with pytest.raises(SystemExit):
        plot_ablation.main()
    assert not output.exists()
