#!/usr/bin/env bash
# Controlled ablation runs on the fixed 92-question set.
# Prerequisites: official repo cloned to ./official_repo, videos downloaded and
# frames extracted for those videos (see README steps 4-5).
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Override with PY=/path/to/python if your environment is not the project venv.
if [[ -z "${PY:-}" ]]; then
  if [[ -x "$ROOT/.venv/Scripts/python.exe" ]]; then
    PY="$ROOT/.venv/Scripts/python.exe"
  elif [[ -x "$ROOT/.venv/bin/python" ]]; then
    PY="$ROOT/.venv/bin/python"
  else
    PY="python"
  fi
fi
export HF_HUB_OFFLINE=1
export PYTHONUNBUFFERED=1

mkdir -p experiments/ablation/predictions experiments/ablation/metrics experiments/ablation/diagnostics
if [[ ! -f experiments/ablation/fixed92_annotations.json ]]; then
  echo "=== building fixed 92-question annotations ==="
  "$PY" scripts/build_inference_annotations.py \
    --annotations official_repo/data/test.json \
    --question-ids results/subsets/fixed92_question_ids.json \
    --output experiments/ablation/fixed92_annotations.json
fi

run_config() {
  local name="$1" frames="$2" selection="$3" prompt="$4"
  echo "=== $name (frames=$frames selection=$selection prompt=$prompt) ==="
  "$PY" scripts/infer_qwen_vl.py \
    --model-path models/Qwen2.5-VL-3B-Instruct \
    --annotations experiments/ablation/fixed92_annotations.json \
    --only-available \
    --max-frames "$frames" --frame-selection "$selection" --prompt-variant "$prompt" \
    --max-pixels 100352 --max-new-tokens 256 --load-in-4bit \
    --config-name "$name" \
    --output "experiments/ablation/predictions/${name}.json" --overwrite
  "$PY" official_repo/evaluation/evidence_metrics.py \
    --input "experiments/ablation/predictions/${name}.json" \
    --output "experiments/ablation/metrics/${name}_evidence_metrics.json" \
    --semantic-device cpu --overwrite
  "$PY" scripts/diagnose_predictions.py \
    --predictions "experiments/ablation/predictions/${name}.json" \
    --metrics "experiments/ablation/metrics/${name}_evidence_metrics.json" \
    --meta "experiments/ablation/predictions/${name}.meta.json" \
    --label "$name" \
    --output "experiments/ablation/diagnostics/${name}.json"
}

if [[ "${RUN_A2:-1}" == "1" ]]; then run_config A2_uniform_8 8 uniform official; fi
if [[ "${RUN_B:-1}" == "1" ]]; then run_config B_uniform_16 16 uniform official; fi
if [[ "${RUN_C:-1}" == "1" ]]; then run_config C_uniform_32 32 uniform official; fi
if [[ "${RUN_D:-1}" == "1" ]]; then run_config D_uniform_8_timestamp 8 uniform timestamp; fi

echo "=== summarizing ==="
"$PY" scripts/summarize_ablation.py \
  --metrics-dir experiments/ablation/metrics \
  --diagnostics-dir experiments/ablation/diagnostics \
  --configs-dir configs \
  --meta-dir experiments/ablation/predictions \
  --output-dir experiments/ablation/summary

echo "ABLATION DONE"
