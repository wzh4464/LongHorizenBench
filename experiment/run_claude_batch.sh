#!/bin/bash
# Batch run Claude Code to solve tasks
#
# Usage: ./run_claude_batch.sh [parallel] [limit]
# Example: ./run_claude_batch.sh 10 20  # 10 parallel, first 20 tasks

set -e

BASE_DIR="/Users/zihanwu/Public/codes/huawei-eval"
EXPERIMENT_DIR="$BASE_DIR/experiment"
BASE_REPO="$BASE_DIR/base_repo"
PARALLEL="${1:-10}"
LIMIT="${2:-999}"
RUN_DATE=$(date +%Y-%m-%d)
CONFIG="claude-opus"

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
  "run_date": "$RUN_DATE",
  "prompt_file": "$prompt_file"
}
EOF

  # Read prompt
  local prompt_content=$(cat "$prompt_file")

  # Run Claude Code
  local log_file="$exp_dir/claude_run.log"
  local json_log="$exp_dir/claude_run.jsonl"

  cd "$exp_dir"

  # Run with --dangerously-skip-permissions to auto-accept all
  # Use --print for non-interactive, --model opus for best results
  timeout 1200 claude \
    --model opus \
    --dangerously-skip-permissions \
    --permission-mode bypassPermissions \
    --print \
    --output-format stream-json \
    --verbose \
    --no-session-persistence \
    "$prompt_content" \
    < /dev/null \
    > "$json_log" 2>&1 || true

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
echo "=== Claude Code Batch Run ==="
echo "Model: opus"
echo "Config: $CONFIG"
echo "Parallel: $PARALLEL"
echo "Date: $RUN_DATE"
echo ""

# Count tasks
all_tasks=$(get_tasks)
total=$(echo "$all_tasks" | wc -l | tr -d ' ')
echo "Total tasks: $total"

# Filter to limit
tasks_to_run=$(echo "$all_tasks" | head -$LIMIT)
to_run=$(echo "$tasks_to_run" | wc -l | tr -d ' ')
echo "Running: $to_run tasks"
echo ""

# Record batch info
cat > "$EXPERIMENT_DIR/claude_batch_info.json" << EOF
{
  "batch_start": "$(date -Iseconds)",
  "agent": "claude-code",
  "model": "opus",
  "config": "$CONFIG",
  "parallel": $PARALLEL,
  "total_tasks": $to_run
}
EOF

# Run in parallel
echo "$tasks_to_run" | xargs -P "$PARALLEL" -I {} bash -c 'run_task "$@"' _ {}

echo ""
echo "=== Batch Complete ==="
