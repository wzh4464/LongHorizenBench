#!/usr/bin/env python3
"""Aggregate T-series eval reports into eval_scores_3evaluators.csv format."""
import csv
import os
import re
import sys
from pathlib import Path

ROOT = Path("/Users/zihanwu/Public/codes/huawei-eval")
EXP = ROOT / "experiment"
OUT = ROOT / "eval_scores_3evaluators_full.csv"

AGENT_CONFIGS = {
    "claude-opus-max": "claude-opus-max",
    "codex-gpt-5_4": "codex-gpt-5_4",
    "cursor-composer2": "cursor-composer2",
    "opencode-glm51": "opencode-glm51",
}

EVALUATORS = {
    "claude": "eval_report-claude.md",
    "codex":  "eval_report-codex.md",
    "glm":    "eval_report-opencode-glm-5.1.md",
}

VERDICT_RE = re.compile(r"verdict[^\n:]*[:\*\s]+\*?\*?\s*(PASS|PARTIAL|FAIL)", re.IGNORECASE)

SCORE_RE = re.compile(
    r"\*\*?([ABC])\.\s+[^*:]+\*\*?\s*[:\-–]\s*(\d+)(?:\s*/\s*5)?",
)

# fallback patterns
SCORE_ALT = re.compile(r"^[-•\s]*\*?\*?([ABC])\.[^:]*[:\-–]\s*\*?\*?(\d+)", re.MULTILINE)
TABLE_SCORE = re.compile(r"\|\s*([ABC])\s*\|.*?\|\s*(\d+)\s*/", re.DOTALL)

def extract(path):
    if not path.exists() if False else not os.path.exists(path):
        return None
    text = open(path, encoding="utf-8", errors="replace").read()

    verdict = None
    m = re.search(r"(?:^|\n)\s*#+\s*verdict[^\n]*\n+\s*\**\s*(PASS|PARTIAL|FAIL)",
                  text, re.IGNORECASE)
    if not m:
        m = re.search(r"verdict[^\n]*[:\-]\s*\**\s*(PASS|PARTIAL|FAIL)\**", text, re.IGNORECASE)
    if not m:
        m = re.search(r"\*\*Verdict\*\*[^A-Z]*(PASS|PARTIAL|FAIL)", text, re.IGNORECASE)
    if m:
        verdict = m.group(1).upper()

    scores = {}
    # Primary: "A. Functional Correctness: X/5" or "A. ... : X"
    for m in re.finditer(
        r"(?:^|\n)\s*[-*]?\s*\**\s*([ABC])\.\s*[^:\n]*?:\s*\**\s*(\d+)",
        text,
    ):
        letter = m.group(1).upper()
        val = int(m.group(2))
        if letter not in scores:
            scores[letter] = val

    # Fallback forms: "- A: 3" or "**A (Functional)**: 3/5"
    if len(scores) < 3:
        for m in re.finditer(
            r"(?:^|\n)\s*[\*\-]?\s*\*?\*?([ABC])\*?\*?\s*[:=]\s*\**\s*(\d+)", text
        ):
            letter = m.group(1).upper()
            val = int(m.group(2))
            if letter not in scores:
                scores[letter] = val

    return verdict, scores.get("A"), scores.get("B"), scores.get("C")


def aggregate():
    experiment_dir = os.path.join(REPO, "experiment")
    rows = []

    # Pattern: T{NN}-{agent_config}-{prompt}-{date}
    for entry in sorted(os.listdir(experiment_dir)):
        if not entry.startswith("T"):
            continue
        full = os.path.join(experiment_dir, entry)
        if not os.path.isdir(full):
            continue

        m = re.match(
            r"^(T\d{2})-(claude-opus-max|codex-gpt-5_4|cursor-composer2|opencode-glm51)-(short|long)-\d+",
            entry,
        )
        if not m:
            continue
        task_id, agent, prompt = m.group(1), m.group(2), m.group(3)

        row = {
            "dir": entry,
            "task_id": task_id,
            "prompt_type": prompt,
            "agent_config": agent,
        }
        # Extract each evaluator's verdict + scores
        for ev, fname in EVALUATORS.items():
            path = full / fname
            info = parse(str(path)) if path.is_file() else None
            if info is None:
                row[f"{ev}_verdict"] = ""
                row[f"{ev}_A"] = row[f"{ev}_B"] = row[f"{ev}_C"] = ""
            else:
                verdict, a, b, c = info
                row[f"{ev}_verdict"] = verdict or ""
                row[f"{ev}_A"] = a if a is not None else ""
                row[f"{ev}_B"] = b if b is not None else ""
                row[f"{ev}_C"] = c if c is not None else ""
        rows.append(row)

    # write
    fieldnames = [
        "dir", "task_id", "prompt_type", "agent_config",
        "claude_verdict", "claude_A", "claude_B", "claude_C",
        "codex_verdict", "codex_A", "codex_B", "codex_C",
        "glm_verdict", "glm_A", "glm_B", "glm_C",
    ]
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {OUT}")

if __name__ == "__main__":
    main()
