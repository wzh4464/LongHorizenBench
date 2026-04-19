#!/bin/bash
# 批量运行实验脚本
# 用法: ./run_batch.sh batch1_experiments.txt [并行数]

set -e

BATCH_FILE="${1:-batch1_experiments.txt}"
PARALLEL="${2:-4}"
DATE="2026-04-12"
EXPERIMENT_DIR="/Users/zihanwu/Public/codes/huawei-eval/experiment"
BASE_REPO="/Users/zihanwu/Public/codes/huawei-eval/base_repo"
ACTION_DIRECTIVE="$BASE_REPO/ACTION_DIRECTIVE.md"

if [[ ! -f "$BATCH_FILE" ]]; then
  echo "ERROR: Batch file not found: $BATCH_FILE"
  exit 1
fi

echo "=== 批量运行实验 ==="
echo "批次文件: $BATCH_FILE"
echo "并行数: $PARALLEL"
echo ""

# 运行单个实验
run_experiment() {
  local exp_dir=$1
  local prompt_file="$exp_dir/TASK_PROMPT.md"
  local log_file="$exp_dir/codex_output.log"
  local json_log="$exp_dir/codex_events.jsonl"

  if [[ ! -d "$exp_dir" ]]; then
    echo "ERROR: $exp_dir not found"
    return 1
  fi

  if [[ -f "$exp_dir/COMPLETED" ]]; then
    echo "SKIP: $exp_dir (already completed)"
    return 0
  fi

  if [[ -f "$exp_dir/RUNNING" ]]; then
    echo "SKIP: $exp_dir (already running)"
    return 0
  fi

  echo "RUN: $(basename $exp_dir)"
  echo "$(date -Iseconds)" > "$exp_dir/RUNNING"

  # 拼接 TASK_PROMPT.md + ACTION_DIRECTIVE.md
  local action_file="/Users/zihanwu/Public/codes/huawei-eval/base_repo/ACTION_DIRECTIVE.md"
  { cat "$prompt_file"; echo ""; cat "$action_file"; } | codex exec \
    -m gpt-5.4 \
    --full-auto \
    -c web_search=disabled \
    -C "$exp_dir" \
    --json \
    - \
    > "$json_log" 2> "$log_file" || true

  rm -f "$exp_dir/RUNNING"
  echo "$(date -Iseconds)" > "$exp_dir/COMPLETED"
  echo "DONE: $(basename $exp_dir)"
}

export -f run_experiment

# 读取批次文件并并行运行
grep -v '^#' "$BATCH_FILE" | grep -v '^$' | \
  xargs -P "$PARALLEL" -I {} bash -c 'run_experiment "$@"' _ "$EXPERIMENT_DIR/{}"

echo ""
echo "=== 批次完成 ==="
echo "已完成: $(ls */COMPLETED 2>/dev/null | wc -l)"
