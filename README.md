# RMBench Memory Labeling

A Codex skill and local scripts for reviewing temporal Memory annotations in RMBench. It links English clauses to time-bounded facts, records visible changes, outcomes and handoffs on separate clocks, and checks which facts enter supervised decisions.

## Install the skill

```bash
git clone https://github.com/Minghe111/rmbench-memory-labeling.git ~/.codex/skills/rmbench-memory-labeling
```

In Codex, invoke `$rmbench-memory-labeling` with a local trajectory, task and collection, and the frame interval to review. A review can cover a single transition or a full trajectory.

## Command-line tools

Python 3.11 or newer runs the annotation validator. Install the optional renderer dependencies in your own environment if you need camera contact sheets.

```bash
python -m pip install -r requirements.txt
python scripts/render_evidence.py path/to/episode.hdf5 --window-end 120 \
  --output evidence.png --metadata evidence.json
python3 scripts/validate_annotation.py examples/semantic-review.json
```

The renderer reads all three synchronized camera streams by default. `--window-end 120` shows raw frames 117 through 120, with one row per frame and one column per camera. To compare individually selected frames, use `--frames 100 110 120`. The synthetic review includes button pressing, cover transitions and battery trials. The validator checks fact lifetimes, clause references, decision history and official intervals when supplied. It reports fact coverage when supervised decisions are provided. Review the images to determine whether each claim matches its evidence. See the [task guide](references/task-rules.md) and [annotation schema](references/annotation-schema.md).

## 中文简要说明

使用 `$rmbench-memory-labeling` 复核指定轨迹。依据四帧三视角画面记录每条事实的有效区间，分别标明可见变化、完成结果和物理交接。用当前仍成立的事实重写英文 Memory，复核实际采样点的监督覆盖及前序记忆。事实记录和原图证据供离线审查。

Sources: [RMBench](https://github.com/RoboTwin-Platform/RMBench), [official HDF5 data](https://huggingface.co/datasets/TianxingChen/RMBench), [Multi-Scale Embodied Memory](https://arxiv.org/abs/2603.03596v2).

The skill and scripts are available under the [MIT License](LICENSE). Use the upstream dataset under its published terms.
