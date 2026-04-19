#!/bin/bash
# 监控 Codex 实验状态

EXPERIMENT_DIR="/Users/zihanwu/Public/codes/huawei-eval/experiment"
DATE="2026-04-12"

echo "=========================================="
echo "Codex 实验监控 - $(date)"
echo "=========================================="
echo ""

# 统计
total=$(ls "$EXPERIMENT_DIR" | grep "codex-gpt-5_4-.*-$DATE" | wc -l | tr -d ' ')
prepared=$(ls "$EXPERIMENT_DIR"/*/experiment_meta.json 2>/dev/null | wc -l | tr -d ' ')
running=$(ls "$EXPERIMENT_DIR"/*/RUNNING 2>/dev/null | wc -l | tr -d ' ')
completed=$(ls "$EXPERIMENT_DIR"/*/COMPLETED 2>/dev/null | wc -l | tr -d ' ')
has_changes=$(for d in "$EXPERIMENT_DIR"/*-codex-gpt-5_4-*-$DATE; do
  if [[ -d "$d/.git" ]]; then
    cd "$d" && git status --porcelain | grep -q . && echo 1
  fi
done | wc -l | tr -d ' ')

echo "总实验数:    $total / 124"
echo "已准备:      $prepared"
echo "运行中:      $running"
echo "已完成:      $completed"
echo "有代码改动:  $has_changes"
echo ""

# 显示运行中的实验
if [[ $running -gt 0 ]]; then
  echo "--- 运行中的实验 ---"
  for f in "$EXPERIMENT_DIR"/*/RUNNING; do
    [[ -f "$f" ]] && dirname "$f" | xargs basename
  done
  echo ""
fi

# 显示最近完成的实验
if [[ $completed -gt 0 ]]; then
  echo "--- 最近完成的 5 个实验 ---"
  ls -t "$EXPERIMENT_DIR"/*/COMPLETED 2>/dev/null | head -5 | while read f; do
    exp=$(dirname "$f" | xargs basename)
    time=$(cat "$f")
    echo "$exp (完成于 $time)"
  done
  echo ""
fi

# 显示有代码改动的实验
if [[ $has_changes -gt 0 ]]; then
  echo "--- 有代码改动的实验 ---"
  for d in "$EXPERIMENT_DIR"/*-codex-gpt-5_4-*-$DATE; do
    if [[ -d "$d/.git" ]]; then
      cd "$d"
      if git status --porcelain | grep -q .; then
        exp=$(basename "$d")
        changes=$(git status --porcelain | wc -l | tr -d ' ')
        echo "$exp: $changes 文件改动"
      fi
    fi
  done
  echo ""
fi

# 磁盘使用
echo "--- 磁盘使用 ---"
du -sh "$EXPERIMENT_DIR" 2>/dev/null | awk '{print "实验目录总大小: " $1}'
