---
name: rmbench-memory-labeling
description: Draft, repair, or audit causal RMBench Memory labels and visual handoffs from synchronized HDF5 camera frames. Use for stale observations, missing stage history, premature subtask transitions, or whole-trajectory relabeling. 适用于记忆补标、纠错与关键帧复核。
---

# RMBench 记忆标注

以同步原图建立事实、核定生效时点，再重写当前 Memory。官方 Subtask 区间提供检查位置，原始文案和区间照录。

1. **确定范围和对象。** 记录数据版本、任务、集合、轨迹和原始帧号。用早期画面绑定对象身份、原位及在任务中的角色。区分单次变化、阶段和整条轨迹的复核范围。
2. **对照变化前、变化时及动作结束后的画面。** 每组取截至目标帧 `t` 的连续四帧 `[t−3,t−2,t−1,t]`，并列头部、左腕和右腕。运动较慢时前移窗口找参照。为每条事实保留真正支持它的帧和视角。看后续画面可以定位变化，每一帧的标签仅引用截至该帧的证据。
3. **记录事实和有效区间。** 审查稿区分持久绑定、已完成结果、当前状态。临时状态在最后仍成立的帧之后结束，证据不足时记录最后可辨事实。可见变化、结果确认、物理交接、官方切换和实际采样各自记时。查找应用于该任务的完成、撤离、重试与反向变化判据。
4. **重写完整英文 Memory。** 保留后续步骤需要的绑定和历史结果，当前动作只写仍成立的进度。结果有证据后，用结果替换过程。历史结果按其原来的时间与对象保留。审查稿把英文中的每个表达对应到支持它的事实，并可标出在有效期内每条摘要都要保留的事实。
5. **回查快照有效区间和实际决策。** 用校验器核对证据时间、状态互斥、过期描述及前序引用。分别查看变化前后实际采到的 Memory 目标和上一决策点参考 Memory。检查终帧和失败中断样例。记录已查证的范围，并保留原始数据及旧标注作为对照。

用 `scripts/render_evidence.py --window-end t` 渲染四帧三视角图。任务判据见 [references/task-rules.md](references/task-rules.md)。审查稿和校验命令见 [references/annotation-schema.md](references/annotation-schema.md)。事实条目与句子证据供离线审查，模型侧仍使用英文 Memory。
