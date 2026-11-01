"""Build a video-level annotation subset for videos that exist locally.

Used to keep frame extraction fast: the official annotation lists all videos,
but only a few may have been downloaded. Records are copied unchanged; no
annotation field is modified.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".webm", ".mov")


def find_video(videos_dir: Path, video_id: str) -> Path | None:
    for extension in VIDEO_EXTENSIONS:
        candidate = videos_dir / f"{video_id}{extension}"
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep annotation records whose video file exists.")
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--videos-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.overwrite:
        print(f"error: {args.output} exists; pass --overwrite", file=sys.stderr)
        return 2

    try:
        payload: List[Dict[str, Any]] = json.loads(args.annotations.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"error: cannot read {args.annotations}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(payload, list):
        print("error: official annotations must be a JSON list", file=sys.stderr)
        return 2
    if not args.videos_dir.is_dir():
        print(f"error: videos directory not found: {args.videos_dir}", file=sys.stderr)
        return 2

    selected = []
    missing = 0
    for video in payload:
        if not isinstance(video, dict) or not video.get("video_id"):
            continue
        if find_video(args.videos_dir, str(video["video_id"])):
            selected.append(video)
        else:
            missing += 1

    if not selected:
        print(f"error: no videos found under {args.videos_dir}", file=sys.stderr)
        return 2

    stats = {
        "annotations": str(args.annotations),
        "videos_dir": str(args.videos_dir),
        "selected_videos": len(selected),
        "selected_questions": sum(len(video.get("questions") or []) for video in selected),
        "missing_videos": missing,
        "videos_by_source": dict(sorted(collections.Counter(v.get("data_source") for v in selected).items())),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(selected, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
