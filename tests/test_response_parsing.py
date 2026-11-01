"""Unit tests for the response parser in evaluation/evaluate.py."""

from __future__ import annotations

import pytest as _pytest
from pathlib import Path as _Path

if not (_Path(__file__).resolve().parents[1] / "official_repo/evaluation/evaluate.py").is_file():
    _pytest.skip(
        "official EG-VQA repository is not vendored; clone it to ./official_repo (see README)",
        allow_module_level=True,
    )

import evaluate


GOOD = """<evidence>
Time:00:10-00:15, Des: Person picks up a hammer.
</evidence>
<think>
He picks up a hammer.
</think>
<answer>
A hammer.
</answer>"""


def test_parse_full_response():
    parsed = evaluate.parse_model_response(GOOD)
    assert "00:10-00:15" in parsed["evidence"]
    assert parsed["think"].startswith("He picks")
    assert parsed["answer"] == "A hammer."


def test_parse_missing_closing_evidence_tag():
    text = "<evidence>\nTime:00:10-00:15, Des: x\n<think>t</think><answer>a</answer>"
    parsed = evaluate.parse_model_response(text)
    assert "00:10-00:15" in parsed["evidence"]
    assert parsed["answer"] == "a"


def test_parse_missing_closing_answer_tag():
    text = "<evidence>Time:00:01-00:02, Des: x</evidence><answer>final"
    parsed = evaluate.parse_model_response(text)
    assert parsed["answer"] == "final"


def test_parse_garbage_returns_none():
    parsed = evaluate.parse_model_response("no tags at all")
    assert parsed["evidence"] is None and parsed["think"] is None and parsed["answer"] is None


def test_parse_empty_response():
    parsed = evaluate.parse_model_response("")
    assert parsed == {"evidence": None, "think": None, "answer": None}


def test_frame_paths_natural_sort(tmp_path):
    video_dir = tmp_path / "vid1"
    video_dir.mkdir()
    for name in ["vid1_f10.png", "vid1_f2.png", "vid1_f1.png", "notes.txt"]:
        (video_dir / name).write_bytes(b"x")
    paths = evaluate.frame_paths_for_video(tmp_path, "vid1", max_frames=2)
    assert [p.name for p in paths] == ["vid1_f1.png", "vid1_f2.png"]


def test_frame_paths_missing_dir(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError):
        evaluate.frame_paths_for_video(tmp_path, "absent", max_frames=32)


def test_load_test_samples_flattens(tmp_path):
    import json

    payload = [
        {
            "video_id": "v",
            "duration": 10,
            "questions": [
                {"question_id": "v_q1", "question": "q?", "type": "descriptive", "answer": "a", "evidence": []}
            ],
        }
    ]
    path = tmp_path / "t.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    samples = evaluate.load_test_samples(path)
    assert len(samples) == 1 and samples[0]["question_id"] == "v_q1"
