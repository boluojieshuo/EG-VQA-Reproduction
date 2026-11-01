"""Unit tests for answer scoring helpers.

The judge itself is an external LLM API. These tests cover prompt construction,
score extraction, sample normalization and aggregation with no network calls.
"""

from __future__ import annotations

import pytest as _pytest
from pathlib import Path as _Path

if not (_Path(__file__).resolve().parents[1] / "official_repo/evaluation/answer_metrics.py").is_file():
    _pytest.skip(
        "official EG-VQA repository is not vendored; clone it to ./official_repo (see README)",
        allow_module_level=True,
    )

import answer_metrics as am


def test_extract_score_variants():
    assert am.extract_score("Answer: 1") == 1.0
    assert am.extract_score("Answer: 0.5") == 0.5
    assert am.extract_score("Answer: 0") == 0.0
    assert am.extract_score("answer: 1.0") == 1.0
    assert am.extract_score("The answer: 1") is None
    assert am.extract_score("no score here") is None


def test_extract_score_does_not_match_inline_text():
    # Only a line-start "Answer:" is a valid judge verdict.
    assert am.extract_score("I think Answer: 1 is right") is None


def test_prompt_contains_all_fields():
    prompt = am.create_evaluation_prompt(
        metadata="- segment one", question="Q?", golden_answer="G.", model_answer="M.", title="T"
    )
    for needle in ["T", "segment one", "Q?", "G.", "M.", "Answer: 0.5"]:
        assert needle in prompt


def test_prepare_samples_maps_schema():
    items = [
        {
            "video_id": "v1",
            "question_id": "v1_q01",
            "question": "why?",
            "type": "causal",
            "answer": "because",
            "metadata": {"title": "t", "segments": [{"description": "seg a"}, {"description": "seg b"}]},
            "parsed_response": {"answer": "BECAUSE", "evidence": "", "think": ""},
        }
    ]
    samples = am.prepare_samples(items)
    assert samples[0]["question_type"] == "causal"
    assert samples[0]["video_segments"] == ["seg a", "seg b"]
    assert samples[0]["model_answer"] == "BECAUSE"
    assert samples[0]["standard_answer"] == "because"


def test_prepare_samples_marks_source_error():
    samples = am.prepare_samples([{"video_id": "v", "question_id": "q", "error": "boom"}])
    assert samples[0]["source_error"] == "boom"


def test_summarize_relaxed_and_strict():
    results = [
        {"question_type": "temporal", "evaluation_score": 1.0, "strict_score": 1.0},
        {"question_type": "temporal", "evaluation_score": 0.5, "strict_score": 0.0},
        {"question_type": "causal", "evaluation_score": 0.0, "strict_score": 0.0, "error": "x"},
    ]
    summary = am.summarize(results)
    assert summary["overall_stats"]["relaxed_accuracy"] == 0.5
    assert summary["overall_stats"]["strict_accuracy"] == round(1 / 3, 4)
    assert summary["overall_stats"]["failed_samples"] == 1
    assert summary["type_stats"]["temporal"]["relaxed_accuracy"] == 0.75


def test_load_evaluation_items_accepts_wrapped_samples(tmp_path):
    path = tmp_path / "r.json"
    path.write_text('{"samples": [{"question_id": "q1"}]}', encoding="utf-8")
    assert am.load_evaluation_items(path) == [{"question_id": "q1"}]


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error

    def create(self, **kwargs):
        if self.error:
            raise RuntimeError(self.error)
        return _FakeResponse(self.content)


class _FakeClient:
    """MOCK judge client: tests control flow only, never used for real scores."""

    def __init__(self, content=None, error=None):
        self.chat = type("Chat", (), {"completions": _FakeCompletions(content, error)})()


def _sample():
    return {
        "video_id": "v",
        "question_id": "q",
        "data_source": "HiREST",
        "question": "why?",
        "question_type": "causal",
        "title": "t",
        "video_segments": ["s"],
        "standard_answer": "gold",
        "model_answer": "pred",
        "model_response_raw": "raw",
        "source_error": None,
    }


def test_evaluate_sample_mock_score_one(monkeypatch):
    # MOCK judge; validates wiring, not judge quality.
    monkeypatch.setattr(am, "get_client", lambda *a, **k: _FakeClient("Answer: 1"))
    result = am.evaluate_sample(_sample(), "key", None, "mock-model", 0)
    assert result["evaluation_score"] == 1.0 and result["strict_score"] == 1.0


def test_evaluate_sample_mock_partial(monkeypatch):
    monkeypatch.setattr(am, "get_client", lambda *a, **k: _FakeClient("Answer: 0.5"))
    result = am.evaluate_sample(_sample(), "key", None, "mock-model", 0)
    assert result["evaluation_score"] == 0.5 and result["strict_score"] == 0.0


def test_evaluate_sample_unparseable_reply(monkeypatch):
    monkeypatch.setattr(am, "get_client", lambda *a, **k: _FakeClient("I cannot decide"))
    result = am.evaluate_sample(_sample(), "key", None, "mock-model", 0)
    assert result["error"] == "could not parse judge score"
    assert result["evaluation_score"] == 0.0


def test_evaluate_sample_api_failure_kept_in_denominator(monkeypatch):
    monkeypatch.setattr(am, "get_client", lambda *a, **k: _FakeClient(error="timeout"))
    result = am.evaluate_sample(_sample(), "key", None, "mock-model", 0)
    assert "timeout" in result["error"]
    summary = am.summarize([result])
    assert summary["overall_stats"]["total_samples"] == 1
    assert summary["overall_stats"]["failed_samples"] == 1


def test_missing_model_answer_skips_api(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("judge must not be called")

    monkeypatch.setattr(am, "get_client", explode)
    sample = _sample()
    sample["model_answer"] = "  "
    result = am.evaluate_sample(sample, "key", None, "mock-model", 0)
    assert result["error"] == "missing model answer"
