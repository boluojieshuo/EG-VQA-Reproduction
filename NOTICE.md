# Third-Party Notices

This repository builds on the EG-VQA benchmark and on open models. Their licenses differ from this
repository's MIT license. Nothing below is relicensed by this project.

## 1. EG-VQA official implementation

- Repository: https://github.com/HCPLab-SYSU/EG-VQA
- Commit used during development: `0ca6b53c8d3aa998eaf24f903b0f6cb6b8ab88f5`
- License: Apache License 2.0, declared in `EG-Reasoner/LICENSE` of the official repository.
  The official repository root does not contain a separate LICENSE file.
- **No official source code is redistributed in this repository.** Users clone it themselves into
  `./official_repo`. The scripts here import it at runtime.
- Copyright remains with the EG-VQA authors (Huang, Chen, Chen, Liu, Lin).

## 2. EG-VQA dataset

- Source: https://huggingface.co/datasets/lphuang33/EG-VQA
- License: CC-BY-4.0 (as declared by the dataset card).
- The dataset annotations (train/test JSON) are **not** redistributed as standalone files here.
- Files under `results/predictions/` contain, for evaluation purposes, the ground-truth question,
  answer and evidence fields of the evaluated test samples, alongside model responses. Files under
  `results/metrics/` contain per-sample metric results derived from those annotations.
  This is redistribution of a small subset of CC-BY-4.0 material **with attribution** to the EG-VQA
  authors and a link to the dataset. If you reuse these files, keep this attribution.
- Videos are not included. Obtain them from the official dataset, subject to its license and the terms
  of the original source datasets (ActivityNet Captions, YouCook2, HiREST).

## 3. Models

| Component | Model | License |
|---|---|---|
| Substitute video-language model | Qwen2.5-VL-3B-Instruct | Apache-2.0 |
| Semantic similarity | BAAI/bge-m3 | MIT |

Model weights are not included. Model outputs saved under `results/predictions/` are provided as
experimental evidence only.

## 4. Paper and website content

The arXiv paper, its HTML/PDF renders, the project page, and the official repository's README are not
redistributed. This repository links to them and reports only the numbers produced by this project's
runs. The paper's reported model scores are cited but not reproduced.

## 5. Python dependencies

Dependencies are installed from their own distributions and remain under their respective licenses.
See `requirements.txt` and `requirements-inference.txt`.

## 6. Experimental result files

Files under `results/` are outputs of this project's runs, not source code:

- `results/predictions/*.json` contain model responses plus ground-truth question, answer and evidence
  fields for the evaluated samples. Those annotation fields remain CC-BY-4.0 material, attributed to
  the EG-VQA authors above; reuse them under CC-BY-4.0 with attribution.
- `results/metrics/*.json` contain metric values and per-sample metric outputs derived from those
  annotations; the annotation-derived parts carry the same CC-BY-4.0 terms.
- Figures under `results/figures/` plot these results and are provided for research documentation.

None of these result files are relicensed under this repository's MIT license. Metric values and model
responses are provided as experimental evidence; no warranty is made about their fitness for reuse.
