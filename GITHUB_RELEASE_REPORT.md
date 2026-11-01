# GitHub Release Report

Date: 2026-11-01
Status: public-release snapshot prepared locally. No remote was created and no push was performed.

## 1. Directories

| Role | Directory |
|---|---|
| Reviewed development repository (unchanged) | `EG-VQA-Reproduction` (sibling of this release directory) |
| Backup of the reviewed repository, including its Git history | `EG-VQA-Reproduction_backup-2026-11-01` |
| Public release directory | `EG-VQA-Reproduction-public` |
| Superseded first export (kept, not for publication) | `EG-VQA-Reproduction-public-draft-20261101` |

All directories are siblings under the same parent. The original source workspace remains untouched.

## 2. How the public snapshot was produced

1. The reviewed repository was backed up with its `.git` directory.
2. Its `HEAD` (`c8ba23d`) was exported with `git archive`, so **no Git history is inherited**.
3. Five result-metadata files still contained local absolute paths after export (environment reports,
   frame-check report, and the tokenizer path in the two truncation analyses). Those fields were
   replaced with placeholders in the public copy only. No prediction or metric file was touched.
4. A new Git repository was initialized, and a clean initial commit was created.

## 3. Git

| Item | Value |
|---|---|
| Branch | `main` |
| Initial public commit | `3f14066ba05712c906d7352b3aa4e8384ad6b368` |
| Initial commit message | `Initial public release: EG-VQA reproduction and experimental analysis` |
| Commits at initial release | 1 |
| Tracked files at initial release | 124 |
| Tracked files including this report | 125 |
| Remote | none |
| Push | not performed |

The initial commit's tree differs from the reviewed tree only in the five sanitized metadata files.

## 4. Content preservation

A blob-level comparison against the reviewed `HEAD` found:

- 124 paths present in both trees; no missing or extra files.
- **119 files byte-identical** (all predictions, all metrics, scripts, tests, configs, figures,
  reports, README, LICENSE, NOTICE).
- **5 files differ only in sanitized metadata**:
  - `results/summaries/env_report_base.json` — executable path and disk keys replaced.
  - `results/summaries/env_report_inference.json` — executable path and disk keys replaced.
  - `results/summaries/frame_check_test.json` — video/frame paths made repository-relative.
  - `results/summaries/truncation_analysis.json` — tokenizer path replaced.
  - `results/summaries/truncation_analysis_tok512.json` — tokenizer path replaced.

Explicit check: **all files under `results/predictions/` and `results/metrics/` have identical SHA-256
hashes to the reviewed versions.** No experimental value was modified.

## 5. Test results

| Condition | Result |
|---|---|
| Public repository, no official EG-VQA clone | **31 passed, 9 skipped, 0 failed** |
| Public repository copied to a temporary directory with a junction to the official clone | **119 passed, 2 skipped, 0 failed** |

The 9 skips are official-repository-dependent test modules (they print an explicit reason); the 2 skips
are BGE-M3 integration tests that need the semantic model weights.

Additional checks in the public repository:

- README commands and flags validated by `tests/test_readme_commands.py`.
- 21 relative Markdown links checked; 0 broken.
- Headline numbers re-checked against `results/` (all passed).

## 6. Security and privacy checks

| Check | Result |
|---|---|
| Windows drive-letter paths / POSIX local paths | none |
| API keys, tokens, private keys, password assignments | none |
| Personal names, university, phone numbers, personal email | none |
| Email strings | only the neutral commit identity `noreply@example.com` in audit docs |
| Videos, frames, model weights, `.venv`, caches, `.claude` | none tracked |
| Largest tracked file | 0.81 MB (`expanded_C32_evidence_metrics.json`) |
| Total tracked size | about 6.4 MB before this report |

## 7. License and attribution checks

- `LICENSE`: MIT applies only to original code and text; explicitly excludes the dataset,
  annotation-derived content in `results/`, and third-party components.
- `NOTICE.md`: official repository is Apache-2.0 and **not redistributed**; dataset is CC-BY-4.0 with
  attribution; Qwen2.5-VL-3B-Instruct (Apache-2.0) and BGE-M3 (MIT) weights are not included;
  `results/` files are explicitly not relicensed under MIT.
- No official source code is present in the public snapshot.
- Prediction files contain dataset question/answer/evidence fields; this is disclosed in README §9 and
  `NOTICE.md` §2/§6.

## 8. Requirements coverage of this release

- Only files from the reviewed `HEAD` are present (plus this report).
- README, LICENSE, NOTICE, configs, scripts, tests, metrics, predictions, figures, and necessary docs
  are included.
- No model weights, videos, virtual environments, caches, keys, personal contact details, or local
  absolute paths are included.

## 9. Remaining manual items before publishing

1. Create the GitHub repository and remote, then push (not performed here).
2. Decide whether to add the author's name/affiliation to `README.md` (currently omitted).
3. Confirm the CC-BY-4.0 redistribution of dataset-derived prediction files is acceptable; attribution
   is already present.
4. Optional manual semantic spot-check of model outputs before publication.
5. Decide whether the observed 526-question sampling pool and static figures (without plotting scripts)
   need further documentation.
6. Confirm the official repository's Apache-2.0 scope if you later wish to vendor `evaluation/` or
   `preprocess/`.

## 10. Notes

- This report itself was added in a second commit after the clean initial commit, so it can record the
  initial commit hash. The initial commit remains a clean snapshot of the reviewed tree.
- The superseded draft directory contains the earlier export with unsanitized metadata; do not publish it.
