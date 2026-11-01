"""Integration test for the real BGE-M3 semantic encoder.

Skipped (not failed) when sentence-transformers or the model weights are absent.
"""

from __future__ import annotations

import pytest as _pytest
from pathlib import Path as _Path

if not (_Path(__file__).resolve().parents[1] / "official_repo/evaluation/evidence_metrics.py").is_file():
    _pytest.skip(
        "official EG-VQA repository is not vendored; clone it to ./official_repo (see README)",
        allow_module_level=True,
    )

from pathlib import Path

import pytest

import evidence_metrics as em

MODEL_DIR = Path(__file__).resolve().parents[1] / "official_repo" / "EG-Reasoner" / "Science_Bert"
MODEL_READY = (MODEL_DIR / "modules.json").is_file() and (MODEL_DIR / "pytorch_model.bin").is_file()


pytestmark = pytest.mark.skipif(
    not MODEL_READY, reason="BGE-M3 weights not present under EG-Reasoner/Science_Bert"
)


def test_real_encoder_identical_texts():
    pytest.importorskip("sentence_transformers")
    encoder = em.SemanticEncoder(MODEL_DIR, "cpu")
    cache = encoder.encode_texts(["heat oil in a pan", "heat oil in a pan", "chop onions"])
    assert cache["heat oil in a pan"].shape == (1024,)
    sim_same = float(cache["heat oil in a pan"] @ cache["heat oil in a pan"])
    sim_diff = float(cache["heat oil in a pan"] @ cache["chop onions"])
    assert sim_same == pytest.approx(1.0, abs=1e-5)
    assert sim_diff < sim_same
    assert 0.0 <= sim_diff <= 1.0


def test_real_encoder_similarity_matrix():
    pytest.importorskip("sentence_transformers")
    encoder = em.SemanticEncoder(MODEL_DIR, "cpu")
    gts = [em.Evidence(0, 5, "heat little oil in a skillet")]
    preds = [em.Evidence(0, 5, "warm some oil in the pan"), em.Evidence(0, 5, "")]
    cache = encoder.encode_texts([g.description for g in gts] + [p.description for p in preds if p.description])
    matrix = encoder.similarity_matrix(gts, preds, cache)
    assert matrix.shape == (1, 2)
    assert 0.0 < matrix[0, 0] <= 1.0
    assert matrix[0, 1] == 0.0
