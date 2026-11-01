"""Run the official frame extractor without modifying the official repository.

The official `preprocess/video_clip.py` hard-codes a Linux font path. Instead of
editing that file, this wrapper imports it and sets the module-level font path to
an available font. Sampling, resizing, naming and timestamp drawing all remain
the official implementation.

Usage is identical to the official script's arguments.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_PREPROCESS = REPO_ROOT / "official_repo" / "preprocess"
sys.path.insert(0, str(OFFICIAL_PREPROCESS))

import video_clip  # noqa: E402


def resolve_font() -> str:
    candidates = [os.environ.get("EG_VQA_FONT", ""), "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    windows_dir = os.environ.get("WINDIR")
    if windows_dir:
        candidates.extend(str(Path(windows_dir) / "Fonts" / name) for name in
                          ("arial.ttf", "seguisb.ttf", "DejaVuSans.ttf"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise FileNotFoundError(
        "No usable timestamp font found. Set EG_VQA_FONT to a .ttf path."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract EG-VQA frames via the official implementation.")
    parser.add_argument("--dataset", type=Path, default=REPO_ROOT / "official_repo" / "data" / "train.json")
    parser.add_argument("--video-root", type=Path, default=REPO_ROOT / "official_repo" / "data")
    parser.add_argument("--output-root", type=Path, default=REPO_ROOT / "official_repo" / "data" / "frames" / "train")
    parser.add_argument("--num-frames", type=int, default=32)
    args = parser.parse_args()

    font_path = resolve_font()
    video_clip.TIMESTAMP_FONT_PATH = font_path
    print(f"[wrapper] timestamp font: {font_path}")
    video_clip.batch_extract_from_dataset(
        dataset_path=args.dataset,
        video_root=args.video_root,
        output_root=args.output_root,
        num_frames=args.num_frames,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
