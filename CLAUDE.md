# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An evaluation benchmark for an ASE 2026 Industry Showcase paper, measuring how well LLM-based coding agents implement real features from industrial codebases (Huawei CANN, MindSpeed, torch_npu) and open-source projects (Kubernetes, Kafka, Airflow, etc.). There is no buildable application — this repo contains evaluation infrastructure, experiment data, and the LaTeX manuscript.

**62 tasks total**: 12 original (C1-C5, M1-M3, K1-K4) + 50 CapBench (T01-T50) from 15 OSS projects.

## Key Documents

- `GUIDE.md` — authoritative technical reference (task registry with commit SHAs, sanitization protocol, full evaluation pipeline, scoring rubric, anti-cheating audit details)
- `docs/PROJECT_KNOWLEDGE.md` — project context, layout, workflow ground rules, current state of base_repo
- `docs/CAPBENCH_CLASSIFICATION_TODO.md` — HW/AG classification work order for 41 unclassified CapBench tasks
- `experiment_plan.md` — frozen experiment design matrix
- `paper2/` — LaTeX manuscript, git submodule (`paper2/main.tex` + `paper2/sections/*.tex`)

## Common Commands

```bash
# Run a single Codex experiment
bash experiment/run_codex_experiment.sh run T01 long

# Check Codex experiment status
bash experiment/run_codex_experiment.sh status

# Run anti-cheating audit over experiment logs
python3 experiment/audit_codex_cheating.py

# Batch run: Codex (all 62 tasks × 2 prompts)
bash experiment/run_batch.sh batch1_experiments.txt [parallel_count]

# Batch run: Claude Code
bash experiment/run_claude_batch.sh [parallel] [limit]

# Batch run: Cursor
bash experiment/run_cursor_batch.sh

# Batch evaluation (opencode + minimax evaluator)
bash experiment/run_eval_batch.sh [parallel]
bash experiment/run_eval_codex.sh

# Docker-isolated experiment run
bash experiment/run_isolated_batch.sh [parallel]

# Monitor running experiments
bash experiment/monitor_experiments.sh

# Diagnose a Claude session (detect brainstorming traps, unanswered questions)
python3 experiment/diagnose_session.py <experiment_dir>

# Check for GT pre-application contamination bug
bash experiment/check_gt_preapplied.sh

# Validate HW/AG classification files
python3 scripts/verify_classification.py

# Build paper PDF
cd paper2 && pdflatex main && bibtex main && pdflatex main && pdflatex main

# Build CapBench task directories from capbench_sampled.csv
python3 _build_capbench_tasks.py
```

## Repository Structure

```
base_repo/{task_id}/               # 62 canonical task definitions (sanitized)
├── repo/                          # Git checkout at parent commit (remotes stripped, GT unreachable)
├── prompts/{long,short}.md        # Task prompts (short = summary, long = design hints)
└── eval/
    ├── gt_diff.patch              # Ground truth diff
    ├── gt_files.txt               # All files changed in GT
    ├── handwritten_files.txt      # HW subset (human-authored, gates PASS/FAIL)
    └── auto_generated_files.txt   # AG subset (protobuf, lockfiles, snapshots — informational only)

experiment/
├── {task}-{config}-{prompt}[-{date}]/  # Per-run experiment repos (each is a git repo)
├── eval_results/{task}-{config}-{prompt}/  # Eval output (eval_report.md, coverage.json, diffs)
├── prompts/                       # Legacy prompt files ({task}-{short,long}.md)
├── bin/gh                         # Fake gh binary (blocks GitHub API during experiments, may not be in git)
├── run_batch.sh                   # Codex batch runner
├── run_claude_batch.sh            # Claude Code batch runner
├── run_cursor_batch.sh            # Cursor batch runner
├── run_eval_batch.sh              # Evaluation batch runner
├── run_isolated_batch.sh          # Docker-isolated runner
└── *.py                           # audit_cheating, build_scores_csv, diagnose_session

source_repos/                      # Full clones of upstream repos (for building tasks)
paper2/                            # LaTeX manuscript (git submodule → wzh4464/LongHorizenBench-paper)
  main.tex, sections/*.tex, references.bib
```

## Task Registry

| ID Range | Repo | Complexity | Lang | Count |
|----------|------|-----------|------|-------|
| C1-C5 | cann-ops / cann-ops-adv / torch_npu | Low-High | C++/Python | 5 |
| M1-M3 | MindSpeed | Low-High | Python | 3 |
| K1-K4 | kubernetes | Low-High | Go | 4 |
| T01-T50 | 15 OSS repos (Kafka, CPython, Airflow, K8s, etc.) | Mixed | Java/Python/Go | 50 |

Full task details (commit SHAs, GT lines, file counts) are in `GUIDE.md` §2.

## Agent Configurations

| Config | Agent | Model | Notes |
|--------|-------|-------|-------|
| A1 | Claude Code | Sonnet 4.6 | Legacy naming (no config suffix) |
| A2 | Claude Code | Opus 4.6 | Standard |
| A3 | Claude Code | Opus 4.6 | + Loops harness (syntax/structure validation, up to 3 rounds) |
| codex | Codex CLI | gpt-5.4 | `codex exec --full-auto`, web_search disabled |
| minimax/opencode | OpenCode | MiniMax M2.5 | Via OpenRouter |

## Experiment Naming

**Current pattern**: `{task}-{config}-{prompt}-{date}` e.g. `C4-codex-gpt-5_4-long-2026-04-12`

**Legacy pattern**: `{prefix}-{task}-{config}-{prompt}` e.g. `cann-ops-C4-A2-long`

Legacy prefix mapping: C1 → `cann-ops-adv`, C2/C4/C5 → `cann-ops`, C3 → `torch_npu`, M1-M3 → `MindSpeed`, K1-K4 → `kubernetes`. A1 repos omit the config suffix entirely.

## Scoring

Three dimensions (0-5 each):
- **A. Functional Correctness** — Does the code solve the task?
- **B. Completeness & Coverage** — Are all required files/logic/tests present?
- **C. Behavioral Equivalence** — How closely does behavior match ground truth?

**Verdict rules**: PASS = A≥4 AND B≥4 AND C≥3; FAIL = A≤1 OR destructive; PARTIAL = otherwise.

### HW/AG File Classification (Critical for Scoring)

Each task's `gt_files.txt` is split into **handwritten** (HW) and **auto-generated** (AG) files. Only HW files gate the PASS/FAIL verdict. AG files (protobuf stubs, lockfiles, `zz_generated_*`, snapshots) are noted but don't lower scores.

- The split lives in `base_repo/<task>/eval/{handwritten,auto_generated}_files.txt`
- If `handwritten_files.txt == gt_files.txt` and `auto_generated_files.txt` is empty, the task is **unclassified** — scoring will be inflated
- 12 original tasks + 9 CapBench tasks are classified; 41 CapBench tasks remain unclassified (see `docs/CAPBENCH_CLASSIFICATION_TODO.md`)

## Experiment Repo Sanitization (Critical)

All experiment repos must have GT commit unreachable. Two methods:

1. **C/M repos**: Clone with history up to parent, remove branches/tags/remotes pointing beyond, `git gc --prune=now`. Verify: `git cat-file -e <GT_SHA>` must fail.
2. **K repos**: `git archive` parent into a fresh single-commit repo (no history at all).

**Why**: gpt-5.4 cherry-picked the GT commit from full git history on unsanitized K4 (98/98 file coverage). All repos were rebuilt after discovery.

Additional measures: `experiment/bin/gh` fake binary on PATH blocks `gh pr view`; prompt preamble forbids GitHub API access.

## Local Skills

This repo vendors evaluation skills in `.claude/skills/` and `.codex/skills/`:

| Skill | Purpose |
|-------|---------|
| `diff-eval-local` | Score agent output against GT diff + handwritten file list |
| `diff-eval-claude` | Batch eval using Claude Code agent team |
| `diff-eval-codex` | Batch eval using Codex CLI |
| `diff-eval-opencode` | Batch eval using OpenCode CLI |
| `run-benchmark` | Parallel 4-agent benchmark run (Claude/Cursor/Codex/OpenCode) |
| `run-k-benchmark` | Multi-agent team for parallel benchmark execution |

## Coding Conventions

- Python: 4-space indent, `snake_case`, `UPPER_SNAKE_CASE` for constants. Manage all Python with `uv`.
- Bash: `#!/bin/bash`, `set -euo pipefail` when failure handling matters.
- Prefer additive edits to scripts and docs. Do not hand-edit generated files in `eval_results/`.
- Experiment timeout: always use 7200s for all agent runs (3600s caused M2-short timeout).
- Always use `2>&1` when capturing agent output to merge stderr (fixes 0-byte JSONL capture).

## CapBench Extension

`capbench_sampled.csv` (50 rows) defines benchmark tasks from 15 OSS repos (Kafka, CPython, Airflow, K8s, etc.). `_build_capbench_tasks.py` builds `base_repo/T{01-50}/` entries from `source_repos/` clones. Each task gets: `repo/` (sanitized git), `eval/` (GT diff, file lists), `prompts/` (short + long).
