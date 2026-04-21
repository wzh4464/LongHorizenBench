#!/usr/bin/env python3
"""Aggregate four-evaluator markdown reports into a CSV under scripts/eval."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DIRS_FILE = REPO_ROOT / "scripts/eval/all_dirs.txt"
OUT_CSV = REPO_ROOT / "scripts/eval/eval_scores_4evaluators.csv"

EVALUATORS = (
    ("claude", "eval_report-claude.md"),
    ("codex", "eval_report-codex.md"),
    ("opencode", "eval_report-opencode-glm-5.1.md"),
    ("cursor", "eval_report-cursor.md"),
)

VERDICT_RE = re.compile(
    r"(?im)^\s*#{1,6}\s*verdict\s*[:\-]?\s*\**\s*(PASS|PARTIAL|FAIL)\b"
)
SCORE_RE = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?\**\s*([ABC])\.\s*[^:\n*]+\**\s*:\s*([0-5](?:\.\d+)?)\s*/?\s*5?"
)


def read_dirs(path: Path) -> list[Path]:
    return [
        Path(line.strip().rstrip("/"))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def read_metadata(experiment_dir: Path) -> dict:
    for filename in ("run_metadata.json", "run_info.json"):
        path = experiment_dir / filename
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def parse_report(path: Path) -> dict[str, str]:
    if not path.exists():
        return {"verdict": "", "A": "", "B": "", "C": ""}

    text = path.read_text(encoding="utf-8", errors="replace")
    verdict_match = VERDICT_RE.search(text)
    scores = {label: "" for label in "ABC"}
    for label, score in SCORE_RE.findall(text):
        scores[label.upper()] = score

    return {
        "verdict": verdict_match.group(1).upper() if verdict_match else "",
        **scores,
    }


def build_row(experiment_dir: Path) -> dict[str, str]:
    metadata = read_metadata(experiment_dir)
    row = {
        "experiment": experiment_dir.name,
        "task_id": str(metadata.get("task_id", "")),
        "prompt_type": str(metadata.get("prompt_type", "")),
        "agent_config": str(
            metadata.get("config", metadata.get("agent", metadata.get("agent_name", "")))
        ),
        "run_date": str(metadata.get("run_date", "")),
    }

    for evaluator, filename in EVALUATORS:
        parsed = parse_report(experiment_dir / filename)
        row[f"{evaluator}_verdict"] = parsed["verdict"]
        row[f"{evaluator}_A"] = parsed["A"]
        row[f"{evaluator}_B"] = parsed["B"]
        row[f"{evaluator}_C"] = parsed["C"]

    return row


def fieldnames() -> list[str]:
    fields = ["experiment", "task_id", "prompt_type", "agent_config", "run_date"]
    for evaluator, _ in EVALUATORS:
        fields.extend(
            [
                f"{evaluator}_verdict",
                f"{evaluator}_A",
                f"{evaluator}_B",
                f"{evaluator}_C",
            ]
        )
    return fields


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames())
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows: list[dict[str, str]]) -> None:
    print(f"Wrote {len(rows)} rows to {OUT_CSV}")
    for evaluator, _ in EVALUATORS:
        counts = Counter(
            row[f"{evaluator}_verdict"]
            for row in rows
            if row.get(f"{evaluator}_verdict")
        )
        print(f"{evaluator}: {dict(counts)}")


def main() -> None:
    experiment_dirs = [path for path in read_dirs(DIRS_FILE) if path.is_dir()]
    rows = [build_row(path) for path in experiment_dirs]
    write_csv(rows, OUT_CSV)
    print_summary(rows)


if __name__ == "__main__":
    main()
