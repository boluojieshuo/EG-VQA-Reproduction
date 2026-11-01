"""Check that downloaded videos decode and agree with annotation durations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2


def probe(path: Path) -> dict:
    cap = cv2.VideoCapture(str(path))
    info = {"path": str(path), "opened": bool(cap.isOpened())}
    if cap.isOpened():
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        info.update(
            {
                "fps": round(fps, 3),
                "frames": frames,
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                "duration_sec": round(frames / fps, 2) if fps > 0 else None,
            }
        )
        ok, frame = cap.read()
        info["first_frame_ok"] = bool(ok)
        info["first_frame_shape"] = list(frame.shape) if ok and frame is not None else None
    cap.release()
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe downloaded EG-VQA videos against annotations.")
    parser.add_argument("--videos", type=Path, default=Path("official_repo/data/videos"))
    parser.add_argument("--data-root", type=Path, default=Path("official_repo/data"))
    parser.add_argument("--output", type=Path, default=Path("experiments/video_check.json"))
    args = parser.parse_args()

    annotations = {}
    for split in ("train", "test"):
        for item in json.loads((args.data_root / f"{split}.json").read_text(encoding="utf-8")):
            annotations[item["video_id"]] = {
                "split": split,
                "duration": item.get("duration"),
                "data_source": item.get("data_source"),
                "questions": len(item.get("questions") or []),
            }

    rows = []
    for path in sorted(args.videos.iterdir()):
        if not path.is_file():
            continue
        info = probe(path)
        meta = annotations.get(path.stem, {})
        info["video_id"] = path.stem
        info["annotated"] = bool(meta)
        info.update(meta)
        if info.get("duration_sec") and meta.get("duration"):
            info["duration_delta_sec"] = round(info["duration_sec"] - float(meta["duration"]), 2)
        info["size_bytes"] = path.stat().st_size
        rows.append(info)
        print(json.dumps(info, ensure_ascii=False))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nChecked {len(rows)} videos -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
