"""Shared pytest configuration.

The official EG-VQA code is not redistributed with this repository. Clone it into
./official_repo (see README) to run the tests that depend on it; those tests skip
cleanly when it is absent.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = REPO_ROOT / "official_repo"

for path in (OFFICIAL / "evaluation", OFFICIAL / "preprocess"):
    if path.is_dir() and str(path) not in sys.path:
        sys.path.insert(0, str(path))
