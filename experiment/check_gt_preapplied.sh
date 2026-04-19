#!/usr/bin/env bash
# check_gt_preapplied.sh
# Checks all codex experiments from 2026-04-12 for GT pre-application bug.
#
# For each experiment:
#   1. Count uncommitted changed files (git diff --stat HEAD)
#   2. Count handwritten files from base_repo/{TASK}/eval/handwritten_files.txt
#   3. Check codex_events.jsonl size and content quality
#   4. Flag as SUSPICIOUS if events show no real work but changes exist
#
# Known-bad: T39-codex-long (error in events), T16-codex-short (pre-applied)

set -euo pipefail

BASE="/Users/zihanwu/Public/codes/huawei-eval"
EXPERIMENT_DIR="$BASE/experiment"
BASE_REPO="$BASE/base_repo"

# Header
printf "%-50s | %5s | %5s | %10s | %6s | %4s | %s\n" \
    "EXPERIMENT" "UNCOMM" "HW" "EVENTS_SZ" "LINES" "CMDS" "SUSPICIOUS"
printf "%-50s-+-%5s-+-%5s-+-%10s-+-%6s-+-%4s-+-%s\n" \
    "$(printf '%0.s-' {1..50})" "-----" "-----" "----------" "------" "----" "----------"

SUSPICIOUS_COUNT=0
declare -a SUSPICIOUS_LIST=()

for dir in "$EXPERIMENT_DIR"/*-codex-gpt-5_4-*-2026-04-12; do
    [ -d "$dir" ] || continue

    exp_name="$(basename "$dir")"

    # Extract task ID from experiment_meta.json or directory name
    task_id=""
    if [ -f "$dir/experiment_meta.json" ]; then
        task_id=$(python3 -c "import json; print(json.load(open('$dir/experiment_meta.json'))['task'])" 2>/dev/null || true)
    fi
    if [ -z "$task_id" ]; then
        # Fallback: extract from directory name (e.g., T39-codex-... -> T39, C1-codex-... -> C1)
        task_id=$(echo "$exp_name" | sed -E 's/^([A-Z][0-9]+)-codex-.*/\1/')
    fi

    # Count uncommitted changed files
    diff_summary=$(cd "$dir" && git diff --stat HEAD 2>/dev/null | tail -1 || true)
    uncommitted=$(echo "$diff_summary" | grep -oE '^[[:space:]]*[0-9]+' | tr -d ' ' || true)
    if [ -z "$uncommitted" ] || ! [[ "$uncommitted" =~ ^[0-9]+$ ]]; then
        uncommitted=0
    fi

    # Count handwritten files
    hw_file="$BASE_REPO/$task_id/eval/handwritten_files.txt"
    if [ -f "$hw_file" ]; then
        hw_count=$(wc -l < "$hw_file" | tr -d ' ')
    else
        hw_count="N/A"
    fi

    # Check events file
    events_file="$dir/codex_events.jsonl"
    events_size=0
    events_lines=0
    if [ -f "$events_file" ]; then
        events_size=$(wc -c < "$events_file" | tr -d ' ')
        events_lines=$(wc -l < "$events_file" | tr -d ' ')
    fi

    # Count actual command executions
    command_count=0
    has_error=false
    if [ -f "$events_file" ] && [ "$events_size" -gt 0 ]; then
        command_count=$(grep -c '"command_execution"' "$events_file" 2>/dev/null || true)
        if [ -z "$command_count" ] || ! [[ "$command_count" =~ ^[0-9]+$ ]]; then
            command_count=0
        fi
        if grep -q '"type":"error"' "$events_file" 2>/dev/null; then
            has_error=true
        fi
    fi

    # Determine suspicion level
    suspicious="OK"
    reason=""

    if [ "$uncommitted" -gt 0 ]; then
        # Case 1: No events at all but uncommitted changes exist
        if [ "$events_size" -eq 0 ]; then
            suspicious="YES"
            reason="no events file, $uncommitted changed files"
        # Case 2: Tiny events file (<1KB), likely just error/start messages
        elif [ "$events_size" -lt 1000 ] && [ "$command_count" -eq 0 ]; then
            if [ "$has_error" = true ]; then
                suspicious="YES"
                reason="error+no cmds, $uncommitted changed files"
            else
                suspicious="YES"
                reason="tiny events+no cmds, $uncommitted changed files"
            fi
        # Case 3: Has error, no commands, but larger events file (unlikely but check)
        elif [ "$has_error" = true ] && [ "$command_count" -eq 0 ]; then
            suspicious="YES"
            reason="error+no cmds, $uncommitted changed files"
        fi
    fi

    if [ "$suspicious" = "YES" ]; then
        SUSPICIOUS_COUNT=$((SUSPICIOUS_COUNT + 1))
        SUSPICIOUS_LIST+=("$exp_name")
        flag_display="<<< YES ($reason)"
    else
        flag_display=""
    fi

    printf "%-50s | %5s | %5s | %10s | %6s | %4s | %s\n" \
        "$exp_name" "$uncommitted" "$hw_count" "$events_size" "$events_lines" "$command_count" "$flag_display"
done

echo ""
echo "============================================="
echo "  SUMMARY"
echo "============================================="
echo "Total experiments scanned: $(ls -d "$EXPERIMENT_DIR"/*-codex-gpt-5_4-*-2026-04-12 2>/dev/null | wc -l | tr -d ' ')"
echo "Suspicious (GT pre-applied, no agent work): $SUSPICIOUS_COUNT"
echo ""

if [ "$SUSPICIOUS_COUNT" -gt 0 ]; then
    echo "SUSPICIOUS EXPERIMENTS:"
    for s in "${SUSPICIOUS_LIST[@]}"; do
        echo "  - $s"
    done
    echo ""

    echo "============================================="
    echo "  DETAIL FOR SUSPICIOUS EXPERIMENTS"
    echo "============================================="
    for dir in "$EXPERIMENT_DIR"/*-codex-gpt-5_4-*-2026-04-12; do
        [ -d "$dir" ] || continue
        exp_name="$(basename "$dir")"

        events_file="$dir/codex_events.jsonl"
        events_size=0
        [ -f "$events_file" ] && events_size=$(wc -c < "$events_file" | tr -d ' ')

        uncommitted=$(cd "$dir" && git diff --stat HEAD 2>/dev/null | tail -1 | grep -oE '^[[:space:]]*[0-9]+' | tr -d ' ' || true)
        [ -z "$uncommitted" ] && uncommitted=0

        command_count=0
        if [ -f "$events_file" ] && [ "$events_size" -gt 0 ]; then
            command_count=$(grep -c '"command_execution"' "$events_file" 2>/dev/null || true)
            [ -z "$command_count" ] && command_count=0
        fi

        if [ "$uncommitted" -gt 0 ] && [ "$command_count" -eq 0 ]; then
            echo ""
            echo "--- $exp_name ---"
            echo "Events content:"
            cat "$events_file" 2>/dev/null || echo "(no file)"
            echo ""
            echo "Changed files (first 20):"
            (cd "$dir" && git diff --name-only HEAD | head -20)
            echo "..."
            echo "Git diff summary:"
            (cd "$dir" && git diff --stat HEAD | tail -1)
        fi
    done
fi
