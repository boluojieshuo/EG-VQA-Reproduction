"""Run a local Qwen2.5-VL checkpoint on EG-VQA test frames (substitute baseline).

This is NOT the paper's EG-Reasoner (a Qwen2.5-VL-7B model trained with GRPO).
It reuses the official prompt template and response parser from
evaluation/evaluate.py so the output schema and metric input are identical.

Outputs:
  <output>            list of official-schema result dicts
  <output>.meta.json  what model/device/frames were actually used
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "official_repo" / "evaluation"))

import evaluate  # noqa: E402


def load_samples(annotation_path: Path, video_ids: List[str], limit: int, frames_root: Path, only_available: bool) -> List[Dict[str, Any]]:
    samples = evaluate.load_test_samples(annotation_path)
    if video_ids:
        wanted = set(video_ids)
        samples = [s for s in samples if s["video_id"] in wanted]
    if only_available:
        samples = [s for s in samples if (frames_root / s["video_id"]).is_dir()]
    if limit > 0:
        samples = samples[:limit]
    return samples


TIMESTAMP_GUIDANCE = """

ADDITIONAL TIMESTAMP REQUIREMENT:
- Every frame has a timestamp burned into its top-right corner in MM:SS format.
- Read those timestamps and use them to select evidence from the whole video, not only its beginning.
- All evidence times must lie within the video duration.
"""


def select_frame_paths(frames_root: Path, video_id: str, count: int, mode: str) -> List[Path]:
    """Pick `count` frames either from the start (legacy) or evenly across all extracted frames."""
    all_paths = evaluate.frame_paths_for_video(frames_root, video_id, max_frames=1_000_000)
    if mode == "first":
        return all_paths[:count]
    if mode == "uniform":
        if count >= len(all_paths):
            return list(all_paths)
        import numpy as np

        indices = np.linspace(0, len(all_paths) - 1, count)
        return [all_paths[int(round(i))] for i in indices]
    raise ValueError(f"unknown frame selection mode: {mode}")


def build_messages(frame_paths: List[Path], question: str, max_pixels: int, prompt_variant: str = "official") -> List[Dict[str, Any]]:
    prompt = evaluate.PROMPT_TEMPLATE.format(question=question)
    if prompt_variant == "timestamp":
        prompt = prompt + TIMESTAMP_GUIDANCE
    elif prompt_variant != "official":
        raise ValueError(f"unknown prompt variant: {prompt_variant}")
    return [
        {
            "role": "user",
            "content": [{"type": "image", "image": str(p), "max_pixels": max_pixels} for p in frame_paths]
            + [{"type": "text", "text": prompt}],
        }
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Substitute-baseline inference on EG-VQA frames.")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--annotations", type=Path, default=REPO_ROOT / "official_repo" / "data" / "test.json")
    parser.add_argument("--frames-root", type=Path, default=REPO_ROOT / "official_repo" / "data" / "frames" / "test")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--video-ids", nargs="*", default=[])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only-available", action="store_true", help="Keep only questions whose frame dir exists.")
    parser.add_argument("--frame-selection", default="first", choices=["first", "uniform"],
                        help="first: legacy first-N frames; uniform: evenly spaced across the video.")
    parser.add_argument("--prompt-variant", default="official", choices=["official", "timestamp"],
                        help="official prompt, or official + explicit burned-in timestamp instruction.")
    parser.add_argument("--config-name", default=None, help="Label stored in the meta file.")
    parser.add_argument("--max-frames", type=int, default=8)
    parser.add_argument("--max-pixels", type=int, default=128 * 28 * 28)
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float16", "float32"])
    parser.add_argument("--load-in-4bit", action="store_true", help="Quantize the model with bitsandbytes NF4.")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    import torch
    from qwen_vl_utils import process_vision_info
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

    output_path: Path = args.output
    if output_path.exists() and not args.overwrite:
        raise FileExistsError(f"{output_path} exists; pass --overwrite")

    samples = load_samples(args.annotations, args.video_ids, args.limit, args.frames_root, args.only_available)
    if not samples:
        raise ValueError("No samples selected")
    print(f"Selected {len(samples)} questions from {args.annotations}")

    dtype = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}[args.dtype]
    device = args.device
    if device.startswith("cuda") and not torch.cuda.is_available():
        print("CUDA unavailable; falling back to CPU")
        device = "cpu"
        dtype = torch.float32
    if device == "cpu":
        dtype = torch.float32

    print(f"Loading {args.model_path} on {device} ({dtype}) ...")
    load_start = time.time()
    processor = AutoProcessor.from_pretrained(args.model_path)
    model_kwargs = {"device_map": device}
    if args.load_in_4bit:
        from transformers import BitsAndBytesConfig

        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
    else:
        model_kwargs["torch_dtype"] = dtype
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(args.model_path, **model_kwargs).eval()
    load_seconds = round(time.time() - load_start, 1)
    if device != "cpu":
        torch.cuda.synchronize()
        print(f"GPU memory after load: {torch.cuda.memory_allocated() / 1024**3:.2f} GiB")

    results: List[Dict[str, Any]] = []
    for index, sample in enumerate(samples, start=1):
        started = time.time()
        base = {k: sample[k] for k in ("video_id", "question_id", "video_path", "duration",
                                       "data_source", "metadata", "question", "type", "answer", "evidence")}
        try:
            frame_paths = select_frame_paths(args.frames_root, sample["video_id"], args.max_frames, args.frame_selection)
            messages = build_messages(frame_paths, sample["question"], args.max_pixels, args.prompt_variant)
            text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            image_inputs, video_inputs = process_vision_info(messages)
            inputs = processor(
                text=[text], images=image_inputs, videos=video_inputs, padding=True, return_tensors="pt"
            ).to(device)
            with torch.no_grad():
                generated = model.generate(
                    **inputs, max_new_tokens=args.max_new_tokens, do_sample=False
                )
            trimmed = generated[:, inputs["input_ids"].shape[1]:]
            raw = processor.batch_decode(trimmed, skip_special_tokens=True)[0]
            output_tokens = int(trimmed.shape[1])
            results.append(
                {**base, "model_response_raw": raw, "parsed_response": evaluate.parse_model_response(raw),
                 "num_frames_used": len(frame_paths), "frame_selection": args.frame_selection,
                 "prompt_variant": args.prompt_variant, "output_tokens": output_tokens,
                 "hit_token_cap": output_tokens >= args.max_new_tokens,
                 "processing_time": round(time.time() - started, 2)}
            )
        except Exception as exc:
            results.append({**base, "error": f"{type(exc).__name__}: {exc}"})
        print(f"[{index}/{len(samples)}] {sample['question_id']} done in {time.time() - started:.1f}s")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")

    meta = {
        "config_name": args.config_name,
        "frame_selection": args.frame_selection,
        "prompt_variant": args.prompt_variant,
        "model_path": args.model_path,
        "is_paper_model": False,
        "note": "Substitute baseline; the paper model EG-Reasoner is Qwen2.5-VL-7B trained with GRPO.",
        "device": device,
        "dtype": "4bit-nf4" if args.load_in_4bit else str(dtype),
        "load_in_4bit": args.load_in_4bit,
        "max_frames": args.max_frames,
        "max_pixels": args.max_pixels,
        "max_new_tokens": args.max_new_tokens,
        "num_samples": len(samples),
        "load_seconds": load_seconds,
        "gpu_peak_gib": round(torch.cuda.max_memory_allocated() / 1024**3, 2) if device != "cpu" else None,
        "torch_version": torch.__version__,
        "answers": [r.get("parsed_response", {}).get("answer") if isinstance(r.get("parsed_response"), dict) else None for r in results],
    }
    output_path.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    errors = sum(1 for r in results if r.get("error"))
    print(f"Finished: {len(results)} samples, {errors} errors -> {output_path}")
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
