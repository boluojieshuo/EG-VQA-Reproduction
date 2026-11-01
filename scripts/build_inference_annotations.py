"""Build inference-ready annotations for a fixed list of question ids.

The official EG-VQA annotations are a list of video records. Inference scripts
expect exactly that structure, while the reported experiments use fixed question
subsets. This tool filters the official annotations to those questions without
changing any field of the selected records.

Input id file can be either:
  {"question_ids": ["...", ...]}
or
  {"questions": [{"question_id": "...", "video_id": "..."}, ...]}

Missing or duplicate ids abort with a non-zero exit code; ids are never skipped
silently.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_requested_ids(path: Path) -> Tuple[List[str], Dict[str, Optional[str]]]:
    """Return requested ids in file order and an optional video_id mapping."""
    payload = load_json(path)
    ids: List[str] = []
    videos: Dict[str, Optional[str]] = {}
    if isinstance(payload, dict) and isinstance(payload.get("question_ids"), list):
        ids = [str(item) for item in payload["question_ids"]]
    elif isinstance(payload, dict) and isinstance(payload.get("questions"), list):
        for item in payload["questions"]:
            if not isinstance(item, dict) or not item.get("question_id"):
                raise ValueError(f"invalid question entry in {path}: {item!r}")
            ids.append(str(item["question_id"]))
            videos[str(item["question_id"])] = item.get("video_id")
    else:
        raise ValueError(
            f"{path} must contain a 'question_ids' list or a 'questions' list"
        )
    duplicates = [qid for qid, count in collections.Counter(ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate question ids in {path}: {duplicates}")
    return ids, videos


def index_annotations(payload: Any) -> Dict[str, Dict[str, Any]]:
    """Map question_id -> {"video": video_record, "question": question_record}."""
    if not isinstance(payload, list):
        raise ValueError("official annotations must be a JSON list of video records")
    index: Dict[str, Dict[str, Any]] = {}
    duplicates: List[str] = []
    for video in payload:
        if not isinstance(video, dict) or not video.get("video_id"):
            raise ValueError(f"video record missing video_id: {video!r}")
        questions = video.get("questions")
        if not isinstance(questions, list):
            raise ValueError(f"video {video['video_id']} has no questions list")
        for question in questions:
            if not isinstance(question, dict) or not question.get("question_id"):
                raise ValueError(f"question missing question_id in video {video['video_id']}")
            qid = str(question["question_id"])
            if qid in index:
                duplicates.append(qid)
            index[qid] = {"video": video, "question": question}
    if duplicates:
        raise ValueError(f"duplicate question ids in official annotations: {duplicates}")
    return index


REQUIRED_QUESTION_FIELDS = ("question", "type", "answer", "evidence")
REQUIRED_VIDEO_FIELDS = ("video_id", "video_path", "duration")


def validate_selected(video: Dict[str, Any], question: Dict[str, Any]) -> List[str]:
    problems = []
    for field in REQUIRED_VIDEO_FIELDS:
        if field not in video:
            problems.append(f"video {video.get('video_id')} missing {field}")
    for field in REQUIRED_QUESTION_FIELDS:
        if field not in question:
            problems.append(f"question {question.get('question_id')} missing {field}")
    evidence = question.get("evidence")
    if not isinstance(evidence, list):
        problems.append(f"question {question.get('question_id')} evidence is not a list")
    else:
        for item in evidence:
            if not isinstance(item, dict):
                problems.append(f"question {question.get('question_id')} evidence item is not an object")
                continue
            timestamps = item.get("timestamp")
            if not isinstance(timestamps, list) or len(timestamps) != 2:
                problems.append(f"question {question.get('question_id')} evidence timestamp is invalid")
            if not isinstance(item.get("description"), str):
                problems.append(f"question {question.get('question_id')} evidence description is missing")
    if not str(question.get("question") or "").strip():
        problems.append(f"question {question.get('question_id')} question text is empty")
    return problems


def build_subset(
    annotations_path: Path,
    ids_path: Path,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    annotations = load_json(annotations_path)
    index = index_annotations(annotations)
    requested, expected_videos = load_requested_ids(ids_path)

    missing = [qid for qid in requested if qid not in index]
    if missing:
        raise ValueError(
            f"{len(missing)} question id(s) not found in {annotations_path}: {missing[:20]}"
            + (" ..." if len(missing) > 20 else "")
        )

    mismatched = []
    for qid in requested:
        expected = expected_videos.get(qid)
        actual = str(index[qid]["video"]["video_id"])
        if expected is not None and str(expected) != actual:
            mismatched.append((qid, expected, actual))
    if mismatched:
        raise ValueError(f"video_id mismatch between id file and annotations: {mismatched[:10]}")

    field_problems: List[str] = []
    for qid in requested:
        field_problems.extend(validate_selected(index[qid]["video"], index[qid]["question"]))
    if field_problems:
        raise ValueError(f"incomplete selected records: {field_problems[:20]}")

    selected_by_video: "collections.OrderedDict[str, Dict[str, Any]]" = collections.OrderedDict()
    for qid in requested:
        video = index[qid]["video"]
        vid = str(video["video_id"])
        if vid not in selected_by_video:
            record = {key: value for key, value in video.items() if key != "questions"}
            record["questions"] = []
            selected_by_video[vid] = record
        selected_by_video[vid]["questions"].append(index[qid]["question"])

    payload = list(selected_by_video.values())
    types = collections.Counter(
        question.get("type") for video in payload for question in video["questions"]
    )
    stats = {
        "annotations": str(annotations_path),
        "question_ids_file": str(ids_path),
        "requested_questions": len(requested),
        "selected_questions": sum(len(video["questions"]) for video in payload),
        "selected_videos": len(payload),
        "questions_by_type": dict(sorted(types.items())),
        "missing_questions": 0,
    }
    if stats["selected_questions"] != len(requested):
        raise AssertionError("internal error: selected question count differs from request")
    return payload, stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Filter official annotations to fixed question ids.")
    parser.add_argument("--annotations", type=Path, required=True,
                        help="Official EG-VQA annotations, e.g. official_repo/data/test.json")
    parser.add_argument("--question-ids", type=Path, required=True,
                        help="JSON with question_ids or questions (see module docstring)")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.output.exists() and not args.overwrite:
        print(f"error: {args.output} exists; pass --overwrite", file=sys.stderr)
        return 2
    try:
        payload, stats = build_subset(args.annotations, args.question_ids)
    except (ValueError, AssertionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(stats, indent=2))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
