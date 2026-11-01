"""Download selected videos from a remote uncompressed .tar via HTTP Range requests.

The official EG-VQA dataset ships all videos as a single multi-GB tar archive on
the Hugging Face Hub. Downloading the whole archive is unnecessary for smoke
tests, so this script walks the tar headers (512-byte blocks fetched with Range
requests) and extracts only the members whose video ids are requested.

It never writes anything outside --out-dir and verifies each extracted file
against the size recorded in the tar header.
"""

from __future__ import annotations

import argparse
import http.client
import json
import ssl
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BLOCK = 512
DEFAULT_URL = "https://hf-mirror.com/datasets/lphuang33/EG-VQA/resolve/main/videos.tar"


class RemoteTar:
    """Persistent-connection reader for a remote tar served over HTTP Range.

    The Hub resolve URL redirects to a signed CDN URL. Resolving that redirect
    per request costs several seconds, so it is resolved once and reused over a
    keep-alive connection.
    """

    def __init__(self, url: str, retries: int = 5):
        self.url = url
        self.retries = retries
        self._local = threading.local()
        self._final: Optional[str] = None
        self._lock = threading.Lock()

    def _resolve(self) -> None:
        request = urllib.request.Request(
            self.url,
            headers={"Range": f"bytes=0-{BLOCK - 1}", "User-Agent": "eg-vqa-repro/1.0"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            self._final = response.geturl()

    def _connection(self) -> Tuple[http.client.HTTPSConnection, str]:
        conn = getattr(self._local, "conn", None)
        path = getattr(self._local, "path", None)
        if conn is None:
            if self._final is None:
                with self._lock:
                    if self._final is None:
                        self._resolve()
            parsed = urllib.parse.urlparse(self._final or self.url)
            path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
            conn = http.client.HTTPSConnection(
                parsed.netloc, timeout=60, context=ssl.create_default_context()
            )
            self._local.conn = conn
            self._local.path = path
        return conn, path

    def fetch(self, start: int, length: int) -> bytes:
        last_error: Optional[Exception] = None
        for attempt in range(1, self.retries + 1):
            try:
                conn, path = self._connection()
                conn.request("GET", path, headers={"Range": f"bytes={start}-{start + length - 1}"})
                response = conn.getresponse()
                data = response.read()
                if response.status not in (200, 206):
                    raise IOError(f"HTTP {response.status} at {start}")
                if len(data) != length:
                    raise IOError(f"expected {length} bytes, got {len(data)}")
                return data
            except Exception as exc:  # network errors are retried with a fresh connection
                last_error = exc
                self._local.conn = None
                print(f"[range] attempt {attempt}/{self.retries} failed at {start}: {exc}", file=sys.stderr)
                time.sleep(min(2 ** attempt, 20))
        raise RuntimeError(f"range fetch failed at offset {start}") from last_error


def parse_tar_header(block: bytes) -> Optional[Tuple[str, int, int]]:
    """Return (name, size, typeflag) for a tar header block, or None at end-of-archive."""
    if not block or block == b"\0" * BLOCK:
        return None
    name = block[0:100].rstrip(b"\0").decode("utf-8", "replace")
    prefix = block[345:500].rstrip(b"\0").decode("utf-8", "replace")
    if prefix:
        name = f"{prefix}/{name}"
    raw_size = block[124:136].rstrip(b"\0 ").strip()
    try:
        size = int(raw_size, 8) if raw_size else 0
    except ValueError:
        raise ValueError(f"bad size field in tar header for {name!r}: {raw_size!r}")
    typeflag = block[156:157].decode("ascii", "replace") or "0"
    return name, size, typeflag


def build_index(reader: RemoteTar, archive_size: int, log_every: int = 50) -> List[Dict[str, object]]:
    """Walk the tar sequentially through ranged header reads."""
    entries: List[Dict[str, object]] = []
    offset = 0
    while offset + BLOCK <= archive_size:
        block = reader.fetch(offset, BLOCK)
        parsed = parse_tar_header(block)
        if parsed is None:
            break
        name, size, typeflag = parsed
        entries.append(
            {
                "name": name,
                "size": size,
                "typeflag": typeflag,
                "header_offset": offset,
                "data_offset": offset + BLOCK,
            }
        )
        if len(entries) % log_every == 0:
            print(f"[index] {len(entries)} members, offset={offset}", flush=True)
        # long name (L) and pax (x/g) entries carry the next member's name; their
        # payload still counts toward the offset, which is all we need here.
        offset += BLOCK + ((size + BLOCK - 1) // BLOCK) * BLOCK

    # Resolve GNU long-name ('L') and PAX ('x') records into their target member.
    resolved: List[Dict[str, object]] = []
    pending_name: Optional[str] = None
    pending_pax_path: Optional[str] = None
    for entry in entries:
        typeflag = entry["typeflag"]
        if typeflag == "L":
            payload = reader.fetch(int(entry["data_offset"]), int(entry["size"]))
            pending_name = payload.rstrip(b"\0").decode("utf-8", "replace")
            continue
        if typeflag == "x":
            payload = reader.fetch(int(entry["data_offset"]), int(entry["size"]))
            for line in payload.split(b"\n"):
                if line.startswith(b"path="):
                    pending_pax_path = line[5:].decode("utf-8", "replace")
            continue
        if typeflag == "g":
            continue
        name = pending_pax_path or pending_name or str(entry["name"])
        entry["name"] = name
        pending_name = None
        pending_pax_path = None
        resolved.append(entry)
    return resolved


def download_member(reader: RemoteTar, entry: Dict[str, object], out_dir: Path, chunk: int = 8 * 1024 * 1024) -> Path:
    """Stream one tar member to disk and verify its size."""
    name = Path(str(entry["name"])).name
    target = out_dir / name
    size = int(entry["size"])
    if target.exists() and target.stat().st_size == size:
        print(f"[skip] already present: {target.name}")
        return target

    data_offset = int(entry["data_offset"])
    written = 0
    with target.open("wb") as handle:
        while written < size:
            length = min(chunk, size - written)
            handle.write(reader.fetch(data_offset + written, length))
            written += length
    if written != size:
        raise IOError(f"size mismatch for {target}: {written} != {size}")
    print(f"[ok] {target.name} ({size / 1e6:.1f} MB)")
    return target


def scan_and_extract(
    reader: RemoteTar,
    archive_size: int,
    wanted: Dict[str, str],
    quotas: Dict[str, int],
    out_dir: Path,
    max_members: int = 0,
) -> List[Dict[str, object]]:
    """Walk tar headers in order and download members until quotas or max_members.

    Returns a manifest of downloaded videos (video_id, split, member, size).
    """
    found: Dict[str, int] = {split: 0 for split in quotas}
    manifest: List[Dict[str, object]] = []
    offset = 0
    seen = 0
    pending_name: Optional[str] = None
    pending_pax: Optional[str] = None

    while offset + BLOCK <= archive_size:
        if max_members and seen >= max_members:
            print(f"[scan] reached --max-members={max_members}")
            break
        if all(found[split] >= quota for split, quota in quotas.items()):
            break

        block = reader.fetch(offset, BLOCK)
        parsed = parse_tar_header(block)
        if parsed is None:
            break
        raw_name, size, typeflag = parsed
        data_offset = offset + BLOCK
        offset += BLOCK + ((size + BLOCK - 1) // BLOCK) * BLOCK
        seen += 1

        if typeflag == "L":
            pending_name = reader.fetch(data_offset, size).rstrip(b"\0").decode("utf-8", "replace")
            continue
        if typeflag == "x":
            payload = reader.fetch(data_offset, size)
            for line in payload.split(b"\n"):
                if line.startswith(b"path="):
                    pending_pax = line[5:].decode("utf-8", "replace")
            continue
        if typeflag == "g":
            continue

        name = pending_pax or pending_name or raw_name
        pending_name = pending_pax = None
        stem = Path(name).stem
        split = wanted.get(stem)
        if split is None or found[split] >= quotas.get(split, 0):
            continue

        entry = {"name": name, "size": size, "typeflag": typeflag, "data_offset": data_offset}
        target = download_member(reader, entry, out_dir)
        manifest.append({"video_id": stem, "split": split, "member": name, "size": size, "path": str(target)})
        found[split] += 1
        print(f"[scan] split={split} {found[split]}/{quotas[split]} {stem}", flush=True)

    print(f"[scan] examined {seen} members; downloaded {len(manifest)}", flush=True)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract selected videos from a remote tar using HTTP Range.")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--archive-size", type=int, default=13_090_641_920)
    parser.add_argument("--video-ids", nargs="*", default=[], help="Video ids (file stems) to extract.")
    parser.add_argument("--from-json", type=Path, default=None, help="Annotation JSON; extract --limit ids from it.")
    parser.add_argument("--limit", type=int, default=0, help="With --from-json, take this many video ids.")
    parser.add_argument("--index-out", type=Path, default=None, help="Write the full tar index to this JSON file.")
    parser.add_argument("--index-in", type=Path, default=None, help="Reuse a previously written index.")
    parser.add_argument("--scan", action="store_true", help="Scan in tar order and fetch videos that match --from-json.")
    parser.add_argument("--per-split", type=int, default=3, help="With --scan, how many videos per split.")
    parser.add_argument("--max-members", type=int, default=0, help="With --scan, stop after this many tar members.")
    parser.add_argument("--manifest", type=Path, default=None, help="Write a manifest of downloaded videos here.")
    args = parser.parse_args()

    if args.scan:
        if not args.from_json:
            parser.error("--scan requires --from-json (a single annotation file)")
        data = json.loads(args.from_json.read_text(encoding="utf-8"))
        split = args.from_json.stem
        wanted = {item["video_id"]: split for item in data if isinstance(item, dict) and item.get("video_id")}
        reader = RemoteTar(args.url)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        manifest = scan_and_extract(
            reader,
            args.archive_size,
            wanted,
            {split: args.per_split},
            args.out_dir,
            args.max_members,
        )
        if args.manifest:
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            args.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return 0 if len(manifest) >= args.per_split else 2

    reader = RemoteTar(args.url)
    if args.index_in and args.index_in.is_file():
        entries = json.loads(args.index_in.read_text(encoding="utf-8"))
        print(f"Loaded index with {len(entries)} members from {args.index_in}")
    else:
        print("Building tar index from remote headers ...", flush=True)
        entries = build_index(reader, args.archive_size)
        print(f"Indexed {len(entries)} members")
        if args.index_out:
            args.index_out.parent.mkdir(parents=True, exist_ok=True)
            args.index_out.write_text(json.dumps(entries, indent=1), encoding="utf-8")

    wanted: List[str] = list(args.video_ids)
    if args.from_json:
        data = json.loads(args.from_json.read_text(encoding="utf-8"))
        ids = [item["video_id"] for item in data if isinstance(item, dict) and item.get("video_id")]
        wanted.extend(ids[: args.limit] if args.limit > 0 else ids)
    if not wanted:
        print("No video ids requested; index-only run.", file=sys.stderr)
        return 0

    by_stem: Dict[str, Dict[str, object]] = {}
    for entry in entries:
        stem = Path(str(entry["name"])).stem
        by_stem.setdefault(stem, entry)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    missing = [vid for vid in wanted if vid not in by_stem]
    for vid in wanted:
        if vid in by_stem:
            download_member(reader, by_stem[vid], args.out_dir)
    if missing:
        print(f"[warn] ids not found in archive: {missing}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
