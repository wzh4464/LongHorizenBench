#!/usr/bin/env python3
"""Print markdown statistics for the v2 consolidated evaluation CSV."""

from __future__ import annotations

import argparse
import csv
import itertools
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

try:
    import pandas as pd  # type: ignore
except ImportError:  # pragma: no cover - exercised in lightweight sandboxes.
    pd = None


VALID_VERDICTS = {"PASS", "PARTIAL", "FAIL"}
VERDICT_ORDER = ("PASS", "PARTIAL", "FAIL")
PROMPT_ORDER = {"short": 0, "long": 1}
COMPLEXITY_ORDER = {"easy": 0, "medium": 1, "hard": 2, "unknown": 3}


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def load_rows(path: Path) -> list[dict]:
    if pd is not None:
        frame = pd.read_csv(path, dtype=str).fillna("")
        return frame.to_dict("records")

    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def valid_rows(rows: Iterable[dict]) -> list[dict]:
    cleaned = []
    for row in rows:
        verdict = str(row.get("verdict", "")).upper()
        score = as_float(row.get("mean_score"))
        if verdict not in VALID_VERDICTS or score is None:
            continue
        item = dict(row)
        item["verdict"] = verdict
        item["_mean_score"] = score
        item["_run_key"] = (
            item.get("dir")
            or f"{item.get('task')}|{item.get('agent')}|{item.get('prompt_variant')}"
        )
        cleaned.append(item)
    return cleaned


def pct(value: float | None) -> str:
    if value is None or math.isnan(value):
        return ""
    return f"{value * 100:.1f}%"


def fmt(value: float | None, digits: int = 2) -> str:
    if value is None or math.isnan(value):
        return ""
    return f"{value:.{digits}f}"


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    out = []
    out.append("| " + " | ".join(headers) + " |")
    out.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        out.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(out)


def grouped(rows: Iterable[dict], keys: tuple[str, ...]) -> dict[tuple, list[dict]]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(key, "") for key in keys)].append(row)
    return groups


def summarize_group(rows: list[dict]) -> dict:
    verdicts = [row["verdict"] for row in rows]
    scores = [row["_mean_score"] for row in rows]
    runs = {row["_run_key"] for row in rows}
    total = len(rows)
    return {
        "runs": len(runs),
        "judgments": total,
        "pass_rate": verdicts.count("PASS") / total if total else None,
        "partial_rate": verdicts.count("PARTIAL") / total if total else None,
        "fail_rate": verdicts.count("FAIL") / total if total else None,
        "mean_score": sum(scores) / len(scores) if scores else None,
    }


def pass_rate_by_agent_prompt(rows: list[dict]) -> list[dict]:
    table = []
    for (agent, prompt), items in grouped(rows, ("agent", "prompt_variant")).items():
        summary = summarize_group(items)
        table.append({"agent": agent, "prompt": prompt, **summary})
    table.sort(key=lambda r: (r["agent"], PROMPT_ORDER.get(r["prompt"], 99)))
    return table


def mean_score_by_agent(rows: list[dict]) -> list[dict]:
    table = []
    for (agent,), items in grouped(rows, ("agent",)).items():
        summary = summarize_group(items)
        table.append({"agent": agent, **summary})
    table.sort(key=lambda r: (-r["mean_score"], -r["pass_rate"], r["agent"]))
    for index, row in enumerate(table, start=1):
        row["rank"] = index
    return table


def complexity_breakdown(rows: list[dict]) -> list[dict]:
    table = []
    for (complexity, agent), items in grouped(rows, ("complexity", "agent")).items():
        summary = summarize_group(items)
        table.append({"complexity": complexity, "agent": agent, **summary})
    table.sort(
        key=lambda r: (
            COMPLEXITY_ORDER.get(r["complexity"], 99),
            r["agent"],
        )
    )
    return table


def verdict_matrix(rows: list[dict]) -> dict[str, dict[str, str]]:
    by_run: dict[str, dict[str, str]] = defaultdict(dict)
    for row in rows:
        by_run[row["_run_key"]][row["evaluator"]] = row["verdict"]
    return by_run


def cohen_kappa(pairs: list[tuple[str, str]]) -> tuple[float | None, float | None]:
    if not pairs:
        return None, None
    total = len(pairs)
    observed = sum(1 for left, right in pairs if left == right) / total
    left_counts = Counter(left for left, _ in pairs)
    right_counts = Counter(right for _, right in pairs)
    expected = sum((left_counts[label] / total) * (right_counts[label] / total) for label in VERDICT_ORDER)
    if math.isclose(1.0 - expected, 0.0):
        return (1.0 if math.isclose(observed, 1.0) else 0.0), observed
    return (observed - expected) / (1.0 - expected), observed


def evaluator_agreement(rows: list[dict]) -> list[dict]:
    matrix = verdict_matrix(rows)
    evaluators = sorted({row["evaluator"] for row in rows})
    table = []
    for left, right in itertools.combinations(evaluators, 2):
        pairs = [
            (verdicts[left], verdicts[right])
            for verdicts in matrix.values()
            if left in verdicts and right in verdicts
        ]
        kappa, observed = cohen_kappa(pairs)
        table.append(
            {
                "pair": f"{left}/{right}",
                "n": len(pairs),
                "raw_agreement": observed,
                "kappa": kappa,
            }
        )
    table.sort(key=lambda r: r["pair"])
    return table


def kappa_label(kappa: float | None) -> str:
    if kappa is None:
        return "unknown"
    if kappa < 0:
        return "poor"
    if kappa < 0.20:
        return "slight"
    if kappa < 0.40:
        return "fair"
    if kappa < 0.60:
        return "moderate"
    if kappa < 0.80:
        return "substantial"
    return "near-perfect"


def overall_by_complexity(rows: list[dict]) -> list[dict]:
    table = []
    for (complexity,), items in grouped(rows, ("complexity",)).items():
        summary = summarize_group(items)
        table.append({"complexity": complexity, **summary})
    table.sort(key=lambda r: COMPLEXITY_ORDER.get(r["complexity"], 99))
    return table


def prompt_summary(rows: list[dict]) -> list[dict]:
    table = []
    for (prompt,), items in grouped(rows, ("prompt_variant",)).items():
        summary = summarize_group(items)
        table.append({"prompt": prompt, **summary})
    table.sort(key=lambda r: PROMPT_ORDER.get(r["prompt"], 99))
    return table


def build_markdown(rows: list[dict], source_csv: Path) -> str:
    agent_prompt = pass_rate_by_agent_prompt(rows)
    agent_means = mean_score_by_agent(rows)
    agreement = evaluator_agreement(rows)
    by_complexity = complexity_breakdown(rows)
    complexity_overall = overall_by_complexity(rows)
    prompts = prompt_summary(rows)

    unique_runs = {row["_run_key"] for row in rows}
    unique_tasks = {row.get("task", "") for row in rows}
    unique_agents = {row.get("agent", "") for row in rows}
    unique_evaluators = {row.get("evaluator", "") for row in rows}

    kappas = [row["kappa"] for row in agreement if row["kappa"] is not None]
    raw_agreements = [row["raw_agreement"] for row in agreement if row["raw_agreement"] is not None]
    mean_kappa = sum(kappas) / len(kappas) if kappas else None
    mean_raw = sum(raw_agreements) / len(raw_agreements) if raw_agreements else None

    top_agent = agent_means[0] if agent_means else None
    lowest_complexity = min(
        complexity_overall,
        key=lambda r: (r["pass_rate"] if r["pass_rate"] is not None else 1.0, r["mean_score"] or 5.0),
        default=None,
    )
    best_prompt = max(
        prompts,
        key=lambda r: (r["mean_score"] if r["mean_score"] is not None else -1.0, r["pass_rate"] or 0.0),
        default=None,
    )

    lines = [
        "# V2 Evaluation Summary",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Source CSV: `{source_csv}`",
        "",
        (
            f"Coverage: {len(unique_tasks)} tasks, {len(unique_agents)} agent configs, "
            f"{len(unique_runs)} runs, {len(unique_evaluators)} evaluators, "
            f"{len(rows)} evaluator judgments."
        ),
        "",
        "## Short Summary",
    ]

    if top_agent:
        ranking = ", ".join(
            f"{row['rank']}. {row['agent']} ({fmt(row['mean_score'])})" for row in agent_means
        )
        lines.append(f"- Agent ranking by mean score: {ranking}.")
    lines.append(
        f"- Evaluator agreement: mean pairwise kappa {fmt(mean_kappa, 3)} "
        f"({kappa_label(mean_kappa)}), raw agreement {pct(mean_raw)}."
    )
    if lowest_complexity:
        lines.append(
            f"- Weakest complexity tier: {lowest_complexity['complexity']} "
            f"with {pct(lowest_complexity['pass_rate'])} pass votes and "
            f"{fmt(lowest_complexity['mean_score'])} mean score."
        )
    if best_prompt:
        lines.append(
            f"- Prompt effect: {best_prompt['prompt']} has the higher mean score "
            f"({fmt(best_prompt['mean_score'])}) in this aggregate."
        )

    lines.extend(
        [
            "",
            "## Pass Rate by Agent and Prompt",
            markdown_table(
                [
                    "agent",
                    "prompt",
                    "runs",
                    "eval judgments",
                    "pass rate",
                    "partial rate",
                    "fail rate",
                    "mean score",
                ],
                [
                    [
                        row["agent"],
                        row["prompt"],
                        row["runs"],
                        row["judgments"],
                        pct(row["pass_rate"]),
                        pct(row["partial_rate"]),
                        pct(row["fail_rate"]),
                        fmt(row["mean_score"]),
                    ]
                    for row in agent_prompt
                ],
            ),
            "",
            "## Mean Score by Agent",
            markdown_table(
                ["rank", "agent", "runs", "eval judgments", "pass rate", "mean score"],
                [
                    [
                        row["rank"],
                        row["agent"],
                        row["runs"],
                        row["judgments"],
                        pct(row["pass_rate"]),
                        fmt(row["mean_score"]),
                    ]
                    for row in agent_means
                ],
            ),
            "",
            "## Evaluator Agreement",
            markdown_table(
                ["pair", "shared runs", "raw agreement", "Cohen kappa"],
                [
                    [
                        row["pair"],
                        row["n"],
                        pct(row["raw_agreement"]),
                        fmt(row["kappa"], 3),
                    ]
                    for row in agreement
                ],
            ),
            "",
            "## Complexity Breakdown",
            markdown_table(
                ["complexity", "agent", "runs", "eval judgments", "pass rate", "mean score"],
                [
                    [
                        row["complexity"],
                        row["agent"],
                        row["runs"],
                        row["judgments"],
                        pct(row["pass_rate"]),
                        fmt(row["mean_score"]),
                    ]
                    for row in by_complexity
                ],
            ),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    repo_root = repo_root_from_script()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        default=repo_root / "reports" / "eval_scores_v2_long.csv",
    )
    parser.add_argument("--output", type=Path, default=repo_root / "reports" / "summary.md")
    args = parser.parse_args()

    rows = valid_rows(load_rows(args.csv_path))
    markdown = build_markdown(rows, args.csv_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown + "\n", encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
