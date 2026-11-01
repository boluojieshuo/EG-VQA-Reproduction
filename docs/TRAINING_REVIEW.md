# EG-Reasoner 训练可行性审查

> 依据：`official_repo/EG-Reasoner/examples/eg_vqa.yaml`、`train_eg_vqa.sh`、`Dockerfile`、
> `verl/workers/fsdp_workers.py`，以及论文附录 D。
> 本机：RTX 4060 Laptop 8 GB，Windows 11，32 GB RAM。

## 1. 官方配置（逐项）

| 项目 | 值 | 出处 |
|---|---|---|
| 基础模型 | `Qwen/Qwen2.5-VL-7B-Instruct` | yaml `model_path` |
| GPU 数 | 4 | yaml `n_gpus_per_node`，脚本 `NUM_GPUS=4` |
| 全局 batch | 16 | yaml `global_batch_size` |
| rollout 采样数 n | 8 | yaml `rollout.n` |
| prompt 最大长度 | 7000 | yaml `max_prompt_length` |
| response 最大长度 | 1024 | yaml `max_response_length` |
| 每视频帧数 | 32 | 脚本 `NUM_FRAMES=32` |
| 像素预算 | min 75264 / max 100352 | yaml `min_pixels` / `max_pixels` |
| 并行策略 | FSDP full-shard | yaml `enable_full_shard: true` |
| 参数/优化器 offload | 均开启 | yaml `offload_params/offload_optimizer: true` |
| rollout 引擎 | vLLM，TP=2，显存占用 0.6 | yaml `tensor_parallel_size: 2` |
| reference 模型 | 独立副本，CPU offload | yaml `ref` |
| 学习率 / KL | 1e-6 / 0.01 | yaml |
| 保存频率 | 每 20 步 | yaml `save_freq: 20` |
| 运行环境 | `nvcr.io/nvidia/pytorch:24.08-py3`（Ubuntu 22.04 + CUDA 12.6） | Dockerfile |
| 论文附录 D | 全局 batch 4、558 步、G=8、4 卡、all-MiniLM-L6-v2 | 论文附录 D |

注：仓库的全局 batch（16）与论文附录（4）不一致，已记录在 `docs/METRIC_REVIEW.md`。

## 2. 显存构成（估算）

| 组件 | 全精度/bf16 大小 | 4 卡 FSDP 后每卡 | 说明 |
|---|---|---|---|
| Actor 权重 | 7B × 2 B ≈ 15.1 GB | ≈ 3.8 GB | 训练时需 gather |
| Reference 权重 | 15.1 GB | ≈ 3.8 GB | 额外完整副本 |
| AdamW 优化器状态 | 7B × 8 B ≈ 56 GB | ≈ 14 GB | fp32 动量+方差 |
| 激活（32 帧、7k prompt、1k response、G=8） | — | 数 GB | 已开 gradient checkpointing |
| vLLM rollout | — | 每卡 60% 显存 | TP=2，与前两者分时复用 |

即使开启参数与优化器 CPU offload，**单卡 8 GB 在第一项就失败**：一个 7B bf16 权重副本需要约 15 GB，
无法放入 8 GB 显存。唯一的本地出路是 4-bit 量化 + LoRA，但：

- veRL 配置没有 QLoRA/LoRA 路径（`freeze_vision_tower` 之外没有适配器选项）；
- vLLM、flash-attn、ray 在 Windows 原生不可用；
- 即使强行改造，也不是论文方法，不能称为复现。

**结论：官方训练在本机不可行，且不是"调小 batch"能解决的问题。** 论文规模需要 4 张 ≥48 GB 的 GPU
（A6000 / A100-80G 级别）。

## 3. 训练代码审查（静态）

- 数据流：`verl/utils/dataset.py` 从 Parquet 读 `images`（PNG 字节列表）、`problem`、`answer`；
  `answer` 字段是整段 ground-truth JSON，奖励函数用 `parse_ground_truth` 解析。
- 图像处理：`max_pixels=100352`、`min_pixels=75264`，即每帧约 96–128 个视觉 token（28×28 patch）。
  32 帧约 3k–4k 视觉 token，加上 7k 文本上限，接近 `max_prompt_length=7000`。
- 奖励：`compute_score` 同时做格式、证据（BGE-M3）、答案（外部 LLM judge）。`accuracy_reward`
  每次调用一次 judge API；每个 batch 16 × G=8 = 128 次调用，558 步约 7 万次 judge 调用。
  这同时是**成本**与**外部依赖**（需要 OPENAI_API_KEY）。
- 断点：`save_freq=20`、`save_limit=1`，FSDP 分片保存，需 `scripts/model_merger.py` 合并。
- 合并脚本支持 FSDP / DDP+FSDP，不支持 FSDP+TP。

## 4. 可本地完成的替代工作

| 工作 | 状态 |
|---|---|
| 配置逐项解释（本节） | ✅ |
| 奖励函数纯逻辑测试（格式、解析、时间转换） | ✅ `tests/test_reward_parsing.py` |
| 奖励中证据部分与论文公式对照 | ✅ `docs/METRIC_REVIEW.md` |
| 训练数据 Parquet 构建（15 行 smoke） | ✅ |
| 实际训练 | ❌ 未执行（硬件/系统限制） |

## 5. 若要继续，最低成本路径（未执行，仅建议）

1. 租用 1 张 ≥48 GB 的 Linux GPU，先做**单卡推理**复核替代基线（需把 vLLM 或 transformers 路径调通）。
2. 若要训练：4×A100-80G，按官方 Dockerfile 起容器；先跑 `total_episodes=1` 的极小步数 smoke，
   确认显存与 judge API 调用正常，再考虑完整 558 步。
3. 在 Windows 本地继续推进的部分：数据、指标、预处理、文档与测试（本次已完成）。
