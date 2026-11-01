# EG-VQA 复现总结

> 日期：2026-10-30
> 官方仓库 commit：`0ca6b53c8d3aa998eaf24f903b0f6cb6b8ab88f5`
> 论文：arXiv 2606.24797（HTML 全文已核对）
> 数据集：HF `lphuang33/EG-VQA`（CC-BY-4.0），标注与仓库内文件 SHA-256 一致

## 1. 已完成且可复核的内容

| 工作 | 证据文件 |
|---|---|
| 环境采集（两套 Python 环境） | `experiments/env_report.json`、`experiments/env_report_egvqa.json` |
| 官方仓库审查（含 README 流程逐项核对） | `docs/REPRODUCTION_PLAN.md` |
| 论文公式 vs 官方实现逐项对照 | `docs/METRIC_REVIEW.md` |
| 标注一致性（与 HF 官方 JSON 哈希一致） | `docs/EXPERIMENT_LOG.md` |
| 数据审计（规模、类型、来源、时间戳合法性、泄漏） | `experiments/data_audit.json` |
| 按类型分布统计 | `experiments/annotation_stats.json` |
| 6+ 个真实视频（从 `videos.tar` 按需抽取） | `experiments/videos_manifest_*.json`、`experiments/video_check.json` |
| 官方预处理（帧提取）与校验 | `experiments/frame_check_{train,test}.json` |
| 训练 Parquet（15 行 smoke 子集） | `official_repo/data/train_set_parquet/part-00000.parquet` |
| 官方证据指标单元测试 + 集成测试 | `tests/`，`experiments/pytest_*.log` |
| 官方证据指标 end-to-end（oracle） | `experiments/oracle/test_oracle_full_evidence_metrics.json` |
| 指标敏感性实验（时间抖动 / 描述打乱） | `experiments/metric_sensitivity/summary.json`、`sensitivity.png` |
| 训练可行性审查 | `docs/TRAINING_REVIEW.md` |
| 替代基线推理（Qwen2.5-VL-3B-Instruct） | `experiments/predictions/`（见第 4 节） |

测试结果（真实输出）：

- 基础环境（Python 3.13，无 torch）：**83 passed, 2 skipped**（跳过的是 BGE-M3 集成测试）
- 推理环境（Python 3.10，torch 2.4.1+cu124，BGE-M3 可用）：**85 passed**

## 2. 未完成的内容与原因

| 未完成 | 原因（可验证） |
|---|---|
| 官方 EG-Reasoner 训练 | 需 Qwen2.5-VL-7B + 4 GPU + vLLM + FSDP；8 GB 显存连一份 bf16 7B 权重（约 15 GB）都放不下；Windows 无 vLLM/flash-attn/ray。`docs/TRAINING_REVIEW.md` |
| 官方 checkpoint 推理 | 权重未公开：HF 上检索 `EG-Reasoner` 与作者 `lphuang33` 均为空 |
| 官方 `evaluation/evaluate.py` | 依赖 vLLM；在本机实际运行报 `ModuleNotFoundError: No module named 'vllm'`（日志：`experiments/official_evaluate_probe.log`） |
| 论文表格数值复核 | 无 checkpoint、无完整数据管线（未训练），无法复核 |
| 答案指标（relaxed/strict accuracy） | 需要 OpenAI 兼容 judge API key。实际运行官方脚本报 `RuntimeError: OPENAI_API_KEY must be set`（`experiments/answer_metrics_no_key.log`）。未用 mock 冒充结果 |
| 全量 2067 个视频的帧 | 只按需下载了少量视频；完整 `videos.tar` 为 13.09 GB，未全量下载 |

## 3. 与论文的差距

1. **模型**：论文 EG-Reasoner 是 Qwen2.5-VL-7B + GRPO 训练；本地使用的是 Qwen2.5-VL-3B-Instruct，未训练。
   指标数值不可与论文表格直接比较。
2. **数据规模**：本地推理只覆盖少量测试视频（见第 4 节），与 2,889 条测试问题不可比。
3. **答案指标**：完全未计算（无 judge）。
4. **训练**：完全未执行。
5. **发现的上游不一致**（不是本次引入）：
   - 论文附录 D 的 λ 权重（0.1/0.6/0.3）与仓库 yaml（0.1/0.3/0.6）互换；
   - 论文语义模型 all-MiniLM-L6-v2 vs 仓库 BGE-M3；
   - 论文软匹配权重 `IoU·Sim` vs 实现 `0.5·IoU+0.5·Sim`；
   - 论文 `R_evi = R_soft + R_hard` vs 实现 `0.5·R_soft + 0.5·R_hard`；
   - 论文全局 batch 4 vs 仓库 16；
   - 论文硬 EG-F1 公式与实现一致。

## 4. 替代基线推理

模型：`Qwen/Qwen2.5-VL-3B-Instruct`（非论文模型），4-bit NF4，8 帧，贪心解码。
样本：10 个测试视频的 **92 条问题**（四类均衡）。显存峰值 3.29 GiB，92 条约 14 分钟。

官方证据指标（真实 BGE-M3，`evaluation/evidence_metrics.py`）：

| 指标 | 数值 |
|---|---|
| EG-F1 (0.3,0.5) | 0.0455 |
| EG-F1 (0.3,0.75) | 0.0127 |
| EG-F1 (0.5,0.75) | 0.0000 |
| IoU-F1 @0.1 / @0.3 / @0.5 / @0.7 | 0.1045 / 0.0595 / 0.0229 / 0.0000 |

按类型 EG-F1(0.3,0.5)：descriptive 0.0908 > causal 0.0736 > temporal 0.0238 > counterfactual 0.0000。

输出健康度：89/92 有 evidence，85/92 有完整 think+answer，0 个非法时间戳，7 条因 256 token 截断。
时间偏置：预测证据起点中位数 12.0 s，标准答案 78.9 s；55% 的问题全部预测落在视频前 30 秒。

以上是替代基线的真实结果，**不能**与论文表格比较，也不构成 EG-Reasoner 的复现。详见 `docs/RESULTS_ANALYSIS.md` 第 4 节。

## 5. 当前可复核的核心结论

1. **数据规模与论文完全一致**：2,067 视频 / 11,838 问答 / 8,949 训练 / 2,889 测试；train/test 视频零重叠。
2. **标注存在已知缺陷**：14 个零长度证据（训练 12、测试 2）、7 个超出视频时长，共 21 个缺陷；测试集 2 条零长度证据使官方 EG-F1 的理论上限为 **0.999654**（oracle 实测一致）。
3. **官方 EG-F1 实现与论文硬匹配公式一致**；训练奖励中的软匹配与论文存在实质差异。
4. **EG-F1 对语义不匹配敏感、对纯时间 IoU 不敏感**：描述完全打乱时 IoU-F1 保持 0.9967，EG-F1(0.3,0.75) 降至 0.3451。
5. **官方预处理在 Windows 可运行，且官方仓库未被修改**：字体通过 `scripts/extract_frames.py` 包装注入；60/60 视频各 32 帧、时间戳绘制正确、提取结果字节级可复现。

## 6. 下一步建议

1. 若需论文数值：向作者申请 EG-Reasoner checkpoint（7B，需 ≥24 GB 显存的 Linux GPU 运行官方 `evaluate.py`）。
2. 若需训练复现：使用官方 Docker 镜像 `nvcr.io/nvidia/pytorch:24.08-py3`，4×A100-80G，先跑极小步数 smoke；注意需要 judge API key 与 BGE-M3。
3. 若继续在本地：可扩大替代基线样本（下载更多视频），或把答案指标换成有 key 的 judge——但必须继续标注为替代基线。
4. 数据层面建议向作者报告零长度证据标注（14 处：训练 12、测试 2）与 7 处越界时间戳。
