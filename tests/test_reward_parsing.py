"""Tests for the training reward helpers that need no BGE-M3 weights.

Evidence scoring itself (HESEvaluator.evaluate_sample) needs the semantic model
and is covered only by the integration test when BGE-M3 is available.
"""

from __future__ import annotations

import pytest as _pytest
from pathlib import Path as _Path

if not (_Path(__file__).resolve().parents[1] / "official_repo/EG-Reasoner/examples/score_function/evidence_reward.py").is_file():
    _pytest.skip(
        "official EG-VQA repository is not vendored; clone it to ./official_repo (see README)",
        allow_module_level=True,
    )

import sys
from pathlib import Path

import pytest

SCORE_DIR = Path(__file__).resolve().parents[1] / "official_repo" / "EG-Reasoner" / "examples" / "score_function"
sys.path.insert(0, str(SCORE_DIR))

import eg_vqa_reward as reward  # noqa: E402
import evidence_reward as er  # noqa: E402


def test_format_reward_accepts_exact_order():
    text = "<evidence>Time:00:01-00:02, Des: x</evidence><think>t</think><answer>a</answer>"
    assert reward.format_reward(text) == 1.0


def test_format_reward_rejects_wrong_order():
    text = "<answer>a</answer><think>t</think><evidence>Time:00:01-00:02, Des: x</evidence>"
    assert reward.format_reward(text) == 0.0


def test_format_reward_rejects_missing_block():
    assert reward.format_reward("<evidence>x</evidence><answer>a</answer>") == 0.0


def test_normalize_generated_text():
    assert reward.normalize_generated_text("< answer >a< /answer >") == "<answer>a</answer>"


def test_parse_ground_truth_json_string():
    gt = er.parse_ground_truth(
        '{"question":"q?","answer":"a","evidence":[{"timestamp":[0,1],"description":"d"}],'
        '"metadata":{"title":"t","segments":[{"description":"s1"}]}}'
    )
    assert gt["answer"] == "a"
    assert gt["question"] == "q?"
    assert gt["title"] == "t"
    assert gt["video_segments"] == ["s1"]
    assert len(gt["evidence"]) == 1


def test_parse_ground_truth_plain_string():
    gt = er.parse_ground_truth("just an answer")
    assert gt["answer"] == "just an answer" and gt["evidence"] == []


def test_parse_model_response_repairs_missing_closers():
    text = "<evidence>\nTime:00:01-00:02, Des: x\n<think>t<answer>a"
    parsed, repaired = er.parse_model_response(text)
    assert "00:01-00:02" in parsed["evidence"]
    assert parsed["think"] == "t"
    assert parsed["answer"] == "a"
    assert "</evidence>" in repaired and "</think>" in repaired and "</answer>" in repaired


def test_evidence_string_parsing_valid_and_invalid():
    evaluator = er.HESEvaluator(iou_threshold=0.3, sim_threshold=0.5)
    parsed = evaluator.parse_evidence_from_json(
        "Time:00:10-00:20, Des: a\nTime:00:30-00:20, Des: b\nTime:bad, Des: c"
    )
    assert parsed[0].is_valid and (parsed[0].start, parsed[0].end) == (10.0, 20.0)
    assert not parsed[1].is_valid  # start >= end
    assert not parsed[2].is_valid


def test_time_to_seconds():
    evaluator = er.HESEvaluator()
    assert evaluator.time_to_seconds("01:05") == (65.0, True)
    assert evaluator.time_to_seconds("1:02:03") == (3723.0, True)
    assert evaluator.time_to_seconds("01:05.5") == (65.5, True)
    assert evaluator.time_to_seconds("61:00")[1] is False
    assert evaluator.time_to_seconds("")[1] is False


def test_dataset_evidence_list_parsing():
    evaluator = er.HESEvaluator()
    parsed = evaluator.parse_evidence_from_json(
        [{"timestamp": [0, 5], "description": "x"}, {"description": "missing ts"}]
    )
    assert len(parsed) == 1 and parsed[0].is_valid


def test_iou_helpers_agree_with_evaluation_metric():
    evaluator = er.HESEvaluator()
    a = er.Evidence(0, 10, "x")
    b = er.Evidence(5, 15, "y")
    assert evaluator.compute_iou(a, b) == pytest.approx(5 / 15)

    import evidence_metrics as em

    assert em.compute_iou(em.Evidence(0, 10, "x"), em.Evidence(5, 15, "y")) == pytest.approx(5 / 15)
