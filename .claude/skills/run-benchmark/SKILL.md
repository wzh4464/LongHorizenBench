---
name: run-benchmark
description: 对指定 task×type 组合，并行运行 4 个 agent（Claude/Cursor/Codex/OpenCode）的标准跑法。包含 base_repo 清洁验证、eval 保护、CONSTRAINT_DIRECTIVE 注入、实验目录创建、各 agent 启动命令。
argument-hint: "<TASK>:<TYPE>[,<TASK>:<TYPE>...]  例: C2:short,C2:long,K2:short,K2:long"
---

# Run Benchmark: 4-Agent 并行实验

对一批 task:type 组合，用 4 个 agent 配置并行跑实验。

## 参数

| 参数 | 必须 | 说明 |
|------|------|------|
| task-type-list | 是 | 逗号分隔，如 `C2:short,C2:long,K2:short,K2:long` |
| agents | 否 | 逗号分隔，默认全部：`claude,cursor,codex,opencode` |
| date | 否 | 默认今日 `YYYYMMDD` |

## 用法示例

```
/run-benchmark C2:short,C2:long,K2:short,K2:long
/run-benchmark K1:short,K1:long  agents=claude,codex
```

---

## Step 0: 读取参数

```python
import datetime
args = "<task-type-list>"
agent_filter = "claude,cursor,codex,opencode"  # 默认全部
run_date = datetime.datetime.now().strftime("%Y%m%d")

specs = [s.strip() for s in args.split(",")]
tasks = list({s.split(":")[0] for s in specs})
```

---

## Step 1: 验证 base_repo 清洁（必须在 rsync 前）

```bash
REPO_ROOT="/Users/zihanwu/Public/codes/huawei-eval"
BASE_REPO="$REPO_ROOT/base_repo"

for TASK in <TASKS>; do
  REPO="$BASE_REPO/$TASK/repo"
  dirty=$(git -C "$REPO" diff HEAD --name-only | wc -l | tr -d ' ')
  untracked=$(git -C "$REPO" ls-files --others --exclude-standard \
    | grep -vE 'codex_review|\.log|^\.git' | wc -l | tr -d ' ')
  if [[ "$dirty" -gt 0 || "$untracked" -gt 0 ]]; then
    echo "ERROR: $TASK/repo contaminated! dirty=$dirty untracked_gt=$untracked"
    exit 1
  fi
  echo "OK: $TASK/repo clean"
done
```

**如发现污染：**
```bash
git -C "$REPO" checkout --               # 恢复 tracked 修改
git -C "$REPO" ls-files --others --exclude-standard  # 找新增 GT 文件
rm "$REPO/path/to/new_file"             # 手动删除新增 GT 文件
rm -f "$REPO/.git/index.lock"           # 若有 stale lock
```

---

## Step 2: 保护 eval 目录

```bash
for TASK in <TASKS>; do
  chmod 000 "$BASE_REPO/$TASK/eval" && echo "  chmod 000 $TASK/eval"
done
```

---

## Step 3: CONSTRAINT_DIRECTIVE（追加到所有 prompt）

```bash
CONSTRAINT_DIRECTIVE='

---

**Benchmark Constraints (MANDATORY)**:
- Do NOT read or access `eval/` directories, `handwritten_files.txt`, `gt_diff.patch`, or any ground-truth files
- Do NOT access parent directories (e.g., `../base_repo/`, `../experiment/`)
- Do NOT use web search to look up the specific patch, commit, PR, or KEP/JEP/RFC being implemented
- Implement using ONLY the existing codebase and the task description above
'
```

---

## Step 4: 创建实验目录（通用）

```bash
prepare_exp() {
  local TASK="$1" TYPE="$2" CONFIG="$3"
  local EXP_DIR="$REPO_ROOT/experiment/${TASK}-${CONFIG}-${TYPE}-${RUN_DATE}"
  [[ -d "$EXP_DIR" ]] && { echo "  [SKIP] $EXP_DIR exists"; echo "$EXP_DIR"; return; }
  rsync -a --copy-links "$BASE_REPO/$TASK/repo/" "$EXP_DIR/"
  cp "$BASE_REPO/$TASK/prompts/${TASK}-${TYPE}.md" "$EXP_DIR/TASK_PROMPT.md"
  echo "$EXP_DIR"
}
```

---

## Step 5: 各 Agent 运行命令

### Claude Code (config: claude-opus-max)

```bash
EXP_DIR=$(prepare_exp "$TASK" "$TYPE" "claude-opus-max")
cat > "$EXP_DIR/run_metadata.json" <<EOF
{"task_id":"$TASK","prompt_type":"$TYPE","agent":"claude-code","model":"opus","config":"claude-opus-max","run_date":"$RUN_DATE"}
EOF

# Hook 自动应答（防止 agent 交互式提问卡住）
mkdir -p "$EXP_DIR/.claude"
cat > "$EXP_DIR/.claude/settings.local.json" <<'HOOK'
{"hooks":{"PreToolUse":[{"matcher":"AskUserQuestion","hooks":[{"type":"command","command":"echo '{\"decision\":\"approve\",\"reason\":\"auto\"}'"}]}]}}
HOOK

prompt_content="$(cat "$EXP_DIR/TASK_PROMPT.md")${CONSTRAINT_DIRECTIVE}"
cd "$EXP_DIR"
timeout 7200 claude-yunwu \
  --model opus --effort max \
  --dangerously-skip-permissions --permission-mode bypassPermissions \
  --disallowedTools 'WebSearch,WebFetch,Skill' \
  --print --output-format stream-json --verbose \
  "$prompt_content" \
  < /dev/null > claude_run.jsonl 2>&1 || true
# 注意：2>&1 是必须的，否则 JSONL 捕获为 0B
# 使用 claude-yunwu 而非 claude；禁用 Skill 防止调用 superpowers；保留 session（不加 --no-session-persistence）
```

### Cursor (config: cursor-composer2)

```bash
EXP_DIR=$(prepare_exp "$TASK" "$TYPE" "cursor-composer2")
cat > "$EXP_DIR/run_metadata.json" <<EOF
{"task_id":"$TASK","prompt_type":"$TYPE","agent":"cursor","model":"composer-2","config":"cursor-composer2","run_date":"$RUN_DATE"}
EOF

prompt_content="$(cat "$EXP_DIR/TASK_PROMPT.md")${CONSTRAINT_DIRECTIVE}"
cd "$EXP_DIR"
timeout 7200 cursor-agent \
  --model composer-2 --yolo --print --output-format json --trust \
  "$prompt_content" > claude_run.jsonl 2> claude_run.log || true
# 注意：Cursor 在 timeout 终止时 JSONL 为 0B（正常，仅在正常退出时 flush）
```

### Codex gpt-5.4 (config: codex-gpt-5_4) — macOS 直接运行

```bash
EXP_DIR=$(prepare_exp "$TASK" "$TYPE" "codex-gpt-5_4")
cat > "$EXP_DIR/run_metadata.json" <<EOF
{"task_id":"$TASK","prompt_type":"$TYPE","agent":"codex","model":"gpt-5.4","config":"codex-gpt-5_4","run_date":"$RUN_DATE"}
EOF

prompt_content="$(cat "$EXP_DIR/TASK_PROMPT.md")${CONSTRAINT_DIRECTIVE}"
cd "$EXP_DIR"
echo "$prompt_content" | timeout 7200 codex exec \
  -m gpt-5.4 \
  --full-auto \
  -c web_search=disabled \
  -C "$EXP_DIR" \
  --json \
  - \
  > codex_events.jsonl 2> codex_output.log || true
# 警告：不要用 run_isolated.sh（Docker bwrap 在 macOS 上无法创建 namespace）
```

### OpenCode GLM-5.1 (config: opencode-glm51)

```bash
EXP_DIR=$(prepare_exp "$TASK" "$TYPE" "opencode-glm51")
cat > "$EXP_DIR/run_metadata.json" <<EOF
{"task_id":"$TASK","prompt_type":"$TYPE","agent":"opencode","model":"zhipuai-coding-plan/glm-5.1","config":"opencode-glm51","run_date":"$RUN_DATE"}
EOF
printf '%s' '{"mcp": {}}' > "$EXP_DIR/opencode.json"

prompt_content="$(cat "$EXP_DIR/TASK_PROMPT.md")${CONSTRAINT_DIRECTIVE}"
cd "$EXP_DIR"
timeout 7200 opencode run \
  --model "zhipuai-coding-plan/glm-5.1" \
  --dangerously-skip-permissions --pure --format json \
  "$prompt_content" \
  < /dev/null > claude_run.jsonl 2>&1 || true
```

---

## Step 6: 并行启动

```bash
for TASK_TYPE in <TASK:TYPE list>; do
  TASK="${TASK_TYPE%%:*}"; TYPE="${TASK_TYPE##*:}"
  run_claude   "$TASK" "$TYPE" &
  run_cursor   "$TASK" "$TYPE" &
  run_codex    "$TASK" "$TYPE" &
  run_opencode "$TASK" "$TYPE" &
done
wait
```

---

## Step 7: 恢复权限 + 汇总

```bash
for TASK in <TASKS>; do
  chmod 755 "$BASE_REPO/$TASK/eval" && echo "  chmod 755 $TASK/eval"
done

for TASK_TYPE in <TASK:TYPE list>; do
  TASK="${TASK_TYPE%%:*}"; TYPE="${TASK_TYPE##*:}"
  for CONFIG in claude-opus-max cursor-composer2 codex-gpt-5_4 opencode-glm51; do
    d="$REPO_ROOT/experiment/${TASK}-${CONFIG}-${TYPE}-${RUN_DATE}"
    [[ -d "$d" ]] || continue
    changed=$(git -C "$d" diff HEAD --name-only 2>/dev/null | wc -l | tr -d ' ')
    untracked=$(git -C "$d" ls-files --others --exclude-standard 2>/dev/null | grep -v '^\.' | wc -l | tr -d ' ')
    echo "  $TASK:$TYPE:$CONFIG => changed=$changed untracked=$untracked"
  done
done
```

---

## 反作弊审计（运行后）

```bash
# 扫描所有实验 JSONL 是否有 GT 泄漏
python3 experiment/audit_cheating.py

# 快速检查特定 JSONL
grep -c "gt_diff\|handwritten_files\|WebSearch\|WebFetch\|base_repo.*eval" \
  experiment/{TASK}-{CONFIG}-{TYPE}-{RUN_DATE}/claude_run.jsonl
```

---

## 已知问题

| 问题 | 原因 | 解决 |
|------|------|------|
| Codex 在 Docker 内所有 shell 命令失败 | bwrap 在 macOS Docker 容器内无法创建 namespace | 直接在 macOS 宿主机运行 codex exec |
| Claude JSONL 为 0B | stderr 未合并 | 加 `2>&1` |
| Cursor JSONL 为 0B | timeout 强制终止时未 flush | 正常现象，检查 claude_run.log |
| git checkout -- 后仍有 GT 文件 | gt_diff 新增的文件是 untracked，checkout -- 不删除 | 额外用 `git ls-files --others` 找并手动删除 |
| base_repo dirty 文件被 rsync 复制 | rsync 复制工作树（非 HEAD） | 实验前必须验证 base_repo 干净 |

---

## 实现时，在这里生成完整的 bash 脚本

根据参数解析后，生成一个完整的可执行脚本写到 `/tmp/run_benchmark_<slug>.sh`，然后后台运行：

```bash
bash /tmp/run_benchmark_<slug>.sh > /tmp/run_benchmark_<slug>.log 2>&1 &
echo "PID: $! | log: /tmp/run_benchmark_<slug>.log"
```

5 秒后读取日志确认启动正常。
