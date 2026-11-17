# 可审查的因果记忆记录

用 JSON 保存审查稿。帧号为从 0 开始的原始整数帧。顶层的 `schema` 为 `rmbench.memory-review.v1`，`episodes` 为轨迹数组。每条轨迹用 `task_id`、`collection`、`episode_id` 唯一标识，`frame_count` 为原始帧数。`scope: "complete"` 至少保留首帧和真实终帧的 Memory 快照。`scope: "partial"` 用于片段复核。

| 字段 | 结构和约定 |
| --- | --- |
| `snapshots` | 必填。按帧升序，每条含 `frame`、英文 `memory` 和 `evidence`。快照持续到下一条，末条持续到审查范围结束。 |
| `facts` | 可选。给出事实的有效区间和证据。提供后，所有快照都需用 `claims` 将英文内容关联到事实。旧审查稿仍可直接校验。 |
| `review_end` | 提供 `facts` 的片段复核可设排他结束帧，范围为 `1…frame_count`。对应快照和决策均在其前。省略时范围持续到轨迹末尾。 |
| `source_subtasks` | 可选。照录官方 `{start, end, text}`，左闭右开且覆盖全轨迹。片段复核也保留官方原区间。 |
| `stages` | 可选。每条含从 0 开始的 `subtask_index`、`observable_onset`、`outcome_frame`、`handoff_frame` 和以这三个时间点字段名为键的 `evidence`。各时点独立。 |
| `decisions` | 可选。每条含 `frame`、`prev_decision_frame`、`memory_frame`、`previous_memory_frame`、`supervise_memory` 和 `supervise_subtask`。完整轨迹的决策序列覆盖真实终帧，终帧的 Subtask 监督关闭。 |

`evidence` 为 `{frame, camera}` 数组，视角为 `head`、`left_wrist` 或 `right_wrist`。可附 `sha256` 记录解码后连续排列的 RGB 字节的校验值。支持某个事实或时点的画面须在该时点及以前。阶段时点未确定或没有后继操作时填 `null`，对应证据可省略或写空数组。

## 事实及快照

每条事实含下列字段。

| 字段 | 含义 |
| --- | --- |
| `id` | 本轨迹内唯一的事实标识，供快照引用。 |
| `kind` | `binding` 是初始身份、位置或角色关系。 `outcome` 是已观察的历史结果。 `state` 是当前状态或动作进度。 |
| `subject`、`predicate`、`value` | 主体、关系、值。沿轨迹复用对象标识和关系名。同一种类下相同的主体与关系同一时刻只保留一条有效事实。分开的操作尝试用不同主体，例如 `trial_1` 与 `trial_2`。 |
| `start`、`end` | 证据支持的左闭右开区间 `[start,end)`。 `end: null` 表示仍有效到轨迹结束。 |
| `evidence`、`end_evidence` | `evidence` 支持事实的生效。事实在轨迹中结束时提供 `end_evidence`，其帧号截至排他结束帧，并至少有一帧达到或晚于生效帧。 |
| `required_in_memory` | 可选布尔值，默认为 `false`。标为 `true` 时，与事实有效期有交集的每条快照均须在 `claims` 引用它。生效和过期时点落在原快照中间时，按需要拆分快照。 |

快照含 `claims` 数组。每条为 `{"text": "...", "facts": ["fact-id"]}`。按原顺序拼接各条文本，归一化空白后须与 `memory` 一致。每条表达可引用多条事实。引用的事实须覆盖整条快照的有效区间。事实在中途结束时，最迟在其排他结束帧写入新的快照，或结束片段复核。片段开始时可引用已经生效且持续有效的历史事实。

同一个对象可以在历史上放到某处、当前又被夹持。历史结果与当前状态分别建条目，重试结果依附于对应尝试。先用取证窗口确定相应的时点，再据有效事实重写完整英文句子。事实与句子引用用于审查，模型输入和输出仍是自然语言。

## 决策投影

决策点的 `memory_frame` 取截至本帧的最近快照。 `prev_decision_frame` 取实际序列中的上一个决策点。 `previous_memory_frame` 则取截至上一个决策点的最近快照。没有对应帧时用 `null`。核验时同时查看当前目标及上一决策点实际读取的记忆。临时事实可以在四帧图中得到确认，其整个区间也可能落在相邻采样点之间。

提供决策序列后，校验报告统计出现在开启 Memory 监督的目标中的不同事实。该统计反映采样覆盖，短时信息是否需要补采由任务目标决定。

## 检查

[语义审查合成示例](../examples/semantic-review.json)涵盖按键、遮盖和电池试插。 [基础格式示例](../examples/synthetic-review.json)也可用于兼容性检查。

```bash
python3 scripts/validate_annotation.py examples/semantic-review.json
```

可为每个任务和集合附一份官方 `language_annotation.json`。校验器按原始时长逐条比较官方分段及英文文本。

```bash
python3 scripts/validate_annotation.py review.json \
  --official-annotations cover_blocks demo_clean path/to/language_annotation.json
```

校验器能定位未生效、已过期、重叠冲突和错误的前序引用。图像是否支持所记事实，以及英文的意思是否和引用一致，仍由逐句复核确定。脚本仅校验证据哈希的格式。
