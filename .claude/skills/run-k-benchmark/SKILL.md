---
name: run-k-benchmark
description: Launch a multi-agent team to execute benchmark tasks in parallel. Team lead handles all setup (repo copy, hooks, metadata); agents directly code in their sessions without spawning subprocess claude invocations.
argument-hint: <task-spec-list>
---

# Run K Benchmark: Multi-Agent Parallel Execution

Launch a distributed team of agents to execute benchmark tasks in parallel.
**Team lead** prepares all experiment directories; **agents** directly execute coding tasks in their own sessions (no subprocess `claude` invocation).

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `task-spec-list` | Yes | Comma-separated task specs: `K1:short,K1:long,K2:short,K2:long` |

## Configuration (Hardcoded)

| Setting | Value |
|---------|-------|
| Model | `opus` |
| Permission Mode | `bypassPermissions` |
| Auto-reply | First option (via agent prompt instruction) |
| Team Size | N = number of task specs |
| Execution | Parallel (all agents run simultaneously) |

## Usage

```bash
# Run K1 short and long (2 parallel agents)
/run-k-benchmark K1:short,K1:long

# Run K1-K4 all variants (8 parallel agents)
/run-k-benchmark K1:short,K1:long,K2:short,K2:long,K3:short,K3:long,K4:short,K4:long
```

## Architecture: Lead Setup + Agent Direct Execution

### Phase 1: Team Lead Setup

The **team lead** (main session) does ALL preparation before spawning any agent:

```
1. Parse task specs from input
2. Create team: TeamCreate(team_name="k-benchmark-<N>-<DATE>")
3. For EACH task spec:
   a. Copy base_repo/<TASK>/repo/ → experiment/<TASK>-claude-opus-max-<TYPE>-<DATE>/
   b. Write run_metadata.json into experiment dir
   c. Write .claude/auto_answer.py into experiment dir
   d. Write .claude/settings.local.json into experiment dir
   e. Copy prompt file → experiment dir (reference only, agent reads from base_repo)
4. Create one TaskCreate per task spec in shared TaskList
```

#### 1a. Copy Repo

```bash
rsync -a --copy-links base_repo/<TASK>/repo/ experiment/<TASK>-claude-opus-max-<TYPE>-<DATE>/
```

Use `rsync -a --copy-links` instead of `cp -r` to dereference symlinks and avoid broken symlinks in the copy.
Always copy a fresh repo from base_repo. If the experiment directory already exists, append a run number suffix (e.g., `-run2`, `-run3`).

#### 1b. Write Metadata

```json
// experiment/<TASK>-claude-opus-max-<TYPE>-<DATE>/run_metadata.json
{
  "task_id": "<TASK>",
  "prompt_type": "<TYPE>",
  "agent": "claude-code",
  "model": "opus",
  "config": "claude-opus-max",
  "run_date": "<DATE>"
}
```

#### 1c. Write Auto-Reply Hook

```python
# experiment/<...>/.claude/auto_answer.py
#!/usr/bin/env python3
import json, sys
payload = json.load(sys.stdin)
event = payload.get("hook_event_name")
tool_name = payload.get("tool_name")
tool_input = payload.get("tool_input", {})

def choose_answer(q):
    opts = q.get("options", [])
    return opts[0].get("label", "1") if opts else "1"

if event == "PreToolUse" and tool_name == "AskUserQuestion":
    qs = tool_input.get("questions", [])
    ans = {q.get("question"): choose_answer(q) for q in qs if q.get("question")}
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
           "updatedInput": {"questions": qs, "answers": ans}}}
elif event == "PreToolUse" and tool_name == "ExitPlanMode":
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow", "updatedInput": tool_input}}
elif event == "PermissionRequest":
    out = {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow", "updatedInput": tool_input}}}
else:
    out = {}
json.dump(out, sys.stdout)
sys.stdout.write("\n")
```

#### 1d. Write Hook Config

```json
// experiment/<...>/.claude/settings.local.json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "AskUserQuestion|ExitPlanMode",
      "hooks": [{"type": "command", "command": "python3 .claude/auto_answer.py"}]
    }],
    "PermissionRequest": [{
      "matcher": "",
      "hooks": [{"type": "command", "command": "python3 .claude/auto_answer.py"}]
    }]
  }
}
```

#### 1e. Create Tasks

```python
for each spec in [K1:short, K1:long, ...]:
    TaskCreate(
        subject="运行 <TASK>:<TYPE>",
        description="experiment dir path, prompt file path, task context"
    )
```

### Phase 2: Agent Spawning

After ALL setup is complete, spawn one agent per task:

```python
for each task:
    Agent(
        subagent_type="general-purpose",
        name="agent-<TASK>-<TYPE>",
        team_name="k-benchmark-<N>-<DATE>",
        model="opus",
        mode="bypassPermissions",
        prompt="<agent prompt template (see below)>"
    )
```

### Phase 3: Agent Direct Execution

Each agent **directly works on its experiment directory**. The agent IS the coder — it does NOT spawn a subprocess `claude` invocation.

Agent execution flow:

```
1. TaskList() → find unassigned task → TaskUpdate(owner=self, status=in_progress)
2. Read experiment directory path from task description
3. Read prompt content from base_repo/<TASK>/prompts/<TASK>-<TYPE>.md (ONLY prompts/ — never read eval/)
4. cd to experiment directory
5. Directly implement the task:
   - Read and understand the codebase
   - Edit/create files as needed
   - Run tests/verification
   - Iterate until complete
   - Do NOT git commit — leave all changes as dirty worktree (unstaged/untracked)
6. Report: TaskUpdate(status=completed, metadata={files_changed, summary})
7. Check TaskList for next available task; if none, go idle
```

### Phase 4: Monitoring

Main session monitors progress:

```bash
# Check output size and completion
for each experiment dir:
    wc -c < claude_run.jsonl
    tail -1 claude_run.jsonl | grep '"type":"result"'
    git status --porcelain | wc -l
```

## Agent Prompt Template

When spawning agents, use this prompt structure:

```
你是一个编码 agent，负责完成 benchmark 任务。

## 任务
认领一个未分配的任务（TaskList → 找 status=pending 的任务 → TaskUpdate 认领）。

## 执行流程
1. 从 task description 获取 experiment 目录路径
2. 读取 prompt: base_repo/<TASK>/prompts/<TASK>-<TYPE>.md
3. cd 到 experiment 目录，直接开始编码
4. 按照 prompt 要求实现功能（编辑文件、运行测试等）
5. 完成后 TaskUpdate(status=completed) 并报告修改文件数

## 禁止
- **绝对不要 git commit**——保留 dirty worktree，所有修改留在工作区（unstaged/untracked）
- 调用任何 memory 工具（read_memory, write_memory, /memory, /remember）
- 访问 .claude/projects/.../memory/ 目录
- 启动子进程调用 claude 命令
- 使用 TaskCreate/TaskDelete（只使用 TaskList/TaskUpdate）
- **绝对不要读取 base_repo/ 下的 eval/ 目录**（包括 ground_truth.diff、handwritten_files.txt、auto_generated_files.txt 等）——这是评估用的 GT 数据，agent 读取会污染实验
- **绝对不要读取 experiment/eval_results/ 目录**下的任何内容

## 注意
- 如果遇到选择性问题，选第一个选项
- 如果遇到 ExitPlanMode，直接 approve
- 工作目录是 experiment 目录，不要修改 base_repo
- 只能读取 base_repo/<TASK>/prompts/ 下的 prompt 文件，不能读取 base_repo 的其他非 repo 内容
```

## Key Design Decisions

### Lead Handles All Setup
All initialization (repo copy, hook files, metadata) is done by the team lead BEFORE agents are spawned.
- No duplicate setup work across agents
- Consistent configuration across all experiments
- Agents can start coding immediately upon claiming a task

### Agents Execute Directly (No Subprocess)
Agents work directly in their experiment directories. They do NOT spawn `timeout 18000 claude ...` subprocesses.
The agent itself IS the coding agent — no double-invocation overhead.

### No Memory for Agents
Agents are explicitly prohibited from using memory-related tools. This prevents:
- Cross-session state pollution
- Data consistency issues
- Distraction from task execution

### Hook-Based Auto-Reply
Pre-configured by Lead in each experiment directory. Handles:
- `AskUserQuestion` → auto-select first option
- `ExitPlanMode` → auto-approve
- `PermissionRequest` → auto-allow

## Notes

- **Team name**: `k-benchmark-<N>-<DATE>` (N = task count)
- **Agent names**: `agent-<TASK>-<TYPE>` (e.g., `agent-k3-short`)
- **Task coordination**: Via shared TaskList (`.claude/tasks/k-benchmark-.../`)
- **Experiment dir**: `experiment/<TASK>-claude-opus-max-<TYPE>-<DATE>/`
- **All agents run in parallel** with shared task coordination
