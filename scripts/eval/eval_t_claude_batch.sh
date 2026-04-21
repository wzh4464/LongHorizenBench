#!/bin/bash
set -euo pipefail

REPO_ROOT="/Users/zihanwu/Public/codes/huawei-eval"
PARALLEL=8
COMPLETED=0
TOTAL=$(wc -l < /tmp/eval_t_dirs.txt | tr -d ' ')
LOCK="/tmp/eval_claude_lock"

eval_single() {
  local EXP_DIR="${1%/}"
  local DIR_NAME=$(basename "$EXP_DIR")
  local REPORT="$EXP_DIR/eval_report-claude.md"

  [[ -f "$REPORT" ]] && { echo >&2 "[SKIP] $DIR_NAME (exists)"; return 0; }

  local TASK_ID PROMPT_TYPE
  TASK_ID=$(python3 -c "import json; print(json.load(open('$EXP_DIR/run_metadata.json')).get('task_id',''))")
  PROMPT_TYPE=$(python3 -c "import json; print(json.load(open('$EXP_DIR/run_metadata.json')).get('prompt_type',''))")

  local GT_DIFF="$REPO_ROOT/base_repo/$TASK_ID/eval/gt_diff.patch"
  local HW_FILES="$REPO_ROOT/base_repo/$TASK_ID/eval/handwritten_files.txt"
  local PROMPT_FILE="$REPO_ROOT/base_repo/$TASK_ID/prompts/${TASK_ID}-${PROMPT_TYPE}.md"

  [[ -f "$GT_DIFF" ]] || { echo >&2 "[ERR] $DIR_NAME: GT not found"; return 1; }

  local EVAL_PROMPT="You are an evaluation agent. Evaluate the code changes in this experiment directory against the ground truth.

IMPORTANT: Use bash tools (comm, sort, wc) for ALL deterministic metrics. Do NOT use LLM judgment for file/function coverage.

## Paths
- Experiment dir: $EXP_DIR
- GT diff: $GT_DIFF
- HW files: $HW_FILES
- Prompt/requirements: $PROMPT_FILE

## Evaluation Steps (follow exactly)

### Step 1: Compute deterministic HW file coverage (MUST use bash)
\`\`\`bash
EVAL_TMP=\$(mktemp -d)
LC_ALL=C sort \"$HW_FILES\" > \"\$EVAL_TMP/hw.txt\"
{ git -C \"$EXP_DIR\" diff HEAD --name-only; git -C \"$EXP_DIR\" ls-files --others --exclude-standard | grep -v '^\\.'; } | LC_ALL=C sort -u > \"\$EVAL_TMP/gen.txt\"
LC_ALL=C comm -12 \"\$EVAL_TMP/hw.txt\" \"\$EVAL_TMP/gen.txt\" > \"\$EVAL_TMP/covered.txt\"
LC_ALL=C comm -23 \"\$EVAL_TMP/hw.txt\" \"\$EVAL_TMP/gen.txt\" > \"\$EVAL_TMP/missing.txt\"
echo \"Covered: \$(wc -l < \"\$EVAL_TMP/covered.txt\") / \$(wc -l < \"\$EVAL_TMP/hw.txt\")\"
cat \"\$EVAL_TMP/covered.txt\"
echo \"Missing:\"
cat \"\$EVAL_TMP/missing.txt\"
\`\`\`

### Step 2: Explore GT diff
The GT diff is at: $GT_DIFF
It may be very large (some tasks have multi-MB diffs). Do NOT try to read the entire file at once.
Strategy:
1. Check size: wc -c < \"$GT_DIFF\"
2. List changed files: grep '^diff --git' \"$GT_DIFF\" | sed 's|^diff --git a/.* b/||'
3. For each covered HW file, extract its section: sed -n '/^diff --git.*\\/FILE/,/^diff --git/p' to read relevant parts
4. Skip reading sections for files not in the covered set unless needed for context

### Step 3: Explore experiment diff
Strategy:
1. Overview: git -C \"$EXP_DIR\" diff HEAD --stat
2. Read diffs for specific HW files: git -C \"$EXP_DIR\" diff HEAD -- FILE
3. List untracked: git -C \"$EXP_DIR\" ls-files --others --exclude-standard | grep -v '^\\\\.'; then read relevant ones
4. Do NOT dump the entire diff at once if there are many changes

### Step 4: Read requirements
Read $PROMPT_FILE if it exists (use Read tool or cat).

### Step 5: Score (A/B/C each 0-5)
- A. Functional Correctness: Does the code correctly implement the feature?
- B. Completeness: Are all HW files covered with necessary logic? (Use deterministic coverage as primary input)
- C. Behavioral Equivalence: How close is the behavior to GT?

Verdict: PASS = A>=4 AND B>=4 AND C>=3; FAIL = A<=1 OR (A+B+C)<=5; PARTIAL = otherwise

### Step 6: Write report to $REPORT
Use this exact format:
## Evaluation Report
**Evaluator**: Claude Code (claude-opus-max)
### Summary
### Verdict: [PASS / PARTIAL / FAIL]
### Scores
- **A. Functional Correctness**: [X]/5 — [justification]
- **B. Completeness**: [X]/5 — [justification]
- **C. Behavioral Equivalence**: [X]/5 — [justification]
### Deterministic Coverage
#### HW File Coverage: [X]/[Y] = [Z]%
#### Function Coverage: [X]/[Y] = [Z]%
### Analysis
### Confidence: [0.0-1.0]"

  echo >&2 "[START] $DIR_NAME"
  cd "$EXP_DIR"
  claude-yunwu \
    --model opus \
    --dangerously-skip-permissions --permission-mode bypassPermissions \
    --disallowedTools 'WebSearch,WebFetch,Skill' \
    --print \
    "$EVAL_PROMPT" \
    < /dev/null > /dev/null 2>&1 || true

  if [[ -f "$REPORT" ]]; then
    local verdict=$(grep "^### Verdict:" "$REPORT" | head -1 | sed 's/### Verdict: //')
    echo >&2 "[DONE] $DIR_NAME → $verdict"
  else
    echo >&2 "[FAIL] $DIR_NAME (no report generated)"
  fi
}

export -f eval_single
export REPO_ROOT

echo >&2 "=== Claude Evaluation Batch ==="
echo >&2 "Total experiments: $TOTAL, Parallelism: $PARALLEL"
echo >&2 ""

cat /tmp/eval_t_dirs.txt | xargs -P${PARALLEL} -I{} bash -c 'eval_single "$@"' _ {}

echo >&2 ""
echo >&2 "=== Complete ==="

# Summary
done_count=0
pass_count=0
while read d; do
  d="${d%/}"
  r="$d/eval_report-claude.md"
  [[ -f "$r" ]] || continue
  done_count=$((done_count+1))
  grep -q "PASS" "$r" 2>/dev/null && pass_count=$((pass_count+1))
done < /tmp/eval_t_dirs.txt
echo >&2 "Reports: $done_count/$TOTAL  PASS: $pass_count"
