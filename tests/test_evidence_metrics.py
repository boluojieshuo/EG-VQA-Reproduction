"""Unit tests for official evidence metrics (evaluation/evidence_metrics.py).

Pure-function tests need no model weights. The EG-F1 tests use a deterministic
stand-in encoder so the matching logic can be exercised offline; they are NOT
real BGE-M3 measurements and must not be reported as such.
"""

from __future__ import annotations

import pytest as _pytest
from pathlib import Path as _Path

if not (_Path(__file__).resolve().parents[1] / "official_repo/evaluation/evidence_metrics.py").is_file():
    _pytest.skip(
        "official EG-VQA repository is not vendored; clone it to ./official_repo (see README)",
        allow_module_level=True,
    )

import numpy as np
import pytest

import evidence_metrics as em


def gt(start, end, desc="d"):
    return em.Evidence(start, end, desc)


def test_parse_number_variants():
    assert em.parse_number(12) == 12.0
    assert em.parse_number("12.5") == 12.5
    assert em.parse_number("01:05") == 65.0
    assert em.parse_number("1:02:03") == 3723.0
    assert em.parse_number("01:60") is None
    assert em.parse_number("abc") is None
    assert em.parse_number(None) is None


def test_parse_evidence_list_marks_invalid():
    parsed = em.parse_evidence(
        [
            {"timestamp": [10, 20], "description": "ok"},
            {"timestamp": [20, 20], "description": "zero length"},
            {"timestamps": [30, 25], "description": "reversed"},
            {"timestamp": "bad", "description": "bad ts"},
            {"timestamp": [1, 2]},
        ]
    )
    assert [p.is_valid for p in parsed] == [True, False, False, False, True]


def test_parse_evidence_string_format():
    text = "Time:00:10-00:20, Des: stir the soup\nTime:00:30-00:40, Des: add salt"
    parsed = em.parse_evidence(text)
    assert [(p.start, p.end) for p in parsed] == [(10.0, 20.0), (30.0, 40.0)]
    assert parsed[0].description == "stir the soup"


def test_empty_prediction():
    assert em.parse_evidence("") == []
    assert em.parse_evidence(None) == []


def test_invalid_span_in_string():
    parsed = em.parse_evidence("Time:00:30-00:20, Des: backwards")
    assert len(parsed) == 1 and not parsed[0].is_valid


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ((0, 10), (0, 10), 1.0),
        ((0, 10), (20, 30), 0.0),
        ((0, 10), (5, 15), 5 / 15),
        ((0, 10), (10, 20), 0.0),
        ((0, 10), (5, 6), 1 / 10),
    ],
)
def test_compute_iou(a, b, expected):
    assert em.compute_iou(gt(*a), gt(*b)) == pytest.approx(expected)


def _item(gt_spans, pred_text, qid="q1"):
    return {
        "video_id": "v1",
        "question_id": qid,
        "question": "q?",
        "answer": "a",
        "evidence": [{"timestamp": list(s), "description": d} for s, d in gt_spans],
        "parsed_response": {"evidence": pred_text},
    }


def test_iou_perfect_match():
    items = [_item([((0, 10), "heat oil")], "Time:00:00-00:10, Des: heat oil")]
    result = em.evaluate_iou(items, [0.5])
    metrics = result["metrics_by_threshold"]["0.5"]
    assert metrics["avg_f1"] == 1.0
    assert metrics["avg_precision"] == 1.0 and metrics["avg_recall"] == 1.0


def test_iou_disjoint_predictions():
    items = [_item([((0, 10), "heat oil")], "Time:01:00-01:10, Des: heat oil")]
    metrics = em.evaluate_iou(items, [0.5])["metrics_by_threshold"]["0.5"]
    assert metrics["avg_f1"] == 0.0


def test_iou_partial_overlap_and_threshold():
    items = [_item([((0, 10), "heat oil")], "Time:00:05-00:15, Des: heat oil")]
    result = em.evaluate_iou(items, [0.1, 0.5])
    assert result["metrics_by_threshold"]["0.1"]["avg_f1"] == 1.0
    assert result["metrics_by_threshold"]["0.5"]["avg_f1"] == 0.0


def test_empty_prediction_counts_as_zero_recall():
    items = [_item([((0, 10), "heat oil")], "")]
    metrics = em.evaluate_iou(items, [0.1])["metrics_by_threshold"]["0.1"]
    assert metrics["avg_recall"] == 0.0 and metrics["avg_f1"] == 0.0


def test_many_to_many_matching():
    gt_spans = [((0, 10), "a"), ((20, 30), "b")]
    pred = (
        "Time:00:20-00:30, Des: b\n"
        "Time:00:00-00:10, Des: a"
    )
    items = [_item(gt_spans, pred)]
    metrics = em.evaluate_iou(items, [0.5])["metrics_by_threshold"]["0.5"]
    assert metrics["total_valid_matches"] == 2
    assert metrics["avg_f1"] == 1.0


def test_hungarian_prefers_best_overlap():
    """One GT, two predictions: the better-overlapping one must be matched."""
    items = [_item([((0, 10), "a")], "Time:00:00-00:04, Des: a\nTime:00:00-00:10, Des: a")]
    metrics = em.evaluate_iou(items, [0.3])["metrics_by_threshold"]["0.3"]
    assert metrics["total_valid_matches"] == 1
    assert metrics["avg_precision"] == 0.5  # one of two predictions matched


class FakeEncoder:
    """Deterministic encoder: similarity is 1.0 for identical text, else 0.0."""

    def __init__(self):
        self.calls = 0

    def encode_texts(self, texts):
        self.calls += 1
        return {text: np.array([1.0, 0.0], dtype=np.float32) for text in texts if text}

    def similarity_matrix(self, gts, preds, cache):
        matrix = np.zeros((len(gts), len(preds)), dtype=np.float32)
        for i, g in enumerate(gts):
            for j, p in enumerate(preds):
                if p.is_valid and g.description and g.description == p.description:
                    matrix[i, j] = 1.0
        return matrix


def test_eg_f1_time_correct_text_wrong():
    items = [_item([((0, 10), "heat oil")], "Time:00:00-00:10, Des: chop onions")]
    result = em.evaluate_eg(items, [(0.3, 0.5)], FakeEncoder())
    assert result["metrics_by_threshold"]["iou@0.3_sim@0.5"]["avg_f1"] == 0.0


def test_eg_f1_text_correct_time_wrong():
    items = [_item([((0, 10), "heat oil")], "Time:01:00-01:10, Des: heat oil")]
    result = em.evaluate_eg(items, [(0.3, 0.5)], FakeEncoder())
    assert result["metrics_by_threshold"]["iou@0.3_sim@0.5"]["avg_f1"] == 0.0


def test_eg_f1_both_correct():
    items = [_item([((0, 10), "heat oil")], "Time:00:00-00:10, Des: heat oil")]
    result = em.evaluate_eg(items, [(0.3, 0.5), (0.3, 0.75), (0.5, 0.75)], FakeEncoder())
    for key, metrics in result["metrics_by_threshold"].items():
        assert metrics["avg_f1"] == 1.0, key


def test_eg_f1_multiple_pairs():
    gt_spans = [((0, 10), "a"), ((20, 30), "b")]
    pred = "Time:00:20-00:30, Des: b\nTime:00:00-00:10, Des: a"
    items = [_item(gt_spans, pred)]
    metrics = em.evaluate_eg(items, [(0.3, 0.5)], FakeEncoder())["metrics_by_threshold"]["iou@0.3_sim@0.5"]
    assert metrics["total_valid_matches"] == 2 and metrics["avg_f1"] == 1.0


def test_eg_f1_empty_gt_and_pred():
    items = [_item([], "")]
    metrics = em.evaluate_eg(items, [(0.3, 0.5)], FakeEncoder())["metrics_by_threshold"]["iou@0.3_sim@0.5"]
    assert metrics["avg_f1"] == 1.0


def test_ground_truth_takes_priority_over_similarity():
    """GT evidence list wins; parsed_response is model output."""
    item = _item([((0, 10), "gt text")], "Time:00:00-00:10, Des: gt text")
    assert em.ground_truth_evidence(item)[0].description == "gt text"
    assert em.predicted_evidence(item)[0].description == "gt text"


def test_aggregate_weighting():
    per_sample = [
        {"f1": 1.0, "precision": 1.0, "recall": 1.0, "valid_matches": 1, "n_gt": 1, "n_pred": 1, "n_pred_invalid": 0},
        {"f1": 0.0, "precision": 0.0, "recall": 0.0, "valid_matches": 0, "n_gt": 3, "n_pred": 2, "n_pred_invalid": 0},
    ]
    agg = em.aggregate(per_sample)
    assert agg["avg_f1"] == 0.5
    assert agg["weighted_precision"] == pytest.approx(1 / 3)
    assert agg["weighted_recall"] == pytest.approx(1 / 4)


def test_model_evidence_string_path():
    """evaluate.py stores model evidence as a string; metrics must parse it."""
    items = [_item([((0, 10), "heat oil")], "Time:00:00-00:10, Des: heat oil")]
    metrics = em.evaluate_eg(items, [(0.3, 0.5)], FakeEncoder())["metrics_by_threshold"]["iou@0.3_sim@0.5"]
    assert metrics["total_predictions"] == 1
    assert metrics["total_invalid_predictions"] == 0
    assert metrics["avg_f1"] == 1.0


def test_malformed_model_evidence_counts_against_precision():
    items = [_item([((0, 10), "heat oil")], "Time:bad, Des: heat oil")]
    metrics = em.evaluate_eg(items, [(0.3, 0.5)], FakeEncoder())["metrics_by_threshold"]["iou@0.3_sim@0.5"]
    assert metrics["total_predictions"] == 1
    assert metrics["total_invalid_predictions"] == 1
    assert metrics["avg_f1"] == 0.0
