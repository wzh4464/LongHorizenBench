---
name: diff-eval-local
description: Evaluate agent-generated code against ground truth diff and handwritten file list. Prefer reading GT inputs directly from base_repo via experiment metadata. Trigger on "/diff-eval-local", "evaluate diff", "eval experiment".
argument-hint: <repo-path> [gt-diff] [hw-files] [prompt-file]
---

# Diff Eval Local: Agent Code Evaluation

Evaluate agent-generated code against a ground truth diff, using a handwritten file list to scope scoring.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `repo-path` | Yes | Path to repo with agent-generated changes |
| `gt-diff` | No | Path to ground truth `.diff` or `.patch` file. If omitted, resolve `base_repo/<task>/eval/gt_diff.patch` from repo metadata. |
| `hw-files` | No | Path to `handwritten_files.txt` (one file per line). If omitted, resolve `base_repo/<task>/eval/handwritten_files.txt` from repo metadata. |
| `prompt-file` | No | Path to requirements/prompt `.md` file |

## Usage

```bash
# Preferred in this repo: pass only the experiment repo path.
# GT diff / HW files are read from base_repo via run_metadata.json or experiment_meta.json.
/diff-eval-local experiment/T19-claude-opus-max-long-2026-04-14

# Basic usage
/diff-eval-local <repo> <gt.diff> <hw-files.txt>

# With prompt file
/diff-eval-local <repo> <gt.diff> <hw-files.txt> <prompt.md>

# Example
/diff-eval-local \
  experiment/K3-codex-gpt-5_4-long-2026-04-12 \
  base_repo/K3/eval/gt_diff.patch \
  base_repo/K3/eval/handwritten_files.txt \
  base_repo/K3/prompts/K3-long.md
```

## Parameter Parsing

Parse arguments by pattern:
- Path ending in `.diff` or `.patch` → GT diff
- Path containing `handwritten` or `hw` → HW file list
- Path ending in `.md` → prompt/requirements
- Other path (usually first) → repo path

```bash
REPO_PATH=""
GT_DIFF=""
HW_FILES=""
PROMPT_FILE=""

for arg in "$@"; do
  if [[ "$arg" == *.diff ]] || [[ "$arg" == *.patch ]]; then
    GT_DIFF="$arg"
  elif [[ "$arg" == *handwritten* ]] || [[ "$arg" == *hw_files* ]] || [[ "$arg" == *hw-files* ]]; then
    HW_FILES="$arg"
  elif [[ "$arg" == *.md ]]; then
    PROMPT_FILE="$arg"
  elif [[ -d "$arg" ]]; then
    REPO_PATH="$arg"
  fi
done

# If GT/HW inputs are omitted, resolve them from repo metadata and base_repo.
# Supported metadata files:
# - <repo>/run_metadata.json
# - <repo>/experiment_meta.json
#
# Resolution rules:
# - task_id / task -> <TASK>
# - GT diff -> <repo-root>/base_repo/<TASK>/eval/gt_diff.patch
# - HW files -> <repo-root>/base_repo/<TASK>/eval/handwritten_files.txt
# - prompt_file from metadata is reused when available
if [[ -n "$REPO_PATH" ]] && [[ -z "$GT_DIFF" || -z "$HW_FILES" || -z "$PROMPT_FILE" ]]; then
  META_FILE=""
  for candidate in "$REPO_PATH/run_metadata.json" "$REPO_PATH/experiment_meta.json"; do
    if [[ -f "$candidate" ]]; then
      META_FILE="$candidate"
      break
    fi
  done

  if [[ -n "$META_FILE" ]]; then
    eval "$(
      python3 - "$META_FILE" <<'PY'
import json
import shlex
import sys
from pathlib import Path

meta_path = Path(sys.argv[1]).resolve()
data = json.loads(meta_path.read_text())

task_id = data.get("task_id") or data.get("task") or ""
prompt_file = data.get("prompt_file") or ""

task_dir = None
if prompt_file:
    prompt_path = Path(prompt_file).resolve()
    if prompt_path.parent.name == "prompts":
        task_dir = prompt_path.parent.parent

if task_dir is None and task_id:
    repo_root = meta_path.parent.parent
    task_dir = repo_root / "base_repo" / task_id

def emit(key: str, value: str) -> None:
    if value:
        print(f"{key}={shlex.quote(value)}")

emit("TASK_ID", task_id)
if task_dir:
    emit("GT_DIFF", str(task_dir / "eval" / "gt_diff.patch"))
    emit("HW_FILES", str(task_dir / "eval" / "handwritten_files.txt"))
if prompt_file:
    emit("PROMPT_FILE", prompt_file)
PY
    )"
  fi
fi

# Validate required params
for var in REPO_PATH GT_DIFF HW_FILES; do
  if [[ -z "${!var}" ]]; then
    echo "ERROR: Missing required parameter: $var"
    exit 1
  fi
done

echo "Repo: $REPO_PATH"
echo "GT Diff: $GT_DIFF"
echo "HW Files: $HW_FILES"
echo "Prompt: ${PROMPT_FILE:-"(none)"}"
```

## CRITICAL Rules

1. **All git commands MUST use `git -C <REPO_PATH>`**
2. **File/function coverage MUST use deterministic bash set operations, NOT LLM judgment**
3. **B score is relative to HANDWRITTEN files only**

## Workflow

### Step 1: Gather Inputs

#### 1a. Read Handwritten Files (Authoritative Scoring Scope)

```bash
echo "=== Handwritten Files ==="
cat "$HW_FILES"
HW_COUNT=$(wc -l < "$HW_FILES" | tr -d ' ')
echo ""
echo "Total: $HW_COUNT files"
```

#### 1b. Extract Generated Patch

```bash
echo "=== Generated Changes ==="
git -C "$REPO_PATH" diff HEAD --stat

echo "=== Untracked Files ==="
git -C "$REPO_PATH" ls-files --others --exclude-standard | grep -v '^\.' | head -20

# Full generated file list
{ git -C "$REPO_PATH" diff HEAD --name-only; git -C "$REPO_PATH" ls-files --others --exclude-standard | grep -v '^\.' ; } | sort -u
```

Full diff (tracked + untracked):
```bash
# Tracked changes
git -C "$REPO_PATH" diff HEAD

# Untracked as unified diff
while IFS= read -r f; do
  [ -f "$REPO_PATH/$f" ] || continue
  echo "diff --git a/$f b/$f"
  echo "new file mode 100644"
  echo "--- /dev/null"
  echo "+++ b/$f"
  lines=$(wc -l < "$REPO_PATH/$f")
  echo "@@ -0,0 +1,$lines @@"
  sed 's/^/+/' "$REPO_PATH/$f"
done < <(git -C "$REPO_PATH" ls-files --others --exclude-standard | grep -v '^\.')
```

#### 1c. Read Ground Truth Diff

GT diff should be read directly from `base_repo/<task>/eval/gt_diff.patch` when evaluating this repository. Do not try to reconstruct it from the experiment repo.

```bash
echo "=== GT Diff Stats ==="
echo "Files: $(grep -c '^diff --git' "$GT_DIFF")"

# List GT files
grep '^diff --git' "$GT_DIFF" | sed 's|^diff --git a/.* b/||' | head -20
```

#### 1d. Read Requirements (if provided)

```bash
if [[ -n "$PROMPT_FILE" ]] && [[ -f "$PROMPT_FILE" ]]; then
  echo "=== Requirements ==="
  cat "$PROMPT_FILE"
fi
```

### Step 2: Deterministic File Coverage (MUST use bash)

```bash
EVAL_DIR=$(mktemp -d /tmp/diff-eval-XXXXXX)

# HW files (sorted)
LC_ALL=C sort "$HW_FILES" > "$EVAL_DIR/hw.txt"

# Generated files (sorted)
{ git -C "$REPO_PATH" diff HEAD --name-only; git -C "$REPO_PATH" ls-files --others --exclude-standard | grep -v '^\.' ; } | LC_ALL=C sort -u > "$EVAL_DIR/gen.txt"

echo "=== Deterministic File Coverage ==="

TOTAL=$(wc -l < "$EVAL_DIR/hw.txt" | tr -d ' ')
GEN_COUNT=$(wc -l < "$EVAL_DIR/gen.txt" | tr -d ' ')

echo "HW files: $TOTAL"
echo "Generated files: $GEN_COUNT"

# Intersection
LC_ALL=C comm -12 "$EVAL_DIR/hw.txt" "$EVAL_DIR/gen.txt" > "$EVAL_DIR/covered.txt"
COVERED=$(wc -l < "$EVAL_DIR/covered.txt" | tr -d ' ')

echo ""
echo "Covered HW files ($COVERED):"
cat "$EVAL_DIR/covered.txt"

# Missing
LC_ALL=C comm -23 "$EVAL_DIR/hw.txt" "$EVAL_DIR/gen.txt" > "$EVAL_DIR/missing.txt"
MISSING=$(wc -l < "$EVAL_DIR/missing.txt" | tr -d ' ')

echo ""
echo "Missing HW files ($MISSING):"
cat "$EVAL_DIR/missing.txt"

# Extra (not in HW)
echo ""
echo "Extra files (first 10):"
LC_ALL=C comm -13 "$EVAL_DIR/hw.txt" "$EVAL_DIR/gen.txt" | head -10

echo ""
if [[ $TOTAL -gt 0 ]]; then
  PCT=$(echo "scale=1; $COVERED * 100 / $TOTAL" | bc)
  echo "**HW File Coverage: $COVERED/$TOTAL = $PCT%**"
else
  echo "**HW File Coverage: 0/0 = N/A**"
fi

# Save for later
echo "$EVAL_DIR" > /tmp/diff-eval-dir.txt
```

### Step 3: Function-Level Coverage (MUST use bash)

```bash
EVAL_DIR=$(cat /tmp/diff-eval-dir.txt)

# GT functions (file :: context)
awk '
  /^diff --git/ { match($0, / b\/(.+)$/, m); file = m[1] }
  /^@@.*@@/ { ctx = $0; sub(/^@@[^@]*@@ ?/, "", ctx); if (ctx != "") print file " :: " ctx }
' "$GT_DIFF" | LC_ALL=C sort -u > "$EVAL_DIR/gt-func.txt"

# Gen functions
{ git -C "$REPO_PATH" diff HEAD; while IFS= read -r f; do [ -f "$REPO_PATH/$f" ] || continue; echo "diff --git a/$f b/$f"; echo "--- /dev/null"; echo "+++ b/$f"; wc -l < "$REPO_PATH/$f" | xargs -I{} echo "@@ -0,0 +1,{} @@"; sed 's/^/+/' "$REPO_PATH/$f"; done < <(git -C "$REPO_PATH" ls-files --others --exclude-standard | grep -v '^\.' ) ; } | awk '
  /^diff --git/ { match($0, / b\/(.+)$/, m); file = m[1] }
  /^@@.*@@/ { ctx = $0; sub(/^@@[^@]*@@ ?/, "", ctx); if (ctx != "") print file " :: " ctx }
' | LC_ALL=C sort -u > "$EVAL_DIR/gen-func.txt"

# Filter to HW files only
awk -F ' :: ' 'NR==FNR {f[$1]; next} ($1 in f)' "$EVAL_DIR/hw.txt" "$EVAL_DIR/gt-func.txt" > "$EVAL_DIR/gt-func-hw.txt"
awk -F ' :: ' 'NR==FNR {f[$1]; next} ($1 in f)' "$EVAL_DIR/hw.txt" "$EVAL_DIR/gen-func.txt" > "$EVAL_DIR/gen-func-hw.txt"

echo "=== Function Coverage (HW files) ==="
GT_F=$(wc -l < "$EVAL_DIR/gt-func-hw.txt" | tr -d ' ')
GEN_F=$(wc -l < "$EVAL_DIR/gen-func-hw.txt" | tr -d ' ')
echo "GT functions: $GT_F"
echo "Gen functions: $GEN_F"

# Intersection
LC_ALL=C comm -12 "$EVAL_DIR/gt-func-hw.txt" "$EVAL_DIR/gen-func-hw.txt" > "$EVAL_DIR/func-covered.txt"
COVERED_F=$(wc -l < "$EVAL_DIR/func-covered.txt" | tr -d ' ')

echo ""
echo "Covered functions:"
cat "$EVAL_DIR/func-covered.txt" | head -15

echo ""
echo "Missing functions:"
LC_ALL=C comm -23 "$EVAL_DIR/gt-func-hw.txt" "$EVAL_DIR/gen-func-hw.txt" | head -15

echo ""
if [[ $GT_F -gt 0 ]]; then
  PCT_F=$(echo "scale=1; $COVERED_F * 100 / $GT_F" | bc)
  echo "**Function Coverage: $COVERED_F/$GT_F = $PCT_F%**"
else
  echo "**Function Coverage: N/A**"
fi
```

### Step 4: Semantic Analysis

#### 4a. Requirements Checklist
If prompt provided, decompose into discrete items. Check against GT and generated.

#### 4b. File Comparison
For each covered HW file: compare approach, scope, missing/extra logic.

#### 4c. Test Gap
Compare test files in GT vs generated.

### Step 5: Scoring

Read [references/scoring_rubric.md](references/scoring_rubric.md).

| Score | Criteria |
|-------|----------|
| A (0-5) | Functional Correctness |
| B (0-5) | Completeness (HW files only) |
| C (0-5) | Behavioral Equivalence to GT |

**Verdict rules**:
- PASS: A≥4 AND B≥4 AND C≥3
- FAIL: A≤1 OR destructive
- PARTIAL: otherwise

### Step 6: Save Report

Save to `<REPO_PATH>/eval_report.md`:

```markdown
## Evaluation Report

### Summary
[1-3 sentences]

### Verdict: [PASS / PARTIAL / FAIL]

### Scores
- **A. Functional Correctness**: [X]/5 — [justification]
- **B. Completeness**: [X]/5 — [justification, HW scope]
- **C. Behavioral Equivalence**: [X]/5 — [justification]

### Deterministic Coverage

#### HW File Coverage: [X]/[Y] = [Z]%
| File | Status |
|------|--------|
| file1.go | ✓ Covered |
| file2.go | ✗ Missing |

#### Function Coverage: [X]/[Y] = [Z]%

### Requirements Checklist
| # | Requirement | GT | Gen | Status |
|---|-------------|:--:|:---:|--------|

### Analysis
- Approach differences
- Missing logic
- Test gaps

### Confidence: [0.0-1.0]
```

## Examples

```bash
# Kubernetes K3 task
/diff-eval-local \
  experiment/K3-codex-gpt-5_4-long-2026-04-12 \
  base_repo/K3/eval/gt_diff.patch \
  base_repo/K3/eval/handwritten_files.txt \
  base_repo/K3/prompts/K3-long.md

# Generic project
/diff-eval-local \
  ./my-project \
  ./ground-truth.diff \
  ./handwritten_files.txt

# With relative paths
/diff-eval-local repo/ gt.patch hw.txt requirements.md
```
