#!/bin/bash
# Batch run Claude Code with --effort max to solve tasks
# Experiment directories get "-max" marker in config name
#
# Usage: ./run_claude_batch_max.sh [parallel] [task_filter_regex]
# Example: ./run_claude_batch_max.sh 10 "^T(09|1[0-8]):"   # T09-T18 with 10 parallel

set -e

BASE_DIR="/Users/zihanwu/Public/codes/huawei-eval"
EXPERIMENT_DIR="$BASE_DIR/experiment"
BASE_REPO="$BASE_DIR/base_repo"
PARALLEL="${1:-10}"
TASK_FILTER="${2:-.*}"   # regex filter applied to task_id:prompt_type
RUN_DATE=$(date +%Y-%m-%d)
CONFIG="claude-opus-max"

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

  # Create experiment directory by copying repo
  cp -r "$src_repo" "$exp_dir"

  # Record metadata
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

  # Read prompt
  local prompt_content=$(cat "$prompt_file")

  # Run Claude Code with --effort max
  local log_file="$exp_dir/claude_run.log"
  local json_log="$exp_dir/claude_run.jsonl"

  cd "$exp_dir"

  timeout 1200 claude \
    --model opus \
    --effort max \
    --dangerously-skip-permissions \
    --permission-mode bypassPermissions \
    --print \
    --output-format stream-json \
    --verbose \
    --no-session-persistence \
    "$prompt_content" \
    < /dev/null \
    > "$json_log" 2>&1 || true

  # Check if session ended with a question, and if so resume with recommended answer
  # Note: With stream-json format, check for 'user' message type (Claude asking question)
  if [[ -s "$json_log" ]]; then
    # Look for the last line type to see if it's a 'user' message (question)
    last_line=$(tail -1 "$json_log")

    if echo "$last_line" | grep -q '"type":"user"'; then
      echo "RESUME: $exp_name (Claude asked a question, resuming with recommended answer)"
      # Extract session_id from any line that contains it (stream-json compatible)
      session_id=$(python3 -c "
import json
with open('$json_log') as f:
    for line in f:
        try:
            d = json.loads(line.strip())
            if 'session_id' in d:
                print(d['session_id'])
                break
        except:
            continue
" 2>/dev/null)

      if [[ -n "$session_id" ]]; then
        timeout 1200 claude \
          --resume "$session_id" \
          --model opus \
          --effort max \
          --dangerously-skip-permissions \
          --print \
          --output-format stream-json \
          "1" \
          < /dev/null \
          >> "$json_log" 2>&1 || true
      fi
    fi
  fi

  cd "$EXPERIMENT_DIR"

  # Check if any changes were made
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
export BASE_DIR EXPERIMENT_DIR BASE_REPO RUN_DATE CONFIG

# Main
echo "=== Claude Code Batch Run (MAX EFFORT) ==="
echo "Model: opus"
echo "Config: $CONFIG"
echo "Effort: max"
echo "Parallel: $PARALLEL"
echo "Task filter: $TASK_FILTER"
echo "Date: $RUN_DATE"
echo ""

# Get and filter tasks
all_tasks=$(get_tasks | grep -E "$TASK_FILTER")
total=$(echo "$all_tasks" | grep -c . || true)
echo "Matching tasks: $total"
echo ""

# Record batch info
cat > "$EXPERIMENT_DIR/claude_batch_max_info.json" << EOF
{
  "batch_start": "$(date -Iseconds)",
  "agent": "claude-code",
  "model": "opus",
  "config": "$CONFIG",
  "effort": "max",
  "parallel": $PARALLEL,
  "task_filter": "$TASK_FILTER",
  "total_tasks": $total
}
EOF

# Run in parallel
echo "$all_tasks" | xargs -P "$PARALLEL" -I {} bash -c 'run_task "$@"' _ {}

echo ""
echo "=== Batch Complete ==="
