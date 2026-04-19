#!/usr/bin/env python3
"""Batch-run OpenCode + GLM-5.1 evaluation for Codex experiment repos.

This script preserves the original `eval_report.md` and writes the new
OpenCode/GLM-5.1 result to `eval_report_opencode_glm51.md`.
"""

from __future__ import annotations

import argparse
import filecmp
import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


REPORT_FILE = "eval_report.md"
NEW_REPORT_FILE = "eval_report_opencode_glm51.md"
LOG_FILE = "eval_opencode_glm51.log"
SUMMARY_FILE = "opencode_glm51_codex_eval_summary.json"
PID_FILE = "opencode_glm51_codex_eval.pid"
RUN_LOG_FILE = "opencode_glm51_codex_eval.batch.log"


@dataclass
class RepoTask:
    repo: Path
    task_id: str
    prompt_type: str
    gt_diff: Path
    hw_files: Path
    prompt_file: Path
    attempt: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root.",
    )
    parser.add_argument(
        "--model",
        default="zhipuai-coding-plan/glm-5.1",
        help="OpenCode model identifier.",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=4,
        help="Maximum concurrent OpenCode runs.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1200,
        help="Per-task timeout in seconds.",
    )
    parser.add_argument(
        "--stall-secs",
        type=int,
        default=600,
        help="Retry if startup log is tiny and unchanged for this many seconds.",
    )
    parser.add_argument(
        "--stall-log-bytes",
        type=int,
        default=200,
        help="Only treat tiny logs below this size as startup stalls.",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=2,
        help="Retry budget per repo.",
    )
    parser.add_argument(
        "--include",
        default="",
        help="Optional regex to restrict repo names.",
    )
    parser.add_argument(
        "--rerun-completed",
        action="store_true",
        help="Recompute repos that already have eval_report_opencode_glm51.md.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned work without launching OpenCode.",
    )
    return parser.parse_args()


def backup_dir(experiment_dir: Path) -> Path:
    return experiment_dir / ".opencode_glm51_backups"


def backup_path(experiment_dir: Path, repo: Path) -> Path:
    return backup_dir(experiment_dir) / f"{repo.name}.eval_report.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def repo_name_filter(name: str, pattern: str) -> bool:
    return not pattern or re.search(pattern, name) is not None


def looks_like_codex_repo(repo: Path) -> bool:
    return repo.is_dir() and "codex-gpt-5_4" in repo.name


def parse_repo_task(root: Path, repo: Path) -> RepoTask | None:
    match = re.match(r"([A-Z]\d+|T\d+)-codex-gpt-5_4-(long|short)-\d{4}-\d{2}-\d{2}$", repo.name)
    if not match:
        return None
    task_id, prompt_type = match.group(1), match.group(2)
    task_dir = root / "base_repo" / task_id
    gt_diff = task_dir / "eval" / "gt_diff.patch"
    hw_files = task_dir / "eval" / "handwritten_files.txt"
    prompt_file = task_dir / "prompts" / f"{task_id}-{prompt_type}.md"
    if not (gt_diff.exists() and hw_files.exists() and prompt_file.exists()):
        return None
    return RepoTask(repo=repo, task_id=task_id, prompt_type=prompt_type, gt_diff=gt_diff, hw_files=hw_files, prompt_file=prompt_file)


def restore_interrupted_repo(experiment_dir: Path, repo: Path) -> None:
    backup = backup_path(experiment_dir, repo)
    if not backup.exists():
        return

    original = repo / REPORT_FILE
    new_report = repo / NEW_REPORT_FILE

    if new_report.exists():
        if not original.exists():
            shutil.move(str(backup), str(original))
        else:
            shutil.copy2(backup, original)
            backup.unlink()
        return

    if not original.exists():
        shutil.move(str(backup), str(original))
        return

    if filecmp.cmp(original, backup, shallow=False):
        backup.unlink()
        return

    # The repo still contains a temporary OpenCode report with no final output file.
    shutil.move(str(original), str(new_report))
    shutil.move(str(backup), str(original))


def restore_all_interruptions(experiment_dir: Path) -> None:
    for repo in experiment_dir.iterdir():
        if looks_like_codex_repo(repo):
            restore_interrupted_repo(experiment_dir, repo)


def build_message(root: Path, task: RepoTask) -> str:
    repo_rel = task.repo.relative_to(root)
    gt_rel = task.gt_diff.relative_to(root)
    hw_rel = task.hw_files.relative_to(root)
    prompt_rel = task.prompt_file.relative_to(root)
    return (
        "Use only the diff-eval-local skill. "
        "Follow the skill workflow exactly; do not broad-search the repository. "
        "For deterministic function coverage, derive contexts only from patch hunks "
        "(`diff --git` and `@@` lines) from the GT diff and the generated diff/untracked patch. "
        "Do not scan the full repository to invent function lists. "
        "On macOS BSD awk, do not use match($0, regex, array); use python or grep+sed instead. "
        "If python reads files, open them with errors='ignore' and skip binary/non-UTF8 content. "
        f"Evaluate this experiment and write the report to {REPORT_FILE}: "
        f"/diff-eval-local {repo_rel} {gt_rel} {hw_rel} {prompt_rel}"
    )


def start_run(root: Path, experiment_dir: Path, task: RepoTask, model: str) -> dict[str, object]:
    task.attempt += 1
    task.repo.mkdir(parents=True, exist_ok=True)

    original = task.repo / REPORT_FILE
    new_report = task.repo / NEW_REPORT_FILE
    log_path = task.repo / LOG_FILE
    backup = backup_path(experiment_dir, task.repo)
    backup.parent.mkdir(parents=True, exist_ok=True)

    if original.exists():
        shutil.copy2(original, backup)
        original.unlink()
    elif backup.exists():
        backup.unlink()

    if new_report.exists():
        new_report.unlink()
    if log_path.exists():
        log_path.unlink()

    cmd = [
        "opencode",
        "run",
        "--dir",
        str(root),
        "--model",
        model,
        "--dangerously-skip-permissions",
        build_message(root, task),
    ]
    log_file = log_path.open("w")
    proc = subprocess.Popen(
        cmd,
        cwd=root,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    now = time.time()
    return {
        "task": task,
        "proc": proc,
        "log_file": log_file,
        "log_path": log_path,
        "start_time": now,
        "last_progress_at": now,
        "last_log_size": 0,
    }


def restore_original_report(experiment_dir: Path, repo: Path) -> None:
    backup = backup_path(experiment_dir, repo)
    original = repo / REPORT_FILE
    if backup.exists():
        shutil.move(str(backup), str(original))


def finalize_success(experiment_dir: Path, running: dict[str, object]) -> dict[str, object]:
    task: RepoTask = running["task"]  # type: ignore[assignment]
    original = task.repo / REPORT_FILE
    new_report = task.repo / NEW_REPORT_FILE
    if original.exists():
        if new_report.exists():
            new_report.unlink()
        original.rename(new_report)
    restore_original_report(experiment_dir, task.repo)
    return {
        "repo": str(task.repo.relative_to(experiment_dir.parent)),
        "status": "ok",
        "attempts": task.attempt,
        "seconds": round(time.time() - float(running["start_time"]), 1),
    }


def finalize_failure(experiment_dir: Path, running: dict[str, object], status: str) -> dict[str, object]:
    task: RepoTask = running["task"]  # type: ignore[assignment]
    original = task.repo / REPORT_FILE
    if original.exists():
        original.unlink()
    restore_original_report(experiment_dir, task.repo)
    return {
        "repo": str(task.repo.relative_to(experiment_dir.parent)),
        "status": status,
        "attempts": task.attempt,
        "seconds": round(time.time() - float(running["start_time"]), 1),
    }


def collect_tasks(args: argparse.Namespace, experiment_dir: Path) -> tuple[list[RepoTask], list[dict[str, object]]]:
    pending: list[RepoTask] = []
    initial_results: list[dict[str, object]] = []
    for repo in sorted(experiment_dir.iterdir()):
        if not looks_like_codex_repo(repo) or not repo_name_filter(repo.name, args.include):
            continue
        task = parse_repo_task(args.root, repo)
        if task is None:
            initial_results.append(
                {
                    "repo": str(repo.relative_to(args.root)),
                    "status": "skip_bad_inputs",
                    "attempts": 0,
                }
            )
            continue
        if (repo / NEW_REPORT_FILE).exists() and not args.rerun_completed:
            initial_results.append(
                {
                    "repo": str(repo.relative_to(args.root)),
                    "status": "preexisting",
                    "attempts": 0,
                }
            )
            continue
        pending.append(task)
    return pending, initial_results


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    experiment_dir = root / "experiment"
    if not experiment_dir.is_dir():
        raise SystemExit(f"missing experiment dir: {experiment_dir}")

    restore_all_interruptions(experiment_dir)

    pending, initial_results = collect_tasks(args, experiment_dir)
    summary_path = experiment_dir / SUMMARY_FILE
    results: dict[str, dict[str, object]] = {item["repo"]: item for item in initial_results}
    write_json(summary_path, list(results.values()))

    if args.dry_run:
        for task in pending:
            print(f"PLAN\t{task.repo.relative_to(root)}")
        print(f"TOTAL\t{len(pending)}")
        return 0

    running: list[dict[str, object]] = []
    while pending or running:
        while pending and len(running) < args.parallel:
            task = pending.pop(0)
            run = start_run(root, experiment_dir, task, args.model)
            results[str(task.repo.relative_to(root))] = {
                "repo": str(task.repo.relative_to(root)),
                "status": f"running_attempt_{task.attempt}",
                "attempts": task.attempt,
            }
            write_json(summary_path, [results[key] for key in sorted(results)])
            print(f"START\t{task.repo.relative_to(root)}\tattempt={task.attempt}", flush=True)
            running.append(run)

        time.sleep(5)
        next_running: list[dict[str, object]] = []
        for run in running:
            task: RepoTask = run["task"]  # type: ignore[assignment]
            proc: subprocess.Popen[str] = run["proc"]  # type: ignore[assignment]
            log_file = run["log_file"]
            log_path: Path = run["log_path"]  # type: ignore[assignment]
            original = task.repo / REPORT_FILE
            elapsed = time.time() - float(run["start_time"])

            if original.exists():
                try:
                    proc.kill()
                except OSError:
                    pass
                log_file.close()
                result = finalize_success(experiment_dir, run)
                results[result["repo"]] = result
                write_json(summary_path, [results[key] for key in sorted(results)])
                print(
                    f"DONE\t{result['repo']}\t{result['status']}\tattempts={result['attempts']}\t{result['seconds']}s",
                    flush=True,
                )
                continue

            if log_path.exists():
                current_size = log_path.stat().st_size
                if current_size != int(run["last_log_size"]):
                    run["last_log_size"] = current_size
                    run["last_progress_at"] = time.time()

            if proc.poll() is not None:
                log_file.close()
                if original.exists():
                    result = finalize_success(experiment_dir, run)
                    results[result["repo"]] = result
                    write_json(summary_path, [results[key] for key in sorted(results)])
                    print(
                        f"DONE\t{result['repo']}\t{result['status']}\tattempts={result['attempts']}\t{result['seconds']}s",
                        flush=True,
                    )
                    continue

                status = f"exit_{proc.returncode}"
                if task.attempt < args.max_attempts:
                    print(
                        f"RETRY\t{task.repo.relative_to(root)}\t{status}\tnext_attempt={task.attempt + 1}",
                        flush=True,
                    )
                    pending.append(task)
                else:
                    result = finalize_failure(experiment_dir, run, status)
                    results[result["repo"]] = result
                    write_json(summary_path, [results[key] for key in sorted(results)])
                    print(
                        f"DONE\t{result['repo']}\t{result['status']}\tattempts={result['attempts']}\t{result['seconds']}s",
                        flush=True,
                    )
                continue

            if elapsed > args.timeout:
                try:
                    proc.kill()
                except OSError:
                    pass
                log_file.close()
                if original.exists():
                    result = finalize_success(experiment_dir, run)
                else:
                    status = "timeout"
                    if task.attempt < args.max_attempts:
                        print(
                            f"RETRY\t{task.repo.relative_to(root)}\t{status}\tnext_attempt={task.attempt + 1}",
                            flush=True,
                        )
                        pending.append(task)
                        continue
                    result = finalize_failure(experiment_dir, run, status)
                results[result["repo"]] = result
                write_json(summary_path, [results[key] for key in sorted(results)])
                print(
                    f"DONE\t{result['repo']}\t{result['status']}\tattempts={result['attempts']}\t{result['seconds']}s",
                    flush=True,
                )
                continue

            last_progress_gap = time.time() - float(run["last_progress_at"])
            if last_progress_gap > args.stall_secs and int(run["last_log_size"]) < args.stall_log_bytes:
                try:
                    proc.kill()
                except OSError:
                    pass
                log_file.close()
                status = "stalled"
                if task.attempt < args.max_attempts:
                    print(
                        f"RETRY\t{task.repo.relative_to(root)}\t{status}\tnext_attempt={task.attempt + 1}",
                        flush=True,
                    )
                    pending.append(task)
                else:
                    result = finalize_failure(experiment_dir, run, status)
                    results[result["repo"]] = result
                    write_json(summary_path, [results[key] for key in sorted(results)])
                    print(
                        f"DONE\t{result['repo']}\t{result['status']}\tattempts={result['attempts']}\t{result['seconds']}s",
                        flush=True,
                    )
                continue

            next_running.append(run)

        running = next_running

    write_json(summary_path, [results[key] for key in sorted(results)])
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
