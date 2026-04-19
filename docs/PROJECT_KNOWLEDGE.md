# Project Knowledge — huawei-eval

This document captures everything a fresh Claude Code session needs to continue working on this project. Read this first.

---

## What this project is

Evaluation benchmark for AI coding agents (Claude, Codex/GPT, MiniMax, Qwen) on real-world software engineering tasks. Built for the **ASE 2026 Industry track paper** about whether AI agents can replace developers on complex industrial Huawei codebases (CANN ops, MindSpeed, Kubernetes-style features).

**Core question:** Given a real merged PR's *requirement* (not the diff), can an AI agent independently produce a functionally equivalent change?

**Pass rate result:** Across 116 experiments (5 agents × 12 tasks × 2 prompt lengths), Codex CLI scored highest at 26.1%, overall pass rate 12.1%. Most failures are partial — agents implement the gist but miss edge cases or test coverage.

## Layout

```
huawei-eval/
├── base_repo/           # canonical task definitions (12 original + 50 CapBench = 62)
│   ├── C1..C5/          # CANN ops tasks (low → high difficulty)
│   ├── M1..M3/          # MindSpeed tasks
│   ├── K1..K4/          # Kubernetes tasks (huge codebase, K3/K4 are real KEPs)
│   └── T01..T50/        # CapBench: 50 PRs from 15 OSS repos (Kubernetes, Airflow, etc.)
├── experiment/          # agent runs (only post-Apr-9 sanitized survivors remain — see legacy/)
│   ├── eval_results/    # one dir per (task, agent, prompt) with eval markdown + diffs
│   ├── prompts/         # task prompts shipped to agents
│   ├── all_scores.csv   # consolidated leaderboard
│   ├── bin/             # fake `gh` to block GitHub access during runs
│   └── *.sh             # batch runners for each agent×model
├── source_repos/        # bare clones of upstream projects (used to spin up base_repo)
├── paper2/              # LaTeX + figures for the ASE submission
├── legacy_empty_dirs.txt # record of empty K3 reruns we deleted
└── _build_capbench_tasks.py  # builds T01-T50 from capbench_sampled.csv
```

## Workflow ground rules

1. **Never commit anything that lets the agent see the head of the upstream repo.** `base_repo/<task>/repo` is checked out at *parent* of the merge commit and has remotes stripped, history rewritten, and reflog expired. The PR sha is unreachable inside the repo.
2. **`experiment/bin/gh` is on PATH** during runs to make `gh pr view` etc. fail loudly. Don't remove it, even when debugging.
3. **Sanitize before publishing.** `_build_capbench_tasks.py` and `sanitize_repo.sh` should both succeed clean before checking the result into `base_repo/`. Re-run them if you touch a task.
4. **Eval scoring is offline.** `experiment/score.py` reads `gen.diff` + `gt.diff` + `gt_files.txt` and produces `eval/eval.json`. The HW vs AG split lives in `base_repo/<task>/eval/{handwritten,auto_generated}_files.txt` — keep them in sync.
5. **Memory & secrets.** Don't expose API keys; the eval shell sources `~/.config/eval-secrets.env`.

## Key directories

```
/Users/zihanwu/Public/codes/huawei-eval/
├── base_repo/                 # 62 task definitions (sanitized base repos)
│   └── <TASK>/                # T01..T50, C1..C5, M1..M3, K1..K4
│       ├── repo/              # checkout at base_sha (no .git remotes, no future commits)
│       ├── prompts/{long,short}.md
│       └── eval/
│           ├── gt_diff.patch         (all 50 capbench have it; legacy 12 just got it)
│           ├── gt_files.txt          (filenames only, sorted)
│           ├── handwritten_files.txt (subset of gt_files.txt)
│           └── auto_generated_files.txt (the rest, pasted from gt_files.txt — gen files)
├── experiment/                # one subdir per agent run, plus shared infra
│   ├── bin/, capbench/, eval_results/, prompts/, plus a few KEEP runs
│   └── (146 historical runs were archived to /Volumes/MacData/huawei-eval-legacy/experiment/)
├── source_repos/              # upstream clones used to seed base_repo
├── docs/                      # team notes, task definition rules
└── legacy/                    # work-in-progress notes; not in git
```

## Task naming

- **C1–C5**: legacy "CANN" series (cann-ops, torch-cann)
- **M1–M3**: MindSpore / MindSpeed
- **K1–K4**: Kubernetes (K3 is the hardest — 49 hand-written files)
- **T01–T50**: CapBench (mixed OSS, sourced from `capbench_sampled.csv`)

## What tools/agents we evaluate

Five harness configs ("agents"):

| Code | Underlying | Notes |
|------|------------|-------|
| `A1` | Claude 4.5 Sonnet | Anthropic CLI |
| `A2` | Claude 4.5 Opus | Anthropic CLI |
| `A3` | GPT-4o | OpenAI Responses API |
| `codex` | Codex CLI (gpt-5) | OpenAI Codex CLI 0.x |
| `opencode` / `minimax` | OpenCode + MiniMax | self-hosted |

Each agent runs each task twice — once with `short` prompt (problem statement only) and once with `long` prompt (problem + design hints).

## How scoring works

`scripts/score.py` (a thin wrapper around `eval_diff_v2.py`) reads:

1. The agent's `gen.diff` (its diff against `base_repo/<task>/repo`)
2. The ground-truth `gt_diff.patch`
3. The HW classification (`handwritten_files.txt` and `auto_generated_files.txt`)

Then it computes:

- **HW file coverage**: how many handwritten files the agent touched
- **HW line precision/recall**: how closely the agent's edits match GT on HW files
- **AG file coverage**: same for auto-generated files (informational only — these don't gate PASS/FAIL)
- **Pass criteria**: HW file recall ≥ 0.8 AND HW line recall ≥ 0.5 (rough)

This is why **the HW/AG split is critical**: if everything is marked HW, then trivial generated noise (proto stubs, snapshot fixtures, package-lock) inflates the denominator and the agent looks worse than it is. Conversely, if real source is mis-marked AG, the agent gets credit for files it didn't touch.

## Current state of base_repo

### Original 12 (C1-C5, M1-M3, K1-K4)
- ✅ All have `gt_files.txt`, `handwritten_files.txt`, `auto_generated_files.txt`
- ✅ All have `gt_diff.patch` (just added 2026-04-10 by copying from `experiment/eval_results/<task>-gt-ref/ground_truth.diff` or `<task>-A1-long/ground_truth.diff`)
- ✅ HW/AG split was done manually months ago, considered authoritative
- ✅ All have working `repo/` clone

### CapBench 50 (T01-T50)
- ✅ All have `gt_files.txt`, `handwritten_files.txt`, `auto_generated_files.txt`, `gt_diff.patch`
- ✅ All have working `repo/` (sanitized git checkout)
- ⚠️ **Only 9 have proper HW/AG classification** (T12, T31, T34, T38, T40, T43, T17, T48, T49, T50 — exact list TBD)
- ❌ **41 are NOT classified**: their `handwritten_files.txt` = `gt_files.txt` and `auto_generated_files.txt` is empty

## Recent operational state (Apr 9-10, 2026)

- Mass cleanup: 146 historical experiment dirs were archived to `/Volumes/MacData/huawei-eval-legacy/experiment/` as 5 tar files (cann-ops-adv.tar, cann-ops.tar, torch_npu.tar, MindSpeed.tar, kubernetes.tar). They were `git status`-clean for a long time, mostly the result of an earlier accidental codex `git reset` that wiped agent edits.
- Local archive cleanup: `base_repo_v1_0.zip` (2.2G) and `k8s-experiment-repos-K1-K2-K3-sanitized.tar.gz` (1.4G) moved off the repo root into `/Volumes/MacData/huawei-eval-legacy/archives/`.
- 11 empty K3 codex/A2 rerun dirs (the v2/r1-r4 set) were deleted; their base SHA list is in `legacy/empty_dirs_purged_2026-04-10.md`.
- 7 KEEP rerun dirs survive in `experiment/`: K1-A2-short-fresh, K1-codex-short-fresh, K2-{A2,codex}-{long,short}-v2, K3-A2-short-v2.
- 12 old tasks in `base_repo/` just had `gt_diff.patch` populated from `experiment/eval_results/<task>-gt-ref/ground_truth.diff` (or first available run if no gt-ref).

### Open work after this session

1. **(blocked on this todo)** Classify HW vs AG for 41 unclassified CapBench tasks. See `CAPBENCH_CLASSIFY_TODO.md`.
2. Re-run agent experiments on the new sanitized base_repo (after 1 is done).
3. Update paper Section 5 with refreshed numbers.
