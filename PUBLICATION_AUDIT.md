# Publication Audit

Purpose: record what was kept for the public `EG-VQA-Reproduction` repository, what was excluded, and
which items still need a human decision before publishing.

## 1. Excluded: interview and personal-presentation material

The following files exist in the private workspace (`<source-workspace>`) but were **not** copied:

| File | Reason |
|---|---|
| `deliverables/EG_VQA_QA_PREPARATION.md` | 20 interview questions and answers; personal preparation, no research value |
| `deliverables/EG_VQA_SPEAKER_NOTES.md` | Per-slide speech script; personal presentation coaching |
| `PRESENTATION_OUTLINE.md` | Talk outline with timing and delivery tips |
| `deliverables/EG_VQA_Research_Presentation.pptx` / `.pdf` | Presentation deck containing name and affiliation |
| `deliverables/EG_VQA_Project_Introduction.docx` / `.md` | Personal project introduction with name, university, and application framing |
| `deliverables/README.md`, `deliverables/SOURCE_DATA_MAP.md` | Packaging notes for the personal material set; provenance was recreated as `docs/RESULTS_PROVENANCE.md` |
| `deliverables/preview/`, `deliverables/.docxbuild/` | Slide previews and Node build dependencies |
| `deliverables/build_pptx.py`, `sync_notes.py`, `check_deliverables.py`, `build_charts.py` | Presentation authoring/QA tooling, not part of the research pipeline |

No research result was removed with these files. Figures used in the README were copied to
`results/figures/`.

## 2. Preserved: research and engineering material

| Category | Files |
|---|---|
| Reports | `docs/FINAL_REPRODUCTION_REPORT.md`, `ABLATION_REPORT.md`, `RESULTS_ANALYSIS.md`, `METRIC_REVIEW.md`, `TRAINING_REVIEW.md`, `ENVIRONMENT.md`, `EXPERIMENT_LOG.md`, `REPRODUCTION_PLAN.md`, `REPRODUCTION_SUMMARY.md`, `USAGE.md`, `RESULTS_PROVENANCE.md`, `FIX_RECORD_A1_A9.md` |
| Scripts | 23 files under `scripts/` (audit, subset builders, preprocessing wrapper, inference, diagnostics, aggregation, plotting) |
| Configs | 5 ablation JSON configs |
| Tests | 14 test modules + `conftest.py` |
| Results | 7 runs (7 prediction files + metadata), 7 official metric files, summaries, diagnostics, figures, question-id subsets |
| Provenance | `docs/RESULTS_PROVENANCE.md`, `results/summaries/*` |

The experiment log keeps failed runs and fixes (sample-set drift, GPU process contention, missing
`--overwrite`, output truncation). No failure was deleted.

## 3. Official code vs personal code

| Item | Classification | Treatment |
|---|---|---|
| Official EG-VQA repository (`official_repo/`) | Third-party, Apache-2.0 declared at `EG-Reasoner/LICENSE` | **Not copied.** Users clone it into `./official_repo`. Scripts import it at runtime. |
| `scripts/extract_frames.py` | Personal wrapper around the official preprocessor | Included; it sets the font path without editing official files |
| `scripts/*.py` (other) | Personal experimental/analysis code | Included |
| Modifications to official code | None at final state | Official repository had no tracked changes; verified with `git diff` |

The official repository root has no LICENSE file; only `EG-Reasoner/LICENSE` (Apache-2.0). Because the
license scope is not fully explicit, this repository takes the conservative route and does **not**
redistribute official source code.

## 4. Data and model artefacts

| Item | Status |
|---|---|
| Official `train.json` / `test.json` | Not copied; available in the official clone |
| Videos (`videos.tar`, extracted mp4/mkv) | Not copied |
| Extracted frames | Not copied |
| Model weights (Qwen2.5-VL-3B, BGE-M3) | Not copied |
| `results/predictions/*.json` | Included. These contain the evaluated samples' question/answer/evidence ground-truth fields (CC-BY-4.0) with attribution in `NOTICE.md` |
| `results/metrics/*.json` | Included; per-sample metric outputs derived from the same annotations |

Largest shipped file is under 1 MB; the working tree totals about 6.4 MB (124 files).

## 5. Privacy and secret scan

Scanned all shipped `.py`, `.md`, `.json`, `.sh` files for:

- API keys, tokens, passwords, bearer credentials: **no matches** (checked `sk-`, GitHub tokens, AWS keys,
  Slack tokens, private-key headers, password assignments)
- Personal names, university affiliation, interview language: **no matches**
- Personal Windows user paths and local workspace paths were found in the historical
  run log; they were replaced with placeholders (`<workspace>`, `<conda-env>`). No personal names,
  contact details, or credentials were present.
- `.claude/`, `.venv/`, `.pytest_cache/`, model/video files: **absent**
- Contact details: only the neutral commit identity `noreply@example.com` appears; no personal email or phone

`docs/EXPERIMENT_LOG.md` and reports retain the original workspace's relative paths
(`experiments/...`, `official_repo/...`) as historical run records; they contain no user directory.

## 6. License review

- Official code: Apache-2.0 (as declared inside `EG-Reasoner/`), not redistributed; attribution and
  link are provided in `NOTICE.md`.
- Dataset: CC-BY-4.0; attribution provided. Prediction files include a subset of annotation fields.
- Qwen2.5-VL-3B-Instruct: Apache-2.0; weights not redistributed.
- BGE-M3: MIT; weights not redistributed.
- This repository's original code and text: MIT (`LICENSE`). Result files under `results/` are **not**
  relicensed under MIT; annotation-derived content keeps CC-BY-4.0 terms (see `NOTICE.md` §6).

## 7. Claims check

The README and reports state, and the artifacts support, that:

- official EG-Reasoner was **not** trained and its checkpoint was **not** used;
- all model scores come from Qwen2.5-VL-3B-Instruct, 4-bit NF4;
- answer-side metrics were not computed;
- the project is an independent reproduction and analysis, not the official implementation;
- Claude Code assisted implementation; the author planned, configured, reviewed and analysed the work.

No statement claims reproduction of the paper's model or table values.

## 8. Items requiring human confirmation before publishing

1. **Author identity.** The README intentionally omits name and affiliation. Decide whether to add
   them for a personal showcase repository.
2. **Dataset-derived prediction files.** Publishing model outputs that include test-set answers and
   evidence is permitted by CC-BY-4.0 with attribution, but confirm this matches your intended use.
3. **Question-id subsets** (`results/subsets/`) are dataset-derived. They are IDs and type labels only,
   without answer text; confirm they may be published.
4. **Official license scope.** If you prefer to vendor `official_repo/evaluation` and
   `official_repo/preprocess` for out-of-the-box execution, confirm with the authors that Apache-2.0
   covers those directories. The current repository deliberately avoids this.
5. **Sample content.** Model outputs are derived from public instructional/cooking videos; spot-check
   `results/predictions/` before publishing if any source video contains personal data.
6. **Presentation materials.** If you later want the talk deck published, strip name/affiliation and
   presentation coaching first.

## 9. Post-review fixes

All findings A1–A9 from the pre-publication review were fixed without changing predictions or metric
values; details are in `docs/FIX_RECORD_A1_A9.md`. The fixed repository passes 31 tests (9 skipped)
without the official repository and 119 tests (2 skipped) with it mounted.

## 10. Git actions

- No remote repository was created; no `git push` was executed.
- A local Git repository is initialized on branch `main`.
- Initial commit: `e0024d0abb44ad96648277fe8ed17b2b82219b68`.
- Review-fix commit: `bc6d47cfd4ffa2a1d0c61bab90e42c4146e8c92b`.
- Final-cleanup commit: `0d0d297b15807af526cd22722638626f0f47bef6`.
- Documentation-review commit: `b8ec29e23a90d6b3edea6a02f81c442f99a46b09`.
- No remote, no push.
- Commit author uses a neutral placeholder identity; see `REORGANIZATION_REPORT.md` §9.
- **Git history note**: the working tree is clean, but commits `e0024d0` and `f32860f` still contain the
  pre-redaction path strings in `docs/EXPERIMENT_LOG.md` (no usernames, emails, or credentials). If the
  repository is published with full history, rewrite it before pushing (for example with
  `git filter-repo`) or publish a fresh initial commit. This was not done here because rewriting history
  is destructive and requires the owner's decision.

## 11. Final cleanup (2026-11-01)

- **Metrics metadata**: `source_file` in `results/metrics/*.json` now points to
  `results/predictions/<run>.json`. Only this field changed; canonical hashes of all `eg_f1`/`iou_f1`
  values were identical before and after (verified for all 7 files).
- **License boundary**: `LICENSE` and `NOTICE.md` §6 now state explicitly that result files under
  `results/` are not relicensed under MIT; annotation-derived content remains CC-BY-4.0.
- **Path scan**: no drive-letter or POSIX local paths remain in README/docs/audit reports. Scripts use
  environment-provided paths (`WINDIR`, `Path.home()`); the only hard-coded paths left are the official
  Linux font path and the `WINDIR`-derived Windows font directory.
- **Secret/contact scan**: no API keys, tokens, passwords, private keys, personal email, or phone numbers.
  The only email string is the neutral commit identity `noreply@example.com`.
- **Media/weights/caches**: none tracked; largest tracked file is 0.81 MB.
- **History caveat** remains as noted in §10.
