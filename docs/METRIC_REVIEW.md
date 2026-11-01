# 论文公式与官方实现对照

> 论文正文与附录取自 https://arxiv.org/html/2606.24797v1 （2026-10-29 抓取，全文纯文本存于 `experiments/paper_text.txt`）。
> 官方实现取自 commit `0ca6b53`。

## 1. EG-F1（硬匹配，评估指标）

### 论文附录 B.1

1. 对每对 `(g_i, p_j)` 计算 `IoU_ij` 与 `Sim_ij`（余弦相似度）。
2. 候选边集合 `E = {(i,j) | IoU_ij ≥ α 且 Sim_ij ≥ β}`。
3. 边权 `s_ij = IoU_ij · Sim_ij`（若 `(i,j) ∈ E`，否则 0）；在 `G` 与 `P` 上做最大权一对一二分图匹配（匈牙利算法）。记 `M = |{(i,j) ∈ ℳ | s_ij > 0}|`。
4. `P = M/|P|`，`R = M/|G|`，`EG-F1 = 2PR/(P+R)`。

### 官方实现 `evaluation/evidence_metrics.py::evaluate_eg`

```python
valid_matrix = np.where((ious >= iou_threshold) & (similarities >= sim_threshold),
                        ious * similarities, 0.0)
matches = match_by_score(valid_matrix)          # 匈牙利，矩形直接匹配
counts = score_counts(..., lambda i, j: ious[i,j] >= iou_threshold
                                         and similarities[i,j] >= sim_threshold)
```

### 对照结论

| 论文步骤 | 实现 | 一致性 |
|---|---|---|
| IoU 定义 | `intersection / (max(end)-min(start))` | ✅ 等价 |
| Sim = cos(φ(d_i), φ(d_j)) | BGE-M3 `encode(normalize_embeddings=True)` 后点积，截断到 [0,1] | ⚠️ 见下 |
| 门控边 | `where(iou≥α & sim≥β, iou*sim, 0)` | ✅ 一致 |
| 匈牙利最大权匹配 | `linear_sum_assignment(-matrix)` | ✅ 一致 |
| `M` = 正权匹配数 | `valid_matches`（再次检查门控） | ✅ 等价 |
| P、R、F1 | `valid_count/n_pred`、`valid_count/n_gt` | ✅ 一致 |

差异点（均不影响"是否复现同一指标"，但需要说明）：

1. **相似度被截断到 [0,1]**：`np.clip(dot, 0, 1)`。论文未说明截断。BGE-M3 余弦相似度通常为 0.3–0.9，截断上界几乎不触发；下界会把负相关置 0，与"门控后 s=0"效果相同。
2. **无效预测计入分母**：解析失败（时间戳非法、`start>=end`）的预测不会进入匹配，但仍计入 `|P|`。论文未讨论解析失败的样本。实现比论文更严格。官方标注自身存在 14 个零长度区间（训练 12、测试 2，见数据审计），这些 GT 同样无法被匹配，会压低 `R`。
3. **空集合的边界约定**：`|G|=|P|=0` 时实现返回 P=R=1；只有一边为空时返回 0。论文未定义。评估数据中每个问题至少 1 条证据，正常情况下不会触发。

## 2. 软匹配与训练奖励

### 论文

- 附录 B.2：去掉硬阈值，`s_ij^soft = IoU_ij · Sim_ij` 对所有 `(i,j)`；`P_soft = Σ s^soft / |P|`，`R_soft = Σ s^soft / |G|`，`EG-F1_soft = 2 P_s R_s/(P_s+R_s)`。
- 正文 Eq. (4)：`R_evi = R_soft + R_EG-F1`（**相加**）。
- 附录 D：`λ_f / λ_e / λ_a = 0.1 / 0.6 / 0.3`；语义模型 **all-MiniLM-L6-v2**。

### 官方实现 `EG-Reasoner/examples/score_function/evidence_reward.py`

```python
score_matrix[i, j] = 0.5 * iou + 0.5 * sim          # 匹配权重
hard_hes  = F1(valid / n_pred, valid / n_gt)        # 阈值 iou≥τ_i, sim≥τ_s
soft_hes  = F1(sum(0.5*iou+0.5*sim) / n_pred, ... )
hes = 0.5 * soft_hes + 0.5 * hard_hes
```

### 对照结论

| 项目 | 论文 | 官方实现 | 差异 |
|---|---|---|---|
| 软匹配权重 | `IoU · Sim`（乘积） | `0.5·IoU + 0.5·Sim`（算术平均） | **实质差异** |
| 匹配代价 | 按 `IoU·Sim` 求最大权匹配 | 按 `0.5·IoU+0.5·Sim` 求最大权匹配 | 同上 |
| 软/硬组合 | `R_soft + R_hard`（和） | `0.5·R_soft + 0.5·R_hard`（平均） | 差一个常数因子 0.5（对 GRPO 组内归一化后不影响排序，但改变相对权重） |
| λ 权重 | `0.1 / 0.6 / 0.3`（format/evidence/accuracy） | `format_weight=0.1, evidence_weight=0.3, accuracy_weight=0.6` | **evidence 与 accuracy 权重互换** |
| 语义模型 | all-MiniLM-L6-v2 | BGE-M3 (`BAAI/bge-m3`) | **不同模型**，相似度分布不同，阈值不可直接比较 |
| 训练裁剪后处理 | 未提及 | `score in (1,0.5)` 且答案长度 > 5×golden 长度时降为 0.1 | 实现额外规则 |

> 这些差异是**论文与当前公开代码之间**的差异，不是本次复现引入的。按要求，未静默修改官方实现，仅记录在此。

## 3. 答案指标

- 论文附录 C.1：三档 `1 / 0.5 / 0`，由 rule-guided LLM 评审（inclusion + exclusion 原则）。
- 官方 `evaluation/answer_metrics.py`：完全相同的三档；`relaxed = mean(score)`，`strict = mean(score==1)`；默认 judge 模型 `gemini-2.5-pro`。
- 一致性：✅。差异：实现要求 judge 输出行首 `Answer: <0|0.5|1>`，否则记 0 并标记错误；失败的样本仍留在分母。论文未说明失败处理。

## 4. IoU-F1（辅助指标）

论文表格报告 `F1@0.1/0.3/0.5/0.7`。官方 `evaluate_iou` 在 **IoU 矩阵**上做匈牙利匹配，再按阈值统计有效匹配。论文正文未给出该辅助指标的正式定义，但阈值集合与表格一致。属实现自洽。
