# RMBench Memory Labeling

A Codex skill and local scripts for reviewing temporal Memory annotations in RMBench. It records visible observations, stage outcomes, and physical handoffs on separate clocks and checks how a correction affects the next sampled decision.

## Install the skill

```bash
git clone https://github.com/Minghe111/rmbench-memory-labeling.git ~/.codex/skills/rmbench-memory-labeling
```

In Codex, invoke `$rmbench-memory-labeling` with a local trajectory, task and collection, and the frame interval to review. A review can cover a single transition or a full trajectory.

## Command-line tools

Python 3.11 or newer runs the annotation validator. Install the optional renderer dependencies in your own environment if you need camera contact sheets.

```bash
python -m pip install -r requirements.txt
python scripts/render_evidence.py path/to/episode.hdf5 --frames 100 110 120 \
  --output evidence.png --metadata evidence.json
python scripts/validate_annotation.py examples/synthetic-review.json
```

The renderer reads all three synchronized camera streams by default. The validation command checks structure, source interval alignment when supplied, and causality. Review the underlying images to establish the meaning of an annotation. See the [task guide](references/task-rules.md) and [annotation schema](references/annotation-schema.md).

## 中文简要说明

使用 `$rmbench-memory-labeling` 复核指定轨迹。先看三相机原图，再分别记录可见事实、阶段结果和物理交接。修订后核对实际下一个采样点读到的参考记忆。标注与支持证据单独保存。

Sources: [RMBench](https://github.com/RoboTwin-Platform/RMBench), [official HDF5 data](https://huggingface.co/datasets/TianxingChen/RMBench), [Multi-Scale Embodied Memory](https://arxiv.org/abs/2603.03596v2).

The skill and scripts are available under the [MIT License](LICENSE). Use the upstream dataset under its published terms.
