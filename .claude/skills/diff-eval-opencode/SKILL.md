---
name: diff-eval-opencode
description: 使用 OpenCode CLI 以指定模型批量评测实验目录。报告名称包含 "opencode-<model>"。Trigger on "/diff-eval-opencode", "opencode eval", "用 opencode 评测".
argument-hint: --model <model> <eval-dir-or-list>
---

# Diff Eval OpenCode: OpenCode 指定模型批量评测

使用 OpenCode CLI 以指定模型对多个实验目录运行 diff-eval-local 评测。

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--model <model>` | Yes | OpenCode 模型名，如 `minimax-m2.5`、`gpt-4o`、`claude-3-5-sonnet` |
| `eval-dir-or-list` | Yes | 包含实验目录的父目录，或逗号分隔的实验目录列表 |

## Usage

```bash
# 用 MiniMax M2.5 评测某目录下所有实验
/diff-eval-opencode --model minimax-m2.5 experiment/eval-batch-T11-T15

# 用 GPT-4o 评测指定目录
/diff-eval-opencode --model gpt-4o T11-claude-opus-max-short-20260415,T11-claude-opus-max-long-20260415

# 用其他模型
/diff-eval-opencode --model claude-3-5-sonnet experiment/eval-batch-K1-K4
```

## 报告命名

模型名中的 `/` 和特殊字符替换为 `-`，例如：
- `--model minimax-m2.5` → `eval_report-opencode-minimax-m2.5.md`
- `--model gpt-4o` → `eval_report-opencode-gpt-4o.md`
- `--model claude-3-5-sonnet` → `eval_report-opencode-claude-3-5-sonnet.md`

## Parameter Parsing

```bash
MODEL=""
EVAL_INPUT=""

args=("$@")
i=0
while [[ $i -lt ${#args[@]} ]]; do
  if [[ "${args[$i]}" == "--model" ]]; then
    i=$((i+1))
    MODEL="${args[$i]}"
  else
    EVAL_INPUT="${args[$i]}"
  fi
  i=$((i+1))
done

if [[ -z "$MODEL" ]]; then
  echo "ERROR: --model <model> is required"
  echo "Usage: /diff-eval-opencode --model <model> <eval-dir-or-list>"
  exit 1
fi

# 生成报告文件名（替换特殊字符）
REPORT_SUFFIX=$(echo "$MODEL" | tr '/' '-' | tr ':' '-')
REPORT_NAME="eval_report-opencode-${REPORT_SUFFIX}.md"
echo "Model: $MODEL"
echo "Report name: $REPORT_NAME"
```

## Workflow

### Step 1: 扫描实验目录

```bash
if [[ -d "$EVAL_INPUT" && "$EVAL_INPUT" != *","* ]]; then
  mapfile -t DIRS < <(find "$EVAL_INPUT" -maxdepth 1 -name "run_metadata.json" | xargs -I{} dirname {} | sort)
else
  IFS=',' read -ra DIRS <<< "$EVAL_INPUT"
fi
echo "Found ${#DIRS[@]} experiment dirs"
```

### Step 2: 对每个目录预计算确定性指标

与 diff-eval-codex 完全相同的 bash 预计算步骤：

```bash
REPO_ROOT="/Users/zihanwu/Public/codes/huawei-eval"

for EXP_DIR in "${DIRS[@]}"; do
  REPORT="$EXP_DIR/$REPORT_NAME"
  [[ -f "$REPORT" ]] && { echo "Skip $EXP_DIR (already done)"; continue; }

  META="$EXP_DIR/run_metadata.json"
  TASK_ID=$(python3 -c "import json; d=json.load(open('$META')); print(d.get('task_id',''))")
  PROMPT_TYPE=$(python3 -c "import json; d=json.load(open('$META')); print(d.get('prompt_type',''))")
  GT_DIFF="$REPO_ROOT/base_repo/$TASK_ID/eval/gt_diff.patch"
  HW_FILES="$REPO_ROOT/base_repo/$TASK_ID/eval/handwritten_files.txt"
  PROMPT_FILE="$REPO_ROOT/base_repo/$TASK_ID/prompts/${TASK_ID}-${PROMPT_TYPE}.md"

  EVAL_DIR=$(mktemp -d /tmp/opencode-eval-XXXXXX)

  # File coverage
  LC_ALL=C sort "$HW_FILES" > "$EVAL_DIR/hw.txt"
  HW_COUNT=$(wc -l < "$EVAL_DIR/hw.txt" | tr -d ' ')
  { git -C "$EXP_DIR" diff HEAD --name-only
    git -C "$EXP_DIR" ls-files --others --exclude-standard | grep -v '^\.' ; } \
    | LC_ALL=C sort -u > "$EVAL_DIR/gen.txt"
  LC_ALL=C comm -12 "$EVAL_DIR/hw.txt" "$EVAL_DIR/gen.txt" > "$EVAL_DIR/covered.txt"
  LC_ALL=C comm -23 "$EVAL_DIR/hw.txt" "$EVAL_DIR/gen.txt" > "$EVAL_DIR/missing.txt"
  COVERED=$(wc -l < "$EVAL_DIR/covered.txt" | tr -d ' ')
  PCT=$(echo "scale=1; $COVERED * 100 / $HW_COUNT" | bc 2>/dev/null || echo "N/A")

  # Function coverage
  awk '/^diff --git/ { match($0, / b\/(.+)$/, m); file=m[1] }
       /^@@.*@@/ { ctx=$0; sub(/^@@[^@]*@@ ?/,"",ctx); if(ctx) print file " :: " ctx }
      ' "$GT_DIFF" | LC_ALL=C sort -u > "$EVAL_DIR/gt-func.txt"
  { git -C "$EXP_DIR" diff HEAD
    git -C "$EXP_DIR" ls-files --others --exclude-standard | grep -v '^\.' | while IFS= read -r f; do
      [ -f "$EXP_DIR/$f" ] || continue
      echo "diff --git a/$f b/$f"; echo "--- /dev/null"; echo "+++ b/$f"
      wc -l < "$EXP_DIR/$f" | xargs -I{} echo "@@ -0,0 +1,{} @@"
      sed 's/^/+/' "$EXP_DIR/$f"
    done
  } | awk '/^diff --git/ { match($0, / b\/(.+)$/, m); file=m[1] }
           /^@@.*@@/ { ctx=$0; sub(/^@@[^@]*@@ ?/,"",ctx); if(ctx) print file " :: " ctx }
          ' | LC_ALL=C sort -u > "$EVAL_DIR/gen-func.txt"
  awk -F ' :: ' 'NR==FNR {f[$1]; next} ($1 in f)' "$EVAL_DIR/hw.txt" "$EVAL_DIR/gt-func.txt" > "$EVAL_DIR/gt-func-hw.txt"
  awk -F ' :: ' 'NR==FNR {f[$1]; next} ($1 in f)' "$EVAL_DIR/hw.txt" "$EVAL_DIR/gen-func.txt" > "$EVAL_DIR/gen-func-hw.txt"
  LC_ALL=C comm -12 "$EVAL_DIR/gt-func-hw.txt" "$EVAL_DIR/gen-func-hw.txt" > "$EVAL_DIR/func-covered.txt"
  GT_F=$(wc -l < "$EVAL_DIR/gt-func-hw.txt" | tr -d ' ')
  COVERED_F=$(wc -l < "$EVAL_DIR/func-covered.txt" | tr -d ' ')
  PCT_F=$(echo "scale=1; $COVERED_F * 100 / $GT_F" | bc 2>/dev/null || echo "N/A")

  echo "[$EXP_DIR] HW: $COVERED/$HW_COUNT=$PCT% | Func: $COVERED_F/$GT_F=$PCT_F%"

  # 调用 OpenCode（见 Step 3）
  # ...

  rm -rf "$EVAL_DIR"
done
```

### Step 3: 构建 Prompt 并调用 OpenCode

```bash
PROMPT_TMP=$(mktemp /tmp/opencode-eval-prompt-XXXXXX.md)

cat > "$PROMPT_TMP" <<PROMPT_EOF
# 任务：代码评测

请对以下实验结果进行评测，并将报告写入文件 \`$REPORT\`。

## 确定性指标（已预计算，直接使用，不要自行重新计算）

- HW File Coverage: **$COVERED/$HW_COUNT = $PCT%**
- Function Coverage: **$COVERED_F/$GT_F = $PCT_F%**

已覆盖的 HW 文件：
$(cat "$EVAL_DIR/covered.txt")

缺失的 HW 文件：
$(cat "$EVAL_DIR/missing.txt")

## GT Diff（地面真相实现）

$(cat "$GT_DIFF")

## 实验生成的 Diff

$(git -C "$EXP_DIR" diff HEAD)
$(git -C "$EXP_DIR" ls-files --others --exclude-standard | grep -v '^\.' | while IFS= read -r f; do
  [ -f "$EXP_DIR/$f" ] || continue
  echo "--- /dev/null"; echo "+++ b/$f"
  sed 's/^/+/' "$EXP_DIR/$f"
done)

## 需求 / Prompt

$([ -f "$PROMPT_FILE" ] && cat "$PROMPT_FILE" || echo "(no prompt file)")

## 评分规范

请按以下维度评分（0-5 整数）：
- **A. Functional Correctness**：代码是否正确实现了功能？
- **B. Completeness**：是否覆盖了 HW 文件范围内的所有必要逻辑？（以确定性文件覆盖率为主要参考）
- **C. Behavioral Equivalence**：行为是否与 GT 实现等价？

Verdict：PASS = A≥4 AND B≥4 AND C≥3；FAIL = A≤1 OR destructive；PARTIAL = otherwise

## 输出要求

将以下格式的报告写入文件 \`$REPORT\`：

\`\`\`markdown
## Evaluation Report

**Evaluator**: OpenCode ($MODEL)

### Summary
[1-3 sentences]

### Verdict: [PASS / PARTIAL / FAIL]

### Scores
- **A. Functional Correctness**: [X]/5 — [justification]
- **B. Completeness**: [X]/5 — [justification]
- **C. Behavioral Equivalence**: [X]/5 — [justification]

### Deterministic Coverage
#### HW File Coverage: $COVERED/$HW_COUNT = $PCT%
#### Function Coverage: $COVERED_F/$GT_F = $PCT_F%

### Requirements Checklist
| # | Requirement | GT | Gen | Status |
|---|-------------|:--:|:---:|--------|

### Analysis
- Approach differences:
- Missing logic:
- Test gaps:

### Confidence: [0.0-1.0]
\`\`\`
PROMPT_EOF

# 调用 OpenCode（根据实际 CLI 接口调整）
timeout 3600 opencode --model "$MODEL" run --prompt-file "$PROMPT_TMP" --workdir "$EXP_DIR"
# 或：
# timeout 3600 opencode --model "$MODEL" < "$PROMPT_TMP"
# timeout 3600 opencode --model "$MODEL" -p "$(cat $PROMPT_TMP)"

rm -f "$PROMPT_TMP"
```

### Step 4: 汇总结果

```bash
echo "=== Evaluation Summary (model: $MODEL) ==="
for dir in "${DIRS[@]}"; do
  report="$dir/$REPORT_NAME"
  if [[ -f "$report" ]]; then
    verdict=$(grep "^### Verdict:" "$report" | sed 's/### Verdict: //')
    echo "$(basename $dir): $verdict"
  else
    echo "$(basename $dir): (no report)"
  fi
done
```

## Notes

- **Report file**: `<exp_dir>/eval_report-opencode-<model>.md`
- **`--model`** 参数必须指定，无默认值
- **模型名映射**: 直接传给 OpenCode CLI 的 `--model` 参数，不做转换；文件名中特殊字符替换为 `-`
- **确定性指标**由 bash 预计算，不依赖 OpenCode 的判断
- **顺序执行**为默认；多个实验时注意 API rate limit
- OpenCode CLI 的具体 flags（`--model`、`--workdir`、`--prompt-file` 等）需根据实际安装版本确认
- 若 OpenCode 不支持直接写文件，可在 prompt 中要求其输出 markdown，然后重定向：`opencode ... > "$REPORT"`
