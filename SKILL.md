---
name: rmbench-memory-labeling
description: Draft, repair, or audit causal RMBench Memory labels and visual handoffs from synchronized HDF5 camera frames. Use for stale observations, missing stage history, premature subtask transitions, or whole-trajectory relabeling. 适用于记忆补标、纠错与关键帧复核。
---

# RMBench 记忆标注

复核以同步原图为准。分别记录当时可见的事实、阶段结果和下一阶段的物理交接。官方 Subtask 区间和既有 Memory 用于定位与比对。

1. **确定源数据和范围。** 记录官方版本、任务、集合、轨迹和原始帧号。区分单个样例、阶段复核与整条轨迹复核。保留官方子任务文案和半开帧区间。
2. **看图定位证据。** 同步查看头部与左右腕相机。围绕相关阶段查看操作前、首次可辨变化、落位或松夹、交接及终帧。候选检测用于缩小查找范围。为每条待修正的事实定位对应画面，并记录支持视角及帧。靠近、抓持与释放可以分别写成观测快照。若采样只确定了“最迟在某帧可见”，保留该时间精度。
3. **独立记三个时间。** 分别记录 `observable_onset`、`outcome_frame` 和 `handoff_frame`。当前可见事实先进入 Memory。阶段完成与下一动作各自等待相应证据，未知时间用 `null`。查看后续图像可定位证据，标注帧 `t` 的 Memory 只使用 `≤t` 的证据。
4. **写入英文 Memory。** 保留后续仍需要的对象身份、初始绑定和已有操作经历。把最近可见事实与当前状态的证据缺口写清楚。区分遮挡与盖住、夹持与放稳、动作完成与效果出现。明示过去的观测时间语义，避免把旧状态当成当前现场。
5. **沿实际采样时钟检查。** 核对修订帧、受影响的连续区间和后续决策读入的上一条 Memory。确认两个方向的反例、官方区间、角色开关和终帧约定。原始轨迹及旧标签作为对照，另存修订与证据。已看图复核的结论和待审候选分别记录。

任务取证标准和反例见 [references/task-rules.md](references/task-rules.md)。可用 `scripts/render_evidence.py` 从本地 HDF5 生成三相机联系图，并导出解码后的 RGB 哈希。结构化交付与时间线校验见 [references/annotation-schema.md](references/annotation-schema.md) 和 `scripts/validate_annotation.py`。结构校验通过后，视觉判断仍由支持帧复查。
