"""Tests for the ablation frame-selection helper used by scripts/infer_qwen_vl.py."""

from __future__ import annotations

import pytest as _pytest
from pathlib import Path as _Path

if not (_Path(__file__).resolve().parents[1] / "official_repo/evaluation/evaluate.py").is_file():
    _pytest.skip(
        "official EG-VQA repository is not vendored; clone it to ./official_repo (see README)",
        allow_module_level=True,
    )

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "official_repo" / "evaluation"))

import infer_qwen_vl as iq


def make_frames(root: Path, video_id: str, count: int = 32) -> Path:
    directory = root / video_id
    directory.mkdir(parents=True)
    for index in range(count):
        (directory / f"{video_id}_f{index:02d}.png").write_bytes(b"x")
    return directory


def test_first_selection_takes_beginning(tmp_path):
    make_frames(tmp_path, "vid")
    paths = iq.select_frame_paths(tmp_path, "vid", 8, "first")
    assert [p.name for p in paths] == [f"vid_f{i:02d}.png" for i in range(8)]


def test_uniform_selection_spans_video(tmp_path):
    make_frames(tmp_path, "vid")
    paths = iq.select_frame_paths(tmp_path, "vid", 8, "uniform")
    assert len(paths) == 8
    assert paths[0].name == "vid_f00.png"
    assert paths[-1].name == "vid_f31.png"
    assert [p.name for p in paths] == [
        "vid_f00.png", "vid_f04.png", "vid_f09.png", "vid_f13.png",
        "vid_f18.png", "vid_f22.png", "vid_f27.png", "vid_f31.png",
    ]


def test_uniform_more_than_available_returns_all(tmp_path):
    make_frames(tmp_path, "vid", count=5)
    paths = iq.select_frame_paths(tmp_path, "vid", 32, "uniform")
    assert len(paths) == 5


def test_unknown_mode_raises(tmp_path):
    make_frames(tmp_path, "vid")
    with pytest.raises(ValueError):
        iq.select_frame_paths(tmp_path, "vid", 8, "middle")


def test_prompt_variants_differ(tmp_path):
    frame = tmp_path / "f.png"
    frame.write_bytes(b"x")
    official = iq.build_messages([frame], "what?", 100352, "official")[0]["content"][-1]["text"]
    timestamp = iq.build_messages([frame], "what?", 100352, "timestamp")[0]["content"][-1]["text"]
    assert timestamp.startswith(official)
    assert "ADDITIONAL TIMESTAMP REQUIREMENT" in timestamp
    assert "what?" in official
