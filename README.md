# Not Ready Yet: An Industrial Capability Assessment of LLM-Based Coding Agents

> **Are coding agents ready for autonomous feature implementation in production codebases?**
>
> TL;DR: No. The best configurations achieve **12.5% PASS** across 96 experiments. On high-complexity tasks, the pass rate drops to **0%**.

<p align="center">
  <img src="https://img.shields.io/badge/Tasks-62-blue" alt="62 Tasks"/>
  <img src="https://img.shields.io/badge/Experiments-96-green" alt="96 Experiments"/>
  <img src="https://img.shields.io/badge/Agents-4-orange" alt="4 Agents"/>
  <img src="https://img.shields.io/badge/Languages-4-purple" alt="4 Languages"/>
  <img src="https://img.shields.io/badge/Evaluators-3-red" alt="3 Evaluators"/>
</p>

## Overview

This repository contains the evaluation infrastructure, experiment data, and LaTeX manuscript for an ASE 2026 Industry Showcase paper. We measure how well four frontier coding agents implement real features from industrial codebases (Huawei CANN, MindSpeed, torch_npu) and open-source projects (Kubernetes, Kafka, CPython, Airflow, etc.).

Where frontier agents achieve >70% on SWE-bench bug-fix tasks, our benchmark reveals a dramatically different picture for **multi-file feature implementation**:

| Metric | Value |
|--------|-------|
| Overall PASS rate | 8.3% (8/96) |
| Best agent PASS rate | 12.5% (Claude = Codex, tied) |
| High-complexity PASS | **0%** (all agents, all prompts) |
| Failures from engineering gaps | 84.1% |
| Prompt effect (best agents) | +25.0 pp with detailed specs |

## Key Findings

1. **Not ready for autonomous deployment.** No agent reliably completes industrial feature implementation. Even the best configurations fail or only partially pass 87.5% of their tasks.

2. **No clear winner.** Claude Opus 4.6 and Codex GPT-5.4 tie at 12.5% PASS rate. Codex achieves a higher mean composite score (7.36 vs. 6.50), suggesting stronger partial implementations.

3. **Absolute complexity cliff.** Top agents pass 25% of low-complexity tasks but 0% of high-complexity ones (10--98 ground-truth files). The barrier is scope discovery, not per-file code quality.

4. **Prompt granularity is the strongest lever.** Detailed specifications improve pass rates by +25.0 pp for capable agents. Both Claude and Codex pass 25% with long prompts vs. 0% with short prompts.

5. **Engineering-addressable gaps dominate.** 84.1% of failures stem from incomplete file coverage, not fundamental model limitations. Better scope control---not better reasoning---would close most of the gap.

## Agents Evaluated

| Agent | Model | Pass Rate | Mean Score (/15) |
|-------|-------|-----------|-----------------|
| Claude Code | Opus 4.6 | 12.5% | 6.50 |
| Codex CLI | GPT-5.4 | 12.5% | 7.36 |
| Cursor | Composer-2 | 8.3% | 6.31 |
| OpenCode | GLM-5.1 | 0.0% | 5.09 |

Each experiment is independently scored by three LLM evaluators (Claude, Codex, GLM-5.1) with majority verdict.

## Task Inventory

### Industrial Tasks (12)

| ID | Repository | Language | GT Files | Complexity |
|----|-----------|----------|----------|------------|
| C1 | CANN ops (adv) | C++ | 1 | Low |
| C2 | CANN ops | C++ | 4 | Low |
| C3 | torch_npu | Python | 9 | Medium |
| C4 | CANN ops | C++ | 24 | Medium |
| C5 | CANN ops | C++ | 27 | High |
| M1 | MindSpeed | Python | 3 | Low |
| M2 | MindSpeed | Python | 6 | Medium |
| M3 | MindSpeed | Python | 10 | High |
| K1 | Kubernetes | Go | 13 | Low |
| K2 | Kubernetes | Go | 35 | Medium |
| K3 | Kubernetes | Go | 49 | Medium |
| K4 | Kubernetes | Go | 98 | High |

### CapBench Tasks (50)

50 additional tasks sampled from 15 major OSS projects:

Apache Kafka, CPython, Apache Airflow, Kubernetes, TiDB, Elasticsearch, PyTorch, Django, React, Terraform, Grafana, ClickHouse, Envoy Proxy, Apache Flink, VS Code

## Repository Structure

```
base_repo/                    # 62 canonical task definitions
  {task_id}/
    repo/                     # Git checkout at parent commit (sanitized)
    prompts/                  # Long & short task prompts
    eval/                     # Ground truth (gt_diff.patch, file lists)

experiment/                   # Per-run experiment directories
  {task}-{config}-{prompt}-{date}/

eval_scores_3evaluators.csv   # All results: 96 rows x 3 evaluators

paper2/                       # LaTeX manuscript (git submodule)

.claude/skills/               # Evaluation & benchmark skills
  diff-eval-local/            # Single experiment evaluator
  diff-eval-claude/           # Batch eval via Claude agent team
  run-benchmark/              # 4-agent parallel benchmark runner
```

## Scoring Rubric

Three dimensions, each 0--5:

| Dimension | What it measures |
|-----------|-----------------|
| **A. Functional Correctness** | Does the code solve the task? |
| **B. Completeness** | Are all required HW files/logic/tests present? |
| **C. Behavioral Equivalence** | How closely does behavior match ground truth? |

**Verdict**: PASS = A >= 4 AND B >= 4 AND C >= 3; FAIL = A <= 1 OR destructive; PARTIAL = otherwise.

## Quick Start

```bash
# Run a single experiment (Codex)
bash experiment/run_codex_experiment.sh run T01 long

# Run 4-agent parallel benchmark
# (via Claude Code CLI skill)
claude "/run-benchmark T01:short,T01:long"

# Evaluate an experiment
claude "/diff-eval-local experiment/T01-codex-gpt-5_4-long-20260418"

# Anti-cheating audit
python3 experiment/audit_codex_cheating.py

# Build the paper
cd paper2 && pdflatex main && bibtex main && pdflatex main && pdflatex main
```

## Anti-Cheating Measures

All experiment repos are sanitized to prevent ground-truth leakage:

- GT commits are unreachable via `git log` or `git cat-file`
- `eval/` directories are `chmod 000` during experiments
- A fake `gh` binary blocks GitHub API access
- Prompt preamble forbids web search for the specific patch/PR
- Post-hoc Jaccard similarity + trajectory audit on all runs

## Citation

```bibtex
@inproceedings{wu2026notreadyyet,
  title     = {Not Ready Yet: An Industrial Capability Assessment of
               LLM-Based Coding Agents on Feature Implementation},
  author    = {Wu, Zihan and others},
  booktitle = {Proc.\ ASE 2026, Industry Showcase},
  year      = {2026}
}
```

## License

This repository contains evaluation infrastructure and experiment metadata. Source code from upstream projects (Kubernetes, CANN, MindSpeed, etc.) retains its original license.
