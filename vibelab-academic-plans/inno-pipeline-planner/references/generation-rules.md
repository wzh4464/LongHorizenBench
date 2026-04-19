# Generation Rules

Shared rules for generating pipeline files.

## Directory layout

```text
.pipeline/
  config.json
  docs/
    research_brief.json
  tasks/
    tasks.json
```

## `.pipeline/config.json`

Create when missing:

```json
{
  "version": "1.0",
  "provider": "vibelab-web",
  "initializedAt": "<ISO timestamp>"
}
```

## Brief generation rules

- Fill content from user conversation and existing project files only.
- Leave unknown fields as empty string or empty array.
- Set `pipeline.mode`:
- Use `"plan"` when user provides concrete method/architecture/training plan.
- Use `"idea"` otherwise.
- Make `task_blueprints` and `quality_gate` domain-specific to the topic.

## Task generation rules

1. Create tasks from each stage's `task_blueprints`.
2. Create define/refine tasks for each `required_element`:
- Use `Define <field>` when empty.
- Use `Refine <field>` when already populated.
3. Add one quality-gate review task at the end of each stage with `quality_gate`.
4. Order tasks by execution flow:
- exploration -> implementation -> analysis -> writing
5. Add dependencies when obvious (for example, implementation depends on exploration in the same stage).

## `nextActionPrompt` template

```text
Task: <task title>
Stage: <stage>
User inputs: <relevant extracted values from research_brief.json>
Suggested skills: <comma-separated skills>
Quality gate: <gate items if relevant>
Stage guidance: <short stage-specific instruction>
Please produce a concrete next-step plan and execution output. If user inputs are provided, polish and make them concrete, then write updates back to .pipeline/docs/research_brief.json.
```
