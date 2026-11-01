# Reorganization Report

Source workspace: `<source-workspace>` (kept intact; nothing moved or deleted)
Target repository: `<repository-root>`
Date: 2026-11-01

## 1. Audit method

- Listed the source tree without recursing into `.venv`, model weights, videos, or extracted frames.
- Read the headers and dependencies of the key scripts (`audit_pipeline.py`, `build_expanded_set.py`,
  `analyze_temporal_bias.py`, `diagnose_predictions.py`, `summarize_ablation.py`) to classify them as
  project-authored rather than official code.
- Checked the official clone's Git state and license: commit `0ca6b53`, no tracked modifications,
  Apache-2.0 declared only at `EG-Reasoner/LICENSE`.
- Scanned reports and result files for personal information, local paths, credentials, and oversized files.

## 2. Source classification

| Class | Location in source | Decision |
|---|---|---|
| Official implementation | `official_repo/` (2.2 GB with videos/frames) | Not copied; clone link + runtime import |
| Personal scripts | `scripts/` (23 files) | 21 copied; 2 subset-builder scripts added during fixes; presentation/QA helpers excluded |
| Personal tests | `tests/` (10 modules + conftest) | All copied with official-repo guards; 4 new self-contained modules added → 14 modules + conftest in the public repo |
| Configs | `experiments/ablation/configs/` (5 JSON) | Copied to `configs/` |
| Experiment results | `experiments/` (37 MB) | Curated copy only |
| Reports | `docs/` (9 Markdown) | All copied; 3 docs added (`USAGE.md`, `RESULTS_PROVENANCE.md`, `FIX_RECORD_A1_A9.md`) |
| Figures | `experiments/metric_sensitivity/`, `experiments/ablation/`, `deliverables/assets/` | 7 copied to `results/figures/` |
| Interview/presentation material | `deliverables/`, `PRESENTATION_OUTLINE.md`, `README_LOCAL.md` | Excluded (see §4) |
| Environment / caches | `.venv/` (GB-scale), `.pytest_cache/`, `.claude/` | Excluded |
| Dataset / models / media | `official_repo/data/`, `models/` | Excluded |

## 3. Files copied

| Destination | Count | Notes |
|---|---:|---|
| `docs/` | 12 | 9 reports + `USAGE.md` + `RESULTS_PROVENANCE.md` + `FIX_RECORD_A1_A9.md` |
| `scripts/` | 23 | analysis, subset builders, preprocessing, inference, diagnostics, aggregation |
| `tests/` | 15 | `conftest.py` + 14 test modules (9 guarded official-dependent, 5 self-contained) |
| `configs/` | 5 | A, A2, B, C, D configurations |
| `results/predictions/` | 14 | 7 runs × (predictions + run metadata) |
| `results/metrics/` | 7 | official evidence-metric outputs |
| `results/summaries/` | 20 | audit, ablation + expanded, bootstrap, truncation, token comparison, sensitivity, environment, checks |
| `results/summaries/diagnostics/` | 9 | per-run diagnostics and temporal-bias analyses |
| `results/figures/` | 7 | ablation, expanded, localization, token, sampling, sensitivity |
| `results/subsets/` | 3 | fixed 92 IDs, fixed 92 IDs with video/type, stratified 300 |
| Root | 9 | `README.md`, `LICENSE`, `NOTICE.md`, `PUBLICATION_AUDIT.md`, `REORGANIZATION_REPORT.md`, `FINAL_RELEASE_CHECKLIST.md`, `requirements.txt`, `requirements-inference.txt`, `.gitignore` |

Count reconciliation: docs 12 + scripts 23 + tests 15 + configs 5 + results 60 (predictions 14, metrics 7, summaries 20, diagnostics 9, figures 7, subsets 3) + root 9 = **124 tracked files**, about 6.4 MB.

## 4. Excluded files and reasons

| Excluded | Reason |
|---|---|
| `.venv/`, `.pytest_cache/`, `__pycache__/` | Local environment and caches |
| `.claude/` | Local agent session configuration |
| `official_repo/` | Third-party code (Apache-2.0, license scope unclear at repo root); not redistributed |
| `official_repo/data/{videos,frames}`, `models/` | Large media and model weights |
| `experiments/downloads/` | Duplicate copies of the official annotations |
| `experiments/paper.html`, `paper_text.txt` | arXiv page/text; not redistributed |
| Oracle full prediction/metric files (14 MB) | Large, and only an oracle sanity check; aggregate kept as `oracle_summary.json` |
| Logs (`*.log`, `videos_tar_index.json`) | Contain local absolute paths and machine details |
| `deliverables/EG_VQA_QA_PREPARATION.md` | Interview preparation material |
| `deliverables/EG_VQA_SPEAKER_NOTES.md` | Personal speech script |
| `PRESENTATION_OUTLINE.md` | Talk delivery outline |
| `deliverables/*.pptx`, `*.pdf`, `*.docx` | Presentation deck and personal introduction with name/affiliation |
| `deliverables/README.md`, `SOURCE_DATA_MAP.md`, `preview/`, `.docxbuild/` | Presentation packaging; provenance recreated in `docs/RESULTS_PROVENANCE.md` |
| `README_LOCAL.md` | Superseded by the public `README.md` and `docs/USAGE.md` |
| `scripts/check_project.py`, `run_all.sh` | Tied to the private workspace's deliverable checks; not portable |

No experimental result was deleted from the source workspace; only the public copy is curated.

## 5. Official code vs personal code

- `official_repo/evaluation/*`, `official_repo/preprocess/*`, `official_repo/EG-Reasoner/*` are official
  and are not present in this repository.
- All files under `scripts/` are project-authored. `extract_frames.py` wraps the official preprocessor
  by setting `video_clip.TIMESTAMP_FONT_PATH`; it does not modify official files.
- All files under `tests/` are project-authored, except that they import official modules at runtime.
- Result files were produced by the official evidence-metric script driven by project predictions.

## 6. Result provenance

Each reported number maps to a file under `results/`; see `docs/RESULTS_PROVENANCE.md`.
Headline values were re-verified from the JSON files during packaging:

- 8/16/32 frames: EG-F1 (0.3,0.5) = 0.0234 / 0.0479 / 0.0686.
- 300 questions: EG-F1 (0.3,0.5) = 0.0510, 95% CI [0.0358, 0.0680].
- Oracle: 0.999654 over 2,889 questions.
- Token comparison: complete tags 35 → 36/92; paired 0 improved / 1 worsened / 91 unchanged.

## 7. Test execution

| Condition | Result |
|---|---|
| Target repository with no `official_repo/` | `31 passed, 9 skipped` |
| Target repository with a temporary junction to the official clone | `119 passed, 2 skipped` |

The 2 skips are BGE-M3 integration tests that need the 2.27 GB semantic model. No test was weakened or
removed to improve the result. The 9 official-dependent test modules skip with an explicit message
telling the user to clone the official repository. Review fixes are recorded in
`docs/FIX_RECORD_A1_A9.md`.

## 8. Security and privacy checks

- No credentials, tokens, or API keys found.
- No personal names, university name, or interview language in shipped files.
- Historical logs are redacted: absolute local paths were replaced with placeholders
  (`<workspace>`, `<conda-env>`). No personal Windows user paths, personal names, or credentials remain.
- No videos, frames, model weights, `.venv`, or `.claude` directory.
- Largest file is under 1 MB; working tree ≈ 6.4 MB.
- All README relative links resolve; all JSON files parse; all Python files compile.

## 9. Git

- Repository initialized locally on branch `main`; no remote was added and no push was performed.
- Commit author uses a neutral placeholder identity (`EG-VQA-Reproduction <noreply@example.com>`);
  no personal account email is embedded. Set your own identity and rewrite the author if the public
  history should carry it.

| Commit | Actual role |
|---|---|
| `e0024d0` | Initial commit: the curated repository (scripts, reports, results) |
| `f32860f` | Recorded the initial commit hash in the two audit reports |
| `bc6d47c` | Review fixes A1–A9 (docs numbers, input builders, plot/summary scripts, tests, path redaction) |
| `4933ad1` | Recorded the review-fix commit hash |
| `0d0d297` | Final cleanup: normalized 7 `source_file` fields in `results/metrics/`, clarified LICENSE/NOTICE boundary, updated provenance/audit, removed hard-coded drive paths from 3 scripts, genericized the path detector in one test (15 files changed) |
| `b8513cc` | Recorded the final-cleanup commit hash in `PUBLICATION_AUDIT.md` and this report (2 files) |
| `b8ec29e` | Final documentation review: revised this report, added `FINAL_RELEASE_CHECKLIST.md`, updated publication audit |

- Working tree at `b8ec29e`: clean. Later hash-recording commits are bookkeeping only.

### Git history note

The current tree and the latest commits are redacted, but **early commits still contain the pre-redaction
path strings** in `docs/EXPERIMENT_LOG.md` and, before `0d0d297`, a workspace-path literal inside
`tests/test_readme_commands.py`. These strings are local directory names only; the full history was
scanned and contains **no usernames, personal email addresses, phone numbers, API keys, or credentials**.
If the repository is published with full history, either rewrite history (for example with
`git filter-repo`) or publish a fresh initial commit. This report does not perform that rewrite because
it is destructive and requires the owner's decision.

## 10. Open items for manual confirmation

| Item | Status |
|---|---|
| Author name and affiliation in `README.md` | **Pending** — intentionally omitted; owner decides |
| Publishing prediction files with dataset ground truth (CC-BY-4.0) | **Reviewed in final audit** — all 7 files contain answers/evidence, no personal data, keys, or absolute paths; publication is acceptable with the attribution already in `NOTICE.md` and README, but the owner confirms |
| Question-id subsets (`results/subsets/`) | **Reviewed** — IDs, video ids and type labels only; no answers; owner confirms |
| Official repository Apache-2.0 scope for `evaluation/` and `preprocess/` | **Pending** — the repository deliberately does not vendor official code |
| Manual semantic spot-check of model outputs | **Partially done** — automated scan for emails, phones, keys, absolute paths found none; a human content check is still recommended before publishing |
| Rewrite Git history to purge early path strings | **Pending** — destructive; owner decides |
| Use a clean initial commit for release | **Pending** — recommended if full history is not rewritten |
