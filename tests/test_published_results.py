"""Published subsets and summary statistics used in the README.

These tests are self-contained: they only read files shipped in results/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def load(relative: str):
    return json.loads((RESULTS / relative).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fixed_ids():
    return load("subsets/fixed92_question_ids.json")


@pytest.fixture(scope="module")
def expanded():
    return load("subsets/expanded_questions.json")


def test_fixed_set_has_92_unique_questions(fixed_ids):
    ids = fixed_ids["question_ids"]
    assert fixed_ids["count"] == len(ids) == 92
    assert len(set(ids)) == 92

    detailed = load("subsets/fixed92_questions.json")
    assert detailed["count"] == 92
    assert detailed["num_videos"] == 10
    assert {q["question_id"] for q in detailed["questions"]} == set(ids)
    assert len({q["video_id"] for q in detailed["questions"]}) == 10


def test_expanded_set_is_stratified(expanded):
    assert expanded["selected_total"] == 300
    assert expanded["selected_by_type"] == {
        "causal": 75,
        "counterfactual": 75,
        "descriptive": 75,
        "temporal": 75,
    }
    assert expanded["seed"] == 20261030
    assert len(expanded["questions"]) == 300
    assert len({q["question_id"] for q in expanded["questions"]}) == 300
    assert len({q["video_id"] for q in expanded["questions"]}) == expanded["num_videos"]


def test_ablation_headline_numbers():
    payload = load("summaries/ablation_summary.json")
    rows = {row["config"]: row for row in payload["ablation_rows"]}
    assert len(payload["ablation_rows"]) == 5
    assert [row["config"] for row in payload["expanded_rows"]] == ["expanded_C32"]
    assert all(row["config"] != "expanded_C32" for row in payload["ablation_rows"])
    for row in payload["ablation_rows"]:
        assert row["num_questions"] == 92
        assert row["paired_vs_reference_n"] == 92
    assert rows["A2_uniform_8"]["eg_f1_0.3_0.5"] == pytest.approx(0.0234, abs=5e-5)
    assert rows["B_uniform_16"]["eg_f1_0.3_0.5"] == pytest.approx(0.0479, abs=5e-5)
    assert rows["C_uniform_32"]["eg_f1_0.3_0.5"] == pytest.approx(0.0686, abs=5e-5)
    assert rows["C_uniform_32"]["no_overlap_rate"] == pytest.approx(0.5363, abs=5e-5)


def test_expanded_results_are_separate():
    expanded = load("summaries/expanded_summary.json")
    assert expanded["rows"][0]["config"] == "expanded_C32"
    assert expanded["rows"][0]["num_questions"] == 300
    assert "mean_delta" not in expanded["rows"][0] or expanded["rows"][0].get("mean_delta") is None
    ablation_payload = load("summaries/ablation_summary.json")
    assert all(row["config"] != "expanded_C32" for row in ablation_payload["ablation_rows"])


def test_token_subgroup_statistics():
    stats = load("summaries/truncation_analysis.json")["runs"]["C_uniform_32"]["token_stats_by_truncation_point"]
    assert stats["complete"] == {"count": 35, "mean_tokens": 134.2, "median_tokens": 138}
    assert stats["cut_in_think"]["count"] == 41
    assert stats["cut_in_think"]["mean_tokens"] == pytest.approx(45.9, abs=0.05)
    assert stats["cut_in_think"]["median_tokens"] == 33


def test_expanded_headline_numbers():
    metrics = load("metrics/expanded_C32_evidence_metrics.json")
    ci = load("summaries/expanded_bootstrap_ci.json")
    assert metrics["eg_f1"]["metrics_by_threshold"]["iou@0.3_sim@0.5"]["avg_f1"] == pytest.approx(0.0510, abs=5e-5)
    assert ci["mean"] == pytest.approx(0.0510, abs=5e-5)
    assert ci["ci95"] == [pytest.approx(0.0358, abs=5e-5), pytest.approx(0.0680, abs=5e-5)]


def test_token_limit_comparison():
    comparison = load("summaries/token_limit_comparison.json")
    assert comparison["completeness_low"]["closing_tags_complete"] == 35
    assert comparison["completeness_high"]["closing_tags_complete"] == 36
    assert comparison["completeness_low"]["parsed_answer_present"] == 45
    assert comparison["paired_eg_f1_delta"] == {
        "mean": -0.0016,
        "improved": 0,
        "worsened": 1,
        "unchanged": 91,
        "wilcoxon_p": None,
    }


def test_oracle_summary():
    oracle = load("summaries/oracle_summary.json")
    for value in oracle["eg_f1"].values():
        assert value == pytest.approx(0.9996539, abs=1e-6)
    assert oracle["num_questions"] == 2889
