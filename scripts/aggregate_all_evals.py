#!/usr/bin/env python3
"""Aggregate v2 evaluator reports into long and wide CSVs.

The script preserves the existing three-evaluator C/M/K CSV as the baseline
where available, then extends it with the cursor evaluator and T-series rows
discovered under experiment/.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover - exercised in lightweight sandboxes.
    pd = None


VALID_VERDICTS = {"PASS", "PARTIAL", "FAIL"}
EVALUATORS = ("claude", "codex", "glm", "cursor")
THREE_EVALUATORS = ("claude", "codex", "glm")

REPORT_FILES = {
    "claude": ("eval_report-claude.md",),
    "codex": ("eval_report-codex.md",),
    "glm": ("eval_report-glm.md", "eval_report-opencode-glm-5.1.md"),
    "cursor": ("eval_report-cursor.md",),
}

TASK_RE = re.compile(r"^(?P<task>C[1-5]|M[1-3]|K[1-4]|T\d{2})(?:[-_])(?P<body>.+)$")
BODY_RE = re.compile(r"^(?P<agent>.+?)(?:[-_])(?P<prompt>short|long)(?:[-_].*)?$")

VERDICT_PATTERNS = (
    re.compile(
        r"(?im)^\s*#{1,6}\s*verdict\s*[:\-]?\s*\**\s*(PASS|PARTIAL|FAIL)\b"
    ),
    re.compile(
        r"(?im)^\s*(?:[-*]\s*)?\**\s*verdict\s*\**\s*[:\-]?\s*\**\s*(PASS|PARTIAL|FAIL)\b"
    ),
    re.compile(r"(?is)\bverdict\b.{0,120}?\b(PASS|PARTIAL|FAIL)\b"),
    re.compile(r"(?is)(?:判定|结论).{0,80}?\b(PASS|PARTIAL|FAIL)\b"),
)

SCORE_PATTERNS = (
    re.compile(
        r"(?im)^\s*(?:#{1,6}\s*)?(?:[-*+]\s*)?\**\s*(?P<label>[ABC])\.\s*[^:\n|]*?\**\s*[:=\-]\s*\**\s*(?P<score>[0-5](?:\.\d+)?)"
    ),
    re.compile(
        r"(?im)^\s*(?:#{1,6}\s*)?(?:[-*+]\s*)?\**\s*(?P<label>[ABC])\s*(?:\([^)]*\))?\**\s*[:=\-]\s*\**\s*(?P<score>[0-5](?:\.\d+)?)"
    ),
    re.compile(
        r"(?im)^\s*\|\s*\**\s*(?P<label>[ABC])(?:\.|\s|\*)[^|\n]*\|\s*\**\s*(?P<score>[0-5](?:\.\d+)?)\s*(?:/5)?\s*\**\s*\|"
    ),
    re.compile(
        r"(?im)^\s*(?:#{1,6}\s*)?[^:\n|]{0,80}\((?P<label>[ABC])\)\s*[:=\-]\s*\**\s*(?P<score>[0-5](?:\.\d+)?)"
    ),
)


@dataclass(frozen=True)
class RunMeta:
    dir_name: str
    path: Path
    task: str
    agent: str
    prompt_variant: str
    run_date: str = ""


@dataclass(frozen=True)
class ParsedReport:
    verdict: str
    score_a: float
    score_b: float
    score_c: float
    mean_score: float
    report_path: str
    source: str


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def normalize_agent(agent: str) -> str:
    normalized = agent.strip()
    aliases = {
        "claude-opus-4-7": "claude-opus-max",
        "claude-opus-4.7": "claude-opus-max",
        "claude": "claude-opus-max",
        "codex": "codex-gpt-5_4",
        "cursor": "cursor-composer2",
        "opencode": "opencode-glm51",
        "glm": "opencode-glm51",
    }
    return aliases.get(normalized, normalized)


def normalize_prompt(prompt: str) -> str:
    value = prompt.strip().lower()
    return value if value in {"short", "long"} else prompt.strip()


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning("could not read metadata %s: %s", path, exc)
        return {}


def parse_run_dir(path: Path) -> RunMeta | None:
    task_m = TASK_RE.match(path.name)
    if not task_m:
        return None

    metadata = read_json(path / "run_metadata.json") if (path / "run_metadata.json").exists() else {}

    task = str(metadata.get("task_id") or "").strip()
    agent = str(metadata.get("config") or metadata.get("agent") or "").strip()
    prompt = str(metadata.get("prompt_type") or "").strip()
    run_date = str(metadata.get("run_date") or "").strip()

    if not (task and agent and prompt):
        task = task or task_m.group("task")
        body_m = BODY_RE.match(task_m.group("body"))
        if not body_m:
            logging.warning("could not parse experiment directory name: %s", path.name)
            return None
        agent = agent or body_m.group("agent")
        prompt = prompt or body_m.group("prompt")

    if not re.fullmatch(r"C[1-5]|M[1-3]|K[1-4]|T\d{2}", task):
        return None
    prompt = normalize_prompt(prompt)
    if prompt not in {"short", "long"}:
        logging.warning("skipping %s with unknown prompt %r", path.name, prompt)
        return None

    return RunMeta(
        dir_name=path.name,
        path=path,
        task=task,
        agent=normalize_agent(agent),
        prompt_variant=prompt,
        run_date=run_date,
    )


def discover_runs(experiment_dir: Path) -> list[RunMeta]:
    runs: list[RunMeta] = []
    for path in sorted(experiment_dir.iterdir(), key=lambda p: p.name):
        if not path.is_dir():
            continue
        run = parse_run_dir(path)
        if run is not None:
            runs.append(run)
    return runs


def extract_verdict(text: str) -> str | None:
    for pattern in VERDICT_PATTERNS:
        match = pattern.search(text)
        if match:
            verdict = match.group(1).upper()
            if verdict in VALID_VERDICTS:
                return verdict
    return None


def extract_scores(text: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    for pattern in SCORE_PATTERNS:
        for match in pattern.finditer(text):
            label = match.group("label").upper()
            if label in scores:
                continue
            try:
                score = float(match.group("score"))
            except ValueError:
                continue
            if 0 <= score <= 5:
                scores[label] = score
        if all(label in scores for label in "ABC"):
            break
    return scores


def choose_report_path(run_dir: Path, evaluator: str) -> Path | None:
    candidates = list(REPORT_FILES[evaluator])
    if evaluator == "cursor" and not (run_dir / "eval_report-cursor.md").exists():
        candidates.append("eval_report-opencode-glm-5.1.md")

    for filename in candidates:
        path = run_dir / filename
        if path.exists():
            return path
    return None


def parse_report(run_dir: Path, evaluator: str) -> ParsedReport | None:
    report_path = choose_report_path(run_dir, evaluator)
    if report_path is None:
        logging.warning("missing %s evaluator report in %s", evaluator, run_dir)
        return None

    try:
        text = report_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logging.warning("could not read %s: %s", report_path, exc)
        return None

    verdict = extract_verdict(text)
    scores = extract_scores(text)
    if verdict is None or not all(label in scores for label in "ABC"):
        logging.warning(
            "malformed %s report %s: verdict=%s scores=%s",
            evaluator,
            report_path,
            verdict,
            sorted(scores),
        )
        return None

    score_a = scores["A"]
    score_b = scores["B"]
    score_c = scores["C"]
    return ParsedReport(
        verdict=verdict,
        score_a=score_a,
        score_b=score_b,
        score_c=score_c,
        mean_score=round((score_a + score_b + score_c) / 3.0, 4),
        report_path=str(report_path),
        source="report",
    )


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []

    if pd is not None:
        frame = pd.read_csv(path, dtype=str).fillna("")
        return frame.to_dict("records")

    logging.warning("pandas is not installed; using stdlib csv fallback")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def first_value(row: dict, names: Iterable[str]) -> str:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return str(value)
    return ""


def parse_score(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score if 0 <= score <= 5 else None


def report_from_existing(row: dict, evaluator: str) -> ParsedReport | None:
    verdict = first_value(row, [f"{evaluator}_verdict"]).upper()
    if verdict not in VALID_VERDICTS:
        return None

    score_a = parse_score(first_value(row, [f"{evaluator}_A", f"{evaluator}_a"]))
    score_b = parse_score(first_value(row, [f"{evaluator}_B", f"{evaluator}_b"]))
    score_c = parse_score(first_value(row, [f"{evaluator}_C", f"{evaluator}_c"]))
    if score_a is None or score_b is None or score_c is None:
        return None

    return ParsedReport(
        verdict=verdict,
        score_a=score_a,
        score_b=score_b,
        score_c=score_c,
        mean_score=round((score_a + score_b + score_c) / 3.0, 4),
        report_path="",
        source="existing_csv",
    )


def existing_rows_by_dir(existing_csv: Path) -> dict[str, dict]:
    rows = read_csv_rows(existing_csv)
    by_dir = {}
    for row in rows:
        dir_name = first_value(row, ["dir"])
        if dir_name:
            by_dir[dir_name] = row
    return by_dir


def read_text_lines(path: Path) -> list[str] | None:
    try:
        return [
            line.strip()
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()
        ]
    except OSError:
        return None


def tracked_file_lines(repo_root: Path, relative_path: str) -> list[str] | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"HEAD:{relative_path}"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def changed_files_from_patch(path: Path) -> list[str] | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    files: set[str] = set()
    for match in re.finditer(r"(?m)^diff --git a/(.*?) b/(.*?)$", text):
        left, right = match.groups()
        files.add(right if right != "/dev/null" else left)
    for match in re.finditer(r"(?m)^\+\+\+ b/(.*?)$", text):
        files.add(match.group(1))
    return sorted(files) if files else None


def gt_file_count(repo_root: Path, task: str) -> int | None:
    eval_dir = repo_root / "base_repo" / task / "eval"
    candidates = [
        eval_dir / "gt_files.txt",
        eval_dir / "handwritten_files.txt",
    ]
    for candidate in candidates:
        lines = read_text_lines(candidate)
        if lines:
            return len(lines)

    tracked = tracked_file_lines(repo_root, f"base_repo/{task}/eval/gt_files.txt")
    if tracked:
        return len(tracked)

    patch_files = changed_files_from_patch(eval_dir / "gt_diff.patch")
    if patch_files:
        return len(patch_files)

    logging.warning("could not derive complexity for task %s", task)
    return None


def complexity_for_count(count: int | None) -> str:
    if count is None:
        return "unknown"
    if count <= 3:
        return "easy"
    if count <= 10:
        return "medium"
    return "hard"


def format_score(score: float | None) -> str:
    if score is None:
        return ""
    if float(score).is_integer():
        return str(int(score))
    return f"{score:.4f}".rstrip("0").rstrip(".")


def add_report_fields(row: dict, evaluator: str, report: ParsedReport | None) -> None:
    prefix = evaluator
    if report is None:
        row[f"{prefix}_verdict"] = ""
        row[f"{prefix}_A"] = ""
        row[f"{prefix}_B"] = ""
        row[f"{prefix}_C"] = ""
        row[f"{prefix}_mean_score"] = ""
        row[f"{prefix}_source"] = ""
        row[f"{prefix}_report_path"] = ""
        return

    row[f"{prefix}_verdict"] = report.verdict
    row[f"{prefix}_A"] = format_score(report.score_a)
    row[f"{prefix}_B"] = format_score(report.score_b)
    row[f"{prefix}_C"] = format_score(report.score_c)
    row[f"{prefix}_mean_score"] = format_score(report.mean_score)
    row[f"{prefix}_source"] = report.source
    row[f"{prefix}_report_path"] = report.report_path


def aggregate(repo_root: Path, experiment_dir: Path, existing_csv: Path) -> tuple[list[dict], list[dict]]:
    existing = existing_rows_by_dir(existing_csv)
    runs = discover_runs(experiment_dir)
    complexity_cache: dict[str, str] = {}

    wide_rows: list[dict] = []
    long_rows: list[dict] = []

    for run in runs:
        if run.task not in complexity_cache:
            complexity_cache[run.task] = complexity_for_count(gt_file_count(repo_root, run.task))
        complexity = complexity_cache[run.task]

        wide_row = {
            "dir": run.dir_name,
            "task": run.task,
            "agent": run.agent,
            "prompt_variant": run.prompt_variant,
            "complexity": complexity,
            "run_date": run.run_date,
        }
        existing_row = existing.get(run.dir_name, {})

        evaluator_reports: dict[str, ParsedReport | None] = {}
        for evaluator in EVALUATORS:
            report: ParsedReport | None = None
            if evaluator in THREE_EVALUATORS and existing_row:
                report = report_from_existing(existing_row, evaluator)
            if report is None:
                report = parse_report(run.path, evaluator)
            evaluator_reports[evaluator] = report
            add_report_fields(wide_row, evaluator, report)

        valid_means = [
            report.mean_score for report in evaluator_reports.values() if report is not None
        ]
        pass_votes = [
            report.verdict for report in evaluator_reports.values() if report is not None
        ].count("PASS")
        wide_row["evaluator_count"] = len(valid_means)
        wide_row["run_mean_score"] = format_score(
            round(sum(valid_means) / len(valid_means), 4) if valid_means else None
        )
        wide_row["pass_votes"] = pass_votes
        wide_rows.append(wide_row)

        for evaluator, report in evaluator_reports.items():
            if report is None:
                continue
            long_rows.append(
                {
                    "task": run.task,
                    "agent": run.agent,
                    "prompt_variant": run.prompt_variant,
                    "complexity": complexity,
                    "evaluator": evaluator,
                    "verdict": report.verdict,
                    "score_a": format_score(report.score_a),
                    "score_b": format_score(report.score_b),
                    "score_c": format_score(report.score_c),
                    "mean_score": format_score(report.mean_score),
                    "dir": run.dir_name,
                    "run_date": run.run_date,
                    "report_path": report.report_path,
                    "source": report.source,
                }
            )

    return long_rows, wide_rows


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if pd is not None:
        frame = pd.DataFrame(rows)
        for field in fieldnames:
            if field not in frame.columns:
                frame[field] = ""
        frame = frame[fieldnames]
        frame.to_csv(path, index=False)
        return

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def configure_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers = [
        logging.FileHandler(log_path, mode="w", encoding="utf-8"),
        logging.StreamHandler(),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        handlers=handlers,
    )


def main() -> int:
    repo_root = repo_root_from_script()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=repo_root)
    parser.add_argument("--experiment-dir", type=Path, default=repo_root / "experiment")
    parser.add_argument("--existing-csv", type=Path, default=repo_root / "eval_scores_3evaluators.csv")
    parser.add_argument("--out-dir", type=Path, default=repo_root / "reports")
    parser.add_argument("--long-csv", type=Path, default=None)
    parser.add_argument("--wide-csv", type=Path, default=None)
    parser.add_argument("--log", type=Path, default=None)
    args = parser.parse_args()

    out_dir = args.out_dir
    long_csv = args.long_csv or out_dir / "eval_scores_v2_long.csv"
    wide_csv = args.wide_csv or out_dir / "eval_scores_v2_wide.csv"
    log_path = args.log or out_dir / "aggregate_all_evals.log"

    configure_logging(log_path)
    if pd is None:
        logging.warning("pandas is not installed; using stdlib csv fallback")

    long_rows, wide_rows = aggregate(args.repo_root, args.experiment_dir, args.existing_csv)

    long_fields = [
        "task",
        "agent",
        "prompt_variant",
        "complexity",
        "evaluator",
        "verdict",
        "score_a",
        "score_b",
        "score_c",
        "mean_score",
        "dir",
        "run_date",
        "report_path",
        "source",
    ]
    wide_fields = [
        "dir",
        "task",
        "agent",
        "prompt_variant",
        "complexity",
        "run_date",
    ]
    for evaluator in EVALUATORS:
        wide_fields.extend(
            [
                f"{evaluator}_verdict",
                f"{evaluator}_A",
                f"{evaluator}_B",
                f"{evaluator}_C",
                f"{evaluator}_mean_score",
                f"{evaluator}_source",
                f"{evaluator}_report_path",
            ]
        )
    wide_fields.extend(["evaluator_count", "run_mean_score", "pass_votes"])

    write_csv(long_csv, long_rows, long_fields)
    write_csv(wide_csv, wide_rows, wide_fields)

    task_count = len({row["task"] for row in wide_rows})
    agent_count = len({row["agent"] for row in wide_rows})
    prompt_count = len({row["prompt_variant"] for row in wide_rows})
    print(f"Wrote {len(long_rows)} evaluator rows to {long_csv}")
    print(f"Wrote {len(wide_rows)} run rows to {wide_csv}")
    print(f"Coverage: {task_count} tasks x {agent_count} agents x {prompt_count} prompts")
    print(f"Log: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
