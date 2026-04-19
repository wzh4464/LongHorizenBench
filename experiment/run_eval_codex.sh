#!/bin/bash
# 批量运行 diff-eval-local 评估 (使用 Codex CLI + gpt-5.4)
#
# 评测方法:
# - 评测工具: Codex CLI (OpenAI)
# - 评测模型: gpt-5.4 (o3)
# - 评测 Skill: diff-eval-local (确定性文件/函数覆盖 + LLM语义分析)
# - 评分维度: A (功能正确性), B (完整性), C (行为等价性), 各 0-5 分
# - 判定规则: PASS (A>=4, B>=4, C>=3), FAIL (A<=1), PARTIAL (其他)

set -e

EXPERIMENT_DIR="/Users/zihanwu/Public/codes/huawei-eval/experiment"
BASE_REPO="/Users/zihanwu/Public/codes/huawei-eval/base_repo"
SKILL_FILE="/Users/zihanwu/.claude/skills/diff-eval-local/SKILL.md"
PARALLEL="${1:-4}"  # 默认 4 并行
EVAL_METHOD="codex-gpt5.4-diff-eval-local"
EVAL_DATE=$(date +%Y-%m-%d)

# 记录评测元数据
log_metadata() {
  local exp_dir="$1"
  cat > "$exp_dir/eval_metadata.json" << EOF
{
  "eval_tool": "codex",
  "eval_model": "gpt-5.4",
  "eval_skill": "diff-eval-local",
  "eval_method": "$EVAL_METHOD",
  "eval_date": "$EVAL_DATE",
  "scoring_dimensions": {
    "A": "Functional Correctness (0-5)",
    "B": "Completeness & Coverage (0-5)",
    "C": "Behavioral Equivalence (0-5)"
  },
  "verdict_rules": {
    "PASS": "A>=4 AND B>=4 AND C>=3",
    "FAIL": "A<=1 OR destructive",
    "PARTIAL": "otherwise"
  }
}
EOF
}

# 获取所有实验 (不跳过任何)
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

  # 解析任务ID和prompt类型
  local task_id=$(echo "$exp_name" | grep -oE '^[A-Z]+[0-9]+' | head -1)
  local prompt_type=$(echo "$exp_name" | grep -oE '(long|short)' | head -1)

  # 检查必要文件
  local gt_diff="$BASE_REPO/$task_id/eval/gt_diff.patch"
  local hw_files="$BASE_REPO/$task_id/eval/handwritten_files.txt"
  local prompt_file="$BASE_REPO/$task_id/prompts/${task_id}-${prompt_type}.md"

  if [[ ! -f "$gt_diff" ]] || [[ ! -f "$hw_files" ]]; then
    echo "SKIP: $exp_name (missing GT or HW files for $task_id)"
    return 0
  fi

  echo "EVAL: $exp_name"

  # 记录评测元数据
  log_metadata "$exp_dir"

  # 构建 prompt
  local eval_prompt="/diff-eval-local $exp_dir $gt_diff $hw_files"
  if [[ -f "$prompt_file" ]]; then
    eval_prompt="$eval_prompt $prompt_file"
  fi

  # 读取 skill 内容
  local skill_content=$(cat "$SKILL_FILE")

  # 创建临时 prompt 文件
  local tmp_prompt=$(mktemp)
  cat > "$tmp_prompt" << EOF
You are evaluating agent-generated code using the diff-eval-local methodology.

## Evaluation Method
- Tool: Codex CLI
- Model: gpt-5.4
- Skill: diff-eval-local
- Date: $EVAL_DATE

## Instructions
$skill_content

---

## Task
Execute: $eval_prompt

CRITICAL:
1. Use deterministic bash commands for file/function coverage (NOT LLM judgment)
2. Save the evaluation report to: $exp_dir/eval_report.md
3. Include "Evaluation Method: $EVAL_METHOD" in the report header
EOF

  # 运行 Codex (用 stdin 传递 prompt)
  local log_file="$exp_dir/eval_codex.log"
  local json_log="$exp_dir/eval_codex_events.jsonl"

  cat "$tmp_prompt" | codex exec \
    -m gpt-5.4 \
    --full-auto \
    -c web_search=disabled \
    -C "$exp_dir" \
    --json \
    - \
    > "$json_log" 2> "$log_file" || true

  rm -f "$tmp_prompt"

  # 检查结果
  if [[ -f "$exp_dir/eval_report.md" ]]; then
    echo "DONE: $exp_name"
  else
    echo "WARN: $exp_name (no eval_report.md)"
  fi
}

export -f run_eval log_metadata
export EXPERIMENT_DIR BASE_REPO SKILL_FILE EVAL_METHOD EVAL_DATE

# 主流程
echo "=== 批量评估 ==="
echo "评测工具: Codex CLI"
echo "评测模型: gpt-5.4"
echo "评测方法: diff-eval-local"
echo "并行度: $PARALLEL"
echo "日期: $EVAL_DATE"
echo ""

pending=$(get_experiments | wc -l | tr -d ' ')
echo "待评估: $pending 个实验"
echo ""

if [[ "$pending" -eq 0 ]]; then
  echo "所有实验已评估完成"
  exit 0
fi

# 记录批次信息
cat > "$EXPERIMENT_DIR/eval_batch_info.json" << EOF
{
  "batch_start": "$(date -Iseconds)",
  "eval_tool": "codex",
  "eval_model": "gpt-5.4",
  "eval_skill": "diff-eval-local",
  "parallel": $PARALLEL,
  "total_experiments": $pending
}
EOF

# 并行运行
get_experiments | head -${2:-999} | xargs -P "$PARALLEL" -I {} bash -c 'run_eval "$@"' _ {}

# 更新批次信息
echo ""
echo "=== 评估完成 ==="
evaluated=$(ls "$EXPERIMENT_DIR"/*-codex-gpt-5_4-*/eval_report.md 2>/dev/null | wc -l)
echo "已评估: $evaluated"

# 追加完成时间
python3 -c "
import json
with open('$EXPERIMENT_DIR/eval_batch_info.json', 'r') as f:
    data = json.load(f)
data['batch_end'] = '$(date -Iseconds)'
data['completed'] = $evaluated
with open('$EXPERIMENT_DIR/eval_batch_info.json', 'w') as f:
    json.dump(data, f, indent=2)
" 2>/dev/null || true
