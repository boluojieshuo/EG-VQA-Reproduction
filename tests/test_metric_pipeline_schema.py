"""Schema test: output shaped like evaluate.py results feeds both metric modules.

Uses a synthetic response; this checks plumbing, not model quality.
"""

from __future__ import annotations

import pytest as _pytest
from pathlib import Path as _Path

if not (_Path(__file__).resolve().parents[1] / "official_repo/evaluation/evaluate.py").is_file():
    _pytest.skip(
        "official EG-VQA repository is not vendored; clone it to ./official_repo (see README)",
        allow_module_level=True,
    )

import json

import answer_metrics as am
import evidence_metrics as em
import evaluate


SAMPLE = {
    "video_id": "v1",
    "question_id": "v1_q01",
    "video_path": "videos/v1.mp4",
    "duration": 120.0,
    "data_source": "HiREST",
    "metadata": {"title": "t", "segments": [{"description": "cut the sheet"}]},
    "question": "What is cut?",
    "type": "descriptive",
    "answer": "The sheet is cut.",
    "evidence": [{"timestamp": [10.0, 20.0], "description": "cut the sheet"}],
}


def test_result_feeds_evidence_metrics(tmp_path):
    raw = "<evidence>\nTime:00:10-00:20, Des: cut the sheet\n</evidence>\n<think>t</think>\n<answer>The sheet.</answer>"
    result = evaluate.build_result(SAMPLE, model_response_raw=raw, parsed_response=evaluate.parse_model_response(raw))
    path = tmp_path / "run.json"
    path.write_text(json.dumps([result]), encoding="utf-8")

    items = em.load_items(path)
    assert len(items) == 1
    preds = em.predicted_evidence(items[0])
    assert len(preds) == 1 and preds[0].is_valid
    assert em.compute_iou(em.ground_truth_evidence(items[0])[0], preds[0]) == 1.0


def test_result_feeds_answer_metrics(tmp_path):
    raw = "<evidence>\nTime:00:10-00:20, Des: cut the sheet\n</evidence><answer>The sheet.</answer>"
    result = evaluate.build_result(SAMPLE, model_response_raw=raw, parsed_response=evaluate.parse_model_response(raw))
    path = tmp_path / "run.json"
    path.write_text(json.dumps([result]), encoding="utf-8")

    samples = am.prepare_samples(am.load_evaluation_items(path))
    assert samples[0]["model_answer"] == "The sheet."
    assert samples[0]["standard_answer"] == "The sheet is cut."
    assert samples[0]["video_segments"] == ["cut the sheet"]
    assert samples[0]["title"] == "t"


def test_failed_sample_remains_in_denominator(tmp_path):
    result = evaluate.build_result(SAMPLE, error="inference failed: boom")
    path = tmp_path / "run.json"
    path.write_text(json.dumps([result]), encoding="utf-8")

    samples = am.prepare_samples(am.load_evaluation_items(path))
    assert samples[0]["source_error"] == "inference failed: boom"
    summary = am.summarize(
        [{"question_type": "descriptive", "evaluation_score": 0.0, "strict_score": 0.0, "error": "x"}]
    )
    assert summary["overall_stats"]["total_samples"] == 1
