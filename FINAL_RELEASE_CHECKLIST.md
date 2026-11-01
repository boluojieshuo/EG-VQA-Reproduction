# Final Release Checklist

Repository: `EG-VQA-Reproduction`
Review date: 2026-11-01
Documentation-review commit: `b8ec29e23a90d6b3edea6a02f81c442f99a46b09`
Review type: read-only audit plus documentation corrections; no prediction or metric value was changed.
Git: branch `main`, no remote, no push.

## 1. Passed checks

| Area | Check | Result |
|---|---|---|
| Repository | Tracked file count matches the per-directory breakdown | **124 files** (root 9, docs 12, scripts 23, tests 15, configs 5, results 60) |
| Repository | Working tree clean after the checklist commit | verified at commit time |
| Results | Headline numbers match `results/` files | **16/16 checks passed** |
| Results | 92-question ablation values (0.0455 / 0.0234 / 0.0479 / 0.0686 / 0.0280) | match `ablation_summary.json` |
| Results | 300-question result 0.0510 and CI [0.0358, 0.0680] | match metrics + bootstrap files |
| Results | Oracle 0.999654; 14 zero-length + 7 beyond = 21 defects | match audit/oracle summaries |
| Results | Token groups 134.2 / 158.1 / 45.9 / 256.0 | match `truncation_analysis.json` |
| Results | `results/metrics/*.json` `source_file` resolved inside the repo | 7/7 resolved; metric hashes unchanged |
| Documentation | README commands exist and flags are supported | `test_readme_commands.py` passes |
| Documentation | README relative links resolve | yes |
| Documentation | README, LICENSE, NOTICE, PUBLICATION_AUDIT, REORGANIZATION_REPORT, RESULTS_PROVENANCE agree on test counts, file counts and commit roles | yes |
| Tests | Fresh copy, no official repo | **31 passed, 9 skipped, 0 failed** |
| Tests | With official repo mounted (temporary junction) | **119 passed, 2 skipped, 0 failed** |
| Security | API keys, tokens, passwords, private keys | none |
| Security | Personal email / phone / names / university | none (only neutral commit identity `noreply@example.com`) |
| Security | Absolute local paths in README/docs/audit reports | none |
| Security | Videos, model weights, caches, `.venv`, `.claude` | none tracked |
| License | Official code not redistributed; dataset CC-BY attributed; result files excluded from MIT | consistent in LICENSE/NOTICE/README |
| Claims | No claim of official EG-Reasoner training/inference or paper-table reproduction | verified |
| Git | No remote, no push, no history rewrite | verified |

## 2. Prediction files: public-release audit

All files are read-only inspected; none was modified.

| File | Samples | Contains GT answer/evidence | Personal data / keys / absolute paths | Recommendation |
|---|---:|---|---|---|
| `results/predictions/A_legacy_8_first.json` | 92 | 92 / 92 | none | Publish with CC-BY attribution |
| `results/predictions/A2_uniform_8.json` | 92 | 92 / 92 | none | Publish with CC-BY attribution |
| `results/predictions/B_uniform_16.json` | 92 | 92 / 92 | none | Publish with CC-BY attribution |
| `results/predictions/C_uniform_32.json` | 92 | 92 / 92 | none | Publish with CC-BY attribution |
| `results/predictions/C32_tok512.json` | 92 | 92 / 92 | none | Publish with CC-BY attribution |
| `results/predictions/D_uniform_8_timestamp.json` | 92 | 92 / 92 | none | Publish with CC-BY attribution |
| `results/predictions/expanded_C32.json` | 300 | 300 / 300 | none | Publish with CC-BY attribution |
| 7 × `*.meta.json` | run metadata | no annotations | model path is repo-relative; `is_paper_model=false` | Publish |

Notes:

- Each prediction record keeps the dataset's question, answer and evidence fields as ground truth,
  alongside the model response. This is CC-BY-4.0 material; attribution and terms are stated in
  `NOTICE.md` (§2, §6) and README §9.
- No API key, email address, phone number, absolute path, or personal identifier was found in any
  prediction or metadata file.
- The source videos are public instructional/cooking videos; a human semantic spot-check of model
  responses is still recommended before publication.

## 3. Unresolved issues

1. **Git history path strings.** The current tree and latest commits are clean, but early commits contain
   pre-redaction local directory strings in `docs/EXPERIMENT_LOG.md`, and commits before `0d0d297`
   contain one in `tests/test_readme_commands.py`. No usernames, emails, phone numbers, keys, or
   credentials are present. If history will be published as-is, readers can see local directory names.
2. **526-question sampling pool.** The number is documented from the original run but cannot be
   recomputed from shipped files alone.
3. **Static figures.** `fig1`, `fig3`, `fig4`, `fig5` and the three-panel overview are static outputs;
   their input data is shipped but their original plotting scripts are not.
4. **External dependencies.** Official annotations, videos, Qwen weights, BGE-M3 and the judge API key
   are not included; the official EG-Reasoner was not trained or evaluated.
5. **Author identity.** README intentionally omits name and affiliation.
6. **Official license scope.** The official repository's Apache-2.0 declaration is under
   `EG-Reasoner/LICENSE`; this repository conservatively does not vendor official code.

## 4. Recommendation

**Public release is recommended, with conditions.**

The repository is internally consistent, the reported numbers match the shipped artifacts, the
official metrics can be recomputed from the shipped predictions, tests pass, and no secrets, personal
data, media, or model weights are tracked. The conditions are:

- keep the CC-BY-4.0 attribution for dataset-derived content;
- decide on author identity before publishing;
- optionally rewrite history or use a clean initial commit if local directory strings in early commits
  are considered undesirable.

## 5. Clean initial Git commit

**Recommended if full history is not rewritten.**

The current history has six commits and includes the early path strings described in §3. Two acceptable
release options:

1. **Rewrite history** before publishing (e.g. `git filter-repo`) to remove the early strings; this is
   destructive and requires the owner's decision.
2. **Publish a clean initial commit**: create a fresh repository from the current working tree and make
   one commit. This is the simplest way to guarantee that no historical metadata is exposed, at the cost
   of losing the incremental commit history.

If the incremental history is valuable, rewriting history is preferable. If a clean public record is
more important, a fresh initial commit is preferable. Neither action was performed in this review.
