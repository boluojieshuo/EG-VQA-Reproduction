# Usage Notes

This document describes the working layout, how to reproduce each reported number, and known
platform issues. The short version is in the top-level README.

## 1. Working layout

The scripts expect three sibling directories at the repository root:

```text
EG-VQA-Reproduction/
├── official_repo/         # clone of the official EG-VQA repository (not shipped)
├── experiments/           # runtime workspace created by the scripts (git-ignored)
└── results/               # curated outputs shipped with this repository
```

`official_repo/` must contain the official annotations at `official_repo/data/train.json` and
`official_repo/data/test.json` (they are part of the official clone). Videos and frames are placed
under `official_repo/data/videos/` and `official_repo/data/frames/` following the official README.

The shipped `results/` tree is a copy of the experiment outputs, not a live workspace. To re-run an
analysis, write into `experiments/...` and pass explicit `--input`/`--output` paths, or copy the
relevant files into the expected workspace directory.

## 2. Environments

Analysis and tests:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

Inference (optional):

```bash
.venv/Scripts/python -m pip install -r requirements-inference.txt
.venv/Scripts/python -m pip install torch==2.4.1 torchvision==0.19.1 \
  --index-url https://download.pytorch.org/whl/cu124
```

The inference environment used in this project was Python 3.10.6 with torch 2.4.1+cu124,
transformers 4.51.3, sentence-transformers 5.7.0 and bitsandbytes 0.50.2. The analysis environment was
Python 3.13.5. Both are recorded in `results/summaries/env_report_*.json`.

## 3. Data

Annotations come with the official clone and are byte-identical to the Hugging Face release.

Videos are distributed by the official dataset as a 13.09 GB `videos.tar`. Downloading the whole
archive is unnecessary for small experiments; `scripts/fetch_videos_from_tar.py` walks the tar headers
over HTTP Range requests and extracts only the requested videos:

```bash
python scripts/fetch_videos_from_tar.py --scan --from-json official_repo/data/test.json \
  --per-split 10 --max-members 300 --out-dir official_repo/data/videos \
  --manifest experiments/videos_manifest_test.json
```

Frame extraction uses the official preprocessing through a wrapper that supplies a Windows font path.
The official repository is not modified:

```bash
python scripts/extract_frames.py --dataset experiments/subsets/test_subset.json \
  --video-root official_repo/data --output-root official_repo/data/frames/test
python scripts/verify_frames.py --split test
```

`verify_frames.py` checks frame count, naming, decodability, timestamp overlay, and that the last
timestamp does not exceed the video duration.

## 4. Inference

`scripts/infer_qwen_vl.py` accepts:

- `--frame-selection first` (legacy behaviour: first N frames of the 32 extracted frames) or
  `uniform` (evenly spaced across the video). **Use `uniform`** for the reported experiments.
- `--prompt-variant official` (official prompt) or `timestamp` (adds an explicit instruction to read
  the burned-in timestamps).
- `--load-in-4bit` for NF4 quantization; without it the 3B model needs about 7 GiB and is much slower
  on an 8 GB card.

Inference expects official video-level annotations. Build them from a fixed question-id list first;
the converter preserves every field of the selected records and fails on missing or duplicate ids:

```bash
# fixed 92-question set used by the ablation
python scripts/build_inference_annotations.py --annotations official_repo/data/test.json \
  --question-ids results/subsets/fixed92_question_ids.json \
  --output experiments/ablation/fixed92_annotations.json

# 300-question stratified set (requires frames for 60 test videos; fetch 60 if needed,
# see README step 11)
python scripts/build_expanded_set.py --annotations official_repo/data/test.json \
  --frames-root official_repo/data/frames/test --total 300 --seed 20261030 \
  --output experiments/ablation/expanded_questions.json
python scripts/build_inference_annotations.py --annotations official_repo/data/test.json \
  --question-ids experiments/ablation/expanded_questions.json \
  --output experiments/ablation/expanded_annotations.json
```

Example (32 frames, official prompt, 4-bit):

```bash
HF_HUB_OFFLINE=1 .venv/Scripts/python scripts/infer_qwen_vl.py \
  --model-path models/Qwen2.5-VL-3B-Instruct \
  --annotations experiments/ablation/fixed92_annotations.json --only-available \
  --max-frames 32 --frame-selection uniform --max-pixels 100352 --max-new-tokens 256 \
  --load-in-4bit --config-name C_uniform_32 \
  --output experiments/ablation/predictions/C_uniform_32.json --overwrite
```

The output schema is the one expected by the official evaluation script: each record keeps the public
ground-truth fields and adds `model_response_raw` and `parsed_response`.

## 5. Official metrics

Evidence metrics (requires BGE-M3 and sentence-transformers):

```bash
HF_HUB_OFFLINE=1 .venv/Scripts/python official_repo/evaluation/evidence_metrics.py \
  --input experiments/ablation/predictions/C_uniform_32.json \
  --semantic-device cpu
```

BGE-M3 weights are loaded from `official_repo/EG-Reasoner/Science_Bert/` by default and downloaded
there if absent.

Answer metrics (not run in this project) need an OpenAI-compatible judge:

```bash
export OPENAI_API_KEY=<key>
.venv/Scripts/python official_repo/evaluation/answer_metrics.py --input <result>.json
```

The official script raises `RuntimeError` when the key is missing; no answer-side numbers are
fabricated in this repository.

## 6. Diagnostics and aggregation

```bash
# Per-question custom diagnostics + official metrics read from the metrics file
python scripts/diagnose_predictions.py --predictions <run>.json \
  --metrics <run>_evidence_metrics.json --label <run> --output <diagnostics>.json

# Temporal bias: predicted vs ground-truth evidence starts
python scripts/analyze_temporal_bias.py --predictions <run>.json --output <bias>.json

# Output truncation analysis (tokenizer only, no re-inference)
python scripts/analyze_truncation.py --predictions <run>.json

# Paired comparison across token limits
python scripts/compare_token_limits.py --low-pred <a>.json --low-metrics <a>_metrics.json \
  --high-pred <b>.json --high-metrics <b>_metrics.json --output comparison.json

# Aggregate ablation runs (repository layout by default; overrides for a runtime workspace)
python scripts/summarize_ablation.py   --metrics-dir experiments/ablation/metrics   --diagnostics-dir experiments/ablation/diagnostics   --configs-dir configs --meta-dir experiments/ablation/predictions   --output-dir experiments/ablation/summary

# Figures from summary files
python scripts/plot_ablation.py --input results/summaries/ablation_summary.json \
  --output results/figures/ablation_summary.png
python scripts/plot_sensitivity.py --input results/summaries/metric_sensitivity_summary.json \
  --output results/figures/sensitivity.png
```

## 7. Reproducing the reported tables from shipped files

No inference is needed to inspect the reported numbers:

| Table | Source |
|---|---|
| Dataset audit | `results/summaries/data_audit.json`, `annotation_stats.json` |
| Oracle validation | `results/summaries/oracle_summary.json` |
| 92-question ablation | `results/summaries/ablation_summary.{json,csv,md}` |
| 300-question results | `results/metrics/expanded_C32_evidence_metrics.json`, `results/summaries/expanded_bootstrap_ci.json` |
| Localization diagnostics | `results/summaries/diagnostics/expanded_C32.json`, `temporal_bias_expanded.json` |
| Token-limit comparison | `results/summaries/token_limit_comparison.json`, `truncation_analysis*.json` |
| Metric sensitivity | `results/summaries/metric_sensitivity_summary.json` |
| Raw outputs | `results/predictions/*.json` (with `.meta.json` run metadata) |

## 8. Known platform issues

- **vLLM on Windows**: the official `evaluation/evaluate.py` imports vLLM, which has no official
  Windows build. This project therefore uses a transformers-based inference script with the same
  prompt and output schema. The official evidence-metrics script runs fine on Windows.
- **No official training**: the official configuration needs Qwen2.5-VL-7B, four GPUs, FSDP and vLLM.
  An 8 GB laptop GPU cannot load one bf16 copy of the 7B weights. See `docs/TRAINING_REVIEW.md`.
- **Hugging Face access**: when `huggingface.co` is unreachable, set
  `HF_ENDPOINT=https://hf-mirror.com`. Large files were fetched with `curl` range requests in this
  project when `huggingface_hub` rejected the mirror redirect.
- **Windows font in preprocessing**: the official script hard-codes a Linux font path. The wrapper
  sets `video_clip.TIMESTAMP_FONT_PATH` to an available font; `EG_VQA_FONT` overrides it.
- **Frame selection**: always pass `--frame-selection uniform`. The `first` mode exists only to
  reproduce the legacy bias that this project identified.

## 9. Tests

```bash
python -m pytest tests -q
```

- Without `./official_repo`: **31 passed, 9 skipped**. The skipped modules exercise official code or
  need the official annotations and print an explicit skip reason.
- With `./official_repo` cloned: **119 passed, 2 skipped**. The two skips are BGE-M3 integration tests,
  which run once the BGE-M3 weights exist under `official_repo/EG-Reasoner/Science_Bert/`.
