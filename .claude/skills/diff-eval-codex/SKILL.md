---
name: diff-eval-codex
description: 使用 Codex CLI (默认 OpenAI 订阅，无需额外配置) 批量评测实验目录。顺序或并行运行，报告名称包含 "codex"。Trigger on "/diff-eval-codex", "codex eval", "用 codex 评测".
argument-hint: <eval-dir-or-list>
---

# Diff Eval Codex: Codex CLI 批量评测

使用 Codex CLI（默认 OpenAI 订阅）对多个实验目录运行 diff-eval-local 评测。

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `eval-dir-or-list` | Yes | 包含实验目录的父目录，或逗号分隔的实验目录列表 |

## Usage

```bash
# 评测某目录下所有实验
/diff-eval-codex experiment/eval-batch-T11-T15

# 评测指定目录
/diff-eval-codex T11-claude-opus-max-short-20260415,T11-claude-opus-max-long-20260415
```

## 报告命名

每个实验目录内生成：`eval_report-codex.md`

## Workflow

### Step 1: 扫描实验目录

```bash
EVAL_INPUT="<eval-dir-or-list>"
if [[ -d "$EVAL_INPUT" && "$EVAL_INPUT" != *","* ]]; then
  mapfile -t DIRS < <(find "$EVAL_INPUT" -maxdepth 1 -name "run_metadata.json" | xargs -I{} dirname {} | sort)
else
  IFS=',' read -ra DIRS <<< "$EVAL_INPUT"
fi
echo "Found ${#DIRS[@]} experiment dirs:"
printf '  %s\n' "${DIRS[@]}"
```

### Step 2: 对每个目录准备输入并运行 Codex

对每个实验目录，执行以下操作：

#### 2a. 解析 GT 路径

```bash
REPO_ROOT="/Users/zihanwu/Public/codes/huawei-eval"
META="$EXP_DIR/run_metadata.json"
TASK_ID=$(python3 -c "import json; d=json.load(open('$META')); print(d.get('task_id',''))")
PROMPT_TYPE=$(python3 -c "import json; d=json.load(open('$META')); print(d.get('prompt_type',''))")
GT_DIFF="$REPO_ROOT/base_repo/$TASK_ID/eval/gt_diff.patch"
HW_FILES="$REPO_ROOT/base_repo/$TASK_ID/eval/handwritten_files.txt"
PROMPT_FILE="$REPO_ROOT/base_repo/$TASK_ID/prompts/${TASK_ID}-${PROMPT_TYPE}.md"
REPORT="$EXP_DIR/eval_report-codex.md"
```

#### 2b. 预计算确定性指标（bash，不依赖 AI）

```bash
EVAL_DIR=$(mktemp -d /tmp/codex-eval-XXXXXX)

# HW files
LC_ALL=C sort "$HW_FILES" > "$EVAL_DIR/hw.txt"
HW_COUNT=$(wc -l < "$EVAL_DIR/hw.txt" | tr -d ' ')

# Generated files
{ git -C "$EXP_DIR" diff HEAD --name-only
  git -C "$EXP_DIR" ls-files --others --exclude-standard | grep -v '^\.' ; } \
  | LC_ALL=C sort -u > "$EVAL_DIR/gen.txt"

# Coverage
LC_ALL=C comm -12 "$EVAL_DIR/hw.txt" "$EVAL_DIR/gen.txt" > "$EVAL_DIR/covered.txt"
LC_ALL=C comm -23 "$EVAL_DIR/hw.txt" "$EVAL_DIR/gen.txt" > "$EVAL_DIR/missing.txt"
COVERED=$(wc -l < "$EVAL_DIR/covered.txt" | tr -d ' ')
MISSING=$(wc -l < "$EVAL_DIR/missing.txt" | tr -d ' ')
PCT=$(echo "scale=1; $COVERED * 100 / $HW_COUNT" | bc 2>/dev/null || echo "N/A")

# Function coverage
awk '/^diff --git/ { match($0, / b\/(.+)$/, m); file=m[1] }
     /^@@.*@@/ { ctx=$0; sub(/^@@[^@]*@@ ?/,"",ctx); if(ctx) print file " :: " ctx }
    ' "$GT_DIFF" | LC_ALL=C sort -u > "$EVAL_DIR/gt-func.txt"

{ git -C "$EXP_DIR" diff HEAD
  git -C "$EXP_DIR" ls-files --others --exclude-standard | grep -v '^\.' | while IFS= read -r f; do
    [ -f "$EXP_DIR/$f" ] || continue
    echo "diff --git a/$f b/$f"
    echo "--- /dev/null"; echo "+++ b/$f"
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

echo "HW file coverage: $COVERED/$HW_COUNT = $PCT%"
echo "Function coverage: $COVERED_F/$GT_F = $PCT_F%"
```

#### 2c. 构建 Codex 评测 prompt

将所有内容写入临时 prompt 文件，然后调用 Codex：

```bash
PROMPT_TMP=$(mktemp /tmp/codex-eval-prompt-XXXXXX.md)

cat > "$PROMPT_TMP" <<PROMPT_EOF
# 任务：代码评测

请对以下实验结果进行评测，并将报告写入文件 \`$REPORT\`。

## 确定性指标（已预计算，直接使用）

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

Verdict 规则：PASS = A≥4 AND B≥4 AND C≥3；FAIL = A≤1 OR destructive；PARTIAL = otherwise

## 输出要求

将以下格式的报告写入文件 \`$REPORT\`（不要输出到终端，直接写文件）：

\`\`\`markdown
## Evaluation Report

**Evaluator**: Codex (gpt-5.4/o3)

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

# 运行 Codex
timeout 3600 codex "$PROMPT_TMP" --workdir "$EXP_DIR"
# 或者视 CLI 接口调整：
# timeout 3600 codex -p "$PROMPT_TMP"
# timeout 3600 codex < "$PROMPT_TMP"

rm -f "$PROMPT_TMP"
```

### Step 3: 顺序或并行执行

**默认：顺序执行**（避免 API rate limit）：

```bash
for EXP_DIR in "${DIRS[@]}"; do
  [[ -f "$EXP_DIR/eval_report-codex.md" ]] && { echo "Skip $EXP_DIR (already done)"; continue; }
  echo "Evaluating: $EXP_DIR"
  # 执行 Step 2 的所有操作
done
```

**可选：后台并行**（注意 API 并发限制）：

```bash
for EXP_DIR in "${DIRS[@]}"; do
  # 执行 Step 2，加 & 后台运行
  ( <Step 2 commands> ) &
done
wait
```

### Step 4: 汇总结果

```bash
echo "=== Evaluation Summary ==="
for dir in "${DIRS[@]}"; do
  report="$dir/eval_report-codex.md"
  if [[ -f "$report" ]]; then
    verdict=$(grep "^### Verdict:" "$report" | sed 's/### Verdict: //')
    echo "$(basename $dir): $verdict"
  else
    echo "$(basename $dir): (no report)"
  fi
done
```

## Notes

- **Report file**: `<exp_dir>/eval_report-codex.md`
- **Codex CLI**: 使用默认 OpenAI 订阅，无需指定 model 或 API key
- **确定性指标**（文件/函数覆盖率）由 bash 预计算，不依赖 Codex 的判断
- **B 分**基于预计算的文件覆盖率，prompt 中已明确
- **顺序执行**为默认，避免并发 API 压力；如需并行请确认 rate limit
- Codex CLI 的具体调用方式（flags）可能需要根据实际安装版本调整
