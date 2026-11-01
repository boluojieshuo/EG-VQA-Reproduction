"""Audit the EG-VQA annotation files and local video availability.

Writes a JSON report (default: experiments/data_audit.json) with real counts and
validation findings. Nothing is fabricated: video availability is derived from
the files actually present under the given video directory.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_split(path: Path, video_dir: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} is not a JSON list")

    questions: List[Dict[str, Any]] = []
    issues: List[Dict[str, Any]] = []
    video_ids: List[str] = []
    durations: Dict[str, float] = {}
    sources = collections.Counter()
    types = collections.Counter()
    evidence_counts: List[int] = []
    span_lengths: List[float] = []
    available = 0
    video_exts = {".mp4", ".mkv", ".avi", ".webm", ".mov"}

    for index, video in enumerate(data):
        video_id = video.get("video_id")
        if not video_id:
            issues.append({"kind": "missing_video_id", "index": index})
            continue
        video_ids.append(video_id)
        duration = video.get("duration")
        durations[video_id] = duration if isinstance(duration, (int, float)) else float("nan")
        sources[video.get("data_source")] += 1

        video_path = video_dir / f"{video_id}.mp4"
        if video_path.is_file():
            available += 1
        else:
            candidates = [video_dir / f"{video_id}{ext}" for ext in video_exts]
            if any(candidate.is_file() for candidate in candidates):
                available += 1

        for q_index, question in enumerate(video.get("questions") or []):
            q = dict(question)
            q["_video_id"] = video_id
            q["_index"] = (index, q_index)
            questions.append(q)
            types[q.get("type")] += 1
            evidence = q.get("evidence") or []
            evidence_counts.append(len(evidence))
            if not isinstance(q.get("question_id"), str) or not q.get("question_id"):
                issues.append({"kind": "missing_question_id", "video_id": video_id, "q_index": q_index})
            if not str(q.get("question") or "").strip():
                issues.append({"kind": "empty_question", "question_id": q.get("question_id")})
            if not str(q.get("answer") or "").strip():
                issues.append({"kind": "empty_answer", "question_id": q.get("question_id")})
            if not evidence:
                issues.append({"kind": "empty_evidence", "question_id": q.get("question_id")})
            for e_index, span in enumerate(evidence):
                if not isinstance(span, dict):
                    issues.append({"kind": "evidence_not_object", "question_id": q.get("question_id"), "e_index": e_index})
                    continue
                if not str(span.get("description") or "").strip():
                    issues.append({"kind": "empty_evidence_description", "question_id": q.get("question_id"), "e_index": e_index})
                ts = span.get("timestamp")
                if not isinstance(ts, (list, tuple)) or len(ts) != 2:
                    issues.append({"kind": "invalid_timestamp_shape", "question_id": q.get("question_id"), "e_index": e_index, "timestamp": ts})
                    continue
                start, end = ts
                if not all(isinstance(v, (int, float)) for v in (start, end)):
                    issues.append({"kind": "non_numeric_timestamp", "question_id": q.get("question_id"), "e_index": e_index, "timestamp": ts})
                    continue
                if start < 0:
                    issues.append({"kind": "negative_start", "question_id": q.get("question_id"), "e_index": e_index, "timestamp": ts})
                if start >= end:
                    issues.append({"kind": "start_not_before_end", "question_id": q.get("question_id"), "e_index": e_index, "timestamp": ts})
                if isinstance(duration, (int, float)) and end > duration + 1e-6:
                    issues.append({"kind": "end_beyond_duration", "question_id": q.get("question_id"), "e_index": e_index, "timestamp": ts, "duration": duration})
                span_lengths.append(float(end) - float(start))

    question_ids = [q.get("question_id") for q in questions]
    duplicate_qids = [qid for qid, count in collections.Counter(question_ids).items() if count > 1]
    duplicate_vids = [vid for vid, count in collections.Counter(video_ids).items() if count > 1]
    question_texts = [str(q.get("question") or "").strip().lower() for q in questions]
    duplicate_questions = sum(count - 1 for count in collections.Counter(question_texts).values() if count > 1)

    return {
        "file": str(path),
        "sha256": sha256(path),
        "videos": len(video_ids),
        "unique_videos": len(set(video_ids)),
        "questions": len(questions),
        "questions_by_type": dict(sorted(types.items())),
        "videos_by_source": dict(sorted(sources.items())),
        "evidence_spans": len(span_lengths),
        "evidence_per_question": {
            "min": min(evidence_counts) if evidence_counts else 0,
            "max": max(evidence_counts) if evidence_counts else 0,
            "mean": round(sum(evidence_counts) / len(evidence_counts), 3) if evidence_counts else 0,
            "histogram": dict(sorted(collections.Counter(evidence_counts).items())),
        },
        "evidence_span_seconds": {
            "min": round(min(span_lengths), 2) if span_lengths else None,
            "max": round(max(span_lengths), 2) if span_lengths else None,
            "mean": round(sum(span_lengths) / len(span_lengths), 2) if span_lengths else None,
        },
        "duration_seconds": {
            "min": round(min(d for d in durations.values() if d == d), 2),
            "max": round(max(d for d in durations.values() if d == d), 2),
        },
        "duplicate_video_ids": duplicate_vids,
        "duplicate_question_ids": duplicate_qids,
        "duplicate_question_texts": duplicate_questions,
        "videos_available_locally": available,
        "videos_missing_locally": len(set(video_ids)) - available,
        "issues_total": len(issues),
        "issues_by_kind": dict(sorted(collections.Counter(issue["kind"] for issue in issues).items())),
        "issues_sample": issues[:50],
        "_video_id_set": set(video_ids),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit EG-VQA annotations.")
    parser.add_argument("--split", nargs="*", default=None, help="Subset of splits, e.g. train test.")
    parser.add_argument("--data-root", type=Path, default=Path("official_repo/data"))
    parser.add_argument("--video-dir", type=Path, default=None, help="Directory with extracted videos.")
    parser.add_argument("--output", type=Path, default=Path("experiments/data_audit.json"))
    args = parser.parse_args()

    data_root = args.data_root
    video_dir = args.video_dir or data_root / "videos"
    splits = args.split or ["train", "test"]

    results: Dict[str, Any] = {}
    for split in splits:
        path = data_root / f"{split}.json"
        print(f"Auditing {path} ...")
        results[split] = audit_split(path, video_dir)

    train_ids = results.get("train", {}).get("_video_id_set", set())
    test_ids = results.get("test", {}).get("_video_id_set", set())
    overlap = sorted(train_ids & test_ids)
    results["cross_split"] = {
        "train_videos": len(train_ids),
        "test_videos": len(test_ids),
        "video_id_overlap": len(overlap),
        "overlap_examples": overlap[:10],
    }
    for split in results:
        if isinstance(results[split], dict):
            results[split].pop("_video_id_set", None)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ("videos", "questions", "issues_total", "videos_available_locally")} for k, v in results.items() if isinstance(v, dict)}, indent=2))
    print(f"Saved audit to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
