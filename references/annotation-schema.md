# 可审查的因果记忆记录

使用 JSON 保存独立的审查稿。所有时间戳是从 0 开始的原始整数帧。审查稿可记录官方数据版本或文件哈希等溯源字段。

顶层的 `schema` 为 `rmbench.memory-review.v1`，`episodes` 为轨迹数组。每条轨迹用 `task_id`、`collection`、`episode_id` 唯一标识，`frame_count` 为原始帧数。限定在关键窗口的复查用 `scope: "partial"`。全轨迹审查用 `scope: "complete"`，至少保留第 0 帧和真实终帧的 Memory 快照。

| 字段 | 结构和约定 |
| --- | --- |
| `snapshots` | 必填。按帧升序，每条含 `frame`、英文 `memory` 和 `evidence`。记忆在下一条快照生效前保持。 |
| `source_subtasks` | 可选。原始 `{start, end, text}`。照录官方分段和文本，使用左闭右开区间，覆盖全轨迹。 |
| `stages` | 可选。每条含从 0 开始的 `subtask_index`、三个时间点 `observable_onset`、`outcome_frame`、`handoff_frame` 和以时间点字段名为键的 `evidence`。可用 `notes` 记录结果及证据限制。 |
| `decisions` | 可选。记录要验收的实际采样序列。每条含 `frame`、`prev_decision_frame`、`memory_frame`、`previous_memory_frame` 和两个布尔掩码 `supervise_memory`、`supervise_subtask`。 |

每条 `evidence` 是 `{frame, camera}` 数组。视角为 `head`、`left_wrist` 或 `right_wrist`。可附 `sha256` 记录解码后连续排列的 RGB 字节的 SHA-256。证据帧号不晚于所支持的标注帧。证据不足或无下一阶段时，对应的阶段时间点用 `null`，对应证据省略或写空数组。三个时间点独立判断，可同帧。动作已交接但仪表稍后才可辨时，可分别记录交接和仪表结果。

决策点的 `memory_frame` 取截至本帧的最近快照。`prev_decision_frame` 取实际序列中的上一个决策点。`previous_memory_frame` 则取截至上一个决策点的最近快照。没有对应帧时用 `null`。完整轨迹的决策序列覆盖真实终帧，终帧的 Subtask 监督关闭。只验收记忆和证据时可省略整项 `decisions`。

## 检查

最小的合成记录见 [examples/synthetic-review.json](../examples/synthetic-review.json)：

```bash
python3 scripts/validate_annotation.py examples/synthetic-review.json
```

如果提供官方 `language_annotation.json`，校验器会按该文件的原始时长计算区间，逐条比较保留的分段和英文文本：

```bash
python3 scripts/validate_annotation.py review.json \
  --official-annotations cover_blocks demo_clean path/to/language_annotation.json
```

每个任务及数据分组可附一个官方文件。校验报告覆盖字段、时序、终帧及提供的原文对照。证据哈希只检查格式，视觉判断仍需回看原图。
