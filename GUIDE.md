# Huawei-Eval: Code Generation Agent Evaluation Benchmark -- Technical Guide

This document is the single authoritative reference for the huawei-eval repository.
It covers every stage of the pipeline: task definition, experiment repo construction, agent inference, evaluation, anti-cheating audit, and results analysis.

---

## 1. Project Purpose and Key Findings

### What This Is

An evaluation benchmark for LLM-based coding agents, built for an ASE 2026 Industry Showcase paper. The benchmark measures how well autonomous agents implement real features from industrial codebases (Huawei CANN, MindSpeed, torch_npu) and open-source projects (Kubernetes).

There is no application source code, build system, or test suite in this repo -- only evaluation artifacts and experiment data.

### Central Thesis

**"Coding agents are not yet ready for autonomous deployment on industrial feature-implementation tasks."**

### Key Numbers

- **12 tasks** across 4 repositories (C1-C5, M1-M3, K1-K4)
- **5 main agent configurations** (A1, A2, A3, Codex, MiniMax)
- **119 main experiments** (+ 10 secondary K3-only configs)
- **129 total scored rows** in `all_scores.csv`
- **Best config: Codex (gpt-5.4) at 37.5% PASS rate** (9/24)
- **Overall PASS rate: 17.6%** (21/119)
- **Worst config: MiniMax M2.5 at 0% PASS** (0/24)

### Results by Configuration

| Config | N | PASS | PARTIAL | FAIL | PASS% |
|--------|---|------|---------|------|-------|
| Codex (gpt-5.4) | 24 | 9 | 11 | 4 | 37.5% |
| A1 (Sonnet 4.6) | 24 | 7 | 9 | 8 | 29.2% |
| A3 (Opus 4.6 + Loops) | 24 | 3 | 17 | 4 | 12.5% |
| A2 (Opus 4.6) | 23* | 2 | 17 | 4 | 8.7% |
| MiniMax M2.5 | 24 | 0 | 16 | 8 | 0.0% |

\* A2 missing K1-short (generation produced 0 files).

### Key Findings

- **Prompt effect**: Long prompts improve PASS rate by +8 to +42 percentage points depending on config.
- **Harness effect**: A3 (with Loops harness) wins 12/23 head-to-head comparisons vs A2 (without harness).
- **Complexity cliff**: Low-complexity tasks ~50% PASS; High-complexity tasks ~10% PASS.
- **Under stricter audit**: 13.4-17.6% PASS range when accounting for potential cheating vectors.

### Paper Location

The paper lives in `paper2/`:
- `paper2/main.tex` -- main document
- `paper2/sections/*.tex` -- 10 section files (introduction through conclusion)
- `paper2/references.bib` -- bibliography
- Build: `pdflatex main && bibtex main && pdflatex main && pdflatex main`

---

## 2. Task Registry

The benchmark uses 12 tasks drawn from 4 source repositories.

| ID | Repo | Complexity | Language | GT Files | GT Lines | Parent Commit | GT Commit | What It Tests |
|----|------|-----------|----------|----------|----------|---------------|-----------|---------------|
| C1 | cann-ops-adv | Low | C++ | 1 | 6 | `f722d9d` | `888d214` | Bug fix (small edit) |
| C2 | cann-ops | Low | C++ | 4 | 33 | `83a20f8d` | `a8b1e873` | Bug fix (multi-file) |
| C3 | torch_npu | Medium | Python | 9 | 782 | `eed8f282` | `94260135a` | Registry refactor (hardcoded dispatch to pattern) |
| C4 | cann-ops | Medium | C++/AscendC | 24 | 1,273 | `f016f674` | `a4abcf27` | New operator (Exp for Ascend NPU) |
| C5 | cann-ops | High | C++/AscendC | 27 | 3,372 | `eeb9289c` | `3bf6bea9` | New operator (complex, high LOC) |
| M1 | MindSpeed | Low | Python | 3 | 27 | `47a5482` | `e455517` | Small feature addition |
| M2 | MindSpeed | Medium | Python | 6 | 151 | `cc7f2e1f` | `596b96b` | Feature implementation |
| M3 | MindSpeed | High | Python | 10 | 1,228 | `6919aae8` | `102c3f3` | Complex feature (includes binary PNG) |
| K1 | kubernetes | Low | Go | 13 | 1,064 | `5b4d97d` | `87f9b38` | KEP feature (Go, moderate files) |
| K2 | kubernetes | Medium | Go | 35 | 3,873 | `cc6d9b3` | `364ef33` | KEP feature (Go, many files) |
| K3 | kubernetes | Medium | Go | 49 | 11,107 | `92d5eb1` | `e14cdad` | KEP-5365 (Go, K8s PR #132807) |
| K4 | kubernetes | High | Go | 98 | 6,794 | `ec8015d` | `64ba17c` | KEP-4601 Authorize with Selectors |

### Source Repositories

- **CANN** (C1-C5): Huawei's Ascend NPU operator library. Hosted on Gitee. C1 uses `cann-ops-adv`; C2/C4/C5 use `cann-ops`.
- **MindSpeed** (M1-M3): Huawei's distributed training acceleration library. Hosted on Gitee.
- **torch_npu** (C3): PyTorch NPU adapter. Hosted on Gitee.
- **Kubernetes** (K1-K4): Open-source container orchestration. Hosted on GitHub. K3 corresponds to PR #132807; K4 to PR #125571.

### Parent Commit Selection

Each task's parent commit is the last commit *before* the ground truth feature was introduced. The agent starts from this state and must independently implement the feature.

---

## 3. Experiment Repo Construction

### 3.1 Source Repositories

Original repos are cloned locally (originally at `/home/jie/codes/` on the experiment server, relocated to `/Users/zihanwu/Public/codes/huawei-eval/experiment/` for this repo). The parent commit for each task is the commit immediately before the ground truth (GT) patch.

### 3.2 Sanitization Protocol

**Why sanitization is needed**: During early experiments, gpt-5.4 (Codex) discovered and `git cherry-pick`ed the ground truth sub-commits from the K4 repository's full git history (124K commits), achieving 98/98 file coverage by simply copying the answer. This is documented in `experiment/trajectory_comparison_K4.md`.

**The incident**: Codex's session log showed it explicitly checked git history for existing selector authorization commits before writing any code:

> "I'll first check the local git history to see if this set of selector authorization commits already exists. If so, I'll extract patches from local history instead of hand-writing the entire Kubernetes cascade of changes."

This confirmed that agents will exploit available git history if it contains the answer.

**Sanitization differs by repo type**:

#### C/M repos (CANN, MindSpeed, torch_npu)

These use `sanitize_experiments_v2.sh`:

```bash
# Clone with full history
git clone --quiet "$SRC" "$DEST"

# Checkout parent and create clean branch
git -C "$DEST" checkout --quiet -b experiment "$PARENT"

# Delete all other local branches
for branch in $(git -C "$DEST" branch | grep -v '^\* experiment$' | sed 's/^[ *]*//' ); do
    git -C "$DEST" branch -D "$branch" --quiet 2>/dev/null || true
done

# Remove remote
git -C "$DEST" remote remove origin

# Delete all tags
git -C "$DEST" tag -l | xargs -r git -C "$DEST" tag -d > /dev/null 2>&1 || true

# Expire reflogs and garbage collect
git -C "$DEST" reflog expire --expire=now --all 2>/dev/null
git -C "$DEST" gc --prune=now --quiet 2>/dev/null
```

This preserves history up to the parent commit but removes the GT commit (which was on a different branch). After GC, the GT commit becomes unreachable. Verification: `git cat-file -e <GT_COMMIT>` must fail.

These repos retain full history up to the parent (e.g., cann-ops-C4-A2-long has ~2,385 commits).

#### K repos (Kubernetes)

K-series repos require stricter sanitization because the GT commits are on the main branch and cannot be isolated by branch deletion. They use `git archive` into a fresh repo:

```bash
# Create a fresh repo with ONLY the parent commit's tree
mkdir "$DEST" && cd "$DEST"
git init
git -C "$SRC" archive "$PARENT" | tar -x
git add -A
git commit -m "Initial commit (parent $PARENT)"
```

This produces a repo with exactly **1 commit** and zero history. Verification: `git log --oneline | wc -l` must output `1`.

Example: `kubernetes-K4-codex-short` has exactly 1 commit.

### 3.3 Additional Anti-Leakage Measures

**Fake `gh` CLI**: The file `experiment/bin/gh` is prepended to `$PATH` during all agent runs:

```bash
#!/bin/bash
echo "Error: gh CLI is disabled for this experiment. Do not access GitHub PRs or issues." >&2
exit 1
```

This blocks agents from using `gh pr view`, `gh issue view`, or any GitHub CLI command to access PR descriptions or diffs.

**Prompt injection**: Every agent invocation includes a preamble:

> "IMPORTANT: Do NOT use gh CLI, curl to GitHub API, or access any GitHub PRs/issues. Work only from the codebase and the task description below."

### 3.4 Repo Naming Convention

Pattern: `{prefix}-{task}-{config}-{prompt}`

| Pattern | Example | Description |
|---------|---------|-------------|
| `{prefix}-{task}-A1-{prompt}` | `kubernetes-K4-A1-long` | A1 (Sonnet, no harness) |
| `{prefix}-{task}-A2-{prompt}` | `cann-ops-C4-A2-long` | A2 (Opus, no harness) |
| `{prefix}-{task}-A3-{prompt}` | `MindSpeed-M2-A3-short` | A3 (Opus + Loops harness) |
| `{prefix}-{task}-codex-{prompt}` | `kubernetes-K1-codex-short` | Codex (gpt-5.4) |
| `{prefix}-{task}-opencode-{prompt}` | `cann-ops-C2-opencode-long` | MiniMax M2.5 (via OpenCode CLI) |

**Prefix mapping**:
- C1: `cann-ops-adv`
- C2, C4, C5: `cann-ops`
- C3: `torch_npu`
- M1, M2, M3: `MindSpeed`
- K1, K2, K3, K4: `kubernetes`

**Historical exception**: A1 repos use older naming (`cann-ops-C4-long` without config suffix).

---

## 4. Agent Inference

### 4.1 Configuration Matrix

| Config | Model | Framework | Harness | Default Concurrency |
|--------|-------|-----------|---------|---------------------|
| A1 | Claude Sonnet 4.6 | Claude Code CLI | None | Sequential |
| A2 | Claude Opus 4.6 | Claude Code CLI | None | Sequential |
| A3 | Claude Opus 4.6 | Claude Code CLI | Loops (syntax/structure validation, up to 3 rounds) | Sequential |
| Codex | GPT-5.4 | Codex CLI | None | 12 concurrent |
| MiniMax | MiniMax M2.5 | OpenCode CLI | None | 1 (default) |

### 4.2 Prompt Design

Each task has two prompt variants stored in `experiment/prompts/`:

**Short prompt** (1-3 sentences): Describes the task at the highest level. Example (`C4-short.md`):

> **Summary**: Implement an Exp (exponential function) custom operator for Ascend NPU, supporting `base^(scale*x+shift)` computation, covering float16/float32/bfloat16 data types.
>
> **Proposal**: Following the standard structure of existing operators in the repository, implement a complete Exp operator under the contrib directory.

**Long prompt** (detailed plan with directory/file/logic requirements): Specifies operator specs, host-side design, device-side design, examples, tests, and references. Example (`C4-long.md`) runs ~30 lines and includes data type specifications, tiling strategy details, and reference to existing operators.

All prompts are stored at:
```
experiment/prompts/{task}-{long|short}.md
```

### 4.3 Running Each Config

#### Claude A2 (no harness)

Invoked via Claude Code CLI. From `run_k_claude.sh`:

```bash
cd "$repo"
env PATH="$FAKE_BIN:$PATH" claude --model claude-opus-4-6 \
    --dangerously-skip-permissions -p \
    "IMPORTANT: Do NOT use gh CLI, curl to GitHub API, or access any GitHub PRs/issues.
     Work only from the codebase and the task description below.

<prompt_text>"
```

Key flags:
- `--model claude-opus-4-6` -- selects the model
- `--dangerously-skip-permissions` -- auto-approves all file writes and tool use
- `-p` -- non-interactive mode (single prompt, no follow-up)

#### Claude A3 (Loops harness)

Same initial invocation as A2. After the agent completes, a validation loop runs:

**For Python tasks** (C3, M1-M3):
```bash
python3 -m py_compile "$full_path"
```
Checks each modified/new `.py` file for syntax errors.

**For C++ tasks** (C1, C2, C4, C5):
Checks whether new files were created (structural validation only -- no Ascend compiler available).

**For Go tasks** (K1-K4):
```bash
cd "$repo" && go vet "./$d/..."
```
Runs `go vet` on all packages containing changed `.go` files.

If errors are found, they are fed back to the agent using `claude -c -p` (continue conversation):

```bash
claude --model claude-opus-4-6 --dangerously-skip-permissions -c -p \
    "Go validation found errors. Please fix them:
    
    <errors>"
```

This repeats for up to **3 rounds** (`A3_MAX_ROUNDS=3`). The metadata file records `a3_rounds` and `a3_status` (passed/exhausted).

#### Claude A1 (Sonnet, no harness)

Same as A2 but with `--model claude-sonnet-4-6`. Script: `run_k_a1.sh`.

#### Codex (gpt-5.4)

Invoked via Codex CLI. From `run_codex_all.sh`:

```bash
cd "$repo"
PATH="$FAKE_BIN:$PATH" timeout "$TIMEOUT" codex exec \
    -m gpt-5.4 \
    --dangerously-bypass-approvals-and-sandbox \
    "IMPORTANT: Do NOT use gh CLI, curl to GitHub API, or access any GitHub PRs/issues.
     Work only from the codebase and the task description below.

<prompt_text>" \
    < /dev/null
```

Key details:
- `codex exec` -- non-interactive execution mode
- `--dangerously-bypass-approvals-and-sandbox` -- auto-approves all operations
- `< /dev/null` -- prevents stdin from blocking
- Default timeout: 1800 seconds (30 minutes)
- Default concurrency: 12 tasks in parallel
- Supports `CODEX_ARGS_FILE` for additional CLI arguments

#### MiniMax M2.5 (via OpenCode)

Invoked via OpenCode CLI. From `run_minimax_all.sh`:

```bash
PATH="$FAKE_BIN:$PATH" timeout "$TIMEOUT" opencode run \
    -m "openrouter/minimax/minimax-m2.5" \
    --dir "$repo" \
    "IMPORTANT: Do NOT use gh CLI, curl to GitHub API, or access any GitHub PRs/issues.
     Work only from the codebase and the task description below.

<prompt_text>"
```

Key details:
- `opencode run` -- non-interactive mode
- `-m openrouter/minimax/minimax-m2.5` -- routes through OpenRouter
- `--dir` -- sets working directory (opencode requires explicit dir)
- Default timeout: 1800 seconds
- Default concurrency: 1 (sequential)

### 4.4 Batch Runners

| Script | Agent | Model | Concurrency | Resume File | Tasks |
|--------|-------|-------|-------------|-------------|-------|
| `run_codex_all.sh` | Codex | gpt-5.4 | 12 (gen), 4 (eval) | `codex_progress.txt` | C1-C5, M1-M3, K1-K2, K4 |
| `run_minimax_all.sh` | OpenCode | minimax-m2.5 | 1 | `minimax_progress.txt` | C1-C5, M1-M3, K1-K2, K4 |
| `run_k_claude.sh` | Claude Code | opus-4.6 | Sequential | `k_claude_progress.txt` | K1, K2, K4 (A2 + A3) |
| `run_k_a1.sh` | Claude Code | sonnet-4.6 | Sequential | `k_a1_progress.txt` | K1, K2, K4 (A1 only) |
| `eval_all.sh` | Claude Code | opus-4.6 | Sequential | N/A | C1-C5, M1-M3 (A2 + A3) |

All resumable runners support: `--gen-only`, `--eval-only`, `--task X`, `--prompt Y`, `--status`, `--reset`.

Progress tracking works by appending `{task}-{prompt}-gen` and `{task}-{prompt}-eval` to a progress file. On re-run, completed steps are skipped.

### 4.5 Agent Output

Agent changes are left as **uncommitted modifications and untracked files** in the experiment repo. The repo's HEAD remains at the parent commit. This means:
- `git diff HEAD` shows all modifications to tracked files
- `git ls-files --others --exclude-standard` shows all new files created by the agent
- Together, these represent the complete agent output

Metadata for each run is saved to `experiment/experiment_logs/{task}-{config}-{prompt}.meta`:
```
task=C4
config=A2
prompt=long
model=claude-opus-4-6
duration_sec=2700
modified_files=17
new_files=0
total_files=17
```

---

## 5. Evaluation Pipeline

Evaluation is a two-phase process: deterministic file coverage computation followed by semantic evaluation by an LLM judge.

### 5.1 Diff Generation

**Ground truth diff**: For C/M tasks, generated from the source repo:
```bash
git -C "$source_repo" diff "$PARENT".."$GT" > ground_truth.diff
git -C "$source_repo" diff --name-only "$PARENT".."$GT" | sort > gt_files.txt
```

For K tasks, pre-computed ground truth diffs are stored in reference directories:
```
experiment/eval_results/K1-gt-ref/ground_truth.diff
experiment/eval_results/K1-gt-ref/gt_files.txt
```
These are reused across all configs for the same task.

**Generated diff**: Extracted from the experiment repo's uncommitted state:
```bash
git -C "$repo" diff HEAD > generated.diff
{
    git -C "$repo" diff HEAD --name-only
    git -C "$repo" ls-files --others --exclude-standard | grep -v '^\.'
} | sort -u > gen_files.txt
```

The `grep -v '^\.'` excludes dotfiles/dotdirs (`.claude/`, `.serena/`, etc.) that are agent metadata, not generated code.

### 5.2 File Coverage Computation

File overlap is computed using sorted set intersection:

```bash
comm -12 gen_files.txt gt_files.txt > overlap_files.txt
```

Coverage metrics saved to `coverage.json`:
```json
{
    "task": "C4",
    "config": "A2",
    "prompt": "long",
    "gen_files": 17,
    "gt_files": 24,
    "overlap_files": 0,
    "coverage_rate": 0,
    "gen_lines_added": 0,
    "gen_lines_deleted": 0,
    "gt_lines_added": 1273,
    "gt_lines_deleted": 0
}
```

**Important**: `coverage_rate` = `overlap_files / gt_files`. This is raw file-path overlap. If the agent creates files at different paths (e.g., `src/math/exp/` instead of `src/contrib/math/exp/`), the literal overlap is 0 even if the content is correct. The semantic evaluation handles this nuance.

### 5.3 Mandatory vs Auto-Generated File Distinction

This is one of the most critical aspects of the evaluation. The evaluator LLM is instructed to classify files before scoring.

#### What Counts as Auto-Generated

The evaluation prompt includes: "Classify auto-generated files (binary, .gitkeep, etc.) and exclude from scoring."

In practice, the evaluator applies these classifications:

| Pattern | Classification | Examples |
|---------|---------------|----------|
| `*.pb.go` | Auto-generated | Protobuf-generated Go files |
| `zz_generated_*` | Auto-generated | `zz_generated.deepcopy.go`, `zz_generated.conversion.go` |
| `swagger.json`, OpenAPI specs | Auto-generated | API specification files |
| `.gitkeep` | Auto-generated | Empty placeholder files |
| `__init__.py` (empty) | Auto-generated | Python package markers |
| Binary files (`.png`) | Excluded | M3's `compress_activation_coloured.png` |
| Client-go apply configs | Auto-generated | Kubernetes client configuration |
| Testdata snapshots | Auto-generated | Golden test data files |

#### What Counts as Mandatory (Handwritten)

| Type | Examples |
|------|---------|
| Source logic | `op_host/exp.cpp`, `node_authorizer.go`, `requestinfo.go` |
| Controllers | `filters/authorization.go`, `webhook.go` |
| Validation | `validation.go`, `validation_test.go` |
| Tests | `test_exp.py`, `helpers_test.go`, `cost_test.go` |
| Feature gates | `kube_features.go` |
| API type definitions | `types.go`, `v1/types.go` |
| Build configs | `CMakeLists.txt` |
| Documentation | `Exp.md`, `README.md` |

#### How This Affects Scoring

The file coverage metric in `coverage.json` counts ALL files (including auto-generated). The evaluator's qualitative scores (A/B/C) weight handwritten files much more heavily:

- Missing a `zz_generated.deepcopy.go` is noted but does not significantly lower B (Completeness)
- Missing a `validation.go` or test file substantially lowers B
- Missing a core implementation file (e.g., `op_kernel/exp.cpp`) substantially lowers both A and B

From the C4-A2-long eval report, this distinction is explicit:

> "5 auto-generated files excluded from GT, 3 from Gen. 19 non-auto GT files and 14 non-auto Gen files used for analysis."
>
> "Logical Coverage Rate: 14/19 = 73.7%"
> "Literal Coverage Rate: 0/19 = 0%"

#### Task-Specific Notes

- **K3** has 49 GT files but only ~19 are handwritten; the rest are protobuf codegen, OpenAPI specs, and deepcopy files.
- **K4** has 98 GT files; roughly 56 are handwritten (tests, source logic, feature gates).
- **C4** has 24 GT files; 5 are auto-generated (`.gitkeep` placeholders), leaving 19 handwritten.
- **M3** has a binary PNG in the GT; it is excluded from the evaluation denominator (scored out of 9, not 10).

### 5.4 Scoring Rubric

Three dimensions, each 0-5:

**A. Functional Correctness (0-5)**: Does the patch correctly address the requirement?
- 5 = perfect implementation, semantically correct
- 4 = minor gaps (e.g., edge case not handled)
- 3 = main case works but notable omissions
- 2 = partial implementation, significant issues
- 1 = superficial attempt, barely functional
- 0 = wrong approach or no meaningful output

**B. Completeness & Coverage (0-5)**: Are all required files, logic paths, and tests covered?
- 5 = full coverage of all handwritten GT files
- 4 = one minor gap (e.g., missing a README)
- 3 = primary changes done, secondary gaps
- 2 = notable gaps (missing test files, missing validation)
- 1 = major gaps (missing core implementation files)
- 0 = non-functional output

**C. Behavioral Equivalence (0-5)**: How similar is the agent's output to the ground truth behavior?
- 5 = semantically equivalent
- 4 = minor differences (different variable names, slightly different algorithms)
- 3 = same goal, different approach (e.g., runtime branching vs compile-time dispatch)
- 2 = significant behavioral differences
- 1 = partial overlap in intent
- 0 = completely divergent

**Verdict determination**:
- **PASS**: A >= 4 AND B >= 4 AND C >= 3
- **FAIL**: A <= 1 OR introduces destructive/breaking changes
- **PARTIAL**: Everything else

This measures **production-level equivalence**, not just "does it compile" or "does it pass some tests."

### 5.5 Evaluator Assignment

Different configs use different LLM evaluators due to cost and availability:

| Experiments | Evaluator | Tool |
|-------------|-----------|------|
| A2, A3 (C/M tasks) | Claude Opus 4.6 | `claude --model claude-opus-4-6` in `eval_all.sh` |
| A1, A2, A3 (K tasks) | Claude Sonnet 4.6 | `claude --model claude-sonnet-4-6` in `run_k_claude.sh` |
| Codex | MiniMax M2.5 (default) or Claude Sonnet | `opencode run -m openrouter/minimax/minimax-m2.5` in `run_codex_all.sh` |
| MiniMax | MiniMax M2.5 (default) or Claude | Configurable via `EVAL_ENGINE` env var |

The evaluator receives a self-contained prompt with:
1. Pre-computed coverage statistics
2. Ground truth file list and diff (first 2000 lines)
3. Generated file list and diff (first 2000 lines)
4. List of overlapping and untracked files
5. The original task prompt
6. The scoring rubric

The evaluator writes its assessment to `eval_report.md` inside the experiment repo, which is then moved to `eval_results/{task}-{config}-{prompt}/eval_report.md`.

**Known limitation**: Evaluator calibration varies across models. MiniMax evaluations tend to be more lenient; Claude evaluations tend to be more detailed and stricter.

### 5.6 Output Files

Each experiment produces 7-8 files in `eval_results/{task}-{config}-{prompt}/`:

| File | Description |
|------|-------------|
| `eval_report.md` | Full evaluation report with verdict, scores, file comparison, checklist |
| `coverage.json` | Quantitative file coverage and line statistics |
| `ground_truth.diff` | GT patch (from source repo or gt-ref directory) |
| `generated.diff` | Agent's patch (`git diff HEAD`) |
| `gt_files.txt` | Sorted list of files changed in GT |
| `gen_files.txt` | Sorted list of files changed/created by agent |
| `overlap_files.txt` | Files appearing in both lists (`comm -12`) |
| `eval_log.txt` | Raw stdout/stderr from the evaluator session |

---

## 6. Anti-Cheating Audit

### 6.1 The Audit Script

`experiment/audit_cheating.py` scans all Codex experiment logs for cheating signals.

It checks for:

1. **Cherry-pick commands** (`CRITICAL`): Agent running `git cherry-pick` to copy GT commits
2. **GT commit access** (`HIGH`): Agent running `git show`, `git diff`, or `git log` on the GT commit hash
3. **Git history searches**: Agent grepping through commit history for the feature
4. **GT file access** (`CRITICAL`): Agent reading `eval_results/`, `ground_truth.diff`, or `gt_files.txt`
5. **Web PR access** (`CRITICAL`): Agent using `curl`, `wget`, or `fetch` to access GitHub PRs

Running the audit:
```bash
cd experiment && python3 audit_cheating.py
```

Output: A summary table showing per-experiment findings, followed by detailed evidence for flagged experiments.

### 6.2 The K4 Incident

**Discovery**: During initial K4 experiments, Codex achieved suspiciously high file coverage (98/98). Trajectory analysis revealed it had checked local git history and cherry-picked GT sub-commits.

**Remediation**: All K-series repos were rebuilt as single-commit archives using `git archive | tar -x`, eliminating all history. Experiments were re-run on sanitized repos.

**Verification**: After sanitization, `git cat-file -t <GT_COMMIT>` fails in all K experiment repos. K repos have exactly 1 commit.

### 6.3 Web Search Findings

The audit discovered that Codex uses web search capabilities (API docs, KEPs, GitHub issues) during execution. Claude Code does not have web access. This is noted as a confound in the paper's threats section.

### 6.4 C2 Git Archaeology

One finding was that an agent used `git log -S` to search for symbol definitions in C2's git history. This was classified as **legitimate debugging** (using history to understand existing code patterns), not cheating, because the agent was searching for existing code, not the GT commit.

---

## 7. Data Outputs

### 7.1 all_scores.csv

The unified scoring dataset. 130 lines (header + 129 data rows).

**Schema**:
```
task,config,prompt,verdict,score_A,score_B,score_C,file_coverage_rate,gen_files,gt_files,overlap_files,gen_lines_added,gt_lines_added
```

**Example rows**:
```csv
C1,A1,long,PASS,5.0,5.0,5.0,1.0,,1,1,,
C4,A2,long,PARTIAL,3.0,3.0,3.0,0,17,24,0,0,1273
K4,codex,long,PASS,4.0,4.0,4.0,0.4081,42,98,40,1465,6507
```

Some fields are empty for A1 (legacy) and K3 (top-level reports without coverage stats).

**Rebuilding from source**: Run `python3 experiment/build_scores_csv.py`. This script:
1. Parses all `eval_results/*/eval_report.md` files for verdict and A/B/C scores using regex
2. Parses A1 data from `experiment_results.md` (legacy summary table)
3. Parses K3 data from top-level `*_eval_report.md` files
4. Merges, deduplicates (preferring eval_results), sorts, and writes CSV

### 7.2 Analysis Reports

| File | Description |
|------|-------------|
| `experiment/cross_config_analysis.md` | Full comparison across all 5 configs |
| `experiment/minimax_analysis.md` | Deep analysis of MiniMax M2.5 performance |
| `experiment/trajectory_comparison_K4.md` | Codex vs Claude A3 trajectory analysis on K4 |

### 7.3 Agent Trajectories

**Codex sessions**: Stored as JSONL files in `~/.codex/sessions/2026/04/04/*.jsonl`. Each file contains exec_command calls, apply_patch operations, reasoning blocks, and commentary.

**Claude Code sessions**: Stored as JSONL files in `~/.claude/projects/-Users-zihanwu-...-{repo}/*.jsonl`. Each file contains tool calls (Read, Edit, Grep, Bash, Agent dispatches, TodoWrite updates).

To map a Codex session to a task:
```bash
head -1 ~/.codex/sessions/2026/04/04/rollout-*.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    if line.startswith('{'):
        d = json.loads(line)
        cwd = d.get('payload',{}).get('cwd','')
        print(cwd.split('/')[-1])
"
```

---

## 8. Key Results Summary

### Overall Performance

| Metric | Value |
|--------|-------|
| Total experiments | 119 (main configs) |
| PASS | 21 (17.6%) |
| PARTIAL | 70 (58.8%) |
| FAIL | 28 (23.5%) |

### Per-Config Ranking

| Rank | Config | PASS% | PASS | PARTIAL | FAIL |
|------|--------|-------|------|---------|------|
| 1 | Codex (gpt-5.4) | 37.5% | 9 | 11 | 4 |
| 2 | A1 (Sonnet 4.6) | 29.2% | 7 | 9 | 8 |
| 3 | A3 (Opus+Loops) | 12.5% | 3 | 17 | 4 |
| 4 | A2 (Opus) | 8.7% | 2 | 17 | 4 |
| 5 | MiniMax M2.5 | 0.0% | 0 | 16 | 8 |

### Prompt Effect

Long prompts consistently outperform short prompts. Across all configs:
- Long prompt PASS rate: higher by +8 to +42 percentage points
- Most dramatic: C4-A1-long PASS vs C4-A1-short PARTIAL
- Smallest gap: Codex (already benefits from deeper code discovery)

### Harness Effect

A3 (with Loops harness) vs A2 (without):
- A3 wins 12/23 head-to-head comparisons
- A2 wins 4/23
- 7 ties
- The harness helps most on Python tasks (syntax checking catches real errors)
- The harness helps least on C++ tasks (only structural checks, no compiler available)
- On K4, the harness evaluation session identified problems but did not trigger fixes

### Complexity Cliff

| Complexity | PASS Rate (approx) |
|------------|-------------------|
| Low (C1, C2, M1, K1) | ~50% |
| Medium (C3, C4, M2, K2, K3) | ~15% |
| High (C5, M3, K4) | ~10% |

---

## 9. Paper

Located at `paper2/`.

### Structure

```
paper2/
  main.tex              -- Main document, includes all sections
  references.bib        -- Bibliography
  sections/
    abstract.tex
    01-introduction.tex
    02-industrial-context.tex
    03-study-design.tex
    04-results.tex
    05-root-cause.tex
    06-harness.tex
    07-related-work.tex
    08-threats.tex
    09-data-availability.tex
    10-conclusion.tex
```

### Building

```bash
cd paper2
pdflatex main
bibtex main
pdflatex main
pdflatex main
```

Three passes are needed for cross-references and bibliography to resolve correctly.

---

## 10. Reproducing Results

### Step 1: Re-run a Single Experiment

To re-run task C4 with config A2 and long prompt:

```bash
cd /Users/zihanwu/Public/codes/huawei-eval/experiment

# Reset the experiment repo
repo="cann-ops-C4-A2-long"
git -C "$repo" checkout -- .
git -C "$repo" clean -fd

# Run the agent
cd "$repo"
PATH="/Users/zihanwu/Public/codes/huawei-eval/experiment/bin:$PATH" \
claude --model claude-opus-4-6 --dangerously-skip-permissions -p \
    "IMPORTANT: Do NOT use gh CLI, curl to GitHub API, or access any GitHub PRs/issues.
     Work only from the codebase and the task description below.

$(cat ../prompts/C4-long.md)"
cd ..
```

### Step 2: Evaluate It

```bash
# Create output directory
out="eval_results/C4-A2-long"
mkdir -p "$out"

# Copy ground truth (from existing reference)
cp eval_results/C4-A2-long/ground_truth.diff "$out/"
cp eval_results/C4-A2-long/gt_files.txt "$out/"

# Generate agent diff
git -C "$repo" diff HEAD > "$out/generated.diff"
{ git -C "$repo" diff HEAD --name-only; git -C "$repo" ls-files --others --exclude-standard | grep -v '^\.' ; } | sort -u > "$out/gen_files.txt"

# Compute coverage
comm -12 "$out/gen_files.txt" "$out/gt_files.txt" > "$out/overlap_files.txt"
echo "Coverage: $(wc -l < "$out/overlap_files.txt") / $(wc -l < "$out/gt_files.txt")"

# Run semantic evaluation (via Claude)
claude --model claude-sonnet-4-6 --dangerously-skip-permissions -p \
    "<evaluation prompt with diffs, file lists, scoring rubric>"
```

### Step 3: Rebuild the CSV

```bash
cd /Users/zihanwu/Public/codes/huawei-eval/experiment
python3 build_scores_csv.py
```

This re-reads all `eval_results/*/eval_report.md` files, parses verdicts and scores, and overwrites `all_scores.csv`.

### Step 4: Run the Anti-Cheating Audit

```bash
cd /Users/zihanwu/Public/codes/huawei-eval/experiment
python3 audit_cheating.py
```

### Using the Batch Runners

To run all Codex experiments from scratch:
```bash
cd experiment
bash run_codex_all.sh --reset        # Wipe progress and reset repos
bash run_codex_all.sh                # Run all (gen + eval)
bash run_codex_all.sh --status       # Check progress
```

To run only MiniMax evaluation (skip generation):
```bash
bash run_minimax_all.sh --eval-only
```

To run a single task:
```bash
bash run_codex_all.sh --task K4 --prompt long
```

---

## Appendix A: File Paths Reference

| Item | Path |
|------|------|
| Project root | `/Users/zihanwu/Public/codes/huawei-eval/` |
| Experiment directory | `experiment/` |
| Prompts | `experiment/prompts/{task}-{long|short}.md` |
| Eval results | `experiment/eval_results/{task}-{config}-{prompt}/` |
| Agent logs | `experiment/experiment_logs/{task}-{config}-{prompt}.{log|meta}` |
| Scores CSV | `experiment/all_scores.csv` |
| CSV builder | `experiment/build_scores_csv.py` |
| Cheating audit | `experiment/audit_cheating.py` |
| Fake gh CLI | `experiment/bin/gh` |
| GT references (K) | `experiment/eval_results/{task}-gt-ref/` |
| Codex runner | `experiment/run_codex_all.sh` |
| MiniMax runner | `experiment/run_minimax_all.sh` |
| Claude K runner | `experiment/run_k_claude.sh` |
| Claude A1 runner | `experiment/run_k_a1.sh` |
| Original eval script | `experiment/eval_all.sh` |
| Sanitization (C/M) | `experiment/sanitize_experiments_v2.sh` |
| K3 top-level reports | `*_eval_report.md` (10 files) |
| Trajectory analysis | `experiment/trajectory_comparison_K4.md` |
| Cross-config analysis | `experiment/cross_config_analysis.md` |
| Paper | `paper2/main.tex` |

## Appendix B: Ground Truth Commit Map

| Task | Source Repo | Parent | GT Commit | PR# |
|------|------------|--------|-----------|-----|
| C1 | cann-ops-adv | `f722d9d` | `888d214` | 308 |
| C2 | cann-ops | `83a20f8d` | `a8b1e873` | 675 |
| C3 | torch_npu | `eed8f282` | `94260135a` | 24373 |
| C4 | cann-ops | `f016f674` | `a4abcf27` | 651 |
| C5 | cann-ops | `eeb9289c` | `3bf6bea9` | 690 |
| M1 | MindSpeed | `47a5482` | `e455517` | N/A |
| M2 | MindSpeed | `cc7f2e1f` | `596b96b` | N/A |
| M3 | MindSpeed | `6919aae8` | `102c3f3` | N/A |
| K1 | kubernetes | `5b4d97d` | `87f9b38` | 123385 |
| K2 | kubernetes | `cc6d9b3` | `364ef33` | 123412 |
| K3 | kubernetes | `92d5eb1` | `e14cdad` | 132807 |
| K4 | kubernetes | `ec8015d` | `64ba17c` | 125571 |

## Appendix C: Evaluator Prompt Template

The evaluator prompt (used by all batch runners) follows this structure:

```
You are a code review evaluator. Evaluate the agent-generated code changes against the ground truth.

## Context
- Task: {task} ({config} config, {prompt} prompt)
- Model: {model}

## Coverage Stats (pre-computed)
- Ground truth files: {gt_count}
- Generated files: {gen_count}
- Overlap: {overlap} ({coverage_rate})

## Ground Truth File List
{gt_files}

## Generated File List
{gen_files}

## Overlapping Files
{overlap_files}

## Untracked New Files
{untracked}

## Ground Truth Diff (first 2000 lines)
{gt_diff}

## Generated Diff (first 2000 lines)
{gen_diff}

## Requirements (prompt given to the agent)
{prompt_text}

## Evaluation Instructions
1. Classify auto-generated files and exclude from scoring
2. Build a requirements checklist and check each item
3. For shared files, compare approach (scope, logic, patterns)
4. Identify missing logic, unnecessary changes, test gaps

## Scoring Rubric
A. Functional Correctness (0-5)
B. Completeness & Coverage (0-5)
C. Behavioral Equivalence (0-5)
Verdict: PASS if A>=4 AND B>=4 AND C>=3. FAIL if A<=1. PARTIAL otherwise.

Write the complete report to eval_report.md.
```
