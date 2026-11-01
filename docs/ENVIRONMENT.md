# 环境说明

> 公开版本已把本机绝对路径替换为占位符；命令其余部分保持原样。

> 实测时间：2026-10-29
> 机器：Windows 11 Home China 10.0.26200 / AMD64 / 32 逻辑核

## 1. 硬件

| 项目 | 实测值 |
|---|---|
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU |
| 显存 | 8188 MiB（约 8 GB） |
| 驱动 | 560.94 |
| 驱动支持 CUDA | 12.6 |
| 磁盘 D: | 551.6 GB 总，53.8 GB 可用 |
| 磁盘 C: | 约 28 GB 可用 |

> 8 GB 显存不足以加载官方 `Qwen2.5-VL-7B-Instruct`（bf16 权重约 15–16 GB），遑论 veRL 训练的 actor + rollout + reference 三份模型。

## 2. Python 环境

### 2.1 基础环境（数据审计 / 预处理 / 纯函数测试）

| 项目 | 版本 |
|---|---|
| Python | 3.13.5（conda base 环境） |
| numpy | 2.1.3 |
| scipy | 1.15.3 |
| pyarrow | 19.0.0 |
| opencv-python | 5.0.0 |
| Pillow | 11.1.0 |
| pytest | 8.3.4 |
| openai | 2.44.0 |
| torch | **未安装** |

用途：`scripts/audit_data.py`、`scripts/check_env.py`、`scripts/check_videos.py`、`scripts/verify_frames.py`、官方 `preprocess/*.py`、以及除语义相似度以外的全部 pytest。

### 2.2 推理环境（`egvqa`，Python 3.10）

官方 README 指定 `conda create -n eg-reasoner python=3.10`。本机创建：

```bash
conda create -y -n egvqa python=3.10
python -m pip install torch==2.4.1 torchvision==0.19.1 -i https://pypi.tuna.tsinghua.edu.cn/simple
python -m pip install transformers==4.51.3 accelerate sentence-transformers qwen-vl-utils pillow numpy scipy pyarrow opencv-python pytest openai huggingface_hub -i https://pypi.tuna.tsinghua.edu.cn/simple
```

安装结果与环境版本见 `experiments/env_report_egvqa.json`（由 `scripts/check_env.py` 在该环境中生成）。

未安装项及原因：

| 未安装 | 原因 |
|---|---|
| `vllm` | 官方仅支持 Linux；Windows 无官方 wheel。`evaluation/evaluate.py` 与训练 rollout 都依赖它 |
| `flash-attn` | 需要编译，Windows + 非官方 CUDA 工具链下不可行；官方训练硬依赖 |
| `ray` | 训练框架依赖；Windows 支持有限，且训练本身在 8 GB 显存上不可行 |
| `bitsandbytes` | 计划仅在替代基线需要 4-bit 时评估 |

### 2.3 网络与镜像

| 目标 | 直连结果 | 采用的方案 |
|---|---|---|
| huggingface.co | 超时 | `https://hf-mirror.com` |
| hf-mirror.com | 正常，单连接约 10.5 MB/s | 数据集与 BGE-M3 下载 |
| pypi.org | 可连但慢 | TUNA 镜像 `https://pypi.tuna.tsinghua.edu.cn/simple` |
| arxiv.org | 正常 | 仅查阅 |

## 3. 官方仓库

| 项目 | 值 |
|---|---|
| 路径 | `official_repo/` |
| commit | `0ca6b53c8d3aa998eaf24f903b0f6cb6b8ab88f5` |
| commit 日期 | 2026-10-04 |
| 对官方代码的修改 | **无**（`git status` 无跟踪文件改动）。Windows 字体通过 `scripts/extract_frames.py` 包装注入 |

### 3.1 官方代码修改记录

**官方仓库的跟踪文件未被修改。** 早期阶段曾在 `preprocess/video_clip.py` 内加入 Windows 字体回退，
随后已用 `git checkout` 还原；现在通过 `scripts/extract_frames.py` 导入官方模块并设置
`video_clip.TIMESTAMP_FONT_PATH`（可通过环境变量 `EG_VQA_FONT` 覆盖）。

- 采样、缩放、命名、时间戳绘制全部仍由官方实现完成；
- 用该包装脚本重新抽取 `QWowpe84rXw` 的 32 帧，与既有帧逐字节一致（SHA-256 全部相同）。

## 4. 依赖与上游要求对照

官方 `EG-Reasoner/requirements.txt` 的核心项：`torch`、`transformers>=4.51.0`、`vllm>=0.7.3`、`flash-attn>=2.4.3`、`sentence-transformers`、`qwen-vl-utils`、`ray[default]`、`pyarrow>=15.0.0`、`scipy`、`opencv-python`、`openai`、`wandb`。

在 Windows 上的可行性：

| 依赖 | Windows 可行性 | 结论 |
|---|---|---|
| torch | ✅ | 可用 |
| transformers | ✅ | 可用 |
| sentence-transformers | ✅ | 可用（BGE-M3，CPU/GPU） |
| qwen-vl-utils | ✅（依赖 torchvision） | 可用 |
| opencv / pyarrow / scipy | ✅ | 可用 |
| vllm | ❌ 无 Windows 官方支持 | 官方推理脚本与训练 rollout 无法在原生 Windows 运行 |
| flash-attn | ❌ 需编译 | 训练不可行 |
| ray | ⚠️ | 训练不可行 |

结论：**评估指标与预处理可在 Windows 原生完成；官方训练与官方 checkpoint 推理需要 WSL2 或远程 Linux + 大显存 GPU。**
