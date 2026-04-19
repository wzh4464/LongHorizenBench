#!/bin/bash
# Batch run cursor-agent (composer-2) to solve tasks
#
# Usage: ./run_cursor_batch.sh [parallel] [task_filter_regex]
# Example: ./run_cursor_batch.sh 5 ".*"       # all tasks, 5 parallel
# Example: ./run_cursor_batch.sh 5 "^K[1-4]:" # K1-K4 only

set -e

BASE_DIR="/Users/zihanwu/Public/codes/huawei-eval"
EXPERIMENT_DIR="$BASE_DIR/experiment"
BASE_REPO="$BASE_DIR/base_repo"
PARALLEL="${1:-5}"
TASK_FILTER="${2:-.*}"
RUN_DATE=$(date +%Y-%m-%d)
CONFIG="cursor-composer2"
MODEL="composer-2"

# Get all tasks
get_tasks() {
  for task_dir in "$BASE_REPO"/*/; do
    task_id=$(basename "$task_dir")
    for prompt_type in long short; do
      prompt_file="$task_dir/prompts/${task_id}-${prompt_type}.md"
      if [[ -f "$prompt_file" ]]; then
        echo "${task_id}:${prompt_type}"
      fi
    done
  done
}

# Run single task
run_task() {
  local task_spec="$1"
  local task_id=$(echo "$task_spec" | cut -d: -f1)
  local prompt_type=$(echo "$task_spec" | cut -d: -f2)

  local exp_name="${task_id}-${CONFIG}-${prompt_type}-${RUN_DATE}"
  local exp_dir="$EXPERIMENT_DIR/$exp_name"

  # Skip if already done
  if [[ -d "$exp_dir" ]]; then
    echo "SKIP: $exp_name (already exists)"
    return 0
  fi

  local src_repo="$BASE_REPO/$task_id/repo"
  local prompt_file="$BASE_REPO/$task_id/prompts/${task_id}-${prompt_type}.md"

  if [[ ! -d "$src_repo" ]] || [[ ! -f "$prompt_file" ]]; then
    echo "SKIP: $exp_name (missing repo or prompt)"
    return 0
  fi

  echo "RUN: $exp_name"

  cp -r "$src_repo" "$exp_dir"

  cat > "$exp_dir/run_metadata.json" << EOF
{
  "task_id": "$task_id",
  "prompt_type": "$prompt_type",
  "agent": "cursor-agent",
  "model": "$MODEL",
  "config": "$CONFIG",
  "run_date": "$RUN_DATE",
  "prompt_file": "$prompt_file"
}
EOF

  local prompt_content=$(cat "$prompt_file")
  local log_file="$exp_dir/claude_run.log"
  local json_log="$exp_dir/claude_run.jsonl"

  cd "$exp_dir"

  timeout 600 cursor-agent \
    --model "$MODEL" \
    --yolo \
    --print \
    --output-format json \
    --trust \
    "$prompt_content" \
    > "$json_log" 2> "$log_file" || true

  # Auto-answer if session ended with a question
  if [[ -s "$json_log" ]]; then
    result_text=$(python3 -c "
import json
with open('$json_log') as f:
    content = f.read().strip()
lines = [l for l in content.split('\n') if l.strip()]
for line in reversed(lines):
    try:
        d = json.loads(line)
        if d.get('type') == 'result':
            print(d.get('result', ''))
            break
    except:
        continue
" 2>/dev/null)
    last_chars=$(echo "$result_text" | tail -c 50 | tr -d '\n')
    if echo "$last_chars" | grep -q '？\|?'; then
      session_id=$(python3 -c "
import json
with open('$json_log') as f:
    content = f.read().strip()
lines = [l for l in content.split('\n') if l.strip()]
for line in reversed(lines):
    try:
        d = json.loads(line)
        if d.get('type') == 'result':
            print(d.get('session_id', d.get('chatId', '')))
            break
    except:
        continue
" 2>/dev/null)
      echo "RESUME: $exp_name (Claude asked a question, resuming)"
      if [[ -n "$session_id" ]]; then
        echo "1" | timeout 600 cursor-agent \
          --resume "$session_id" \
          --model "$MODEL" \
          --yolo \
          --print \
          --output-format json \
          --trust \
          >> "$json_log" 2>> "$log_file" || true
      fi
    fi
  fi

  cd "$EXPERIMENT_DIR"

  if [[ -d "$exp_dir/.git" ]]; then
    local changes=$(cd "$exp_dir" && git status --porcelain | wc -l | tr -d ' ')
    if [[ "$changes" -gt 0 ]]; then
      echo "DONE: $exp_name (changes: $changes files)"
    else
      echo "DONE: $exp_name (no changes)"
    fi
  else
    echo "DONE: $exp_name"
  fi
}

export -f run_task
export BASE_DIR EXPERIMENT_DIR BASE_REPO RUN_DATE CONFIG MODEL

echo "=== cursor-agent Batch Run ==="
echo "Model: $MODEL"
echo "Config: $CONFIG"
echo "Parallel: $PARALLEL"
echo "Task filter: $TASK_FILTER"
echo "Date: $RUN_DATE"
echo ""

all_tasks=$(get_tasks | grep -E "$TASK_FILTER")
total=$(echo "$all_tasks" | grep -c . || true)
echo "Matching tasks: $total"
echo ""

cat > "$EXPERIMENT_DIR/cursor_batch_info.json" << EOF
{
  "batch_start": "$(date -Iseconds)",
  "agent": "cursor-agent",
  "model": "$MODEL",
  "config": "$CONFIG",
  "parallel": $PARALLEL,
  "task_filter": "$TASK_FILTER",
  "total_tasks": $total
}
EOF

echo "$all_tasks" | xargs -P "$PARALLEL" -I {} bash -c 'run_task "$@"' _ {}

echo ""
echo "=== Batch Complete ==="
