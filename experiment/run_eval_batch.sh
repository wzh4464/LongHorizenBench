#!/bin/bash
# 批量运行 diff-eval-local 评估
# 使用 opencode + openrouter + minimax-m2.7

set -e

# 加载 .env
ENV_FILE="/Users/zihanwu/Public/codes/huawei-eval/.env"
if [[ -f "$ENV_FILE" ]]; then
  export $(cat "$ENV_FILE" | grep -v '^#' | xargs)
fi

EXPERIMENT_DIR="/Users/zihanwu/Public/codes/huawei-eval/experiment"
BASE_REPO="/Users/zihanwu/Public/codes/huawei-eval/base_repo"
MODEL="openrouter/minimax/minimax-m2.7"
PARALLEL="${1:-2}"  # 默认 2 并行 (MiniMax 限流)

# 获取所有 Codex 实验
get_experiments() {
  ls -d "$EXPERIMENT_DIR"/*-codex-gpt-5_4-*-2026-04-12 2>/dev/null | while read exp; do
    # 跳过已有 eval_report.md 的
    if [[ ! -f "$exp/eval_report.md" ]]; then
      basename "$exp"
    fi
  done
}

# 运行单个评估
run_eval() {
  local exp_name="$1"
  local exp_dir="$EXPERIMENT_DIR/$exp_name"

  # 从目录名解析任务ID和prompt类型
  # 格式: T01-codex-gpt-5_4-long-2026-04-12 或 K3-codex-gpt-5_4-short-2026-04-12
  local task_id=$(echo "$exp_name" | grep -oE '^[A-Z]+[0-9]+' | head -1)
  local prompt_type=$(echo "$exp_name" | grep -oE '(long|short)' | head -1)

  # 检查 base_repo 文件是否存在
  local gt_diff="$BASE_REPO/$task_id/eval/gt_diff.patch"
  local hw_files="$BASE_REPO/$task_id/eval/handwritten_files.txt"
  local prompt_file="$BASE_REPO/$task_id/prompts/${task_id}-${prompt_type}.md"

  if [[ ! -f "$gt_diff" ]]; then
    echo "SKIP: $exp_name (no gt_diff.patch for $task_id)"
    return 0
  fi

  if [[ ! -f "$hw_files" ]]; then
    echo "SKIP: $exp_name (no handwritten_files.txt for $task_id)"
    return 0
  fi

  echo "EVAL: $exp_name"

  # 构建 diff-eval-local 命令
  local eval_prompt="/diff-eval-local $exp_dir $gt_diff $hw_files"
  if [[ -f "$prompt_file" ]]; then
    eval_prompt="$eval_prompt $prompt_file"
  fi

  # 运行 opencode
  local log_file="$exp_dir/eval_opencode.log"

  opencode run \
    -m "$MODEL" \
    --dir "$exp_dir" \
    --dangerously-skip-permissions \
    --format json \
    "$eval_prompt" \
    > "$exp_dir/eval_events.jsonl" 2> "$log_file" || true

  # 检查是否生成了 eval_report.md
  if [[ -f "$exp_dir/eval_report.md" ]]; then
    echo "DONE: $exp_name"
  else
    echo "WARN: $exp_name (no eval_report.md generated)"
  fi
}

export -f run_eval
export EXPERIMENT_DIR BASE_REPO MODEL

# 主流程
echo "=== 批量评估 (model: $MODEL, parallel: $PARALLEL) ==="
echo ""

# 统计待评估数量
pending=$(get_experiments | wc -l)
echo "待评估: $pending 个实验"
echo ""

if [[ "$pending" -eq 0 ]]; then
  echo "所有实验已评估完成"
  exit 0
fi

# 并行运行
get_experiments | head -${2:-999} | xargs -P "$PARALLEL" -I {} bash -c 'run_eval "$@"' _ {}

echo ""
echo "=== 评估完成 ==="
evaluated=$(ls "$EXPERIMENT_DIR"/*-codex-gpt-5_4-*/eval_report.md 2>/dev/null | wc -l)
echo "已评估: $evaluated"
