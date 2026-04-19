#!/bin/bash
# K3 test with inline hook-based auto-reply (no --resume needed)

set -e

BASE_DIR="/Users/zihanwu/Public/codes/huawei-eval"
EXPERIMENT_DIR="$BASE_DIR/experiment"
BASE_REPO="$BASE_DIR/base_repo"
RUN_DATE=$(date +%Y-%m-%d)
CONFIG="claude-opus-max"

run_task() {
  local task_spec="$1"
  local task_id=$(echo "$task_spec" | cut -d: -f1)
  local prompt_type=$(echo "$task_spec" | cut -d: -f2)

  local exp_name="${task_id}-${CONFIG}-${prompt_type}-${RUN_DATE}"
  local exp_dir="$EXPERIMENT_DIR/$exp_name"

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

  # === Setup auto-answer hook ===
  mkdir -p "$exp_dir/.claude"

  cat > "$exp_dir/.claude/auto_answer.py" <<'PY'
#!/usr/bin/env python3
import json
import sys

payload = json.load(sys.stdin)
event = payload.get("hook_event_name")
tool_name = payload.get("tool_name")
tool_input = payload.get("tool_input", {})

def choose_answer(question: dict) -> str:
    """Auto-select first option (equivalent to always choosing '1')"""
    options = question.get("options") or []
    if not options:
        return "1"
    return options[0].get("label", "1")

# 1) Claude asking clarifying questions
if event == "PreToolUse" and tool_name == "AskUserQuestion":
    questions = tool_input.get("questions", [])
    answers = {}

    for q in questions:
        q_text = q.get("question")
        if q_text:
            answers[q_text] = choose_answer(q)

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {
                "questions": questions,
                "answers": answers
            }
        }
    }

# 2) Plan mode completion
elif event == "PreToolUse" and tool_name == "ExitPlanMode":
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": tool_input
        }
    }

# 3) Permission requests
elif event == "PermissionRequest":
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {
                "behavior": "allow",
                "updatedInput": tool_input
            }
        }
    }

else:
    out = {}

json.dump(out, sys.stdout)
sys.stdout.write("\n")
PY

  chmod +x "$exp_dir/.claude/auto_answer.py"

  cat > "$exp_dir/.claude/settings.local.json" <<'JSON'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "AskUserQuestion|ExitPlanMode",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/auto_answer.py"
          }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 .claude/auto_answer.py"
          }
        ]
      }
    ]
  }
}
JSON

  # === Run Claude with hook-based auto-reply (no --resume loop needed) ===
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
      echo "DONE: $exp_name (changes=$changes, size=$jsonl_size, status=✅ COMPLETE)"
    else
      echo "DONE: $exp_name (changes=$changes, size=$jsonl_size, status=⚠ INCOMPLETE)"
    fi
  else
    echo "DONE: $exp_name"
  fi
}

echo "=== K3 Test v2 (Hook-based Auto-Reply) ==="
echo "Date: $RUN_DATE"
echo ""

echo "Running K3:short..."
run_task "K3:short"
echo ""

echo "Running K3:long..."
run_task "K3:long"
echo ""

echo "=== Test Complete ==="
