"""Tests for scripts/build_inference_annotations.py (no official repo needed)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_inference_annotations as bia  # noqa: E402


def annotations():
    return [
        {
            "video_id": "v1",
            "video_path": "videos/v1.mp4",
            "duration": 120,
            "data_source": "TestSource",
            "metadata": {"title": "t1", "segments": []},
            "questions": [
                {"question_id": "q1", "question": "Q1?", "type": "descriptive", "answer": "A1", "evidence": [{"timestamp": [0, 1], "description": "d1"}]},
                {"question_id": "q2", "question": "Q2?", "type": "temporal", "answer": "A2", "evidence": []},
            ],
        },
        {
            "video_id": "v2",
            "video_path": "videos/v2.mp4",
            "duration": 60,
            "data_source": "TestSource",
            "metadata": {"title": "t2", "segments": []},
            "questions": [
                {"question_id": "q3", "question": "Q3?", "type": "causal", "answer": "A3", "evidence": []},
            ],
        },
    ]


def write(tmp_path, name, payload):
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_builds_filtered_annotations(tmp_path):
    ann = write(tmp_path, "test.json", annotations())
    ids = write(tmp_path, "ids.json", {"question_ids": ["q1", "q3"]})
    payload, stats = bia.build_subset(ann, ids)

    assert stats["requested_questions"] == 2
    assert stats["selected_questions"] == 2
    assert stats["selected_videos"] == 2
    assert stats["questions_by_type"] == {"causal": 1, "descriptive": 1}
    assert [v["video_id"] for v in payload] == ["v1", "v2"]
    assert [q["question_id"] for q in payload[0]["questions"]] == ["q1"]
    # full video and question fields are preserved
    assert payload[0]["video_path"] == "videos/v1.mp4"
    assert payload[0]["metadata"]["title"] == "t1"
    assert payload[0]["questions"][0]["answer"] == "A1"
    assert payload[0]["questions"][0]["evidence"][0]["description"] == "d1"


def test_accepts_questions_format_with_video_ids(tmp_path):
    ann = write(tmp_path, "test.json", annotations())
    ids = write(tmp_path, "ids.json", {"questions": [
        {"question_id": "q2", "video_id": "v1"},
        {"question_id": "q3", "video_id": "v2"},
    ]})
    payload, stats = bia.build_subset(ann, ids)
    assert stats["selected_videos"] == 2
    assert [q["question_id"] for q in payload[0]["questions"]] == ["q2"]


def test_missing_question_id_raises(tmp_path):
    ann = write(tmp_path, "test.json", annotations())
    ids = write(tmp_path, "ids.json", {"question_ids": ["q1", "missing"]})
    with pytest.raises(ValueError, match="not found"):
        bia.build_subset(ann, ids)


def test_duplicate_requested_id_raises(tmp_path):
    ann = write(tmp_path, "test.json", annotations())
    ids = write(tmp_path, "ids.json", {"question_ids": ["q1", "q1"]})
    with pytest.raises(ValueError, match="duplicate question ids in"):
        bia.build_subset(ann, ids)


def test_duplicate_annotation_id_raises(tmp_path):
    payload = annotations()
    payload[1]["questions"].append(dict(payload[0]["questions"][0]))
    ann = write(tmp_path, "test.json", payload)
    ids = write(tmp_path, "ids.json", {"question_ids": ["q1"]})
    with pytest.raises(ValueError, match="duplicate question ids in official annotations"):
        bia.build_subset(ann, ids)


def test_video_id_mismatch_raises(tmp_path):
    ann = write(tmp_path, "test.json", annotations())
    ids = write(tmp_path, "ids.json", {"questions": [{"question_id": "q1", "video_id": "v2"}]})
    with pytest.raises(ValueError, match="video_id mismatch"):
        bia.build_subset(ann, ids)


def test_cli_missing_id_returns_nonzero_and_writes_nothing(tmp_path, monkeypatch, capsys):
    ann = write(tmp_path, "test.json", annotations())
    ids = write(tmp_path, "ids.json", {"question_ids": ["q1", "missing"]})
    out = tmp_path / "out.json"
    monkeypatch.setattr(sys, "argv", [
        "build_inference_annotations.py", "--annotations", str(ann),
        "--question-ids", str(ids), "--output", str(out),
    ])
    assert bia.main() == 2
    assert not out.exists()
    assert "not found" in capsys.readouterr().err


def test_missing_question_field_raises(tmp_path):
    payload = annotations()
    del payload[0]["questions"][0]["answer"]
    ann = write(tmp_path, "test.json", payload)
    ids = write(tmp_path, "ids.json", {"question_ids": ["q1"]})
    with pytest.raises(ValueError, match="incomplete selected records"):
        bia.build_subset(ann, ids)


def test_invalid_evidence_structure_raises(tmp_path):
    payload = annotations()
    payload[0]["questions"][0]["evidence"] = "not-a-list"
    ann = write(tmp_path, "test.json", payload)
    ids = write(tmp_path, "ids.json", {"question_ids": ["q1"]})
    with pytest.raises(ValueError, match="evidence is not a list"):
        bia.build_subset(ann, ids)
