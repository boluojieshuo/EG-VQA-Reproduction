"""Regression tests on the shipped annotations.

These assert the published dataset scale and the known annotation defects so a
future data swap is noticed instead of silently changing results.
"""

from __future__ import annotations

import pytest as _pytest
from pathlib import Path as _Path

if not (_Path(__file__).resolve().parents[1] / "official_repo/data/test.json").is_file():
    _pytest.skip(
        "official EG-VQA repository is not vendored; clone it to ./official_repo (see README)",
        allow_module_level=True,
    )

import collections
import json
from pathlib import Path

import pytest

DATA = Path(__file__).resolve().parents[1] / "official_repo" / "data"


def load(split: str):
    return json.loads((DATA / f"{split}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def train():
    return load("train")


@pytest.fixture(scope="module")
def test():
    return load("test")


def test_published_scale(train, test):
    assert len(train) == 1731 and len(test) == 336
    assert sum(len(v["questions"]) for v in train) == 8949
    assert sum(len(v["questions"]) for v in test) == 2889
    assert len(train) + len(test) == 2067
    assert sum(len(v["questions"]) for v in train) + sum(len(v["questions"]) for v in test) == 11838


def test_no_train_test_video_overlap(train, test):
    assert not ({v["video_id"] for v in train} & {v["video_id"] for v in test})


def test_question_types(train, test):
    expected = {"descriptive", "temporal", "causal", "counterfactual"}
    for split in (train, test):
        types = collections.Counter(q["type"] for v in split for q in v["questions"])
        assert set(types) == expected
        assert sum(types.values()) == sum(len(v["questions"]) for v in split)


def test_required_fields(train):
    for video in train:
        for key in ("video_id", "video_path", "duration", "data_source", "questions"):
            assert key in video
        for question in video["questions"]:
            for key in ("question_id", "question", "type", "answer", "evidence"):
                assert key in question
            assert question["answer"].strip()
            assert question["evidence"]


def test_known_zero_length_spans(train, test):
    def zero_length(split):
        return [
            (v["video_id"], q["question_id"])
            for v in split
            for q in v["questions"]
            for span in q["evidence"]
            if span["timestamp"][0] >= span["timestamp"][1]
        ]

    assert len(zero_length(train)) == 12
    assert len(zero_length(test)) == 2
    assert {qid for _, qid in zero_length(test)} == {"9pybtCnEqEQ_q01", "9pybtCnEqEQ_q09"}


def test_evidence_inside_duration_except_known_defects(train, test):
    violations = [
        (v["video_id"], q["question_id"], span["timestamp"], v["duration"])
        for split in (train, test)
        for v in split
        for q in v["questions"]
        for span in q["evidence"]
        if span["timestamp"][0] < span["timestamp"][1] and span["timestamp"][1] > v["duration"] + 1e-6
    ]
    assert len(violations) == 7


def test_duplicate_question_texts_are_cross_video(train, test):
    for split in (train, test):
        by_text = collections.defaultdict(set)
        for video in split:
            for question in video["questions"]:
                by_text[question["question"].strip().lower()].add(video["video_id"])
        for text, videos in by_text.items():
            if len(videos) > 1:
                assert len(videos) > 1
        # A duplicated text must never repeat inside a single video.
        counts = collections.Counter(
            (v["video_id"], q["question"].strip().lower()) for v in split for q in v["questions"]
        )
        assert max(counts.values()) == 1
