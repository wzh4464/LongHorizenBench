#!/bin/bash
# Docker 隔离运行 Codex 实验
# 用法: ./run_isolated.sh <实验目录名>
# 例如: ./run_isolated.sh T01-codex-gpt-5_4-long-2026-04-12

set -e

EXPERIMENT_DIR="/Users/zihanwu/Public/codes/huawei-eval/experiment"
BASE_REPO="/Users/zihanwu/Public/codes/huawei-eval/base_repo"
ACTION_DIRECTIVE="$BASE_REPO/ACTION_DIRECTIVE.md"
DOCKER_IMAGE="codex-isolated:latest"

exp_name="$1"
if [[ -z "$exp_name" ]]; then
  echo "用法: $0 <实验目录名>"
  exit 1
fi

exp_dir="$EXPERIMENT_DIR/$exp_name"
if [[ ! -d "$exp_dir" ]]; then
  echo "ERROR: 目录不存在: $exp_dir"
  exit 1
fi

# 检查 Docker 镜像
if ! docker image inspect "$DOCKER_IMAGE" &>/dev/null; then
  echo "构建 Docker 镜像..."
  docker build -t "$DOCKER_IMAGE" -f "$EXPERIMENT_DIR/Dockerfile.codex" "$EXPERIMENT_DIR"
fi

# 准备文件
prompt_file="$exp_dir/TASK_PROMPT.md"
log_file="$exp_dir/codex_output_isolated.log"
json_log="$exp_dir/codex_events_isolated.jsonl"

if [[ ! -f "$prompt_file" ]]; then
  echo "ERROR: TASK_PROMPT.md 不存在: $prompt_file"
  exit 1
fi

# 检查是否已有隔离运行结果
if [[ -f "$exp_dir/codex_events_isolated.jsonl" ]]; then
  events=$(wc -l < "$exp_dir/codex_events_isolated.jsonl")
  if [[ $events -gt 10 ]]; then
    echo "SKIP (isolated): $exp_name (已有 $events events)"
    exit 0
  fi
fi

# 清理旧的运行状态
rm -f "$exp_dir/RUNNING" "$exp_dir/COMPLETED"

echo "RUN (isolated): $exp_name"
echo "$(date -Iseconds)" > "$exp_dir/RUNNING"

# 创建临时 prompt 文件（拼接 TASK_PROMPT + ACTION_DIRECTIVE）
tmp_prompt=$(mktemp)
cat "$prompt_file" > "$tmp_prompt"
echo "" >> "$tmp_prompt"
cat "$ACTION_DIRECTIVE" >> "$tmp_prompt"

# 创建临时 .codex 目录副本（避免污染宿主机配置）
tmp_codex_dir=$(mktemp -d)
cp -r "$HOME/.codex/"* "$tmp_codex_dir/" 2>/dev/null || true

# 运行 Docker 隔离的 Codex
# - 只挂载实验目录到 /workspace
# - 挂载临时 .codex 配置（可写）
# - 不挂载 base_repo，实现完全隔离
# 使用 cat | docker run -i 传递 stdin
cat "$tmp_prompt" | docker run --rm -i \
  -v "$exp_dir:/workspace" \
  -v "$tmp_codex_dir:/home/codex/.codex" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  "$DOCKER_IMAGE" exec \
    -m gpt-5.4 \
    --full-auto \
    -c web_search=disabled \
    -C /workspace \
    --json \
    - \
  > "$json_log" 2> "$log_file" || true

# 清理临时 .codex 目录
rm -rf "$tmp_codex_dir"

# 清理
rm -f "$tmp_prompt"
rm -f "$exp_dir/RUNNING"
echo "$(date -Iseconds)" > "$exp_dir/COMPLETED"
echo "DONE (isolated): $exp_name"
