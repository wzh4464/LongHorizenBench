# Repository Guidelines

## Project Structure & Module Organization
This repository is an evaluation workspace for coding-agent experiments, not a single deployable application. The canonical task definitions live under `base_repo/` (`C1-C5`, `M1-M3`, `K1-K4`, `T01-T50`), each with `repo/`, `prompts/`, and `eval/`. Put benchmark workflow changes under `experiment/`, which now primarily contains per-run experiment repos such as `experiment/K4-codex-gpt-5_4-short-20260418` plus runner/audit scripts. Use `docs/` for project knowledge and CapBench classification notes, `scripts/` for verification helpers, `paper2/` for the ASE paper (`main.tex`, `sections/`, `references.bib`), and `proxy-docker/` for the standalone proxy stack. `experiment_zips/` and `legacy/` hold archival material and notes; top-level `*_eval_report.md`, `scoring_summary.md`, and `sankey.py` are analysis artifacts. Generated directories such as `experiment/eval_results/` or files such as `experiment/all_scores.csv` may be absent in a given checkout. For detailed workflow context, prefer `GUIDE.md` and `docs/PROJECT_KNOWLEDGE.md`.

## Build, Test, and Development Commands
There is no repo-wide build. Use targeted commands:

- `bash experiment/run_codex_experiment.sh status` shows Codex experiment progress; use `prepare`, `run T01 long`, or `run-parallel 4` for targeted execution.
- `cd experiment && bash run_batch.sh batch1_experiments.txt [parallel]` runs a named Codex batch file.
- `bash experiment/run_eval_batch.sh [parallel] [limit]` evaluates Codex runs with the local diff-eval workflow.
- `python3 experiment/audit_codex_cheating.py [--task K4] [--verbose]` reruns the anti-cheating audit over Codex experiment logs.
- `python3 scripts/verify_classification.py T01 T02 ...` verifies HW/AG file classification for CapBench tasks.
- `bash experiment/check_gt_preapplied.sh` checks for accidental GT pre-application contamination.
- `cd paper2 && pdflatex main && bibtex main && pdflatex main && pdflatex main` rebuilds the paper PDF.
- `bash proxy-docker/deploy.sh user@host` deploys the proxy stack.

Several runner and audit scripts are point-in-time snapshots with hardcoded dates, batch files, or model assumptions, especially `run_batch.sh`, `run_eval_batch.sh`, `run_eval_codex.sh`, `monitor_experiments.sh`, and `check_gt_preapplied.sh`. Read the script before reusing it for a new campaign.

## Coding Style & Naming Conventions
Follow the existing file-local style. Python uses 4-space indentation, `snake_case`, module constants in `UPPER_SNAKE_CASE`, and short docstrings for parsing scripts. Bash scripts should start with `#!/bin/bash` and `set -euo pipefail` when failure handling matters. The current dominant experiment naming pattern is `{task}-{agent/model}-{prompt}-{date}` such as `K4-codex-gpt-5_4-short-20260418`, but legacy prefixed names such as `MindSpeed-M2-claude-opus-max-short-20260417` still exist; do not assume only one naming scheme when writing tooling. Prefer additive edits to scripts and docs; do not hand-edit generated evaluation outputs or LaTeX build byproducts unless regeneration is impossible.

## Testing Guidelines
No global coverage target is enforced. Validate only what you touched: rerun `audit_codex_cheating.py` after audit-related changes, rerun `scripts/verify_classification.py` after HW/AG classification edits, and compile `paper2/` after manuscript edits. For runner changes, prefer `bash experiment/run_codex_experiment.sh status` plus a single-task run such as `bash experiment/run_codex_experiment.sh run T01 long` before wider execution.

## Local Skills
This repo vendors a local `diff-eval-local` skill for repo-based experiment scoring:

- Claude Code: `.claude/skills/diff-eval-local/SKILL.md`
- Codex: `.codex/skills/diff-eval-local/SKILL.md`
- Other agents: follow the same workflow from either local copy; GT diff should be read from `base_repo/<task>/eval/gt_diff.patch`, not generated from the experiment repo.

## Commit & Pull Request Guidelines
This workspace now includes `.git`, but the working tree may still contain many untracked or generated artifacts, so inspect `git status` before assuming a clean baseline. Use short imperative subjects with a clear scope, for example `experiment: tighten Codex audit heuristics` or `paper2: refresh results table`. PRs should state the research impact, list affected paths, mention any regenerated artifacts, and include the exact validation commands run.

## Security & Sanitization Notes
Do not reattach remotes or expose ground-truth commits. Treat `base_repo/<task>/eval/` as sensitive ground-truth data: during experiments these directories may be intentionally `chmod 000` to prevent cheating, so do not relax those permissions unless you are explicitly doing sanctioned setup or evaluation work. If a run harness injects a fake `gh` guard or similar anti-leakage wrapper, do not bypass it. Treat `.env` files and VPS credentials in `proxy-docker/` as local secrets.
