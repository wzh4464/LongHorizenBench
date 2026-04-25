---
name: cheat-audit
description: Audit an experiment run (agent+prompt+task) for suspicious output that may have come from the actual GT patch or upstream PR rather than independent implementation. Run whenever a new agent run is declared PASS, or whenever an eval report looks suspiciously high-coverage.
---

# Audit for GT leakage / upstream copy-paste

Coding agents with network + web tools can bypass an experiment by fetching the upstream PR (or GT commit) from GitHub and applying it wholesale. This skill documents how to detect that.

## When to run

- Every agent run whose evaluator verdict is PASS.
- Any run with GT coverage ≥ 90% on tasks with multi-file GT (≥5 files).
- Any run whose evaluator noted "byte-identical" or "complete application of upstream".
- Any run whose assistant-output log contains strings like:
  - `"PR #"`, `"pull/"`, `"上游 PR"`, `"cherry-pick"`, `"apply"`
  - `"完整应用"`, `"applied ... verbatim"`, `"merged the patch"`
  - `"gh pr"`, `"git fetch"`, `"curl https://github.com"`

## Inputs needed

- Experiment directory: `experiment/<task>-<agent>-<prompt>-<date>/`
- GT patch: `base_repo/<task>/eval/gt_diff.patch`
- HW file list: `base_repo/<task>/eval/handwritten_files.txt`
- Agent trace: whatever log the agent wrote (e.g. `claude_run.jsonl`, `codex_events.jsonl`)

## Audit procedure

### Step 1 — Scan the trace for self-admission

```
grep -E -i "PR #[0-9]+|pull/[0-9]+|cherry[- ]pick|git apply|fetched|上游|完整应用" \
  experiment/$EXP/claude_run.jsonl experiment/$EXP/claude_run.log 2>/dev/null
```

If the agent explicitly says it fetched/applied an upstream PR, it is cheating.

### Step 2: Byte-level comparison

```python
import collections, os, subprocess
def parse_adds(text):
    out = collections.defaultdict(set)
    cur = None
    for l in text.split('\n'):
        if l.startswith('+++ b/'): cur = l[6:].rstrip()
        elif cur and l.startswith('+') and not l.startswith('+++'):
            if l[1:].strip(): out[cur].add(l[1:])
    return out

gt = parse_adds(open('base_repo/<task>/eval/gt_diff.patch').read())
exp_diff = subprocess.run(['git','-C',exp_dir,'diff','HEAD'], capture_output=True, text=True).stdout
# include untracked files too by generating pseudo-patches
for f in subprocess.check_output(['git','-C',exp_dir,'ls-files','--others','--exclude-standard'], text=True).split():
    if os.path.isfile(os.path.join(exp_dir,f)):
        exp_diff += f"\n+++ b/{f}\n" + "\n".join("+"+l for l in open(os.path.join(exp_dir, f)).read().splitlines())
ex = parse_adds(exp_diff)

for f in gt:
    shared = len(gt[f] & ex.get(f, set()))
    print(f, len(gt[f]), shared, shared/len(gt[f]))
```

If Jaccard > 0.9 per file or > 0.85 overall, it's a byte-level copy of GT. Mark as INVALID.

Additional red flags (any one warrants closer look):

- Reference to the actual upstream PR number, issue number, or merge commit hash in the agent trace.
- Inclusion of LICENSE headers, AUTHORS lines, or contributor names that were not in the starter repo.
- New files materialising in directories the prompt didn't name.
- Commit messages or TODO comments that match upstream wording.

### Step 3: classify

- **Clean**: trace shows the agent reasoning from first principles; Jaccard low; structure diverges from GT.
- **Partial leak**: some file(s) byte-identical but others are different — often means the agent found a related StackOverflow answer or a helper library.
- **Full leak (INVALID)**: trace admits fetching upstream PR and ≥ 80% of files are byte-identical.

A full leak MUST be excluded from scoring and re-run with mitigations (see below).

## Mitigations for re-runs

When re-running a leaked task:

1. **Block known leakage vectors in the prompt.** If the prompt contains a direct URL or PR number, replace it with prose description of the feature. Keep file paths abstract if possible.
2. **Sandbox network access.** Run the agent in a wrapper that blocks github.com / raw.githubusercontent.com for the tasks whose GT is publicly reachable. For K8s tasks where the repo itself is GitHub-hosted, also block the specific PR/commit hash.
3. **Note in the paper.** Any task that fell to leakage cannot be scored cleanly; document the excluded runs and re-run with sanitized prompt before including results.

## Red-flag strings to grep in traces

```
# Upstream references
git fetch origin pull/
gh pr diff
gh pr checkout
raw.githubusercontent.com
gitlab.com/.*/-/patch
cherry-pick
# PR numbers shaped like #12345 (Kubernetes uses 6-digit range)
#[0-9]{5,6}
# Apply-from-URL
git apply <(curl
curl.*\.patch
wget.*\.patch
```

## Scoring policy

A run that fails this audit is scored **INVALID** in the audit log, not FAIL. Invalid runs are removed from:
- Per-agent PASS rate
- Cross-agent rankings
- Aggregate Fleiss kappa (the evaluators saw a copy-pasted diff, so they agree spuriously)

and are reported separately with a leakage note.
