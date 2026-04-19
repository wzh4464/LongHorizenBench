#!/bin/bash
# 批量运行隔离实验
# 用法: ./run_isolated_batch.sh [并行数]

set -e

PARALLEL="${1:-4}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BATCH_FILE="$SCRIPT_DIR/affected_experiments.txt"

echo "=== 批量运行隔离实验 ==="
echo "并行数: $PARALLEL"
echo ""

# 确保 Docker 镜像存在
DOCKER_IMAGE="codex-isolated:latest"
if ! docker image inspect "$DOCKER_IMAGE" &>/dev/null; then
  echo "构建 Docker 镜像..."
  docker build -t "$DOCKER_IMAGE" -f "$SCRIPT_DIR/Dockerfile.codex" "$SCRIPT_DIR"
fi

# 运行单个实验的函数
run_one() {
  local exp="$1"
  bash "$SCRIPT_DIR/run_isolated.sh" "$exp"
}

export -f run_one
export SCRIPT_DIR
export OPENAI_API_KEY

# 并行运行
cat "$BATCH_FILE" | xargs -P "$PARALLEL" -I {} bash -c 'run_one "$@"' _ {}

echo ""
echo "=== 批次完成 ==="
