#!/bin/bash
# Test K3 with disabled plugins/skills

set -e

BASE_DIR="/Users/zihanwu/Public/codes/huawei-eval"
EXPERIMENT_DIR="$BASE_DIR/experiment"
BASE_REPO="$BASE_DIR/base_repo"
RUN_DATE=$(date +%Y-%m-%d)
CONFIG="claude-opus-max"

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

  # Run Claude Code with --effort max and stream-json
  local json_log="$exp_dir/claude_run.jsonl"

  cd "$exp_dir"

  timeout 2000 claude \
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
  if [[ -s "$json_log" ]]; then
    last_line=$(tail -1 "$json_log")

    if echo "$last_line" | grep -q '"type":"user"'; then
      echo "RESUME: $exp_name (Claude asked a question, resuming)"
      # Extract session_id
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
          --permission-mode bypassPermissions \
          --print \
          --output-format stream-json \
          --verbose \
          --no-session-persistence \
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
    local jsonl_size=$([ -f "$exp_dir/claude_run.jsonl" ] && wc -c < "$exp_dir/claude_run.jsonl" || echo 0)
    echo "DONE: $exp_name (changes=$changes, jsonl_size=$jsonl_size)"
  else
    echo "DONE: $exp_name"
  fi
}

# Main
echo "=== K3 Test (No Plugins/Skills) ===="
echo "Date: $RUN_DATE"
echo ""

# Run K3 short and long
echo "Running K3:short..."
run_task "K3:short"
echo ""

echo "Running K3:long..."
run_task "K3:long"
echo ""

echo "=== Test Complete ==="
