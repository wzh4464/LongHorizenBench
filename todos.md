# ASE 2026 Industry Showcase — Execution Plan (Draft)

> Source: `/research_request.md`

## Top-level recommendation
- **Primary submission focus: Paper 2 (Coding Agent feature implementation)**
  - Rationale: already has task set, evaluation framework, and partial results; open-source repos (K8s/CANN) reduce compliance risk; easier to form a complete evidence chain.
- **Secondary/backup: Paper 1 (MulVul industrialization)**
  - Rationale: publication success depends on (a) compliance boundaries, (b) strong tool comparison, and ideally (c) at least one confirmed high-value vulnerability—higher execution risk.

## Stage plan & success signals

### Paper 2 — Not Ready Yet + Harness Engineering

#### Stage P2-S1 (P0): Freeze tasks + rubric calibration
- **Objective**: lock task set, experimental matrix, and scoring rubric so later results are interpretable.
- **Success signals**:
  - Final task list = 8–10 cases (K8s 3–4 + CANN 4–6) with PR links and ground-truth references.
  - 5-dimension rubric (semantic/completeness/build/tests/quality) and weights frozen.
  - At least 2 cases double-scored by two reviewers with acceptable agreement (document disagreements).
- **What to run / do**:
  - Create `tasks.csv` and `rubric.md`.
  - Create `results_schema.json` describing per-run fields.
- **Expected artifacts**:
  - `/artifacts/paper2/tasks.csv`
  - `/artifacts/paper2/rubric.md`
  - `/artifacts/paper2/results_schema.json`

#### Stage P2-S2 (P0): Agent-only baseline completion (RQ1/RQ3 core)
- **Objective**: produce the main quantitative table over tasks × agent configs × input granularity.
- **Success signals**:
  - For each task, results exist for at minimum:
    - Claude Code (Opus 4.6)
    - Claude Code + Harness (Loops)
  - OpenCode/GLM can be “optional” if time constrained, but must be flagged as partial coverage.
  - Each run records: scores (5 dims + weighted), build/test outcomes, token cost and latency if possible.
- **What to run / do**:
  - Run each agent configuration with two prompt granularities (one-line vs detailed plan) per task.
  - Collect logs and diffs.
- **Expected artifacts**:
  - `/artifacts/paper2/results_raw/*.jsonl`
  - `/artifacts/paper2/logs/*`
  - `/artifacts/paper2/results_table.csv`

#### Stage P2-S3 (P0): Human-in-the-loop evidence (RQ4 key)
- **Objective**: demonstrate industrially relevant workflow: agent draft → engineer fix → final PR-quality.
- **Success signals**:
  - ≥2–3 cases with engineer participation.
  - Record `T_agent`, `T_fix`, change size, and change taxonomy (API design, feature gate, tests, validation, generated code, etc.).
  - Provide at least 1 “representative diff” that is safe to share.
- **What to run / do**:
  - Pick 2–3 cases: 1 K8s + 1–2 CANN (or 2 K8s if CANN delayed).
  - Standardize time logging form.
- **Expected artifacts**:
  - `/artifacts/paper2/hitl/time_logs.csv`
  - `/artifacts/paper2/hitl/diff_summaries.md`
  - `/artifacts/paper2/hitl/case_studies.md`

#### Stage P2-S4 (P1): Root cause analysis (RQ2)
- **Objective**: convert results into actionable findings: what fails, why, and which failures are model-vs-engineering.
- **Success signals**:
  - Failure taxonomy with 3–5 stable categories.
  - Stratified analysis by (language, task complexity, need for API design, need for feature gate).
- **What to run / do**:
  - Qualitative coding of failure logs/diffs.
  - Summarize harness delta patterns.
- **Expected artifacts**:
  - `/artifacts/paper2/analysis/failure_taxonomy.md`
  - `/artifacts/paper2/analysis/harness_delta.csv`

#### Stage P2-S5 (P0): Paper draft package + Data Availability
- **Objective**: produce camera-ready quality structure early.
- **Success signals**:
  - Full draft exists with figures/tables placeholders filled.
  - Threats explicitly cover confounds (OpenCode vs Claude Code model+tool coupling).
  - Data Availability Statement finalized (likely “partial 공개” via Zenodo replication package).
- **What to run / do**:
  - Write sections: Intro, Industrial Context, Study Design, Results, RCA, Harness roadmap, Threats, DAS.
  - Prepare Zenodo package (scripts + anonymized aggregates).
- **Expected artifacts**:
  - `/artifacts/paper2/paper_draft.md`
  - `/artifacts/paper2/figures/*`
  - `/artifacts/paper2/replication_package/README.md`

---

### Paper 1 — MulVul industrialization (backup unless P0 evidence arrives)

#### Stage P1-S1 (P0): Compliance + disclosure boundary (go/no-go)
- **Objective**: determine what can be published.
- **Success signals**:
  - Clear list of what can be shared: aggregate stats, anonymized snippets, vulnerability class distributions, etc.
  - Confirm whether any confirmed vulnerability case can be described.
- **Expected artifacts**:
  - `/artifacts/paper1/compliance/disclosure_matrix.md`

#### Stage P1-S2 (P0): Adaptation runnable + stable outputs
- **Objective**: ensure MulVul runs end-to-end on target repos.
- **Success signals**:
  - Router/Detector/RAG adaptation complete.
  - Stable output export pipeline (alerts, CWE, confidence, evidence).
- **Expected artifacts**:
  - `/artifacts/paper1/runs/*`

#### Stage P1-S3 (P0): Comparison vs existing tools + manual validation
- **Objective**: strongest industrial value: complementarity and unique finds.
- **Success signals**:
  - Overlap/unique findings measured; FP categories reported.
  - Manual validation protocol and sample size documented.
- **Expected artifacts**:
  - `/artifacts/paper1/comparison/overlap.csv`
  - `/artifacts/paper1/analysis/fp_taxonomy.md`

#### Stage P1-S4 (P0): High-value findings package
- **Objective**: at least one compelling case study OR a convincing “capability boundary” narrative.
- **Success signals**:
  - ≥1 confirmed high-value vulnerability (ideal) OR strong systematic analysis of migration success/failure by CWE & language.
- **Expected artifacts**:
  - `/artifacts/paper1/cases/*`

## P0/P1/P2 priority checklist
- **P0 (blocking)**
  - Paper 2: (1) full main results table, (2) ≥2–3 HITL cases, (3) minimal industrial context paragraph.
  - Paper 1: compliance boundary + tool comparison + at least one strong validated finding.
- **P1 (significant boost)**
  - token/latency costs, engineer feedback, CANN full coverage.
- **P2 (nice-to-have)**
  - reasoning decay curve, context saturation.

## Minimal next 7 days (operational)
1. Freeze Paper 2 tasks + rubric; prepare result schema.
2. Run/collect Claude Code vs Claude Code+Harness across all tasks.
3. Start HITL on 2–3 cases and log time + diff taxonomy.
4. Draft Paper 2 skeleton with all tables/figures stubbed.
5. Decide Paper 1 go/no-go via compliance + earliest comparable results.

