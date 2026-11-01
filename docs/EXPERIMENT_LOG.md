# 实验日志

> 公开版本已把本机绝对路径替换为占位符（`<workspace>`、`<conda-env>`），命令其余部分保持原样。

> 本文件只记录**实际执行过**的命令与真实输出。未执行的步骤不写入。
> 时间：2026-10-29（本地时区 Asia/Shanghai）

## 2026-10-29 22:00 — 环境与仓库检查

命令：

```bash
python --version
nvidia-smi
conda env list
git clone https://github.com/HCPLab-SYSU/EG-VQA.git official_repo
```

结果：
- Python 3.13.5（`python（conda base）`），conda 25.5.1，Git 2.54.0
- GPU：NVIDIA GeForce RTX 4060 Laptop，8188 MiB，驱动 560.94，CUDA 12.6（驱动侧）
- 已有环境：base、TF、dassl、py310、pytorch(3.9.25 + torch 2.3.1, CUDA 可用)、qllms-lite、tensorflow
- 官方仓库 clone 成功，HEAD = `0ca6b53c8d3aa998eaf24f903b0f6cb6b8ab88f5`（2026-10-04）

## 2026-10-29 22:01 — 论文与数据源可达性

命令：

```bash
curl -L https://arxiv.org/abs/2606.24797
curl -L https://huggingface.co/api/datasets/lphuang33/EG-VQA
curl -L https://hf-mirror.com/api/datasets/lphuang33/EG-VQA/tree/main
```

结果：
- arXiv 页面返回 200，标题为 "EG-VQA: Benchmarking Verifiable Video Question Answering with Grounded Temporal Evidence"
- `huggingface.co` 直连超时（网络不可达）
- `hf-mirror.com` 正常（200）；`pypi.org` 可连但慢；ModelScope 可连
- HF 数据集文件列表：`train.json` (7,390,047 B)、`test.json` (2,295,519 B)、`videos.tar` (13,090,641,920 B)、`README.md`
- 数据集许可：CC-BY-4.0
- **重要**：官方 README 未提及 `videos.tar`，但 HF 实际提供，且支持 HTTP Range（206）

## 2026-10-29 22:01 — 标注一致性验证

命令：

```bash
curl -L -o experiments/downloads/hf_train.json https://hf-mirror.com/datasets/lphuang33/EG-VQA/resolve/main/train.json
sha256sum hf_train.json hf_test.json official_repo/data/train.json official_repo/data/test.json
```

结果：四个文件哈希完全一致

```
f4992b0d3e239dd3e809b2feecb7bef41f1507153a358c40e9e271ae010622e6  train.json
673560f4a3076321f9da8a2b57422fd04cf3645e0bd5aa0a6d8b92427a740f8b  test.json
```

## 2026-10-29 22:02 — 环境报告脚本

命令：`python scripts/check_env.py`

输出保存：`experiments/env_report.json`

关键结果：base 环境无 torch；已有 numpy 2.1.3、scipy 1.15.3、pyarrow 19.0.0、opencv 5.0.0、Pillow 11.1.0、pytest 8.3.4、openai 2.44.0。

## 2026-10-29 22:03 — 数据审计

命令：`python scripts/audit_data.py`

输出：`experiments/data_audit.json`

真实结果：

| 指标 | train | test |
|---|---|---|
| 视频数 | 1731 | 336 |
| 问题数 | 8949 | 2889 |
| evidence 区间数 | 20009 | 6839 |
| descriptive | 2196 | 657 |
| temporal | 2212 | 751 |
| causal | 1994 | 748 |
| counterfactual | 2547 | 733 |
| ActivityNet / HiREST / YouCook2 | 1277 / 286 / 168 | 223 / 72 / 41 |
| 每问题 evidence 数（均值/最大） | 2.236 / 8 | 2.367 / 8 |
| 视频时长范围 | 30.09–917.0 s | 30.16–616.3 s |
| 标注异常 | 19 | 2 |

train/test 视频 ID 交集 = 0（无视频级泄漏）。
异常明细：train 中 12 个 `start >= end`（全部是零长度区间，如 `[124,124]`）、7 个 `end > duration`；test 中 2 个零长度区间。
重复问题文本：train 221 条、test 67 条，全部是**跨视频**的通用反事实问句（如 "what if butter was not used?"），非泄漏。

## 2026-10-29 22:04 — 指标体系单元测试

命令：`python -m pytest tests/ -q`

结果：`55 passed`（证据指标 23、答案指标 8、响应解析 11、预处理 13；合计 55）
- 证据指标测试中涉及语义相似度的部分使用 `FakeEncoder`（确定性替身），**不是** BGE-M3 实测。

## 2026-10-29 22:10 — 视频获取工具

问题：`urllib` 每次请求都要跟随重定向并新建 TLS 连接，单次约 3–5 s，2000+ 头块索引需数小时。

解决：改为常驻 HTTPS 连接访问签名后的 CDN URL（`RemoteTar`），单次请求降到约 0.7 s；并新增 `--scan` 模式，按 tar 顺序扫描，找到配额数量的目标视频即停止。

命令：

```bash
python scripts/fetch_videos_from_tar.py --scan --from-json official_repo/data/test.json --per-split 3 --max-members 300 --out-dir data/videos --manifest experiments/videos_manifest_test.json
python scripts/fetch_videos_from_tar.py --scan --from-json official_repo/data/train.json --per-split 3 --max-members 300 --out-dir data/videos --manifest experiments/videos_manifest_train.json
```

结果：15 个 tar 成员内即找到 3 个 test 视频；5 个成员内找到 3 个 train 视频。共下载 6 个真实视频（约 62 MB），清单存于 `experiments/videos_manifest_{test,train}.json`。

## 2026-10-29 22:14 — 视频完整性检查

命令：`python scripts/check_videos.py`

输出：`experiments/video_check.json`

结果：6/6 视频可打开、可解码首帧；解码时长与标注时长偏差 0.16–0.72 s。

| video_id | split | source | fps | 时长(解码) | 标注时长 |
|---|---|---|---|---|---|
| QWowpe84rXw | test | HiREST | 25.0 | 480.16 | 480 |
| JAFloXFat6k | test | HiREST | 29.97 | 107.41 | 107 |
| v_fxbEiZrQQzM | test | ActivityNet | 3.0 | 66.33 | 65.78 |
| Dpo1GQa3XMQ | train | HiREST | 25.0 | 352.72 | 352 |
| v_0Zg-7EgFiC8 | train | ActivityNet | 3.0 | 218.67 | 218.22 |
| v_mbGpp_nDwI4 | train | ActivityNet | 3.0 | 98.67 | 98.2 |

## 2026-10-29 22:15 — 官方预处理（真实视频）

路径调整：为与官方默认路径一致，将视频与帧移动到 `official_repo/data/{videos,frames}`。

最小代码适配（记录在案）：`preprocess/video_clip.py` 新增 `FALLBACK_FONT_PATHS` 与 `resolve_font_path()`，在官方 Linux 字体不存在时回退到 Windows 字体（arial/segoe），行为与官方一致；未改变任何采样/尺寸逻辑。

命令：

```bash
cd official_repo
python preprocess/video_clip.py --dataset ../experiments/subsets/train_subset.json --video-root <workspace>/data --output-root <workspace>/data/frames/train
python preprocess/video_clip.py --dataset ../experiments/subsets/test_subset.json  --video-root <workspace>/data --output-root <workspace>/data/frames/test
```

结果：6 个视频各 32 帧，输出 `data/frames/{train,test}/<video_id>/<video_id>_fNN.png`。

## 2026-10-29 22:16 — 帧校验

命令：`python scripts/verify_frames.py --split train|test`

输出：`experiments/frame_check_{train,test}.json`

结果：6/6 通过。帧数=32、命名与官方采样索引一致、图像可解码为 RGB、右上角时间戳区域与原始帧存在 431–509 像素差异（证明时间戳确实被绘制）、最后一帧时间戳 ≤ 视频实际时长。

## 2026-10-29 22:17 — 训练 Parquet（smoke 子集）

命令：`cd official_repo && python preprocess/prepare_train_parquet.py`

结果：

```
[warn] skipped 8934 samples because their frame directories were missing
Built 15 training samples
[1] wrote 15 samples -> data/train_set_parquet/part-00000.parquet   (11 MB)
```

说明：该 Parquet 只包含 3 个训练视频对应的 15 条样本，是**冒烟子集**，不是完整训练集。脚本本身未修改，仍可对全量数据运行。

校验：15 行，列为 `images/problem/answer`，每行 32 张可解码 PNG，`answer` 为合法 JSON，包含 `video_id/question_id/question/answer/type/evidence/metadata`。

## 2026-10-30 00:10 — 论文全文核对

命令：抓取 `https://arxiv.org/html/2606.24797v1`，纯文本保存为 `experiments/paper_text.txt`。

读取到附录 B（EG-F1 完整公式）、B.2（软匹配）、D（训练配置）。与官方实现逐项对照后写入 `docs/METRIC_REVIEW.md`。

关键发现（论文 vs 代码）：

| 项目 | 论文 | 官方代码 |
|---|---|---|
| 软匹配权重 | `IoU·Sim` | `0.5·IoU + 0.5·Sim` |
| 软/硬组合 | `R_soft + R_EG-F1` | `0.5·soft + 0.5·hard` |
| λ_f/λ_e/λ_a | 0.1 / 0.6 / 0.3 | 0.1 / 0.3 / 0.6（e 与 a 互换） |
| 语义模型 | all-MiniLM-L6-v2 | BGE-M3 |

硬 EG-F1 的四步公式与实现完全一致（门控 → `IoU·Sim` 权重 → 匈牙利 → P/R/F1）。

## 2026-10-30 00:20 — Python 环境

Conda 默认源下载 Python 包极慢（12 分钟仅 15%），故改用现有 `py310`（Python 3.10.6）创建 venv：

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cu124
.venv/Scripts/python.exe -m pip install transformers==4.51.3 accelerate sentence-transformers qwen-vl-utils pyarrow scipy opencv-python pytest openai huggingface_hub -i https://pypi.tuna.tsinghua.edu.cn/simple
```

结果：`torch 2.4.1+cu124`，`torch.cuda.is_available() == True`，CUDA 12.4 运行时。

## 2026-10-30 00:21 — BGE-M3 下载与加载

huggingface.co 不可达，使用 `hf-mirror.com` 直接下载 BGE-M3 文件到 `official_repo/EG-Reasoner/Science_Bert/`。

- `pytorch_model.bin`：2,271,145,830 字节，SHA-256 `b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38`
- 总目录约 2.3 GB

加载验证（CPU）：

```
SentenceTransformer('official_repo/EG-Reasoner/Science_Bert', device='cpu')
dim 1024  sim_same 0.8714  sim_diff 0.5739
```

## 2026-10-30 00:24 — 官方证据指标 oracle 验证（50 样本）

命令：

```bash
python scripts/make_oracle_predictions.py --output experiments/oracle/test_oracle_50.json --limit 50
HF_HUB_OFFLINE=1 .venv/Scripts/python.exe official_repo/evaluation/evidence_metrics.py \
  --input experiments/oracle/test_oracle_50.json --output experiments/oracle/test_oracle_50_evidence_metrics.json --semantic-device cpu
```

结果：EG-F1 与 IoU-F1 在全部阈值下均 = **1.0000**。说明解析、匹配、聚合链路正确。

## 2026-10-30 00:26 — 官方证据指标 oracle 验证（全量 2889 样本）

命令同上，输入 `test_oracle_full.json`（2889 条问题，1641 个唯一证据描述）。

结果：

| 指标 | 数值 |
|---|---|
| EG-F1 (0.3,0.5) | 0.999654 |
| EG-F1 (0.3,0.75) | 0.999654 |
| EG-F1 (0.5,0.75) | 0.999654 |
| weighted EG-F1 | 0.999708 |
| IoU-F1 @0.1/0.3/0.5/0.7 | 0.999654 |

**成因（可复核）**：测试集有 2 条问题的 ground truth 含零长度证据 `[125,125]`（`9pybtCnEqEQ_q01`、`9pybtCnEqEQ_q09`）。官方解析将其判为 invalid，因此即使"预测=标准答案"，这两条也只能得到 P=R=F1=0.5。2/2889 → 平均 F1 = 1 - 0.5/2889 ≈ 0.999654，与实测完全吻合。

结论：官方 EG-F1 在完美预测下**不等于 1.0**，理论上限由标注缺陷决定。

## 2026-10-30 00:28 — 指标敏感性实验（真实测试标注，无模型）

命令：

```bash
HF_HUB_OFFLINE=1 .venv/Scripts/python.exe scripts/metric_sensitivity.py --limit 300 --device cpu \
  --output experiments/metric_sensitivity/summary.json
.venv/Scripts/python.exe scripts/plot_sensitivity.py
```

设置：测试集前 300 条问题，对每条 GT 证据边界加独立均匀抖动 `U(-σ,σ)`，描述不变；另做"描述打乱"对照
（时间戳逐字保留，描述替换为其他样本的描述）。

关键结果：

| σ | EG-F1(0.3,0.5) | EG-F1(0.3,0.75) | EG-F1(0.5,0.75) | IoU@0.7 |
|---|---|---|---|---|
| 0 | 0.9967 | 0.9967 | 0.9967 | 0.9967 |
| 5 | 0.9102 | 0.9094 | 0.7954 | 0.6291 |
| 10 | 0.7748 | 0.7654 | 0.6292 | 0.4207 |
| 30 | 0.5066 | 0.4675 | 0.2792 | 0.1259 |

描述打乱（时间戳完全正确）：IoU-F1 全部保持 **0.9967**，而 EG-F1(0.3,0.75) 降到 **0.3451**，
EG-F1(0.3,0.5) 为 0.8112。说明：① 纯 IoU 指标无法发现"定位对、描述错"；② β=0.5 语义阈值偏宽松。

图表：`experiments/metric_sensitivity/sensitivity.png`。

## 2026-10-30 00:29 — 标注分布分析

命令：`python scripts/analyze_annotations.py` → `experiments/annotation_stats.json`

结果摘要：temporal 类问题证据数最多（train 2.66、test 2.90 条/问题）；四类问题的答案平均 12–14 词。
train 视频时长均值 157.1 s，test 177.4 s。

## 2026-10-30 00:31 — 测试覆盖

- 基础环境（Python 3.13）：`75 passed, 2 skipped`（BGE-M3 集成测试因缺 sentence-transformers 跳过）
- 推理环境（Python 3.10 + torch）：`77 passed`（含 BGE-M3 集成测试）
- 新增测试：`tests/test_data_consistency.py`（论文规模、零重叠、已知标注缺陷的回归断言）、
  `tests/test_reward_parsing.py`（训练奖励解析）、`tests/test_semantic_integration.py`（真实 BGE-M3）

## 2026-10-30 00:33 — 公开 checkpoint 核查

在 HF 镜像检索 `EG-Reasoner` 以及作者 `lphuang33` 的模型仓库：**均为空**。
论文模型权重未公开发布，因此无法在本机复现论文表格数值。

## 2026-10-30 00:34 — 扩大测试视频规模

用 `--scan --per-split 10` 继续从 `videos.tar` 抽取测试视频（后台），以增加后续替代基线推理的样本量。

## 2026-10-30 00:53 — 10 个测试视频与帧

扫描 73 个 tar 成员后凑齐 10 个测试视频（含 1 个 .mkv），共 92 条测试问题，四类均衡
（temporal 24 / counterfactual 24 / descriptive 22 / causal 22；来源 ActivityNet 6 / HiREST 3 / YouCook2 1）。

命令：

```bash
python scripts/fetch_videos_from_tar.py --scan --from-json official_repo/data/test.json \
  --per-split 10 --max-members 1500 --out-dir official_repo/data/videos \
  --manifest experiments/videos_manifest_test10.json
cd official_repo && python preprocess/video_clip.py --dataset ../experiments/subsets/test_subset.json \
  --video-root official_repo/data --output-root official_repo/data/frames/test
```

结果：`10/10 videos passed`（`experiments/frame_check_test.json`）。
注：首次处理时第 10 个视频仍在下载（0 字节），libav 报 `moov atom not found`；下载完成后重跑即通过。
该现象已如实保留为"部分文件不可用"的证据，未用替代视频顶替。

## 2026-10-30 00:40 — 官方 evaluate.py 在 Windows 的失败证据

```bash
.venv/Scripts/python.exe official_repo/evaluation/evaluate.py --model-path models/Qwen2.5-VL-3B-Instruct ...
```

结果：`ModuleNotFoundError: No module named 'vllm'`（`experiments/official_evaluate_probe.log`）。

## 2026-10-30 00:33 — 答案指标缺少 API key 的失败证据

```bash
.venv/Scripts/python.exe official_repo/evaluation/answer_metrics.py --input experiments/oracle/test_oracle_50.json
```

结果：`RuntimeError: OPENAI_API_KEY must be set before answer scoring.`，未生成任何结果文件
（`experiments/answer_metrics_no_key.log`）。

## 2026-10-30 00:36 — 预处理确定性

对 `QWowpe84rXw.mp4` 连续提取两次 32 帧，比较 SHA-256：32 个文件全部字节一致。

## 2026-10-30 01:10 — Qwen2.5-VL-3B 替代基线推理

模型下载：`Qwen/Qwen2.5-VL-3B-Instruct`，7.1 GB，两个 safetensors 文件大小与 HF API 完全一致
（3,982,649,232 / 3,526,688,744 字节）。`huggingface_hub` 因镜像重定向报
`FileMetadataError`，改用 curl 直接下载。

显存测试（真实）：

| 配置 | 加载显存 | 速度 |
|---|---|---|
| bf16，8 帧，bf16 未量化 | 7.00 GiB（峰值 7.52） | 单条 129 s，约 1–2 token/s |
| 4-bit NF4，4 帧 | 2.40 GiB | 7–14 s/条 |
| 4-bit NF4，8 帧 | 2.40 GiB（峰值 3.29） | 6–16 s/条 |

未量化时显存逼近 8 GB 上限，Windows WDDM 下性能急剧下降；这不是模型本身的计算量问题。

命令：

```bash
HF_HUB_OFFLINE=1 .venv/Scripts/python.exe scripts/infer_qwen_vl.py \
  --model-path models/Qwen2.5-VL-3B-Instruct --only-available \
  --max-frames 8 --max-pixels 100352 --max-new-tokens 256 --load-in-4bit \
  --output experiments/predictions/qwen25vl3b_4bit_8f_test92.json --overwrite
HF_HUB_OFFLINE=1 .venv/Scripts/python.exe official_repo/evaluation/evidence_metrics.py \
  --input experiments/predictions/qwen25vl3b_4bit_8f_test92.json \
  --output experiments/predictions/qwen25vl3b_4bit_8f_test92_evidence_metrics.json --semantic-device cpu
python scripts/analyze_predictions.py --predictions ... --metrics ... --output ..._analysis.json
python scripts/analyze_temporal_bias.py --predictions ... --output experiments/predictions/temporal_bias.json
```

结果：92/92 成功，0 错误；总耗时 826.5 s。
EG-F1(0.3,0.5)=0.0455，IoU@0.1=0.1045；85/92 输出完整；0 个非法时间戳。
预测证据起点中位数 12.0 s（标准答案 78.9 s），55% 的问题全部预测落在前 30 秒。

**明确声明：这是替代基线，不是论文模型，也不是论文数值的复现。**

## 2026-10-30 02:00 — 受控对照实验（阶段 D）

### 实现审计

新增 `scripts/audit_pipeline.py` → `experiments/ablation/pipeline_audit.json`。

关键发现：本地推理调用官方 `evaluation/evaluate.py::frame_paths_for_video`，
而该函数在排序后取 `[:max_frames]`。当 `max_frames=8` 时，只使用 32 帧中的前 8 帧，
覆盖全片的 22.5%–22.7%（逐视频实测）。官方默认 32 帧不会触发该问题。
另确认：时间戳只以像素形式进入模型；提示词无逐帧时间；旧基线 239 个预测中 0 个解析失败、0 个反转、
11 个终点越界、3 条无证据；用官方函数复算 IoU-F1 与已保存结果完全一致（差值 < 1e-12）。

### 受控实验

新增 `--frame-selection {first,uniform}` 与 `--prompt-variant {official,timestamp}`，固定
`experiments/ablation/fixed92_annotations.json`（92 题），运行 A2/B/C/D；A 复用旧基线。

过程中出现两次必须修正的问题（已如实保留在 `experiments/ablation/run.log`、`run_rest.log`）：

1. 首次运行 B 时可用帧已扩展到 60 个视频，自动选中 526 题，样本集与 A2（92 题）不同。
   终止并删除该产物，冻结 92 题清单后重跑。
2. 终止的任务在 Windows 上遗留 Python 子进程占用 GPU，导致 B 首批样本计时失真（约 100 s/条）。
   定位并终止遗留进程（PID 28976 及其子进程）后从干净状态重跑。

真实结果（92 题，官方证据指标）：

| 配置 | 帧数/选择/提示词 | EG-F1(0.3,0.5) | EG-F1(0.3,0.75) | IoU@0.1 | 前 30 秒比例 | 无时间重叠 | 秒/条 | 峰值 GiB |
|---|---|---|---:|---:|---:|---:|---:|---:|
| A | 8/前 8/官方 | 0.0455 | 0.0127 | 0.1045 | 55.1% | 73.6% | 8.98 | 3.29 |
| A2 | 8/均匀/官方 | 0.0234 | 0.0133 | 0.0546 | 66.7% | 75.0% | 9.68 | 3.29 |
| B | 16/均匀/官方 | 0.0479 | 0.0163 | 0.1152 | 47.3% | 69.1% | 11.25 | 3.29 |
| C | 32/均匀/官方 | **0.0686** | **0.0212** | **0.1578** | **31.5%** | **53.6%** | 19.46 | 3.96 |
| D | 8/均匀/时间戳提示 | 0.0280 | 0.0093 | 0.0566 | 73.9% | 79.3% | 8.78 | 3.29 |

配对检验（vs A2）：C +0.0452（11 好/4 差，Wilcoxon p=0.0399）；B +0.0245（p=0.0701）；
A +0.0221（p=0.1162）；D +0.0046（p=0.2500）。

完整输出数随帧数下降：A 85/92、B 72/92、C 45/92（256 token 被证据行用尽）。
C 组内完整 vs 截断的 EG-F1 为 0.0709 vs 0.0664，说明提升不是截断造成的假象。

结果文件：`experiments/ablation/summary.json`、`summary.csv`、`summary.md`、`bootstrap_ci.json`、
`diagnostics/*.json`。报告：`docs/ABLATION_REPORT.md`。

## 2026-10-30 06:20 — 300 题分层扩展评估

数据：60 个真实测试视频、526 条问题；按类型分层，每类 75 条，共 300 条，seed=20261030。
未修改官方标注，未把答案作为输入。

命令：

```bash
python scripts/build_expanded_set.py --total 300 --seed 20261030
HF_HUB_OFFLINE=1 .venv/Scripts/python.exe scripts/infer_qwen_vl.py \
  --model-path models/Qwen2.5-VL-3B-Instruct \
  --annotations experiments/ablation/expanded_annotations.json --only-available \
  --max-frames 32 --frame-selection uniform --max-pixels 100352 --max-new-tokens 256 \
  --load-in-4bit --config-name expanded_C32 \
  --output experiments/ablation/predictions/expanded_C32.json --overwrite
HF_HUB_OFFLINE=1 .venv/Scripts/python.exe official_repo/evaluation/evidence_metrics.py \
  --input experiments/ablation/predictions/expanded_C32.json \
  --output experiments/ablation/metrics/expanded_C32_evidence_metrics.json \
  --semantic-device cpu --overwrite
```

结果：300/300 成功，0 错误，5060 s（16.87 s/条），峰值 3.96 GiB。

| 指标 | 数值 |
|---|---|
| EG-F1 (0.3,0.5) | 0.0510（bootstrap 95% CI 0.0358–0.0680） |
| EG-F1 (0.3,0.75) | 0.0116 |
| EG-F1 (0.5,0.75) | 0.0058 |
| IoU-F1 @0.1 / 0.3 / 0.5 / 0.7 | 0.1668 / 0.0573 / 0.0210 / 0.0019 |
| 无时间重叠预测 | 55.4% |
| 全部预测在前 30 秒的问题 | 39.3% |
| 非法时间戳 / 越界终点 | 1 / 39 |
| 完整输出（think+answer） | 178/300 |

类型 EG-F1：causal 0.061、counterfactual 0.072、descriptive 0.038、temporal 0.034。
与 92 题子集的排序相反（92 题上 temporal 0.100、counterfactual 0.028），因此本报告不宣称类型排序结论。

结论：92 题的 C 组 0.0686 偏乐观；300 题的 0.0510 更可靠。不建议在当前机器跑全量 2889 题。

## 2026-10-30 10:40 — 官方仓库恢复为未修改状态

早期阶段曾在 `official_repo/preprocess/video_clip.py` 内加入 Windows 字体回退。本阶段已用
`git -C official_repo checkout -- preprocess/video_clip.py` 还原，改用包装脚本
`scripts/extract_frames.py`：导入官方模块并设置 `video_clip.TIMESTAMP_FONT_PATH`（`EG_VQA_FONT` 可覆盖）。

验证：重新抽取 `QWowpe84rXw` 的 32 帧，与既有帧 SHA-256 全部相同；`git -C official_repo status`
无跟踪文件修改。文档、`run_all.sh`、README 中的命令已同步更新，旧补丁文件已删除。

## 2026-10-30 10:50 — 输出截断分析与 256/512 token 配对实验

分析脚本：`scripts/analyze_truncation.py`（用同一 tokenizer 对保存的原始输出计数，不重新推理）。

关键发现：截断不是主要由 256 token 上限造成。C 组 92 条中只有 7 条接近上限，但 57 条不完整；
其中 41 条在 `<think>` 中途提前 EOS（平均 45.9 token，中位数 33；105.4 是全部 92 条的均值），另一类是重复循环撞上限。

配对实验（同一 92 题、32 帧、同一提示词，仅 `max_new_tokens` 256→512）：

```bash
HF_HUB_OFFLINE=1 .venv/Scripts/python.exe scripts/infer_qwen_vl.py \
  --model-path models/Qwen2.5-VL-3B-Instruct \
  --annotations experiments/ablation/fixed92_annotations.json --only-available \
  --max-frames 32 --frame-selection uniform --max-new-tokens 512 --load-in-4bit \
  --config-name C32_tok512 --output experiments/ablation/predictions/C32_tok512.json --overwrite
HF_HUB_OFFLINE=1 .venv/Scripts/python.exe official_repo/evaluation/evidence_metrics.py \
  --input experiments/ablation/predictions/C32_tok512.json \
  --output experiments/ablation/metrics/C32_tok512_evidence_metrics.json --semantic-device cpu --overwrite
python scripts/compare_token_limits.py ...
```

结果：92/92 成功；EG-F1(0.3,0.5) 0.0686 → 0.0669；标签齐全 35/92 → 36/92；think 内提前结束仍为 41；
触及上限 7 → 6；平均耗时 19.46 → 20.61 s；峰值显存均为 3.96 GiB。
逐题配对：0 好、1 差、91 不变；35 条原本完整的输出逐字节相同。唯一变差的题因重复证据降低 precision。

结论：提高 token 上限不能解决问题，主因是格式遵循/重复生成，而非 token 预算。
