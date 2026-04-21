#!/bin/bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/Users/zihanwu/Public/codes/huawei-eval}"
DIR_LIST="${DIR_LIST:-/tmp/eval_t_dirs.txt}"
PARALLELISM="${PARALLELISM:-8}"
MODEL="${MODEL:-gpt-5.4}"
REPORT_NAME="${REPORT_NAME:-eval_report-codex.md}"
GT_DIFF_CHAR_LIMIT="${GT_DIFF_CHAR_LIMIT:-50000}"
STATE_DIR=""

log() {
  printf '%s\n' "$*" >&2
}

die() {
  log "ERROR: $*"
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

format_pct() {
  local numerator="$1"
  local denominator="$2"

  if [[ "$denominator" -gt 0 ]]; then
    awk -v n="$numerator" -v d="$denominator" 'BEGIN { printf "%.1f", (n * 100.0) / d }'
  else
    printf 'N/A'
  fi
}

with_percent() {
  local pct="$1"

  if [[ "$pct" == "N/A" ]]; then
    printf 'N/A'
  else
    printf '%s%%' "$pct"
  fi
}

render_file_with_limit() {
  local file_path="$1"
  local char_limit="$2"

  if [[ ! -f "$file_path" ]]; then
    printf '(missing file: %s)\n' "$file_path"
    return 0
  fi

  local char_count
  char_count="$(wc -c < "$file_path" | tr -d ' ')"

  if [[ "$char_limit" -gt 0 && "$char_count" -gt "$char_limit" ]]; then
    head -c "$char_limit" "$file_path"
    printf '\n\n[TRUNCATED: showing first %s of %s characters from %s]\n' "$char_limit" "$char_count" "$file_path"
  else
    cat "$file_path"
  fi
}

collect_generated_files() {
  local exp_dir="$1"

  {
    git -C "$exp_dir" diff HEAD --name-only
    git -C "$exp_dir" ls-files --others --exclude-standard
  } | sed 's/\r$//' | sed '/^[[:space:]]*$/d' | LC_ALL=C sort -u
}

render_untracked_diff() {
  local exp_dir="$1"

  while IFS= read -r rel_path; do
    [[ -n "$rel_path" ]] || continue
    [[ -f "$exp_dir/$rel_path" ]] || continue

    (
      cd "$exp_dir"
      git diff --no-index -- /dev/null "$rel_path"
    ) || true
  done < <(git -C "$exp_dir" ls-files --others --exclude-standard)
}

extract_function_contexts() {
  local diff_file="$1"
  local out_file="$2"

  LC_ALL=C awk '
    /^diff --git / {
      file = $0
      sub(/^diff --git a\/[^[:space:]]+[[:space:]]b\//, "", file);
      next
    }
    /^@@/ {
      if (file == "") {
        next
      }
      ctx = $0
      sub(/^@@[^@]*@@[[:space:]]*/, "", ctx)
      if (ctx != "") {
        print file " :: " ctx
      }
    }
  ' "$diff_file" 2>/dev/null | LC_ALL=C sort -u > "$out_file"
}

load_metadata() {
  local meta_file="$1"

  python3 - "$meta_file" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)

print((data.get("task_id") or "").strip())
print((data.get("prompt_type") or "").strip())
PY
}

record_progress() {
  local exp_dir="$1"
  local status="$2"

  while ! mkdir "$LOCK_DIR" 2>/dev/null; do
    sleep 0.05
  done

  printf '%s\t%s\n' "$status" "$exp_dir" >> "$PROGRESS_FILE"

  local completed
  completed="$(wc -l < "$PROGRESS_FILE" | tr -d ' ')"
  printf '[%s/%s] %s %s\n' "$completed" "$TOTAL_COUNT" "$status" "$exp_dir" >&2

  rmdir "$LOCK_DIR"
}

worker_on_exit() {
  if [[ -n "${WORKER_TMP_DIR:-}" && -d "${WORKER_TMP_DIR:-}" ]]; then
    rm -rf "$WORKER_TMP_DIR"
  fi

  record_progress "${WORKER_EXP_DIR:-"(unknown)"}" "${WORKER_STATUS:-ERROR}"
}

worker_main() {
  local exp_dir="$1"

  WORKER_EXP_DIR="$exp_dir"
  WORKER_STATUS="ERROR"
  WORKER_TMP_DIR=""
  trap worker_on_exit EXIT

  if [[ ! -d "$exp_dir" ]]; then
    log "ERROR: experiment directory not found: $exp_dir"
    return 0
  fi

  local report_path="$exp_dir/$REPORT_NAME"
  if [[ -f "$report_path" ]]; then
    WORKER_STATUS="SKIP"
    return 0
  fi

  local meta_file="$exp_dir/run_metadata.json"
  if [[ ! -f "$meta_file" ]]; then
    log "ERROR: missing run_metadata.json in $exp_dir"
    return 0
  fi

  local -a metadata_lines=()
  mapfile -t metadata_lines < <(load_metadata "$meta_file")
  local task_id="${metadata_lines[0]:-}"
  local prompt_type="${metadata_lines[1]:-}"

  if [[ -z "$task_id" || -z "$prompt_type" ]]; then
    log "ERROR: could not parse task_id/prompt_type from $meta_file"
    return 0
  fi

  local gt_diff="$REPO_ROOT/base_repo/$task_id/eval/gt_diff.patch"
  local hw_files="$REPO_ROOT/base_repo/$task_id/eval/handwritten_files.txt"
  local prompt_file="$REPO_ROOT/base_repo/$task_id/prompts/${task_id}-${prompt_type}.md"

  if [[ ! -r "$gt_diff" ]]; then
    log "ERROR: GT diff not readable: $gt_diff"
    return 0
  fi

  if [[ ! -r "$hw_files" ]]; then
    log "ERROR: handwritten file list not readable: $hw_files"
    return 0
  fi

  WORKER_TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/eval-t-codex.XXXXXX")"

  local hw_txt="$WORKER_TMP_DIR/hw.txt"
  local gen_txt="$WORKER_TMP_DIR/gen.txt"
  local covered_txt="$WORKER_TMP_DIR/covered.txt"
  local missing_txt="$WORKER_TMP_DIR/missing.txt"
  local extra_txt="$WORKER_TMP_DIR/extra.txt"
  local gt_diff_copy="$WORKER_TMP_DIR/gt.patch"
  local tracked_diff="$WORKER_TMP_DIR/tracked.patch"
  local untracked_diff="$WORKER_TMP_DIR/untracked.patch"
  local generated_diff="$WORKER_TMP_DIR/generated.patch"
  local gt_func_all="$WORKER_TMP_DIR/gt-func-all.txt"
  local gen_func_all="$WORKER_TMP_DIR/gen-func-all.txt"
  local gt_func_hw="$WORKER_TMP_DIR/gt-func-hw.txt"
  local gen_func_hw="$WORKER_TMP_DIR/gen-func-hw.txt"
  local func_covered_txt="$WORKER_TMP_DIR/func-covered.txt"
  local func_missing_txt="$WORKER_TMP_DIR/func-missing.txt"
  local prompt_tmp="$WORKER_TMP_DIR/eval_prompt.md"

  sed 's/\r$//' "$hw_files" | sed '/^[[:space:]]*$/d' | LC_ALL=C sort -u > "$hw_txt"
  collect_generated_files "$exp_dir" > "$gen_txt"

  LC_ALL=C comm -12 "$hw_txt" "$gen_txt" > "$covered_txt"
  LC_ALL=C comm -23 "$hw_txt" "$gen_txt" > "$missing_txt"
  LC_ALL=C comm -13 "$hw_txt" "$gen_txt" > "$extra_txt"

  local hw_count
  local covered_count
  local missing_count
  local extra_count
  hw_count="$(wc -l < "$hw_txt" | tr -d ' ')"
  covered_count="$(wc -l < "$covered_txt" | tr -d ' ')"
  missing_count="$(wc -l < "$missing_txt" | tr -d ' ')"
  extra_count="$(wc -l < "$extra_txt" | tr -d ' ')"

  local hw_pct
  local hw_pct_display
  hw_pct="$(format_pct "$covered_count" "$hw_count")"
  hw_pct_display="$(with_percent "$hw_pct")"

  cat "$gt_diff" > "$gt_diff_copy"
  git -C "$exp_dir" diff HEAD > "$tracked_diff"
  render_untracked_diff "$exp_dir" > "$untracked_diff"
  cat "$tracked_diff" "$untracked_diff" > "$generated_diff"

  extract_function_contexts "$gt_diff_copy" "$gt_func_all"
  extract_function_contexts "$generated_diff" "$gen_func_all"

  awk -F ' :: ' 'NR == FNR { hw[$1] = 1; next } ($1 in hw) { print }' "$hw_txt" "$gt_func_all" | LC_ALL=C sort -u > "$gt_func_hw"
  awk -F ' :: ' 'NR == FNR { hw[$1] = 1; next } ($1 in hw) { print }' "$hw_txt" "$gen_func_all" | LC_ALL=C sort -u > "$gen_func_hw"

  LC_ALL=C comm -12 "$gt_func_hw" "$gen_func_hw" > "$func_covered_txt"
  LC_ALL=C comm -23 "$gt_func_hw" "$gen_func_hw" > "$func_missing_txt"

  local gt_func_count
  local func_covered_count
  local func_pct
  local func_pct_display
  gt_func_count="$(wc -l < "$gt_func_hw" | tr -d ' ')"
  func_covered_count="$(wc -l < "$func_covered_txt" | tr -d ' ')"
  func_pct="$(format_pct "$func_covered_count" "$gt_func_count")"
  func_pct_display="$(with_percent "$func_pct")"

  {
    cat <<EOF
# Task: Evaluate One T-Series Experiment

Evaluate the generated changes for this experiment and write the report to:

\`$report_path\`

Create or overwrite that file. Do not modify any other files.
Use the pre-computed deterministic coverage below as authoritative input.
Do not recompute coverage with your own heuristics.
Use integer scores only for A/B/C.

## Experiment Metadata

- Experiment Dir: \`$exp_dir\`
- Task ID: \`$task_id\`
- Prompt Type: \`$prompt_type\`
- Report Path: \`$report_path\`

## Pre-computed Deterministic Coverage

- HW File Coverage: **$covered_count/$hw_count = $hw_pct_display**
- Function Coverage: **$func_covered_count/$gt_func_count = $func_pct_display**
- Missing HW Files: **$missing_count**
- Extra Generated Files (outside HW scope): **$extra_count**

### Covered HW Files

\`\`\`text
EOF
    if [[ -s "$covered_txt" ]]; then
      cat "$covered_txt"
    else
      printf '(none)\n'
    fi
    cat <<EOF
\`\`\`

### Missing HW Files

\`\`\`text
EOF
    if [[ -s "$missing_txt" ]]; then
      cat "$missing_txt"
    else
      printf '(none)\n'
    fi
    cat <<EOF
\`\`\`

### Missing GT Function Contexts Within HW Scope

\`\`\`text
EOF
    if [[ -s "$func_missing_txt" ]]; then
      head -n 200 "$func_missing_txt"
      if [[ "$(wc -l < "$func_missing_txt" | tr -d ' ')" -gt 200 ]]; then
        printf '... (truncated, showing first 200 missing function contexts)\n'
      fi
    else
      printf '(none)\n'
    fi
    cat <<EOF
\`\`\`

## File Paths (read these yourself as needed)

- GT diff: \`$gt_diff_copy\`
- Generated patch (tracked + untracked): \`$generated_diff\`
- Requirements/prompt: \`$prompt_file\`

Explore these files strategically:
1. Check file sizes first (wc -c)
2. For large diffs, read only sections for covered HW files rather than the entire file
3. Use grep/sed to extract specific file sections from diffs
4. Read the requirements file to understand the task
EOF
    cat <<'EOF'

## Scoring Rubric

Score each dimension with an integer from 0 to 5.
Use these labels consistently: 0 = unacceptable, 1 = very poor, 2 = poor, 3 = acceptable, 4 = good, 5 = excellent.

- **A. Functional Correctness**: Does the generated patch correctly implement the requested behavior at the semantic level?
- **B. Completeness**: Does it cover the necessary handwritten-file scope and related logic? Weight the pre-computed HW file/function coverage heavily here.
- **C. Behavioral Equivalence**: Is the resulting behavior semantically equivalent to the ground truth, even if implementation details differ?

## Verdict Rules

- **PASS** if A >= 4 AND B >= 4 AND C >= 3
- **FAIL** if A <= 1 OR (A + B + C) <= 5
- **PARTIAL** otherwise

## Output Requirements

Write the report directly to the report path shown above using exactly this structure:

```markdown
## Evaluation Report
**Evaluator**: Codex (gpt-5.4)
### Summary
### Verdict: [PASS / PARTIAL / FAIL]
### Scores
- **A. Functional Correctness**: [X]/5 — [justification]
- **B. Completeness**: [X]/5 — [justification]
- **C. Behavioral Equivalence**: [X]/5 — [justification]
### Deterministic Coverage
#### HW File Coverage: X/Y = Z%
#### Function Coverage: X/Y = Z%
### Analysis
### Confidence: [0.0-1.0]
```

Use the exact coverage numbers from the pre-computed section above.
Do not add extra top-level sections.
Do not print the report to stdout; write the file and finish.
EOF
  } > "$prompt_tmp"

  (
    cd "$exp_dir"
    codex exec -m "$MODEL" --full-auto -C "$exp_dir" - < "$prompt_tmp"
  )

  if [[ -f "$report_path" ]]; then
    WORKER_STATUS="DONE"
  else
    log "ERROR: Codex finished without writing report: $report_path"
    WORKER_STATUS="ERROR"
  fi
}

main() {
  require_cmd awk
  require_cmd codex
  require_cmd comm
  require_cmd git
  require_cmd head
  require_cmd mktemp
  require_cmd python3
  require_cmd sed
  require_cmd sort
  require_cmd wc
  require_cmd xargs

  [[ -n "${TIMEOUT_BIN:-}" ]] || die "Neither timeout nor gtimeout is available"

  if [[ ! -f "$DIR_LIST" ]]; then
    die "Directory list not found: $DIR_LIST"
  fi

  TOTAL_COUNT="$(awk 'NF { count++ } END { print count + 0 }' "$DIR_LIST")"
  if [[ "$TOTAL_COUNT" -eq 0 ]]; then
    die "No experiment directories found in $DIR_LIST"
  fi

  STATE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/eval-t-codex-state.XXXXXX")"
  PROGRESS_FILE="$STATE_DIR/progress.tsv"
  LOCK_DIR="$STATE_DIR/progress.lock"
  touch "$PROGRESS_FILE"

  export REPO_ROOT DIR_LIST PARALLELISM MODEL REPORT_NAME GT_DIFF_CHAR_LIMIT
  export TIMEOUT_BIN TOTAL_COUNT PROGRESS_FILE LOCK_DIR
  export -f log die require_cmd format_pct with_percent render_file_with_limit
  export -f collect_generated_files render_untracked_diff extract_function_contexts
  export -f load_metadata record_progress worker_on_exit worker_main

  trap 'rm -rf "$STATE_DIR"' EXIT

  log "Starting Codex batch evaluation for $TOTAL_COUNT experiments from $DIR_LIST"
  log "Parallelism: $PARALLELISM"

  set +e
  while IFS= read -r exp_dir || [[ -n "$exp_dir" ]]; do
    exp_dir="${exp_dir%$'\r'}"
    [[ -n "$exp_dir" ]] || continue
    printf '%s\0' "$exp_dir"
  done < "$DIR_LIST" | xargs -0 -n1 -P "$PARALLELISM" bash -c 'set -euo pipefail; worker_main "$1"' _
  local xargs_status=$?
  set -e

  local done_count
  local skip_count
  local error_count
  done_count="$(awk -F '\t' '$1 == "DONE" { count++ } END { print count + 0 }' "$PROGRESS_FILE")"
  skip_count="$(awk -F '\t' '$1 == "SKIP" { count++ } END { print count + 0 }' "$PROGRESS_FILE")"
  error_count="$(awk -F '\t' '$1 == "ERROR" { count++ } END { print count + 0 }' "$PROGRESS_FILE")"

  log "Finished: DONE=$done_count SKIP=$skip_count ERROR=$error_count TOTAL=$TOTAL_COUNT"

  if [[ "$xargs_status" -ne 0 && "$error_count" -eq 0 ]]; then
    log "WARNING: xargs exited with status $xargs_status even though no worker reported ERROR"
  fi

  if [[ "$error_count" -gt 0 ]]; then
    exit 1
  fi
}

TIMEOUT_BIN="$(command -v timeout || command -v gtimeout || true)"
main "$@"
