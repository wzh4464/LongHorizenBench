---
name: inno-pipeline-planner
description: Guides the user through an interactive conversation to define their research project, then generates research_brief.json and tasks.json. Use when starting a new project, when no research_brief.json exists, or when the user wants to redefine their research pipeline.
---

# Inno Pipeline Planner

Run an interactive planning flow that turns user conversation into:
- `.pipeline/docs/research_brief.json`
- `.pipeline/tasks/tasks.json`

Keep this file short. Load full schemas and field-level rules from:
- `references/pipeline-contract.md` (index)

Read only what you need:
- `references/generation-rules.md`: generation logic, ordering, dependencies, `nextActionPrompt`
- `references/brief-schema.md`: `.pipeline/docs/research_brief.json` contract
- `references/tasks-schema.md`: `.pipeline/tasks/tasks.json` contract

## Non-negotiables

- Work only inside the current project directory.
- Do not fabricate papers, datasets, metrics, or results.
- Ask follow-up questions when information is vague; do not guess.
- Ask in small batches (2-3 questions), not a long static form.

## Workflow

## 1) Inspect existing pipeline state

Check:
- `.pipeline/docs/research_brief.json`
- `.pipeline/tasks/tasks.json`
- `instance.json` (legacy source)

If brief exists, summarize title, goal, and completion status, then ask:
- Refine existing brief/tasks
- Regenerate from scratch

## 2) Collect project context via conversation

Capture at least:
- Topic/problem
- Goal or hypothesis
- Success criteria or evaluation signal

Typical question buckets:
- Project identity: topic, prior paper/method/dataset, target venue (optional)
- Scope and method: core question, approach, expected outcome
- Evaluation: data source, metrics/protocol, baseline expectations

Adapt to context:
- Skip already-provided details.
- If exploratory, keep experiment/publication sections lightweight.
- If user provides concrete plan, prepare for `pipeline.mode = "plan"`; otherwise use `"idea"`.

## 3) Write pipeline files

Create if missing:
- `.pipeline/config.json`
- `.pipeline/docs/research_brief.json`
- `.pipeline/tasks/tasks.json`

Use the exact JSON contracts and generation rules in:
- `references/pipeline-contract.md` and linked reference files

Rules:
- Tailor blueprint titles/descriptions to the user topic (never generic filler).
- Keep quality gates domain-appropriate.
- Resolve recommended skills from local available skills (`.agents/skills/` or `skills/`), optionally using `stage-skill-map.json` if present.

## 4) Summarize and confirm next action

After writing files, present:
- Brief summary (title, goal, filled vs missing sections)
- Task overview (count by stage + first 2-3 task titles per stage)
- Recommended first task and why

## 5) Handle iteration requests

If user asks for updates:
- Update brief content directly when only text/content changes.
- Regenerate `tasks.json` when pipeline structure/blueprints/stages change.
- If asked to add one task only, append a single task with next numeric `id` instead of full regeneration.
