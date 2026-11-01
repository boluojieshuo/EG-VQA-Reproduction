# EG-VQA 复现计划

> 生成时间：2026-10-29
> 官方仓库：https://github.com/HCPLab-SYSU/EG-VQA
> 本地克隆：`official_repo/`，commit `0ca6b53c8d3aa998eaf24f903b0f6cb6b8ab88f5`（2026-10-04）
> 论文：https://arxiv.org/abs/2606.24797（页面已确认存在，标题与给定论文一致）
> 数据集：https://huggingface.co/datasets/lphuang33/EG-VQA（CC-BY-4.0）

## 0. 结论摘要

| 项目 | 可行性 |
|---|---|
| 标注数据 | ✅ 已在仓库中，与 HF 官方文件 SHA-256 完全一致 |
| 原始视频 | ✅ HF 数据集提供 `videos.tar`（13.09 GB），支持 HTTP Range 按需抽取 |
| 视频预处理 | ✅ 可用官方脚本，需将 Linux 字体路径做最小适配 |
| 答案指标 | ⚠️ 需外部 LLM judge（OpenAI 兼容 API key），逻辑可离线单测 |
| 证据指标（IoU-F1 / EG-F1） | ✅ 可在本机 CPU/GPU 运行，需下载 BGE-M3（约 2.3 GB） |
| 官方 EG-Reasoner 训练 | ❌ 8 GB 显存 + Windows 不可行（需 4×GPU + vLLM + FSDP + Linux） |
| 官方 checkpoint 推理 | ❌ 无 checkpoint；7B + vLLM 需要 ≥16 GB 显存 |
| 小模型替代基线推理 | ⚠️ 可行但需明确标注为替代基线，不是论文模型 |

## 1. 官方流程逐项核对（对照 README）

README 描述的流程与当前代码一致，逐项确认：

| README 步骤 | 代码位置 | 当前版本是否成立 | 备注 |
|---|---|---|---|
| 获取 train.json / test.json | `data/train.json`, `data/test.json` | ✅ 已随仓库提供 | 也可从 HF 下载，二者完全相同 |
| 获取原始视频 | 无脚本，README 要求用户自行放到 `data/videos/` | ✅ 但 HF 实际提供 `videos.tar` | README 未提及 `videos.tar`，属于仓库文档滞后 |
| 视频帧提取 | `preprocess/video_clip.py` | ✅ | 默认每视频均匀采样 32 帧，帧上叠加时间戳 |
| 训练 Parquet 转换 | `preprocess/prepare_train_parquet.py` | ✅ | 只转训练集，shard=500 |
| 模型训练 | `EG-Reasoner/examples/train_eg_vqa.sh` + `eg_vqa.yaml` | ✅（需 4 GPU / Linux） | veRL + FSDP + vLLM |
| checkpoint 合并 | `EG-Reasoner/scripts/model_merger.py` | ✅ | 支持 FSDP / DDP+FSDP，不支持 FSDP+TP |
| 模型推理 | `evaluation/evaluate.py` | ✅（需 vLLM） | 支持 `.partial.json` 断点续跑 |
| answer metrics | `evaluation/answer_metrics.py` | ✅（需 API key） | relaxed 0/0.5/1，strict 只算 1 |
| evidence metrics | `evaluation/evidence_metrics.py` | ✅ | IoU-F1 四阈值；EG-F1 三组阈值 |

### 1.1 发现的文档/实现差异（记录，不擅自修改官方代码）

1. **README 说视频需自行从原始数据源下载，但 HF 数据集实际提供 `videos.tar`。** 以 HF 为准可显著降低获取成本。
2. **训练 reward 与评估指标不是同一套计算。**
   - 训练（`score_function/evidence_reward.py`）：匈牙利匹配代价为 `0.5*IoU + 0.5*Sim`，最终 HES = `0.5*soft_hes + 0.5*hard_hes`。
   - 评估（`evaluation/evidence_metrics.py`）：IoU-F1 只在 IoU 矩阵上做匈牙利匹配；EG-F1 在 `IoU≥τ_iou 且 Sim≥τ_sim` 的门控矩阵上做匹配，且**没有 soft 项**。
   - 因此"HES reward" ≠ "EG-F1"。复现报告需分开陈述。
3. **训练配置与论文附录 D 不一致（重要）**：
   - 论文附录 D：`λ_f / λ_e / λ_a = 0.1 / 0.6 / 0.3`；语义模型 **all-MiniLM-L6-v2**。
   - 仓库 `eg_vqa.yaml`：`format_weight=0.1, evidence_weight=0.3, accuracy_weight=0.6`（evidence 与 accuracy 权重**互换**）；语义模型 **BGE-M3**。
   - 论文 Eq.(4)：`R_evi = R_soft + R_EG-F1`（相加）；实现为 `0.5*soft + 0.5*hard`（平均）。
   - 论文附录 B.2 的软匹配权重是 `IoU·Sim`；实现用 `0.5·IoU + 0.5·Sim`。
   - 完整逐项对照见 `docs/METRIC_REVIEW.md`。
4. **训练配置的 reward 阈值**：`eg_vqa.yaml` 中 `iou_threshold: 0.3, sim_threshold: 0.5`；而 `eg_vqa_reward.py` 的函数默认值是 `0.5/0.75`。实际训练以 YAML 传参为准。
4. **零长度证据区间**：官方 `parse_evidence` 将 `start >= end` 标记为 invalid，但 ground truth 中确实存在 14 个零长度区间（训练 12、测试 2，见数据审计），它们会成为永远无法被匹配的 GT，压低 recall。需在分析中单独列出。
5. **`evidence_metrics.compute_iou` 与 `evidence_reward.compute_iou` 公式等价**（union 取 `max(end)-min(start)`，二者一致），但一个是逐对计算，一个走矩阵索引；无差异。
6. **Windows 适配点**：官方 `preprocess/video_clip.py` 硬编码 Linux 字体路径，缺失时回退到极小位图字体。**不改官方文件**，由 `scripts/extract_frames.py` 包装注入可用字体（`EG_VQA_FONT` 可覆盖）；已用字节级比对验证与先前抽取结果一致。

## 2. 任务分类

### A. 可以在当前电脑完成（无需下载视频、无需 GPU）

- 仓库静态审查（已完成）。
- 环境检查脚本 `scripts/check_env.py`（已完成）。
- 数据审计 `scripts/audit_data.py` → `experiments/data_audit.json`（已完成）。
- 官方指标函数的单元测试（不依赖 BGE-M3 权重的纯函数部分）。
- 官方指标实现与论文公式的逐项对照。
- 预处理逻辑的 pytest 测试（用合成视频测试"逻辑"，明确标注合成，不冒充真实数据）。
- 推理输出解析器 `evaluate.py::parse_model_response` 的测试。
- Parquet 转换逻辑测试（用合成帧目录）。

### B. 需要下载公开数据后才能完成

- 真实视频的解码与帧提取（`scripts/fetch_videos_from_tar.py` 按需抽取少量视频）。
- 真实测试样本的端到端推理 + 评估 smoke test。
- BGE-M3 语义相似度的真实集成测试（模型约 2.3 GB，CPU 可跑）。

### C. 可能需要外部 GPU / 大显存

- 官方 EG-Reasoner 训练：`Qwen2.5-VL-7B-Instruct`，`n_gpus_per_node=4`，`global_batch_size=16`，`rollout.n=8`，`max_prompt_length=7000`，FSDP full-shard + CPU offload，vLLM rollout `tensor_parallel_size=2`。**8 GB 单卡不可行**。
- 官方 checkpoint 推理：vLLM bf16 加载 7B 视觉语言模型，通常需要 ≥16 GB 显存（保守估计 16–20 GB，含 KV cache 与 32 帧图像 token）。
- 结论：训练与论文模型推理都需要外部 Linux GPU（≥1×24 GB 可做推理；训练按官方配置需 4×≥40 GB）。

### D. 当前无法确认能否完成

- 官方 checkpoint 未公开发布（仓库和 HF 均未见 `EG-Reasoner` 权重）。需向作者确认。
- 论文表格中的具体数值无法在无 checkpoint 的情况下复核。
- 答案指标依赖的 judge 模型（默认 `gemini-2.5-pro`）需要 API key，本环境未提供。
- 13 GB `videos.tar` 全量下载是否在磁盘/带宽预算内：当前 D 盘剩余 53.8 GB，可容纳，但按"先小规模"原则只抽取少量视频。

## 3. 分阶段执行计划

| 阶段 | 内容 | 状态 |
|---|---|---|
| A | 仓库/论文/环境检查 | ✅ 完成 |
| B | 数据审计 + 环境固化 | ✅ 完成 |
| C | 预处理与评估代码测试 | ✅ 完成（测试套件 + oracle 验证 + 敏感性分析） |
| D | 真实小规模推理（替代基线，明确标注） | ✅ 完成（92 题，Qwen2.5-VL-3B 4-bit） |
| E | 训练可行性评估 / 极小规模实验 | ✅ 完成可行性评估；训练未执行（硬件限制） |
| F | 汇总报告 | ✅ `docs/REPRODUCTION_SUMMARY.md` |

> 最终状态见 `docs/REPRODUCTION_SUMMARY.md`；本文件的 A/B/C/D 分类仍是复现边界说明。

## 4. 资源预算

| 资源 | 数值 |
|---|---|
| GPU | RTX 4060 Laptop，8188 MiB，驱动 560.94，CUDA 12.6 |
| 磁盘 | D: 剩余 53.8 GB；C: 剩余约 28 GB |
| 视频 | 按需抽取，目标 9–12 个视频（每来源 3–4 个），并记录来源与大小 |
| BGE-M3 | 约 2.3 GB（`pytorch_model.bin`），CPU 推理 |
| 模型替代基线 | 优先考虑 ≤3B 的 VLM + 4-bit 量化；需实测显存，且明确标注"替代基线" |

## 5. 验收标准（本复现能做到什么）

- ✅ 能证明：官方指标实现可运行、可解释、有单元测试；数据规模与论文一致；预处理逻辑可用于真实视频。
- ✅ 能证明：在少量真实样本上，一个**明确标注为替代品**的模型可以产出符合官方 schema 的输出，并被官方评估脚本处理。
- ❌ 不能声称：复现了论文的 EG-F1 / accuracy 数值。
- ❌ 不能声称：复现了 EG-Reasoner 训练。
