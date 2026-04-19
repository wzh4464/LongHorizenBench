#!/bin/bash
# Codex 实验批量运行脚本
# 使用 gpt-5.4 模型，禁用 websearch，可访问完整 git 历史

set -e

DATE="2026-04-12"
BASE_REPO="/Users/zihanwu/Public/codes/huawei-eval/base_repo"
EXPERIMENT_DIR="/Users/zihanwu/Public/codes/huawei-eval/experiment"

# 所有任务列表
TASKS=(
  C1 C2 C3 C4 C5
  M1 M2 M3
  K1 K2 K3 K4
  T01 T02 T03 T04 T05 T06 T07 T08 T09 T10
  T11 T12 T13 T14 T15 T16 T17 T18 T19 T20
  T21 T22 T23 T24 T25 T26 T27 T28 T29 T30
  T31 T32 T33 T34 T35 T36 T37 T38 T39 T40
  T41 T42 T43 T44 T45 T46 T47 T48 T49 T50
)

# Prompt 类型
PROMPT_TYPES=(long short)

# 状态文件
STATUS_FILE="$EXPERIMENT_DIR/codex_experiment_status.json"

# 初始化状态文件
init_status() {
  echo '{"experiments": [], "started_at": "'$(date -Iseconds)'"}' > "$STATUS_FILE"
}

# 更新状态
update_status() {
  local task=$1
  local prompt_type=$2
  local status=$3
  local dir=$4

  # 使用 jq 更新状态（如果没有 jq，使用简单的追加）
  echo "{\"task\": \"$task\", \"prompt\": \"$prompt_type\", \"status\": \"$status\", \"dir\": \"$dir\", \"time\": \"$(date -Iseconds)\"}" >> "$EXPERIMENT_DIR/codex_log.jsonl"
}

# 准备单个实验
prepare_experiment() {
  local task=$1
  local prompt_type=$2

  local exp_name="${task}-codex-gpt-5_4-${prompt_type}-${DATE}"
  local exp_dir="$EXPERIMENT_DIR/$exp_name"
  local prompt_file="$BASE_REPO/$task/prompts/${task}-${prompt_type}.md"

  # 检查 prompt 文件是否存在
  if [[ ! -f "$prompt_file" ]]; then
    echo "ERROR: Prompt file not found: $prompt_file"
    return 1
  fi

  # 如果目录已存在，跳过
  if [[ -d "$exp_dir" ]]; then
    echo "SKIP: $exp_name (already exists)"
    return 0
  fi

  echo "PREPARE: $exp_name"

  # 复制 repo (使用 rsync 处理 broken symlinks)
  rsync -a --copy-unsafe-links "$BASE_REPO/$task/repo/" "$exp_dir/"

  # 复制 prompt 到实验目录
  cp "$prompt_file" "$exp_dir/TASK_PROMPT.md"

  # 创建实验元数据
  cat > "$exp_dir/experiment_meta.json" << EOF
{
  "task": "$task",
  "prompt_type": "$prompt_type",
  "date": "$DATE",
  "model": "gpt-5.4",
  "agent": "codex",
  "prompt_file": "$prompt_file",
  "status": "prepared"
}
EOF

  echo "DONE: $exp_name"
}

# 运行单个实验
run_experiment() {
  local task=$1
  local prompt_type=$2

  local exp_name="${task}-codex-gpt-5_4-${prompt_type}-${DATE}"
  local exp_dir="$EXPERIMENT_DIR/$exp_name"
  local prompt_file="$exp_dir/TASK_PROMPT.md"
  local log_file="$exp_dir/codex_output.log"
  local json_log="$exp_dir/codex_events.jsonl"

  if [[ ! -d "$exp_dir" ]]; then
    echo "ERROR: Experiment dir not found: $exp_dir"
    return 1
  fi

  # 检查是否已完成
  if [[ -f "$exp_dir/COMPLETED" ]]; then
    echo "SKIP: $exp_name (already completed)"
    return 0
  fi

  # 检查是否正在运行
  if [[ -f "$exp_dir/RUNNING" ]]; then
    echo "SKIP: $exp_name (already running)"
    return 0
  fi

  echo "RUN: $exp_name"
  echo "$(date -Iseconds)" > "$exp_dir/RUNNING"
  update_status "$task" "$prompt_type" "running" "$exp_dir"

  # 运行 Codex exec (非交互模式)
  # -m gpt-5.4: 使用 gpt-5.4 模型
  # --full-auto: 自动执行模式 (sandbox workspace-write)
  # -c web_search=disabled: 禁用网络搜索 (顶层配置，非 features)
  # -C: 指定工作目录
  # --json: 输出 JSONL 格式事件
  # 通过 stdin 传递 prompt（拼接 TASK_PROMPT + ACTION_DIRECTIVE）
  local action_file="$BASE_REPO/ACTION_DIRECTIVE.md"
  { cat "$prompt_file"; echo ""; cat "$action_file"; } | codex exec \
    -m gpt-5.4 \
    --full-auto \
    -c web_search=disabled \
    -C "$exp_dir" \
    --json \
    - \
    > "$json_log" 2> "$log_file" || true

  # 清理运行标记
  rm -f "$exp_dir/RUNNING"

  # 标记完成
  echo "$(date -Iseconds)" > "$exp_dir/COMPLETED"
  update_status "$task" "$prompt_type" "completed" "$exp_dir"

  echo "DONE: $exp_name"
}

# 准备所有实验
prepare_all() {
  echo "=== Preparing all experiments ==="
  for task in "${TASKS[@]}"; do
    for prompt_type in "${PROMPT_TYPES[@]}"; do
      prepare_experiment "$task" "$prompt_type"
    done
  done
  echo "=== All experiments prepared ==="
}

# 运行所有实验（顺序）
run_all_sequential() {
  echo "=== Running all experiments sequentially ==="
  for task in "${TASKS[@]}"; do
    for prompt_type in "${PROMPT_TYPES[@]}"; do
      run_experiment "$task" "$prompt_type"
    done
  done
  echo "=== All experiments completed ==="
}

# 显示状态
show_status() {
  echo "=== Experiment Status ==="
  local total=0
  local prepared=0
  local completed=0
  local running=0

  for task in "${TASKS[@]}"; do
    for prompt_type in "${PROMPT_TYPES[@]}"; do
      local exp_name="${task}-codex-gpt-5_4-${prompt_type}-${DATE}"
      local exp_dir="$EXPERIMENT_DIR/$exp_name"
      total=$((total + 1))

      if [[ -f "$exp_dir/COMPLETED" ]]; then
        completed=$((completed + 1))
      elif [[ -d "$exp_dir" ]]; then
        prepared=$((prepared + 1))
      fi
    done
  done

  echo "Total: $total"
  echo "Prepared: $prepared"
  echo "Completed: $completed"
  echo "Pending: $((total - prepared - completed))"
}

# 列出所有实验目录
list_experiments() {
  ls -la "$EXPERIMENT_DIR" | grep "codex-gpt-5_4" | head -20
  echo "..."
  echo "Total: $(ls "$EXPERIMENT_DIR" | grep "codex-gpt-5_4" | wc -l)"
}

# 运行下一个未完成的实验
run_next() {
  for task in "${TASKS[@]}"; do
    for prompt_type in "${PROMPT_TYPES[@]}"; do
      local exp_name="${task}-codex-gpt-5_4-${prompt_type}-${DATE}"
      local exp_dir="$EXPERIMENT_DIR/$exp_name"

      if [[ -d "$exp_dir" ]] && [[ ! -f "$exp_dir/COMPLETED" ]] && [[ ! -f "$exp_dir/RUNNING" ]]; then
        run_experiment "$task" "$prompt_type"
        return 0
      fi
    done
  done
  echo "All experiments completed or running"
  return 1
}

# 并行运行多个实验
run_parallel() {
  local max_parallel=${1:-4}
  local pids=()
  local count=0

  for task in "${TASKS[@]}"; do
    for prompt_type in "${PROMPT_TYPES[@]}"; do
      local exp_name="${task}-codex-gpt-5_4-${prompt_type}-${DATE}"
      local exp_dir="$EXPERIMENT_DIR/$exp_name"

      if [[ -d "$exp_dir" ]] && [[ ! -f "$exp_dir/COMPLETED" ]] && [[ ! -f "$exp_dir/RUNNING" ]]; then
        run_experiment "$task" "$prompt_type" &
        pids+=($!)
        count=$((count + 1))

        if [[ $count -ge $max_parallel ]]; then
          # 等待任意一个完成
          wait -n "${pids[@]}" 2>/dev/null || true
          # 清理已完成的 pids
          local new_pids=()
          for pid in "${pids[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
              new_pids+=($pid)
            fi
          done
          pids=("${new_pids[@]}")
          count=${#pids[@]}
        fi
      fi
    done
  done

  # 等待所有剩余任务完成
  wait
  echo "All parallel experiments completed"
}

# 主函数
case "${1:-}" in
  prepare)
    prepare_all
    ;;
  run)
    if [[ -n "${2:-}" ]]; then
      # 运行单个任务
      run_experiment "$2" "${3:-long}"
    else
      run_all_sequential
    fi
    ;;
  run-next)
    run_next
    ;;
  run-parallel)
    run_parallel "${2:-4}"
    ;;
  status)
    show_status
    ;;
  list)
    list_experiments
    ;;
  *)
    echo "Usage: $0 {prepare|run|run-next|run-parallel|status|list}"
    echo ""
    echo "Commands:"
    echo "  prepare          - Prepare all experiment directories"
    echo "  run              - Run all experiments sequentially"
    echo "  run TASK TYPE    - Run single experiment (e.g., run T01 long)"
    echo "  run-next         - Run the next pending experiment"
    echo "  run-parallel [N] - Run up to N experiments in parallel (default: 4)"
    echo "  status           - Show experiment status"
    echo "  list             - List experiment directories"
    ;;
esac
