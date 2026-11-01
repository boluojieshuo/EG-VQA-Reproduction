# Fix Record: Public-Release Review A1–A9

Date: 2026-11-01
Commit: `bc6d47cfd4ffa2a1d0c61bab90e42c4146e8c92b`
Scope: fixes applied to `EG-VQA-Reproduction` after the pre-publication review. The source workspace
was not modified, no model inference was re-run, and no prediction/metric value was altered.

## A1. Zero-length evidence count

- **Problem**: documents said “21 zero-length spans (12 train + 2 test)”; 21 is the number of all
  annotation defects, not zero-length spans.
- **Evidence**: recounted directly from the official annotations:
  train 12 zero-length + 7 beyond-duration; test 2 zero-length + 0 beyond-duration.
- **Fix**: all references now say **14 zero-length (12 train / 2 test) + 7 beyond-duration = 21 defects**.
- **Files**: `README.md`, `docs/FINAL_REPRODUCTION_REPORT.md`, `docs/METRIC_REVIEW.md`,
  `docs/REPRODUCTION_PLAN.md`, `docs/REPRODUCTION_SUMMARY.md`, `docs/RESULTS_PROVENANCE.md`.
- The oracle explanation (2 zero-length test spans → ceiling 0.999654) remains correct.

## A2. Token statistics for truncated outputs

- **Problem**: the 105.4-token mean over all 92 outputs was attributed to the 41 outputs that stop
  inside `<think>`.
- **Evidence**: re-tokenized the saved outputs with the Qwen tokenizer:
  complete 35 → 134.2; answer-truncated 10 → 158.1; think-truncated 41 → **45.9 (median 33)**;
  evidence-truncated 6 → 256.0.
- **Fix**: prose corrected in `README.md`, `docs/FINAL_REPRODUCTION_REPORT.md`,
  `docs/ABLATION_REPORT.md`, `docs/EXPERIMENT_LOG.md`. The overall 105.4 is explicitly labelled as the
  all-output mean.
- **Traceability**: `scripts/analyze_truncation.py` now records
  `token_stats_by_truncation_point`; `results/summaries/truncation_analysis.json` and
  `truncation_analysis_tok512.json` were regenerated (derived statistics only).

## A3. README claim about shipped annotations

- **Problem**: README said the shipped `train.json` / `test.json` were byte-identical, while the repo
  does not include them.
- **Fix**: README now states that the official clone's JSON files were checked locally by SHA-256
  against the Hugging Face files and are byte-identical, and that this public repository does not
  include the annotation files.

## A4. Reproducible 92/300 input pipeline

- **Analysis**: fixed IDs all exist in the official test annotations (92/92 and 300/300); the missing
  piece was filtering them into the official video-level annotation structure.
- **New scripts**:
  - `scripts/build_inference_annotations.py` — filters official annotations by question IDs, preserves
    all fields, validates duplicates/missing IDs/video mismatches, prints selected counts, exits
    non-zero on any missing ID.
  - `scripts/build_video_subset.py` — keeps annotation records whose video file exists locally, for
    frame extraction.
- **Updated**:
  - `scripts/run_ablation.sh` now creates `experiments/ablation/fixed92_annotations.json` if absent,
    writes metrics and diagnostics into the runtime workspace, and summarizes with explicit dirs.
  - `scripts/build_expanded_set.py` now fails (exit 2) when fewer than `--total` questions are
    available unless `--allow-fewer` is given.
  - `README.md` and `docs/USAGE.md` contain the full chain: videos → local video subset → frames →
    fixed-92 annotations → inference → metrics → diagnostics; the 300-question chain is explicit and
    documents the 60-video prerequisite.
- **Verified**: 92 IDs → 10 videos / 92 questions (22/24/22/24); 300 IDs → 60 videos / 300 questions
  (75 per type). No synthetic records were created.

## A5. `plot_ablation.py --output`

- **Problem**: `fig.savefig()` used the module default path, so `--output` was ignored and the
  documented command failed when `experiments/ablation/` did not exist.
- **Fix**: saves to `args.output`, creates the parent directory, prints the actual path; also accepts
  the new `ablation_rows` summary structure.
- **Test**: `tests/test_plot_ablation.py` (custom output path, parent creation, legacy rows key, empty
  summary fails).

## A6. `summarize_ablation.py` layout and errors

- **Problem**: expected `metrics/`, `diagnostics/`, `configs/` under one directory, which does not match
  the repository layout; missing inputs silently produced empty tables.
- **Fix**: repository layout by default (`results/metrics/`, `results/summaries/diagnostics/`,
  `configs/`, meta fallback in `results/predictions/`); explicit warnings for missing diagnostics or
  config/meta; non-zero exit when no valid runs or the reference is absent; writes
  `ablation_summary.{json,csv,md}` and separate `expanded_summary.{json,csv,md}`.
- **Tests**: `tests/test_summarize_ablation.py` covers normal reading, missing diagnostics, empty
  metrics directory, all-missing diagnostics, missing reference, and different question sets.

## A7. Different-subset pairing

- **Problem**: the 300-question run was paired with the 92-question reference on 50 shared questions
  and presented in the same table.
- **Fix**: runs whose question set differs from the reference are reported only in the expanded table;
  `pair_status = different_sample_set`, `mean_delta/improved/worsened/wilcoxon_p = null`, and the shared
  count is recorded without being interpreted. `ablation_summary.md` now includes `num_questions` and
  `paired_vs_reference_n`.
- **Regenerated**: `results/summaries/ablation_summary.{json,csv,md}` (5 runs, all 92 questions),
  `results/summaries/expanded_summary.{json,csv,md}` (1 run, 300 questions). Official metric values are
  unchanged and were re-checked.

## A8. Local absolute paths

- **Problem**: `docs/EXPERIMENT_LOG.md`, `docs/ENVIRONMENT.md`, `PUBLICATION_AUDIT.md`, and
  `REORGANIZATION_REPORT.md` contained local absolute paths or claimed none existed.
- **Fix**: replaced with placeholders (`<workspace>`, `<conda-env>`, `<repository-root>`,
  `<source-workspace>`); added a redaction note to the two environment/log documents; corrected the
  audit statements.
- **Test**: `tests/test_readme_commands.py::test_no_absolute_local_paths_in_public_docs` scans README,
  `docs/*.md`, and the two audit reports.

## A9. Official vs custom metrics

- **Problem**: the README ablation table mixed official EG-F1/IoU-F1 with custom diagnostics.
- **Fix**: README now has an official-metrics table and a separate **custom diagnostics** table
  (first-30-second predictions, no-overlap rate, mean best IoU), with definitions. `FINAL_REPRODUCTION_REPORT.md`
  carries a note that the diagnostic/run columns are not paper metrics.

## Tests and verification

| Condition | Result |
|---|---|
| Fresh copy, no `official_repo` | **31 passed, 9 skipped** |
| With `official_repo` mounted (temporary junction) | **119 passed, 2 skipped** |
| New tests | annotation converter (9), plot output (3), summary layout/subsets (6), README commands/paths (5), published-result structure (2 added) |

Commands re-verified in a temporary copy:

- `build_inference_annotations.py`: 92 IDs → 10 videos/92; 300 IDs → 60 videos/300; all IDs found.
- `build_video_subset.py`: 60 test videos selected from the official annotations.
- `build_expanded_set.py`: 300 questions from 60 videos with seed 20261030.
- `summarize_ablation.py`: 5 ablation rows + 1 expanded row, separated.
- `plot_ablation.py --output`: writes to the requested path.
- Official evidence metrics recomputed from shipped predictions for C (92) and expanded (300):
  all EG-F1/IoU-F1 values identical.

## What is now reproducible from the documentation

1. Dataset audit and annotation statistics (official annotations required).
2. Frame extraction and verification (videos required).
3. Fixed 92-question annotations and the 300-question stratified set (official annotations + frames).
4. Inference (Qwen2.5-VL-3B weights and GPU required), official evidence metrics (BGE-M3 + official code).
5. Diagnostics, summaries, and the ablation figure from shipped or regenerated results.
6. Tests in both modes.

## Remaining external dependencies and limitations

- Official repository, annotations, videos, Qwen weights, and BGE-M3 are not shipped.
- Answer-side metrics still require an OpenAI-compatible judge key; not computed.
- The 526-question sampling pool is still not derivable from shipped files; it is documented as such in
  `docs/RESULTS_PROVENANCE.md`.
- Figures 1, 3, 4, 5 (and the three-panel overview) remain static outputs; their data files are shipped,
  but their original plotting scripts were not part of the curated repository.
- `results/metrics/*.json` retain the original `source_file` paths; the mapping to `results/predictions/`
  is documented.
- The official EG-Reasoner was not trained or evaluated.
