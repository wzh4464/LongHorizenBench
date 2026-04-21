#!/usr/bin/env python3
"""Aggregate T-series evaluation reports into eval_scores_3evaluators.csv"""
import csv
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path("/Users/zihanwu/Public/codes/huawei-eval")
DIRS_FILE = Path("/tmp/eval_t_dirs.txt")
CSV_FILE = REPO_ROOT / "eval_scores_3evaluators.csv"

EVALUATORS = {
    "claude": "eval_report-claude.md",
    "codex": "eval_report-codex.md",
    "glm": "eval_report-opencode-glm-5.1.md",
}

SCORE_RE = re.compile(r"\*\*[ABC]\.\s+\w+[^*]*\*\*:\s*(\d)/5")
VERDICT_RE = re.compile(r"###\s*Verdict:\s*(PASS|PARTIAL|FAIL)")


def parse_report(path: Path) -> dict:
    if not path.exists():
        return {"verdict": "", "A": "", "B": "", "C": ""}
    text = path.read_text(errors="ignore")
    verdict_m = VERDICT_RE.search(text)
    scores = SCORE_RE.findall(text)
    return {
        "verdict": verdict_m.group(1) if verdict_m else "",
        "A": scores[0] if len(scores) > 0 else "",
        "B": scores[1] if len(scores) > 1 else "",
        "C": scores[2] if len(scores) > 2 else "",
    }


def main():
    dirs = [
        line.strip().rstrip("/")
        for line in DIRS_FILE.read_text().strip().splitlines()
        if line.strip()
    ]

    existing = set()
    if CSV_FILE.exists():
        with open(CSV_FILE) as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing.add(row["dir"])

    new_rows = []
    for d in dirs:
        exp = Path(d)
        dirname = exp.name
        if dirname in existing:
            continue

        meta_file = exp / "run_metadata.json"
        if not meta_file.exists():
            continue
        meta = json.loads(meta_file.read_text())
        task_id = meta.get("task_id", "")
        prompt_type = meta.get("prompt_type", "")
        config = meta.get("config", "")

        row = {
            "dir": dirname,
            "task_id": task_id,
            "prompt_type": prompt_type,
            "agent_config": config,
        }

        for prefix, filename in EVALUATORS.items():
            report = parse_report(exp / filename)
            row[f"{prefix}_verdict"] = report["verdict"]
            row[f"{prefix}_A"] = report["A"]
            row[f"{prefix}_B"] = report["B"]
            row[f"{prefix}_C"] = report["C"]

        has_any = any(row.get(f"{p}_verdict") for p in EVALUATORS)
        if has_any:
            new_rows.append(row)

    if not new_rows:
        print("No new rows to add")
        return

    fieldnames = [
        "dir", "task_id", "prompt_type", "agent_config",
        "claude_verdict", "claude_A", "claude_B", "claude_C",
        "codex_verdict", "codex_A", "codex_B", "codex_C",
        "glm_verdict", "glm_A", "glm_B", "glm_C",
    ]

    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        for row in sorted(new_rows, key=lambda r: r["dir"]):
            writer.writerow(row)

    print(f"Added {len(new_rows)} rows to {CSV_FILE}")

    # Stats
    total = len(new_rows)
    for prefix in EVALUATORS:
        verdicts = [r[f"{prefix}_verdict"] for r in new_rows if r[f"{prefix}_verdict"]]
        if verdicts:
            pass_c = sum(1 for v in verdicts if v == "PASS")
            partial_c = sum(1 for v in verdicts if v == "PARTIAL")
            fail_c = sum(1 for v in verdicts if v == "FAIL")
            print(f"  {prefix}: {len(verdicts)} reports — PASS={pass_c} PARTIAL={partial_c} FAIL={fail_c}")


if __name__ == "__main__":
    main()
