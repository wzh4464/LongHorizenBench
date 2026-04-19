#!/bin/bash
# K Benchmark Task Runner
# Executes K benchmark tasks with --effort max, hook-based auto-reply
# Usage: ./run_k_benchmark.sh "K1:short,K1:long,K2:short,K2:long"

set -e

# Configuration
BASE_DIR="/Users/zihanwu/Public/codes/huawei-eval"
EXPERIMENT_DIR="$BASE_DIR/experiment"
BASE_REPO="$BASE_DIR/base_repo"
RUN_DATE=$(date +%Y-%m-%d)
CONFIG="claude-opus-max"

# Parse task list argument
TASK_LIST="${1:-K1:short}"
IFS=',' read -ra TASK_SPECS <<< "$TASK_LIST"

echo "=== K Benchmark Task Runner ==="
echo "Tasks: ${#TASK_SPECS[@]}"
echo "Date: $RUN_DATE"
echo ""

# Function to run a single task
run_task() {
  local task_spec="$1"
  local task_id=$(echo "$task_spec" | cut -d: -f1)
  local prompt_type=$(echo "$task_spec" | cut -d: -f2)

  local exp_base="${task_id}-${CONFIG}-${prompt_type}-${RUN_DATE}"
  local exp_name="$exp_base"
  local exp_dir="$EXPERIMENT_DIR/$exp_name"

  # If directory already exists, append run number suffix
  local run_num=2
  while [[ -d "$exp_dir" ]]; do
    exp_name="${exp_base}-run${run_num}"
    exp_dir="$EXPERIMENT_DIR/$exp_name"
    ((run_num++))
  done

  # Check sources
  local src_repo="$BASE_REPO/$task_id/repo"
  local prompt_file="$BASE_REPO/$task_id/prompts/${task_id}-${prompt_type}.md"

  if [[ ! -d "$src_repo" ]] || [[ ! -f "$prompt_file" ]]; then
    echo "SKIP: $exp_name (missing repo or prompt)"
    return 0
  fi

  echo "RUN: $exp_name"

  # Copy repo
  cp -r "$src_repo" "$exp_dir"

  # Write metadata
  cat > "$exp_dir/run_metadata.json" << EOF
{
  "task_id": "$task_id",
  "prompt_type": "$prompt_type",
  "agent": "claude-code",
  "model": "opus",
  "config": "$CONFIG",
  "effort": "max",
  "run_date": "$RUN_DATE",
  "prompt_file": "$prompt_file"
}
EOF

  local prompt_content=$(cat "$prompt_file")
  local json_log="$exp_dir/claude_run.jsonl"

  # Setup auto-answer hook
  mkdir -p "$exp_dir/.claude"

  cat > "$exp_dir/.claude/auto_answer.py" <<'PY'
#!/usr/bin/env python3
import json
import sys

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
PY

  chmod +x "$exp_dir/.claude/auto_answer.py"

  cat > "$exp_dir/.claude/settings.local.json" <<'JSON'
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
JSON

  # Run Claude
  cd "$exp_dir"

  timeout 18000 claude \
    --model opus \
    --effort max \
    --dangerously-skip-permissions \
    --permission-mode bypassPermissions \
    --settings .claude/settings.local.json \
    --print \
    --output-format stream-json \
    --verbose \
    --no-session-persistence \
    "$prompt_content" \
    < /dev/null \
    > "$json_log" 2>&1 || true

  cd "$EXPERIMENT_DIR"

  # Check results
  if [[ -d "$exp_dir/.git" ]]; then
    local changes=$(cd "$exp_dir" && git status --porcelain | wc -l | tr -d ' ')
    local jsonl_size=$([ -f "$exp_dir/claude_run.jsonl" ] && wc -c < "$exp_dir/claude_run.jsonl" || echo 0)

    # Check final status
    local last_line=$(tail -1 "$exp_dir/claude_run.jsonl" 2>/dev/null || echo "")
    if echo "$last_line" | grep -q '"type":"result"'; then
      echo "DONE: $exp_name (files=$changes, size=$jsonl_size bytes, status=✅ COMPLETE)"
    else
      echo "DONE: $exp_name (files=$changes, size=$jsonl_size bytes, status=⚠️ INCOMPLETE)"
    fi
  else
    echo "DONE: $exp_name"
  fi
}

# Run all tasks
for task_spec in "${TASK_SPECS[@]}"; do
  run_task "$task_spec"
  echo ""
done

echo "=== All Tasks Complete ==="
