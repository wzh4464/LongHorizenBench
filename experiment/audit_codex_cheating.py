#!/usr/bin/env python3
"""
audit_codex_cheating.py  --  Comprehensive cheating audit for Codex experiments.

Checks whether any Codex experiment might have accessed ground-truth data
by examining event logs, git history, diff similarity, and evaluation scores.

Usage:
    python3 audit_codex_cheating.py                # audit all Codex experiments
    python3 audit_codex_cheating.py --task K4      # audit only task K4
    python3 audit_codex_cheating.py --verbose       # detailed per-experiment output
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent          # experiment/
REPO_ROOT = SCRIPT_DIR.parent                         # huawei-eval/
BASE_REPO = REPO_ROOT / "base_repo"

# Codex experiment directory pattern: {TASK}-codex-gpt-5_4-{long|short}-{date}/
CODEX_DIR_RE = re.compile(
    r"^(?P<task>[A-Z]\d+)-codex-gpt-5_4-(?P<prompt>long|short)-(?P<date>\d{4}-\d{2}-\d{2})$"
)

# Task complexity tiers (from CLAUDE.md)
TASK_COMPLEXITY = {
    "C1": "Low",   "C2": "Low",   "C3": "Medium", "C4": "Medium",
    "C5": "High",  "M1": "Low",   "M2": "Medium",  "M3": "High",
    "K1": "Low",   "K2": "Medium", "K3": "Medium", "K4": "High",
}

# ---------------------------------------------------------------------------
# Suspicious-pattern matching
# ---------------------------------------------------------------------------
# We use a function-based approach for command text to reduce false positives.
# Raw patterns are too noisy because agents legitimately exclude metadata files
# in git diff commands, search for "curl" with rg/grep, etc.

# Patterns in agent messages (these are what the agent *says*, so any mention
# of GT/cheating vocabulary is suspicious)
SUSPICIOUS_MSG_PATTERNS = [
    (re.compile(r"ground.?truth", re.I), "mentions ground truth"),
    (re.compile(r"\bcheat\b|\bcopy.*answer\b", re.I), "mentions cheating/copying answer"),
    (re.compile(r"base_repo", re.I), "mentions base_repo"),
    (re.compile(r"gt_diff|gt_patch", re.I), "mentions GT diff/patch"),
    (re.compile(r"\bhandwritten.?files\b", re.I), "mentions handwritten files list"),
]


def classify_command(cmd: str, output: str) -> list[tuple[str, str]]:
    """
    Analyze a command for suspicious patterns, returning list of (severity, reason).
    Severity is "CRITICAL" or "WARNING".

    This function uses contextual heuristics to reduce false positives compared
    to raw regex matching. For example:
    - 'rg "curl"' is a search for "curl" in code, not actual curl usage
    - 'git diff ... :(exclude)experiment_meta.json' is excluding the file, not reading it
    """
    findings: list[tuple[str, str]] = []
    cmd_lower = cmd.lower()
    output_lower = (output or "").lower()

    # --- Cherry-pick ---
    if "cherry-pick" in cmd_lower:
        findings.append(("CRITICAL", "cherry-pick command"))

    # --- Git checkout of specific SHA ---
    if re.search(r"git\s+checkout\s+[0-9a-f]{7,40}", cmd, re.I):
        findings.append(("CRITICAL", "checkout of specific commit SHA"))

    # --- Actual curl/wget usage (not just searching for the word) ---
    # Exclude: rg "curl", grep "curl", commands that are clearly searching for curl
    is_search_cmd = bool(re.match(r".*(rg|grep|ack|ag)\s+", cmd_lower))
    if re.match(r".*\bcurl\s+", cmd_lower) and not is_search_cmd:
        findings.append(("CRITICAL", "curl web access"))
    if re.match(r".*\bwget\s+", cmd_lower) and not is_search_cmd:
        findings.append(("CRITICAL", "wget web access"))

    # --- gh CLI usage ---
    if re.search(r"\bgh\s+(pr|issue|api|repo)", cmd, re.I):
        findings.append(("CRITICAL", "gh CLI usage"))

    # --- Reading base_repo directly ---
    # Exclude: the prompt_file path in experiment_meta.json mentions base_repo,
    # and agents may legitimately read that metadata file. Focus on commands
    # that actually access base_repo/*/eval/ or base_repo/*/repo/ paths.
    if re.search(r"base_repo/\w+/(eval|repo)", cmd):
        findings.append(("CRITICAL", "accessing base_repo eval/repo directory"))
    elif "base_repo" in cmd_lower and not is_search_cmd:
        # Agent navigating to base_repo but not eval/repo specifically
        findings.append(("WARNING", "reference to base_repo path"))

    # --- Ground truth file access ---
    if re.search(r"(cat|less|more|head|tail|sed|bat|nl|view)\b.*\bgt_diff", cmd_lower):
        findings.append(("CRITICAL", "reading GT diff file"))
    elif re.search(r"(cat|less|more|head|tail|sed|bat|nl|view)\b.*\bground_truth\.diff", cmd_lower):
        findings.append(("CRITICAL", "reading ground_truth.diff"))
    elif re.search(r"ground.?truth\.diff", cmd_lower) and not is_search_cmd:
        findings.append(("CRITICAL", "reference to ground_truth.diff"))
    elif re.search(r"\bgt_diff\b", cmd_lower) and not is_search_cmd:
        findings.append(("WARNING", "reference to gt_diff"))

    # --- Handwritten files list access ---
    # Distinguish between reading it vs. mentioning it in an exclude pattern
    if re.search(r"(cat|less|more|head|tail|sed|bat|nl|view)\b.*\bhandwritten_files", cmd_lower):
        findings.append(("CRITICAL", "reading handwritten_files list"))
    elif "handwritten_files" in cmd_lower and "exclude" not in cmd_lower and not is_search_cmd:
        findings.append(("WARNING", "reference to handwritten_files"))

    # --- Reading experiment_meta.json ---
    # Distinguish: 'cat experiment_meta.json' vs ':(exclude)experiment_meta.json'
    if re.search(r"(cat|less|more|head|tail|sed|bat|nl|view)\b.*\bexperiment_meta", cmd_lower):
        findings.append(("WARNING", "reading experiment_meta.json"))
    # Skip when it appears only in exclude patterns or rg/grep globs

    # --- Reading eval_report.md ---
    if re.search(r"(cat|less|more|head|tail|sed|bat|nl|view)\b.*\beval_report", cmd_lower):
        findings.append(("CRITICAL", "reading eval_report.md"))

    # --- Cherry-pick in output ---
    if "cherry-pick" in output_lower:
        findings.append(("WARNING", "cherry-pick referenced in command output"))

    # --- base_repo eval path appearing in output ---
    if re.search(r"base_repo/\w+/eval", output):
        findings.append(("WARNING", "base_repo eval path appears in output"))

    return findings

# Patterns for git archaeology (not cheating per se, but worth tracking)
GIT_ARCHAEOLOGY_PATTERNS = [
    (re.compile(r"git\s+log\b", re.I), "git log"),
    (re.compile(r"git\s+show\s+[0-9a-f]{7,40}", re.I), "git show <sha>"),
    (re.compile(r"git\s+log\s+.*-S\b", re.I), "git log -S (pickaxe search)"),
    (re.compile(r"git\s+log\s+.*--grep", re.I), "git log --grep"),
    (re.compile(r"git\s+log\s+.*--author", re.I), "git log --author"),
    (re.compile(r"git\s+log\s+.*--all", re.I), "git log --all"),
]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    category: str       # "CRITICAL", "WARNING", "INFO"
    check: str          # which audit check produced this
    message: str        # human-readable description
    detail: str = ""    # optional extra context


@dataclass
class ExperimentAudit:
    dir_name: str
    task: str
    prompt: str
    date: str
    exp_dir: Path
    findings: list[Finding] = field(default_factory=list)
    # Eval scores
    score_a: Optional[int] = None
    score_b: Optional[int] = None
    score_c: Optional[int] = None
    verdict: Optional[str] = None
    hw_coverage: Optional[str] = None
    # Diff similarity
    jaccard_sim: Optional[float] = None
    file_overlap: Optional[str] = None
    exact_match_ratio: Optional[float] = None
    # Event log stats
    total_commands: int = 0
    suspicious_commands: int = 0
    git_archaeology_commands: int = 0
    # GT reachability
    gt_reachable: Optional[bool] = None
    experiment_commit_count: int = 0

    def add(self, category: str, check: str, message: str, detail: str = ""):
        self.findings.append(Finding(category, check, message, detail))

    @property
    def has_critical(self) -> bool:
        return any(f.category == "CRITICAL" for f in self.findings)

    @property
    def has_warning(self) -> bool:
        return any(f.category == "WARNING" for f in self.findings)

    @property
    def is_flagged(self) -> bool:
        return self.has_critical or self.has_warning


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_git(args: list[str], cwd: Path, timeout: int = 30) -> tuple[int, str]:
    """Run a git command and return (returncode, stdout)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout
    except subprocess.TimeoutExpired:
        return -1, "<timeout>"
    except Exception as e:
        return -1, str(e)


def parse_diff_lines(diff_text: str) -> tuple[set[str], set[str], set[str]]:
    """Parse a unified diff into (added_lines, removed_lines, changed_files)."""
    added = set()
    removed = set()
    files = set()
    current_file = None
    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            # Extract b-side filename
            m = re.search(r" b/(.+)$", line)
            if m:
                current_file = m.group(1)
                files.add(current_file)
        elif line.startswith("+") and not line.startswith("+++"):
            added.add(line[1:].strip())
        elif line.startswith("-") and not line.startswith("---"):
            removed.add(line[1:].strip())
    return added, removed, files


def jaccard(set_a: set, set_b: set) -> float:
    """Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


# ---------------------------------------------------------------------------
# Audit checks
# ---------------------------------------------------------------------------

def discover_experiments(task_filter: Optional[str] = None) -> list[dict]:
    """Find all Codex experiment directories."""
    experiments = []
    for entry in sorted(SCRIPT_DIR.iterdir()):
        if not entry.is_dir():
            continue
        m = CODEX_DIR_RE.match(entry.name)
        if not m:
            continue
        task = m.group("task")
        if task_filter and task != task_filter:
            continue
        experiments.append({
            "dir_name": entry.name,
            "task": task,
            "prompt": m.group("prompt"),
            "date": m.group("date"),
            "exp_dir": entry,
        })
    return experiments


def check_gt_reachability(audit: ExperimentAudit) -> None:
    """
    Check 1: GT Commit Reachability.

    Verifies the experiment repo does not contain significantly more commits
    than the base repo, which would indicate unsanitized history with GT
    commits reachable.

    Also checks for remote references and extra branches.
    """
    exp_dir = audit.exp_dir
    task = audit.task
    base_repo_dir = BASE_REPO / task / "repo"

    # Count commits in experiment repo
    rc, out = run_git(["rev-list", "--all", "--count"], cwd=exp_dir, timeout=60)
    exp_count = int(out.strip()) if rc == 0 and out.strip().isdigit() else -1
    audit.experiment_commit_count = exp_count

    # Count commits in base repo for comparison
    rc2, out2 = run_git(["rev-list", "--all", "--count"], cwd=base_repo_dir, timeout=60)
    base_count = int(out2.strip()) if rc2 == 0 and out2.strip().isdigit() else -1

    if exp_count > 0 and base_count > 0:
        if exp_count > base_count + 10:
            audit.add("WARNING", "gt_reachability",
                       f"Experiment has {exp_count} commits vs base {base_count} "
                       f"(+{exp_count - base_count} extra) -- possible unsanitized history")
        elif exp_count != base_count:
            audit.add("INFO", "gt_reachability",
                       f"Commit count differs: experiment={exp_count}, base={base_count}")

    # Check for remotes (should be none in sanitized repos)
    rc, out = run_git(["remote", "-v"], cwd=exp_dir)
    if rc == 0 and out.strip():
        audit.add("WARNING", "gt_reachability",
                   f"Experiment repo has remotes: {out.strip()}")

    # Check for extra branches (should only have detached HEAD or none)
    rc, out = run_git(["branch", "-a"], cwd=exp_dir)
    if rc == 0:
        branches = [b.strip() for b in out.strip().splitlines() if b.strip()]
        named_branches = [b for b in branches if not b.startswith("* (")]
        if named_branches:
            audit.add("INFO", "gt_reachability",
                       f"Named branches found: {', '.join(named_branches)}")

    # Check if experiment HEAD matches base repo HEAD (expected after sanitization)
    rc_exp, exp_head = run_git(["rev-parse", "HEAD"], cwd=exp_dir)
    rc_base, base_head = run_git(["rev-parse", "HEAD"], cwd=base_repo_dir)
    if rc_exp == 0 and rc_base == 0:
        exp_sha = exp_head.strip()
        base_sha = base_head.strip()
        if exp_sha != base_sha:
            audit.add("WARNING", "gt_reachability",
                       f"HEAD mismatch: experiment={exp_sha[:12]}, base={base_sha[:12]}")
        audit.gt_reachable = False  # default; set True below if found
    else:
        audit.gt_reachable = None

    # For Kubernetes tasks, check if history is way too large (unsanitized clone)
    if task.startswith("K") and exp_count > 100000:
        audit.add("WARNING", "gt_reachability",
                   f"Very large history ({exp_count} commits) -- Kubernetes repo may contain "
                   "GT commits reachable via git archaeology")
        audit.gt_reachable = True


def check_event_log(audit: ExperimentAudit, verbose: bool = False) -> None:
    """
    Check 2: Suspicious Patterns in Codex Event Log.

    Parses codex_events.jsonl for suspicious commands, messages, and patterns.
    """
    events_file = audit.exp_dir / "codex_events.jsonl"
    if not events_file.exists():
        audit.add("WARNING", "event_log", "codex_events.jsonl not found")
        return

    suspicious_cmds: list[tuple[str, str, str]] = []  # (command, severity, reason)
    suspicious_msgs: list[tuple[str, str]] = []    # (message excerpt, reason)
    archaeology_cmds: list[tuple[str, str]] = []   # (command, type)
    total_cmds = 0

    try:
        with open(events_file) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                item = event.get("item", {})
                etype = event.get("type", "")
                itype = item.get("type", "")

                # Check commands
                if itype == "command_execution":
                    cmd = item.get("command", "")
                    output = item.get("aggregated_output", "") or ""
                    total_cmds += 1

                    # Classify command for suspicious patterns
                    cmd_findings = classify_command(cmd, output)
                    for severity, reason in cmd_findings:
                        suspicious_cmds.append((cmd[:200], severity, reason))

                    for pat, label in GIT_ARCHAEOLOGY_PATTERNS:
                        if pat.search(cmd):
                            archaeology_cmds.append((cmd[:200], label))

                # Check agent messages
                elif itype == "agent_message":
                    text = item.get("text", "")
                    for pat, reason in SUSPICIOUS_MSG_PATTERNS:
                        if pat.search(text):
                            suspicious_msgs.append((text[:200], reason))

    except Exception as e:
        audit.add("WARNING", "event_log", f"Error reading events: {e}")
        return

    audit.total_commands = total_cmds
    audit.suspicious_commands = len(suspicious_cmds)
    audit.git_archaeology_commands = len(archaeology_cmds)

    # Report findings -- deduplicate by (reason, cmd) to avoid double-counting
    # when item.started and item.completed both fire
    seen_cmd_findings: set[tuple[str, str]] = set()
    for cmd, severity, reason in suspicious_cmds:
        key = (reason, cmd)
        if key in seen_cmd_findings:
            continue
        seen_cmd_findings.add(key)
        audit.add(severity, "event_log",
                   f"Suspicious command ({reason})", detail=cmd)

    for msg, reason in suspicious_msgs:
        audit.add("CRITICAL", "event_log",
                   f"Suspicious message ({reason})", detail=msg)

    if archaeology_cmds:
        # Git archaeology is legitimate per project rules, but worth noting
        archaeology_types = defaultdict(int)
        for _, label in archaeology_cmds:
            archaeology_types[label] += 1
        summary = ", ".join(f"{k}: {v}" for k, v in sorted(archaeology_types.items()))
        audit.add("INFO", "event_log",
                   f"Git archaeology activity: {summary} "
                   f"({len(archaeology_cmds)} total commands)")


def check_diff_similarity(audit: ExperimentAudit) -> None:
    """
    Check 3: Diff Similarity Analysis.

    Compares the Codex-generated changes against the ground truth diff.
    """
    task = audit.task
    gt_patch = BASE_REPO / task / "eval" / "gt_diff.patch"

    if not gt_patch.exists():
        audit.add("WARNING", "diff_similarity", "gt_diff.patch not found")
        return

    # Read GT diff
    try:
        gt_text = gt_patch.read_text(errors="replace")
    except Exception as e:
        audit.add("WARNING", "diff_similarity", f"Cannot read GT diff: {e}")
        return

    gt_added, gt_removed, gt_files = parse_diff_lines(gt_text)

    # Generate experiment diff (working tree changes vs HEAD)
    rc, gen_diff = run_git(["diff", "HEAD"], cwd=audit.exp_dir, timeout=60)
    if rc != 0:
        audit.add("WARNING", "diff_similarity", f"Cannot generate experiment diff: {gen_diff[:200]}")
        return

    # Also include new untracked files (exclude known metadata files)
    rc2, untracked_out = run_git(
        ["ls-files", "--others", "--exclude-standard"],
        cwd=audit.exp_dir,
    )
    excluded_untracked = {
        "codex_events.jsonl", "codex_output.log", "codex_review.txt",
        "experiment_meta.json", "eval_report.md", "eval_events.jsonl",
        "eval_metadata.json", "COMPLETED", "TASK_PROMPT.md",
        "eval_codex.log", "eval_codex_events.jsonl",
        "eval_opencode.log", "eval_opencode_glm51.log",
        "eval_report_opencode_glm51.md",
    }
    if rc2 == 0:
        for ufile in untracked_out.strip().splitlines():
            ufile = ufile.strip()
            if ufile and ufile not in excluded_untracked and not ufile.startswith("eval_"):
                rc3, udiff = run_git(["diff", "--no-index", "/dev/null", ufile],
                                     cwd=audit.exp_dir, timeout=10)
                if udiff:
                    gen_diff += "\n" + udiff

    gen_added, gen_removed, gen_files = parse_diff_lines(gen_diff)

    # Calculate metrics
    all_gt_lines = gt_added | gt_removed
    all_gen_lines = gen_added | gen_removed

    # Filter out trivial/empty lines for meaningful comparison
    meaningful_gt = {l for l in all_gt_lines if len(l.strip()) > 3}
    meaningful_gen = {l for l in all_gen_lines if len(l.strip()) > 3}

    audit.jaccard_sim = jaccard(meaningful_gt, meaningful_gen)

    # File overlap
    if gt_files:
        overlap_files = gt_files & gen_files
        audit.file_overlap = f"{len(overlap_files)}/{len(gt_files)}"
    else:
        audit.file_overlap = "N/A"

    # Exact match ratio: what fraction of GT diff lines appear in generated diff
    if meaningful_gt:
        exact_matches = meaningful_gt & meaningful_gen
        audit.exact_match_ratio = len(exact_matches) / len(meaningful_gt)
    else:
        audit.exact_match_ratio = 0.0

    # Flag high similarity on complex tasks
    complexity = TASK_COMPLEXITY.get(task, "Unknown")

    if audit.jaccard_sim is not None and audit.jaccard_sim > 0.9:
        audit.add("WARNING", "diff_similarity",
                   f"Very high diff similarity (Jaccard={audit.jaccard_sim:.3f})",
                   detail=f"Complexity={complexity}, file_overlap={audit.file_overlap}")
    elif audit.exact_match_ratio is not None and audit.exact_match_ratio > 0.95:
        audit.add("WARNING", "diff_similarity",
                   f"Near-perfect GT line reproduction ({audit.exact_match_ratio:.1%})",
                   detail=f"Complexity={complexity}")

    # High-complexity tasks with near-perfect match are very suspicious
    if complexity == "High" and audit.jaccard_sim is not None and audit.jaccard_sim > 0.7:
        audit.add("CRITICAL", "diff_similarity",
                   f"High-complexity task with high diff similarity "
                   f"(Jaccard={audit.jaccard_sim:.3f})",
                   detail=f"Task {task} ({complexity})")
    elif complexity == "Medium" and audit.jaccard_sim is not None and audit.jaccard_sim > 0.85:
        audit.add("WARNING", "diff_similarity",
                   f"Medium-complexity task with very high diff similarity "
                   f"(Jaccard={audit.jaccard_sim:.3f})")


def check_eval_report(audit: ExperimentAudit) -> None:
    """
    Check 4: Eval Report Analysis.

    Parses scores and verdict from eval_report.md.
    """
    report_file = audit.exp_dir / "eval_report.md"
    if not report_file.exists():
        audit.add("INFO", "eval_report", "eval_report.md not found")
        return

    try:
        text = report_file.read_text(errors="replace")
    except Exception as e:
        audit.add("WARNING", "eval_report", f"Cannot read eval report: {e}")
        return

    # Parse verdict
    verdict_m = re.search(r"Verdict:\s*\*?\*?(PASS|FAIL|PARTIAL)\*?\*?", text, re.I)
    if verdict_m:
        audit.verdict = verdict_m.group(1).upper()

    # Parse scores -- look for patterns like "**A. Functional Correctness**: 5/5"
    # or "**A. Functional Correctness**: `5/5`"
    score_patterns = [
        (r"\*?\*?A\.\s*Functional\s*Correctness\*?\*?[:\s]*`?(\d)/5`?", "a"),
        (r"\*?\*?B\.\s*Completeness[^*]*\*?\*?[:\s]*`?(\d)/5`?", "b"),
        (r"\*?\*?C\.\s*Behavioral\s*Equivalence\*?\*?[:\s]*`?(\d)/5`?", "c"),
    ]
    for pattern, attr in score_patterns:
        m = re.search(pattern, text, re.I)
        if m:
            setattr(audit, f"score_{attr}", int(m.group(1)))

    # Parse HW file coverage
    hw_m = re.search(r"HW\s*File\s*Coverage[:\s]*(\d+/\d+)\s*=\s*([\d.]+)%", text)
    if hw_m:
        audit.hw_coverage = f"{hw_m.group(1)} ({hw_m.group(2)}%)"

    # Flag perfect scores
    if audit.score_a == 5 and audit.score_b == 5 and audit.score_c == 5:
        complexity = TASK_COMPLEXITY.get(audit.task, "Unknown")
        if complexity in ("High", "Medium"):
            audit.add("WARNING", "eval_report",
                       f"Perfect scores (5/5/5) on {complexity}-complexity task {audit.task}")
        else:
            audit.add("INFO", "eval_report",
                       f"Perfect scores (5/5/5) on {complexity}-complexity task")


def check_hw_file_coverage(audit: ExperimentAudit) -> None:
    """
    Check 5: Handwritten File Coverage Anomaly.

    Checks if the experiment covers an unusually high fraction of handwritten
    files, especially for high-complexity tasks.
    """
    task = audit.task
    hw_file = BASE_REPO / task / "eval" / "handwritten_files.txt"
    if not hw_file.exists():
        return

    try:
        hw_files = set()
        for line in hw_file.read_text().strip().splitlines():
            line = line.strip()
            if line:
                hw_files.add(line)
    except Exception:
        return

    if not hw_files:
        return

    # Get modified + new files in experiment
    rc, out = run_git(["diff", "HEAD", "--name-only"], cwd=audit.exp_dir, timeout=60)
    modified_files = set()
    if rc == 0:
        for f in out.strip().splitlines():
            f = f.strip()
            if f:
                modified_files.add(f)

    # Also add untracked code files
    rc2, untracked = run_git(
        ["ls-files", "--others", "--exclude-standard"],
        cwd=audit.exp_dir,
    )
    excluded_extensions = {".jsonl", ".log", ".md", ".json", ".txt", ".pid"}
    if rc2 == 0:
        for f in untracked.strip().splitlines():
            f = f.strip()
            if f and not any(f.endswith(ext) for ext in excluded_extensions):
                modified_files.add(f)

    # Compute coverage
    covered_hw = hw_files & modified_files
    coverage_pct = len(covered_hw) / len(hw_files) * 100 if hw_files else 0.0

    complexity = TASK_COMPLEXITY.get(task, "Unknown")

    if coverage_pct == 100.0 and complexity == "High":
        audit.add("CRITICAL", "hw_coverage",
                   f"100% HW file coverage ({len(covered_hw)}/{len(hw_files)}) "
                   f"on High-complexity task {task}")
    elif coverage_pct == 100.0 and complexity == "Medium":
        audit.add("WARNING", "hw_coverage",
                   f"100% HW file coverage ({len(covered_hw)}/{len(hw_files)}) "
                   f"on Medium-complexity task {task}")
    elif coverage_pct >= 90.0 and complexity == "High":
        audit.add("WARNING", "hw_coverage",
                   f"Very high HW coverage ({len(covered_hw)}/{len(hw_files)} = {coverage_pct:.1f}%) "
                   f"on High-complexity task {task}")
    elif coverage_pct == 100.0:
        audit.add("INFO", "hw_coverage",
                   f"Full HW coverage ({len(covered_hw)}/{len(hw_files)}) "
                   f"on {complexity}-complexity task")


# ---------------------------------------------------------------------------
# Main reporting
# ---------------------------------------------------------------------------

def audit_experiment(exp_info: dict, verbose: bool = False) -> ExperimentAudit:
    """Run all audit checks on one experiment."""
    audit = ExperimentAudit(
        dir_name=exp_info["dir_name"],
        task=exp_info["task"],
        prompt=exp_info["prompt"],
        date=exp_info["date"],
        exp_dir=exp_info["exp_dir"],
    )

    check_gt_reachability(audit)
    check_event_log(audit, verbose=verbose)
    check_diff_similarity(audit)
    check_eval_report(audit)
    check_hw_file_coverage(audit)

    return audit


def format_score(val: Optional[int]) -> str:
    if val is None:
        return " - "
    return str(val)


def format_float(val: Optional[float], fmt: str = ".3f") -> str:
    if val is None:
        return "  -  "
    return f"{val:{fmt}}"


def print_summary_table(audits: list[ExperimentAudit]) -> None:
    """Print a summary table of all experiments."""
    print()
    print("=" * 130)
    print("CODEX EXPERIMENT AUDIT SUMMARY")
    print("=" * 130)
    print()

    # Header
    header = (
        f"{'Experiment':<45} "
        f"{'Cmplx':>5} "
        f"{'A':>2} {'B':>2} {'C':>2} "
        f"{'Verdict':<8} "
        f"{'HW Cov':<18} "
        f"{'Jaccard':>7} "
        f"{'Exact%':>7} "
        f"{'Cmds':>5} "
        f"{'Susp':>5} "
        f"{'Flag':>6}"
    )
    print(header)
    print("-" * 130)

    for a in audits:
        flag = ""
        if a.has_critical:
            flag = "**CRIT"
        elif a.has_warning:
            flag = " *WARN"
        else:
            flag = "    ok"

        row = (
            f"{a.dir_name:<45} "
            f"{TASK_COMPLEXITY.get(a.task, '?'):>5} "
            f"{format_score(a.score_a):>2} {format_score(a.score_b):>2} {format_score(a.score_c):>2} "
            f"{a.verdict or '-':<8} "
            f"{a.hw_coverage or '-':<18} "
            f"{format_float(a.jaccard_sim):>7} "
            f"{format_float(a.exact_match_ratio, '.1%'):>7} "
            f"{a.total_commands:>5} "
            f"{a.suspicious_commands:>5} "
            f"{flag:>6}"
        )
        print(row)

    print("-" * 130)
    print()


def print_flagged_details(audits: list[ExperimentAudit], verbose: bool = False) -> None:
    """Print detailed report for flagged experiments."""
    flagged = [a for a in audits if a.is_flagged]
    if not flagged:
        print("No experiments flagged.")
        print()
        return

    print("=" * 90)
    print(f"FLAGGED EXPERIMENTS: {len(flagged)} of {len(audits)}")
    print("=" * 90)

    for a in flagged:
        print()
        print(f"--- {a.dir_name} ---")
        print(f"  Task: {a.task} ({TASK_COMPLEXITY.get(a.task, '?')} complexity)")
        print(f"  Prompt: {a.prompt}")
        print(f"  Scores: A={format_score(a.score_a)} B={format_score(a.score_b)} "
              f"C={format_score(a.score_c)}  Verdict={a.verdict or '-'}")
        print(f"  HW Coverage: {a.hw_coverage or '-'}")
        print(f"  Diff Similarity: Jaccard={format_float(a.jaccard_sim)}, "
              f"Exact={format_float(a.exact_match_ratio, '.1%')}, "
              f"File Overlap={a.file_overlap or '-'}")
        print(f"  Event Log: {a.total_commands} commands, "
              f"{a.suspicious_commands} suspicious, "
              f"{a.git_archaeology_commands} archaeology")
        print(f"  Git: {a.experiment_commit_count} commits, "
              f"GT reachable={'YES' if a.gt_reachable else 'no' if a.gt_reachable is False else '?'}")
        print()

        # Group findings by category
        for category in ("CRITICAL", "WARNING"):
            category_findings = [f for f in a.findings if f.category == category]
            if not category_findings:
                continue
            print(f"  [{category}]")
            for finding in category_findings:
                print(f"    - [{finding.check}] {finding.message}")
                if finding.detail and verbose:
                    # Indent detail lines
                    for dline in finding.detail.splitlines():
                        print(f"      | {dline}")
            print()

    print()


def print_all_findings(audits: list[ExperimentAudit]) -> None:
    """Print all findings (including INFO) for verbose mode."""
    print("=" * 90)
    print("ALL FINDINGS (verbose)")
    print("=" * 90)

    for a in audits:
        if not a.findings:
            continue
        print()
        print(f"--- {a.dir_name} ---")
        for f in a.findings:
            marker = {"CRITICAL": "!!!", "WARNING": " ! ", "INFO": "   "}.get(f.category, "   ")
            print(f"  {marker} [{f.category}] [{f.check}] {f.message}")
            if f.detail:
                for dline in f.detail.splitlines():
                    print(f"        | {dline}")
    print()


def print_statistics(audits: list[ExperimentAudit]) -> None:
    """Print aggregate statistics."""
    total = len(audits)
    critical = sum(1 for a in audits if a.has_critical)
    warnings = sum(1 for a in audits if a.has_warning and not a.has_critical)
    clean = total - critical - warnings

    passing = sum(1 for a in audits if a.verdict == "PASS")
    partial = sum(1 for a in audits if a.verdict == "PARTIAL")
    failing = sum(1 for a in audits if a.verdict == "FAIL")

    print("AGGREGATE STATISTICS")
    print("-" * 50)
    print(f"  Total experiments:    {total}")
    print(f"  CRITICAL flags:       {critical}")
    print(f"  WARNING flags:        {warnings}")
    print(f"  Clean:                {clean}")
    print()
    print(f"  Verdicts:  PASS={passing}  PARTIAL={partial}  FAIL={failing}  "
          f"missing={total - passing - partial - failing}")
    print()

    # Average similarity by task
    print("  Diff Similarity by Task:")
    task_sims: dict[str, list[float]] = defaultdict(list)
    for a in audits:
        if a.jaccard_sim is not None:
            task_sims[a.task].append(a.jaccard_sim)

    for task in sorted(task_sims.keys()):
        vals = task_sims[task]
        avg = sum(vals) / len(vals)
        mx = max(vals)
        print(f"    {task:>3} ({TASK_COMPLEXITY.get(task, '?'):>6}): "
              f"avg={avg:.3f}  max={mx:.3f}  n={len(vals)}")
    print()

    # Summary of suspicious event log findings
    total_suspicious = sum(a.suspicious_commands for a in audits)
    total_archaeology = sum(a.git_archaeology_commands for a in audits)
    print(f"  Event log totals:  {total_suspicious} suspicious commands, "
          f"{total_archaeology} git archaeology commands")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Audit Codex experiments for potential ground-truth access",
    )
    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="Audit only experiments for this task (e.g. K4)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output including INFO findings and command details",
    )
    args = parser.parse_args()

    experiments = discover_experiments(task_filter=args.task)
    if not experiments:
        print(f"No Codex experiments found"
              f"{' for task ' + args.task if args.task else ''}.")
        sys.exit(1)

    print(f"Auditing {len(experiments)} Codex experiment(s)...")
    print()

    audits: list[ExperimentAudit] = []
    for i, exp in enumerate(experiments, 1):
        label = exp["dir_name"]
        print(f"  [{i}/{len(experiments)}] {label} ...", end="", flush=True)
        audit = audit_experiment(exp, verbose=args.verbose)
        audits.append(audit)
        status = "CRITICAL" if audit.has_critical else "WARNING" if audit.has_warning else "ok"
        print(f" {status}")

    # Reports
    print_summary_table(audits)
    print_statistics(audits)
    print_flagged_details(audits, verbose=args.verbose)

    if args.verbose:
        print_all_findings(audits)

    # Exit code: 2 if any CRITICAL, 1 if any WARNING, 0 if clean
    if any(a.has_critical for a in audits):
        sys.exit(2)
    elif any(a.has_warning for a in audits):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
