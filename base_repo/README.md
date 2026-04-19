# Base Repo — Coding Agent Evaluation Benchmark

## Structure

```
base_repo/
├── README.md           (this file)
├── {task_id}/
│   ├── repo/           git repo with sanitized history (GT not reachable)
│   ├── eval/
│   │   ├── handwritten_files.txt   HW files in GT (scored)
│   │   ├── auto_generated_files.txt  auto-gen files in GT (not scored)
│   │   └── gt_files.txt            all GT files (HW + auto)
│   └── prompts/
│       ├── {task}-long.md          detailed spec
│       └── {task}-short.md         summary only
```

## Tasks

| Task | Description | Lang | GT Files | HW Files | Complexity |
|------|------------|------|----------|----------|------------|
| C1 | Buffer alias bug fix | C++ | 1 | 1 | Low |
| C2 | ReduceSum precision fix | C++ | 4 | 4 | Low |
| C3 | Graph dispatch refactor | Python | 9 | 9 | Medium |
| C4 | Exp operator implementation | C++ | 24 | 19 | Medium |
| C5 | ReduceSumV2 operator | C++ | 27 | 25 | High |
| M1 | MoE permutation NaN fix | Python | 3 | 3 | Low |
| M2 | Bucket reorder feature | Python | 6 | 6 | Medium |
| M3 | Memory compression feature | Python | 10 | 9 | High |
| K1 | Relaxed env var validation | Go | 13 | 13 | Low |
| K2 | Job success policy | Go | 35 | 12 | Medium |
| K3 | Image volume digest | Go | 49 | 13 | Medium |
| K4 | Auth selector awareness | Go | 98 | 58 | High |

## Usage

### 1. Create an experiment instance

```bash
# Copy base repo to create a fresh experiment
cp -r base_repo/K3/repo experiment/K3-codex-long

# Verify: repo is clean, has history, GT not reachable
git -C experiment/K3-codex-long log --oneline | head -5
git -C experiment/K3-codex-long status
```

### 2. Run the coding agent

```bash
# Example with Codex
codex exec -m gpt-5.4 --dangerously-bypass-approvals-and-sandbox \
  "$(cat base_repo/prompts/K3-long.md)" \
  < /dev/null

# Example with Claude Code
claude --model claude-sonnet-4-6 --dangerously-skip-permissions -p \
  "$(cat base_repo/prompts/K3-long.md)"

# Example with OpenCode + MiniMax
opencode run -m openrouter/minimax/minimax-m2.5 \
  --dir experiment/K3-codex-long \
  "$(cat base_repo/prompts/K3-long.md)"
```

### 3. Evaluate with diff-eval-local

```bash
# Use the skill
/diff-eval-local \
  experiment/K3-codex-long \
  base_repo/K3/eval/gt_files.txt \
  base_repo/K3/eval/handwritten_files.txt \
  base_repo/K3/prompts/K3-long.md
```

Or manually:
```bash
# Generate agent diff (tracked + untracked)
git -C experiment/K3-codex-long diff HEAD > gen.diff
git -C experiment/K3-codex-long ls-files --others --exclude-standard >> gen_files.txt

# Compute HW coverage
comm -12 <(sort base_repo/K3/eval/handwritten_files.txt) <(sort gen_files.txt)
```

## File Classification

Each task's `eval/` directory contains pre-classified file lists:
- **handwritten_files.txt**: Human-written source code, tests, configs — these are scored
- **auto_generated_files.txt**: Codegen output (protobuf, deepcopy, OpenAPI specs, testdata snapshots) — excluded from scoring
- **gt_files.txt**: All GT files (union of handwritten + auto-generated)

Classification was cross-validated by Claude Opus and GPT-5.4 (via Codex), with unanimous agreement on all 12 tasks.

## Repo Construction

Each task repo is sanitized from the upstream source:
- **History preserved**: Full git history up to parent commit (for `git log`, `git blame`, `git show`)
- **Future removed**: GT commit and all descendant commits are unreachable
- **Remote stripped**: No `origin` remote, no branch refs pointing past parent
- **gh CLI blocked**: Experiment scripts prepend a fake `gh` binary

Verification: `git cat-file -t <GT_COMMIT>` must fail for every task repo.
