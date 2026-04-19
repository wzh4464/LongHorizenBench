# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An evaluation benchmark for an ASE 2026 Industry Showcase paper, measuring how well LLM-based coding agents implement real features from industrial codebases (Huawei CANN, MindSpeed, torch_npu) and open-source projects (Kubernetes). There is no buildable application — this repo contains evaluation infrastructure, experiment data, and the LaTeX manuscript.

**Key finding**: 17.6% overall PASS rate across 119 experiments. Best config: Codex gpt-5.4 (37.5% PASS); worst: MiniMax (0% PASS).

## Key Documents

- `GUIDE.md` — authoritative technical reference (task registry with commit SHAs, sanitization protocol, full evaluation pipeline)
- `experiment/README.md` — experiment directory layout and how to view results
- `experiment_plan.md` — frozen experiment design matrix
- `paper2/` — LaTeX manuscript (`paper2/main.tex` + `paper2/sections/*.tex`)

## Common Commands

```bash
# View scores (single source of truth)
cat experiment/all_scores.csv

# Rebuild scores CSV from eval_report.md files
python3 experiment/build_scores_csv.py

# Run anti-cheating audit over experiment logs
python3 experiment/audit_cheating.py

# Check batch runner status
bash experiment/run_codex_all.sh --status
bash experiment/run_minimax_all.sh --status

# Run evaluation for a single task
bash experiment/run_codex_all.sh --task C1

# Build paper PDF
cd paper2 && pdflatex main && bibtex main && pdflatex main && pdflatex main

# Create sanitized experiment repo from source
bash experiment/sanitize_repo.sh <source_repo> <dest_dir> <parent_commit> <gt_commit>

# Build CapBench task directories from capbench_sampled.csv
python3 _build_capbench_tasks.py
```

## Repository Structure

```
experiment/
├── {prefix}-{task}-{config}-{prompt}/  # 108+ experiment repos (each is a git repo)
├── eval_results/{task}-{config}-{prompt}/  # Eval output per experiment
│   ├── eval_report.md, coverage.json, ground_truth.diff, generated.diff
│   ├── gt_files.txt, gen_files.txt
├── prompts/                           # 24 prompt files ({task}-{short,long}.md)
├── all_scores.csv                     # Unified results (129 rows), rebuilt by build_scores_csv.py
├── build_scores_csv.py                # Parses eval_report.md → CSV
├── audit_cheating.py                  # Scans logs for GT leakage (cherry-pick, web, etc.)
├── run_codex_all.sh                   # Batch runner: Codex (12-way parallel)
├── run_minimax_all.sh                 # Batch runner: MiniMax
├── sanitize_repo.sh                   # Canonical repo sanitization script
├── bin/gh                             # Fake gh binary (blocks API access during experiments)
base_repo/{task_id}/                   # Canonical task repos (sanitized)
├── repo/                              # Git repo at parent commit
├── eval/                              # handwritten_files.txt, auto_generated_files.txt
├── prompts/                           # Task prompts
source_repos/                          # Full clones of upstream repos (for building tasks)
paper2/                                # LaTeX manuscript
  main.tex, sections/*.tex, references.bib
```

## Task Registry (12 tasks)

| ID | Repo | Complexity | Lang | GT Files | HW Files |
|----|------|-----------|------|----------|----------|
| C1 | cann-ops-adv | Low | C++ | 1 | 1 |
| C2 | cann-ops | Low | C++ | 4 | 4 |
| C3 | torch_npu | Medium | Python | 9 | 9 |
| C4 | cann-ops | Medium | C++ | 24 | 24 |
| C5 | cann-ops | High | C++ | 27 | 25 |
| M1 | MindSpeed | Low | Python | 3 | 3 |
| M2 | MindSpeed | Medium | Python | 6 | 6 |
| M3 | MindSpeed | High | Python | 10 | 10 |
| K1 | kubernetes | Low | Go | 13 | 13 |
| K2 | kubernetes | Medium | Go | 35 | 12 |
| K3 | kubernetes | Medium | Go | 49 | 13 |
| K4 | kubernetes | High | Go | 98 | 58 |

## Agent Configurations

| Config | Agent | Model | Notes |
|--------|-------|-------|-------|
| A1 | Claude Code | Sonnet 4.6 | No harness, legacy naming (no config suffix) |
| A2 | Claude Code | Opus 4.6 | No harness |
| A3 | Claude Code | Opus 4.6 | + Loops harness (syntax/structure validation) |
| codex | Codex CLI | gpt-5.4 (o3) | No harness |
| minimax/opencode | OpenCode | MiniMax M2.5 | No harness |

## Experiment Naming

Pattern: `{prefix}-{task}-{config}-{prompt}` e.g. `cann-ops-C4-A2-long`

Prefix mapping: C1 → `cann-ops-adv`, C2/C4/C5 → `cann-ops`, C3 → `torch_npu`, M1-M3 → `MindSpeed`, K1-K4 → `kubernetes`

Legacy A1 repos use older naming without config suffix: `{prefix}-{task}-{prompt}`

## Scoring

Three dimensions (0-5 each):
- **A. Functional Correctness** — Does the code solve the task?
- **B. Completeness & Coverage** — Are all required files/logic/tests present?
- **C. Behavioral Equivalence** — How closely does behavior match ground truth?

**Verdict rules**: PASS = A≥4 AND B≥4 AND C≥3; FAIL = A≤1 OR destructive; PARTIAL = otherwise.

## Experiment Repo Sanitization (Critical)

All experiment repos must have GT commit unreachable. The `experiment/sanitize_repo.sh` script handles this:
1. Clone source → checkout parent commit (detached HEAD)
2. Remove `origin` remote, delete all branches/tags pointing to future commits
3. `git reflog expire --all && git gc --prune=now --aggressive`
4. Verify: `git cat-file -e <GT_SHA>` must fail
5. Block `gh` CLI via `experiment/bin/gh` fake binary on PATH

**Why**: gpt-5.4 cherry-picked the GT commit from full git history on unsanitized K4 (98/98 file coverage). All repos were rebuilt after discovery.

## CapBench Extension

`capbench_sampled.csv` defines additional benchmark tasks from open-source repos. `_build_capbench_tasks.py` builds `base_repo/` entries from `source_repos/` clones. Each task gets: `repo/` (sanitized git), `eval/` (GT diff, file lists), `prompts/` (short + long).
