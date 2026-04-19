---
name: diff-eval-claude
description: 使用 Claude Code agent team 批量评测指定目录中的实验。并行评测，报告名称包含 "claude"。Trigger on "/diff-eval-claude", "claude eval", "用 claude 评测".
argument-hint: <eval-dir-or-list>
---

# Diff Eval Claude: Agent Team 并行评测

使用 Claude Code agent team 对多个实验目录并行运行 diff-eval-local 评测。

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `eval-dir-or-list` | Yes | 包含实验目录的父目录，或逗号分隔的实验目录列表 |

## Usage

```bash
# 评测某目录下所有实验
/diff-eval-claude experiment/eval-batch-T11-T15

# 评测指定的几个目录
/diff-eval-claude T11-claude-opus-max-short-20260415,T11-claude-opus-max-long-20260415

# 相对于 experiment/ 的路径
/diff-eval-claude experiment/T11-claude-opus-max-short-20260415
```

## 报告命名

每个实验目录内生成：`eval_report-claude.md`（不覆盖默认的 `eval_report.md`）

## Architecture

### Phase 1: 扫描实验目录

```python
# 如果参数是目录，扫描其中含 run_metadata.json 的子目录
# 如果参数是逗号分隔列表，直接使用各路径
experiment_dirs = []
arg = "<eval-dir-or-list>"

if "," in arg:
    experiment_dirs = [p.strip() for p in arg.split(",")]
else:
    import os, json
    for entry in sorted(os.listdir(arg)):
        path = os.path.join(arg, entry)
        if os.path.isdir(path) and os.path.exists(os.path.join(path, "run_metadata.json")):
            experiment_dirs.append(path)
```

用 bash 确认：
```bash
EVAL_INPUT="<eval-dir-or-list>"
if [[ -d "$EVAL_INPUT" && "$EVAL_INPUT" != *","* ]]; then
  DIRS=$(find "$EVAL_INPUT" -maxdepth 1 -name "run_metadata.json" | xargs -I{} dirname {} | sort)
else
  IFS=',' read -ra DIRS <<< "$EVAL_INPUT"
fi
echo "Found $(echo "$DIRS" | wc -l) experiment dirs"
echo "$DIRS"
```

### Phase 2: 创建 Team

Team 名称从输入路径派生，格式 `eval-claude-<slug>-<DATE>`：

```python
import re, datetime
slug = re.sub(r'[^a-zA-Z0-9]', '-', os.path.basename(arg.rstrip('/')))[:30]
date = datetime.datetime.now().strftime("%Y%m%d")
team_name = f"eval-claude-{slug}-{date}"
# TeamCreate(team_name=team_name, description="Claude Code 批量评测")
```

若输入为列表（无公共父目录），slug 取第一个目录名前缀。

### Phase 3: 创建 Tasks

每个实验目录创建一个 TaskCreate：

```python
for exp_dir in experiment_dirs:
    meta = json.load(open(f"{exp_dir}/run_metadata.json"))
    task_id = meta.get("task_id", "")
    prompt_type = meta.get("prompt_type", "")
    # 解析 GT 路径
    repo_root = "<project-root>"  # /Users/zihanwu/Public/codes/huawei-eval
    gt_diff = f"{repo_root}/base_repo/{task_id}/eval/gt_diff.patch"
    hw_files = f"{repo_root}/base_repo/{task_id}/eval/handwritten_files.txt"
    prompt_file = f"{repo_root}/base_repo/{task_id}/prompts/{task_id}-{prompt_type}.md"
    
    TaskCreate(
        subject=f"评测 {os.path.basename(exp_dir)}",
        description=f"""experiment_dir: {exp_dir}
gt_diff: {gt_diff}
hw_files: {hw_files}
prompt_file: {prompt_file}
report_name: eval_report-claude.md"""
    )
```

### Phase 4: 并行启动 Agents

所有 Task 创建完毕后，一次发出所有 Agent 调用（单条消息多 tool use）：

```python
for exp_dir in experiment_dirs:
    name = f"eval-{os.path.basename(exp_dir)[:20]}"
    Agent(
        subagent_type="general-purpose",
        name=name,
        team_name=team_name,
        model="opus",
        mode="bypassPermissions",
        run_in_background=True,
        prompt=EVAL_AGENT_PROMPT  # 见下方模板
    )
```

## Agent Prompt 模板

```
你是评测 agent，负责对一个实验目录运行 diff-eval-local 评测。

## 认领任务
TaskList → 找 status=pending 任务 → TaskUpdate(owner=自己名字, status=in_progress)

## 从 task description 读取路径
- experiment_dir: 实验目录路径
- gt_diff: GT diff 文件路径
- hw_files: handwritten_files.txt 路径
- prompt_file: prompt 文件路径（可选）
- report_name: eval_report-claude.md

## 评测流程（严格按照 diff-eval-local 规范）

### Step 1: 读取 HW 文件列表
```bash
cat "$HW_FILES"
HW_COUNT=$(wc -l < "$HW_FILES" | tr -d ' ')
```

### Step 2: 生成实验 diff
```bash
# Tracked changes
git -C "$REPO" diff HEAD --stat
git -C "$REPO" diff HEAD --name-only

# Untracked files
git -C "$REPO" ls-files --others --exclude-standard | grep -v '^\.'

# Full diff (tracked + untracked)
git -C "$REPO" diff HEAD
# 再对 untracked files 生成 unified diff
```

### Step 3: 读取 GT diff
```bash
grep -c '^diff --git' "$GT_DIFF"
grep '^diff --git' "$GT_DIFF" | sed 's|^diff --git a/.* b/||'
cat "$GT_DIFF"
```

### Step 4: 确定性文件覆盖率（必须用 bash set 运算，禁止 LLM 判断）
```bash
EVAL_DIR=$(mktemp -d)
LC_ALL=C sort "$HW_FILES" > "$EVAL_DIR/hw.txt"
{ git -C "$REPO" diff HEAD --name-only; git -C "$REPO" ls-files --others --exclude-standard | grep -v '^\.' ; } | LC_ALL=C sort -u > "$EVAL_DIR/gen.txt"
LC_ALL=C comm -12 "$EVAL_DIR/hw.txt" "$EVAL_DIR/gen.txt" > "$EVAL_DIR/covered.txt"
LC_ALL=C comm -23 "$EVAL_DIR/hw.txt" "$EVAL_DIR/gen.txt" > "$EVAL_DIR/missing.txt"
COVERED=$(wc -l < "$EVAL_DIR/covered.txt" | tr -d ' ')
TOTAL=$(wc -l < "$EVAL_DIR/hw.txt" | tr -d ' ')
```

### Step 5: 函数覆盖率（bash set 运算）
参照 diff-eval-local 的 Step 3。

### Step 6: 语义分析 + 评分

参照 diff-eval-local 的 scoring_rubric：
- A (0-5): Functional Correctness
- B (0-5): Completeness (仅 HW 文件范围)
- C (0-5): Behavioral Equivalence

Verdict: PASS = A≥4 AND B≥4 AND C≥3; FAIL = A≤1 OR destructive; PARTIAL = otherwise

### Step 7: 写报告
保存到 `<experiment_dir>/eval_report-claude.md`，格式：

```markdown
## Evaluation Report

**Evaluator**: Claude Code (claude-opus-max)

### Summary
[1-3 sentences]

### Verdict: [PASS / PARTIAL / FAIL]

### Scores
- **A. Functional Correctness**: [X]/5 — [justification]
- **B. Completeness**: [X]/5 — [justification, HW scope]
- **C. Behavioral Equivalence**: [X]/5 — [justification]

### Deterministic Coverage
#### HW File Coverage: [X]/[Y] = [Z]%
#### Function Coverage: [X]/[Y] = [Z]%

### Requirements Checklist
### Analysis
### Confidence: [0.0-1.0]
```

## 禁止
- 不要读取 eval/ 目录内容（GT 已通过 task description 传入路径，直接读文件即可，但不能遍历 eval/ 目录找其他文件）
- 不要使用 WebFetch/WebSearch 查找参考实现
- 不要 git commit
- 不要用 TaskCreate/TaskDelete
```

## Phase 5: 监控

等待 agent 完成通知，汇总：

```bash
for dir in $DIRS; do
  report="$dir/eval_report-claude.md"
  if [[ -f "$report" ]]; then
    verdict=$(grep "^### Verdict:" "$report" | head -1)
    echo "$dir: $verdict"
  else
    echo "$dir: (pending)"
  fi
done
```

## Notes

- **Team name**: `eval-claude-<slug>-<DATE>`
- **Report file**: `<exp_dir>/eval_report-claude.md`
- **并行度**: 实验数 = agent 数，全部同时启动
- **GT 路径解析**: 从 `run_metadata.json` 读取 task_id，自动定位 `base_repo/<task_id>/eval/`
- **B 分仅针对 HW 文件**，禁止 LLM 自行判断文件覆盖，必须用 bash comm 计算
