"""Verify extracted frames: count, naming, decodability, timestamp overlay, bounds.

For each video this re-renders one frame without the overlay and compares the
top-right region, proving the timestamp was actually drawn.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "official_repo" / "preprocess"))
import video_clip as vc  # noqa: E402


def natural(path: Path):
    import re

    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", path.name)]


def verify(video_path: Path, frame_dir: Path, num_frames: int = 32) -> dict:
    result = {"video_id": video_path.stem, "video": str(video_path), "frame_dir": str(frame_dir)}
    if not video_path.is_file():
        return {**result, "ok": False, "error": "video missing"}
    if not frame_dir.is_dir():
        return {**result, "ok": False, "error": "frame dir missing"}

    paths = sorted([p for p in frame_dir.iterdir() if p.suffix.lower() == ".png"], key=natural)
    cap = cv2.VideoCapture(str(video_path))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    indices = vc.sample_frame_indices(total, num_frames)
    expected_names = [f"{video_path.stem}_f{i:02d}.png" for i in range(len(indices))]
    result.update(
        {
            "fps": round(fps, 3),
            "total_frames": total,
            "expected_frames": len(indices),
            "actual_frames": len(paths),
            "names_match": [p.name for p in paths] == expected_names,
            "last_timestamp_sec": round((indices[-1] / fps) if fps else 0.0, 2),
        }
    )

    cap.set(cv2.CAP_PROP_POS_FRAMES, indices[len(indices) // 2])
    ok, raw = cap.read()
    cap.release()
    overlay_changed = None
    if ok and raw is not None and paths:
        raw_rgb = cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)
        base = vc.resize_if_needed(Image.fromarray(raw_rgb))
        saved = np.asarray(Image.open(paths[len(paths) // 2]).convert("RGB")).astype(int)
        rendered = np.asarray(base).astype(int)
        if saved.shape == rendered.shape:
            region = saved[:40, -160:] - rendered[:40, -160:]
            overlay_changed = int((np.abs(region).sum(axis=2) > 30).sum())
    result["timestamp_pixels_changed"] = overlay_changed
    result["ok"] = bool(
        result["actual_frames"] == result["expected_frames"] == len(expected_names)
        and result["names_match"]
        and (overlay_changed or 0) > 20
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify EG-VQA extracted frames.")
    parser.add_argument("--split", default="test")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    videos = root / "official_repo" / "data" / "videos"
    frames = root / "official_repo" / "data" / "frames" / args.split
    out = args.output or root / "experiments" / f"frame_check_{args.split}.json"

    rows = []
    for frame_dir in sorted(p for p in frames.iterdir() if p.is_dir()):
        video = next(iter(videos.glob(f"{frame_dir.name}.*")), videos / f"{frame_dir.name}.mp4")
        rows.append(verify(video, frame_dir))
    passed = sum(1 for row in rows if row.get("ok"))
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{passed}/{len(rows)} videos passed -> {out}")
    return 0 if passed == len(rows) and rows else 1


if __name__ == "__main__":
    sys.exit(main())
