# Results Provenance

Every headline number in the README and reports maps to a file under `results/`. No value was
re-typed from memory. Where a value cannot be recomputed from shipped files alone, this document says so.

## Run inventory

| Run | Prediction | Official metrics | Diagnostics | Run metadata | Config |
|---|---|---|---|---|---|
| A (legacy 8, first) | `results/predictions/A_legacy_8_first.json` | `results/metrics/A_legacy_8_first_evidence_metrics.json` | `results/summaries/diagnostics/A_legacy_8_first.json` | `...meta.json` | `configs/A_legacy_8_first.json` |
| A2 (8, uniform) | `results/predictions/A2_uniform_8.json` | `results/metrics/A2_uniform_8_evidence_metrics.json` | `results/summaries/diagnostics/A2_uniform_8.json` | `...meta.json` | `configs/A2_uniform_8.json` |
| B (16, uniform) | `results/predictions/B_uniform_16.json` | `results/metrics/B_uniform_16_evidence_metrics.json` | `results/summaries/diagnostics/B_uniform_16.json` | `...meta.json` | `configs/B_uniform_16.json` |
| C (32, uniform) | `results/predictions/C_uniform_32.json` | `results/metrics/C_uniform_32_evidence_metrics.json` | `results/summaries/diagnostics/C_uniform_32.json` | `...meta.json` | `configs/C_uniform_32.json` |
| D (8, timestamp prompt) | `results/predictions/D_uniform_8_timestamp.json` | `results/metrics/D_uniform_8_timestamp_evidence_metrics.json` | `results/summaries/diagnostics/D_uniform_8_timestamp.json` | `...meta.json` | `configs/D_uniform_8_timestamp.json` |
| C token-512 | `results/predictions/C32_tok512.json` | `results/metrics/C32_tok512_evidence_metrics.json` | `results/summaries/diagnostics/C32_tok512.json` | `...meta.json` | no separate config (same as C; token limit differs) |
| Expanded 300 | `results/predictions/expanded_C32.json` | `results/metrics/expanded_C32_evidence_metrics.json` | `results/summaries/diagnostics/expanded_C32.json` | `...meta.json` | no separate config (same as C; sample set differs) |

The two runs without a dedicated config are documented by their `.meta.json` (frames, sampling,
prompt, token limit). They are not part of the 92-question paired ablation table.

## Figures

| Figure | Content | Source data | Regeneration |
|---|---|---|---|
| `results/figures/fig1_sampling.png` | First-8 vs official 32-frame coverage schematic | `results/summaries/pipeline_audit.json` (`frame_coverage`) | **Not scripted in this repository**; static output. Raw data is shipped. |
| `results/figures/fig2_ablation.png` | 8/16/32-frame EG-F1 and overlap rate | `results/summaries/ablation_summary.json` | `python scripts/plot_ablation.py --input results/summaries/ablation_summary.json --output <path>.png` |
| `results/figures/fig3_expanded.png` | 300-question EG-F1 (with CI) and IoU-F1 | `results/metrics/expanded_C32_evidence_metrics.json`, `results/summaries/expanded_bootstrap_ci.json` | **Not scripted**; static output. Both inputs are shipped. |
| `results/figures/fig4_localization.png` | Predicted vs ground-truth evidence starts | `results/summaries/diagnostics/temporal_bias_expanded.json` | **Not scripted**; static output. Input is shipped. |
| `results/figures/fig5_tokens.png` | 256 vs 512 token completeness and EG-F1 | `results/summaries/token_limit_comparison.json`, `truncation_analysis.json`, `truncation_analysis_tok512.json` | **Not scripted**; static output. Inputs are shipped. |
| `results/figures/ablation_summary.png` | Three-panel ablation summary | `results/summaries/ablation_summary.json` | **Static output** from the original workspace; the data is shipped. |
| `results/figures/sensitivity.png` | Metric sensitivity to temporal jitter | `results/summaries/metric_sensitivity_summary.json` | `python scripts/plot_sensitivity.py --input results/summaries/metric_sensitivity_summary.json --output <path>.png` (not byte-identical to the shipped image; same data) |

## Dataset and audit numbers

| Number | Meaning | Source |
|---|---|---|
| 2,067 / 11,838 / 8,949 / 2,889 | Videos, QA pairs, train and test questions | `results/summaries/data_audit.json` |
| 20,009 / 6,839 evidence spans | Per-split evidence spans | `results/summaries/data_audit.json` |
| 2,196 / 2,212 / 1,994 / 2,547 | Train type distribution | `results/summaries/data_audit.json` → `train.questions_by_type` |
| 14 zero-length spans (12 train / 2 test) | Annotation defects; 21 defects in total with 7 spans beyond duration | `results/summaries/data_audit.json` → `issues_by_kind` |
| 7 spans beyond duration | Annotation defects | `results/summaries/data_audit.json` |
| 0 video overlap | No train/test leakage | `results/summaries/data_audit.json` → `cross_split` |

## Metric validation

| Number | Meaning | Source |
|---|---|---|
| 0.999654 | Oracle EG-F1 on all 2,889 test questions | `results/summaries/oracle_summary.json` |
| 2,889 | Oracle sample count | `results/summaries/oracle_summary.json` |

The oracle's per-sample predictions are not shipped (only the aggregate). Recomputing it requires the
official annotations and the official evaluation script; the aggregate can be inspected but not
independently recomputed from this repository alone.

## 92-question controlled ablation

Fixed question list: `results/subsets/fixed92_question_ids.json` (IDs) and
`results/subsets/fixed92_questions.json` (IDs with video and type; 10 videos). The input annotations are
rebuilt with `scripts/build_inference_annotations.py`.

| Number | Meaning | Source |
|---|---|---|
| 0.0455 / 0.0234 / 0.0479 / 0.0686 / 0.0280 | EG-F1 (0.3,0.5) for A / A2 / B / C / D | `results/summaries/ablation_summary.json` → `ablation_rows` |
| 0.0127 / 0.0133 / 0.0163 / 0.0212 / 0.0093 | EG-F1 (0.3,0.75) | same |
| 0.1045 / 0.0546 / 0.1152 / 0.1578 / 0.0566 | IoU-F1 @0.1 | same |
| 55.1% / 66.7% / 47.3% / 31.5% / 73.9% | Predictions all starting within 30 s (custom) | same (`first30_fraction`) |
| 73.6% / 75.0% / 69.1% / 53.6% / 79.3% | No temporal overlap (custom) | same (`no_overlap_rate`) |
| 0.056 / 0.046 / 0.065 / 0.084 / 0.045 | Mean best IoU (custom) | same (`mean_best_iou`) |
| +0.0452, 11/4, p=0.0399 | C vs A2 paired comparison (same 92 questions) | same (`mean_delta`, `improved`, `worsened`, `wilcoxon_p`, `paired_vs_reference_n=92`) |
| 22.6% (22.5–22.7%) | First-8 frame coverage | `results/summaries/pipeline_audit.json` → `frame_coverage` |

## 300-question stratified evaluation

Reported separately from the 92-question ablation: `results/summaries/expanded_summary.{json,csv,md}`.
It is **not** paired with the 92-question reference.

| Number | Meaning | Source |
|---|---|---|
| 300, 75 per type, seed 20261030 | Sampling | `results/subsets/expanded_questions.json` |
| 60 videos | Selected videos | `results/subsets/expanded_questions.json` (`num_videos`) |
| 526 available questions | Sampling pool | **Not recoverable from shipped files.** Recorded in `docs/ABLATION_REPORT.md` §4.1 from the original run; reproducing it requires the official annotations and the 60 videos' frame directories. |
| 0.0510 | EG-F1 (0.3,0.5) | `results/metrics/expanded_C32_evidence_metrics.json` |
| 0.0116 / 0.0058 | EG-F1 (0.3,0.75) / (0.5,0.75) | same |
| 0.1668 / 0.0573 / 0.0210 / 0.0019 | IoU-F1 @0.1/0.3/0.5/0.7 | same |
| [0.0358, 0.0680] | 95% bootstrap CI | `results/summaries/expanded_bootstrap_ci.json` |
| 55.4% (501/905) | No temporal overlap | `results/summaries/diagnostics/expanded_C32.json` |
| 39.3% | All predictions within 30 s | `results/summaries/diagnostics/temporal_bias_expanded.json` |
| 0.081 | Mean best IoU | `results/summaries/diagnostics/expanded_C32.json` |
| 16.0 s vs 73.0 s | Predicted vs GT start medians | `results/summaries/diagnostics/temporal_bias_expanded.json` |
| 1 / 39 / 0 | Invalid timestamps / spans beyond duration / empty evidence | `results/summaries/diagnostics/expanded_C32.json` |
| 178 / 300 | Complete think+answer outputs | same (`format_health`) |
| 16.87 s / 3.96 GiB | Mean time / peak VRAM | same (`timing`) |

## Token-limit experiment

| Number | Meaning | Source |
|---|---|---|
| 0.0686 → 0.0669 | EG-F1 (0.3,0.5), 256 → 512 | `results/summaries/token_limit_comparison.json` |
| 35 → 36 / 92 | Outputs with all closing tags | same |
| 45 / 45 | Outputs with parsed answer | same |
| 41 / 41 | Outputs ending inside `<think>` | `results/summaries/truncation_analysis.json`, `truncation_analysis_tok512.json` |
| 45.9 tokens (median 33) | Mean length of the 41 think-truncated outputs | `truncation_analysis.json` → `token_stats_by_truncation_point.cut_in_think` |
| 134.2 / 158.1 / 45.9 / 256.0 | Mean tokens for complete / answer-cut / think-cut / evidence-cut outputs | `truncation_analysis.json` → `token_stats_by_truncation_point` |
| 105.4 | Mean tokens over all 92 outputs (not the think-cut group) | same (`mean_output_tokens`) |
| 7 → 6 | Outputs hitting the cap | same |
| 0 / 1 / 91 | Paired improved / worsened / unchanged | `results/summaries/token_limit_comparison.json` |
| 19.46 s → 20.61 s | Mean inference time | same |
| 3.96 GiB | Peak VRAM (both) | same |

## Metric sensitivity

| Number | Meaning | Source |
|---|---|---|
| 0.9967 | IoU-F1 after description swap (timestamps kept) | `results/summaries/metric_sensitivity_summary.json` |
| 0.3451 | EG-F1 (0.3,0.75) after description swap | same |
| 0.9967 → 0.5066 | EG-F1 (0.3,0.5) under jitter σ=0 → 30 s | same |

## Environment

| Content | Source |
|---|---|
| Windows 11, RTX 4060 8 GB, Python versions | `results/summaries/env_report_base.json`, `env_report_inference.json`, `docs/ENVIRONMENT.md` |
| 7B bf16 ≈ 15 GB and training infeasibility | `docs/TRAINING_REVIEW.md` |
| vLLM unavailable on Windows | `docs/ENVIRONMENT.md` (recorded failure log in the original workspace; not shipped) |
| Missing judge API key | `docs/FINAL_REPRODUCTION_REPORT.md` §11.2 |

## Known limitations of this mapping

- `results/metrics/*.json` now records `source_file` as a repository-relative path
  (`results/predictions/<run>.json`). Only this metadata field was rewritten; all metric values were
  verified unchanged (identical canonical hashes before/after).
- The 526-question pool is the only headline number not derivable from shipped files.
- Four figures are static outputs; their inputs are shipped, but the plotting code is not.
