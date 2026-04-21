#!/usr/bin/env python3
"""Aggregate JSON evaluator verdicts from experiment runs into one CSV file."""

import csv
import json
from pathlib import Path
from statistics import mean


REPO_ROOT = Path("/Users/zihanwu/Public/codes/huawei-eval")
EXPERIMENT_LIST = REPO_ROOT / "scripts/eval/experiment_list.txt"
OUTPUT_CSV = REPO_ROOT / "eval_aggregate.csv"

EVALUATORS = ("claude", "codex", "opencode")
RUN_INFO_FIELDS = ("run_id", "task_id", "prompt_type", "agent_name")
FIELDNAMES = (
    "run_id",
    "task_id",
    "prompt_type",
    "agent_name",
    "claude_score",
    "codex_score",
    "opencode_score",
    "mean_score",
    "claude_rationale",
    "codex_rationale",
    "opencode_rationale",
)


def read_experiment_dirs(path):
    """Read experiment directories, skipping blank lines and comments."""
    dirs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            dirs.append(Path(stripped))
    return dirs


def read_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def read_run_info(experiment_dir):
    run_info_path = experiment_dir / "run_info.json"
    if run_info_path.exists():
        data = read_json(run_info_path)
        return {field: as_text(data.get(field, "")) for field in RUN_INFO_FIELDS}

    metadata_path = experiment_dir / "run_metadata.json"
    if metadata_path.exists():
        data = read_json(metadata_path)
        return {
            "run_id": as_text(data.get("run_id", experiment_dir.name)),
            "task_id": as_text(data.get("task_id", "")),
            "prompt_type": as_text(data.get("prompt_type", "")),
            "agent_name": as_text(
                data.get("agent_name", data.get("agent", data.get("config", "")))
            ),
        }

    data = {"run_id": experiment_dir.name}
    return {field: as_text(data.get(field, "")) for field in RUN_INFO_FIELDS}


def read_verdict(experiment_dir, evaluator):
    verdict_path = experiment_dir / f"eval_{evaluator}" / "verdict.json"
    if not verdict_path.exists():
        return "", ""

    data = read_json(verdict_path)
    return as_text(data.get("score", "")), as_text(data.get("rationale", ""))


def as_text(value):
    if value is None:
        return ""
    return str(value)


def parse_score(value):
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def format_score(value):
    return f"{value:.6g}"


def build_row(experiment_dir):
    row = read_run_info(experiment_dir)
    scores = []

    for evaluator in EVALUATORS:
        score, rationale = read_verdict(experiment_dir, evaluator)
        row[f"{evaluator}_score"] = score
        row[f"{evaluator}_rationale"] = rationale

        numeric_score = parse_score(score)
        if numeric_score is not None:
            scores.append(numeric_score)

    row["mean_score"] = format_score(mean(scores)) if scores else ""
    return row


def write_csv(rows, path):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows):
    counts = {}
    scores_by_agent = {}

    for row in rows:
        agent_name = row["agent_name"]
        counts[agent_name] = counts.get(agent_name, 0) + 1

        score = parse_score(row["mean_score"])
        if score is not None:
            scores_by_agent.setdefault(agent_name, []).append(score)

    print(f"Total rows: {len(rows)}")
    print("Per-agent count:")
    for agent_name in sorted(counts):
        print(f"  {agent_name}: {counts[agent_name]}")

    print("Mean score per agent:")
    for agent_name in sorted(counts):
        agent_scores = scores_by_agent.get(agent_name, [])
        score_text = format_score(mean(agent_scores)) if agent_scores else ""
        print(f"  {agent_name}: {score_text}")


def main():
    experiment_dirs = read_experiment_dirs(EXPERIMENT_LIST)
    rows = [build_row(experiment_dir) for experiment_dir in experiment_dirs]
    write_csv(rows, OUTPUT_CSV)
    print_summary(rows)


if __name__ == "__main__":
    main()
