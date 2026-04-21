# 评估结果定位指南

## 顶层结构

```
huawei-eval/
├── base_repo/<TASK>/                    # 任务定义
│   ├── eval/                            # 评估元数据（被 chmod 000 保护）
│   │   ├── gt_diff.patch                # Ground truth patch
│   │   ├── handwritten_files.txt        # HW 文件清单（评分用）
│   │   ├── auto_generated_files.txt     # 自动生成文件清单
│   │   └── gt_files.txt                 # GT 所有修改文件
│   ├── prompts/                         # 任务 prompt
│   │   ├── <TASK>-long.md               # 长 prompt（包含设计提示）
│   │   └── <TASK>-short.md              # 短 prompt（只有问题描述）
│   └── repo/                            # 任务初始代码
├── experiment/<TASK>-<AGENT>-<PROMPT>-<DATE>/     # 单次实验
│   ├── <源代码, agent 修改后的 workspace>
│   ├── run_metadata.json                # 任务元数据
│   ├── claude_run.jsonl / codex_events.jsonl     # agent 运行日志
│   ├── eval_report-claude.md            # Claude 作为评估器的评分
│   ├── eval_report-codex.md             # Codex 作为评估器的评分
│   ├── eval_report-opencode-glm-5.1.md  # OpenCode+GLM 作为评估器的评分
│   └── eval_report-cursor.md            # Cursor 作为评估器的评分
└── scripts/eval/
    ├── all_dirs.txt                     # 496 个实验目录列表
    ├── eval_claude_batch.sh             # 各评估器批量脚本
    ├── eval_codex_batch.sh
    ├── eval_opencode_batch.sh
    └── eval_cursor_batch.sh
```

## 任务编号

- **C1-C5**：Huawei CANN 相关任务
- **K1-K4**：Kubernetes 相关任务
- **M1-M3**：MindSpeed 相关任务
- **T01-T50**：通用大型开源项目任务（Kafka, Kubernetes, 等）

## Agent 配置

| Config | 含义 |
|--------|------|
| `claude-opus-max` | Claude Opus via claude-yunwu CLI |
| `codex-gpt-5_4` | Codex CLI with GPT-5.4 |
| `cursor-composer2` | Cursor Agent with Composer 2 |
| `opencode-glm51` | OpenCode with GLM-5.1 via OpenRouter |

## 每个实验目录的结构

```
experiment/<TASK>-<AGENT>-<PROMPT_TYPE>-<DATE>/
├── run_metadata.json       # 实验元数据
├── claude_run.jsonl        # Claude/Cursor agent 的 trajectory 日志
├── eval_report-claude.md           # Claude 评估报告
├── eval_report-codex.md            # Codex 评估报告
├── eval_report-opencode-glm-5.1.md # OpenCode 评估报告
├── eval_report-cursor.md           # Cursor 评估报告
└── <其他源代码文件，agent 修改结果>
```

### run_metadata.json 格式

```json
{
  "task_id": "T01",
  "prompt_type": "long",
  "agent": "codex",
  "model": "gpt-5.4",
  "config": "codex-gpt-5_4",
  "run_date": "2026-04-18"
}
```

### 评估报告格式 (eval_report-*.md)

每个报告包含：
- **Verdict**：`### Verdict: PASS / PARTIAL / FAIL`
- **Scores**：三个维度各 0-5 分
  - `**A. Functional Correctness**: 3/5 — justification`
  - `**B. Completeness**: 2/5 — justification`
  - `**C. Behavioral Equivalence**: 2/5 — justification`
- **Summary** 和 **Analysis** 章节（纯文本）

## 评估流程

1. **Agent 运行**: 每个实验目录里有 agent（claude/codex/cursor/opencode）对 base_repo 做的修改
2. **Evaluator 评估**: 4 个 evaluator（claude-opus / codex-gpt-5.4 / opencode-glm-5.1 / cursor-composer-2）用一致的 rubric 打分
3. **产出报告**: 每个实验目录下最终有 4 份 `eval_report-*.md`

## 实验命名规则

```
<TASK_ID>-<AGENT_CONFIG>-<PROMPT_TYPE>-<DATE>
```

- TASK_ID: C1~C5 / K1~K4 / M1~M3 / T01~T50
- AGENT_CONFIG: claude-opus-max / codex-gpt-5_4 / cursor-composer2 / opencode-glm51
- PROMPT_TYPE: long 或 short
- DATE: 20260415 格式（运行日期）

## 总实验数

62 tasks × 2 prompts × 4 agents = **496 个实验**

- T01~T50: 50 tasks × 8 = 400
- C1~C5: 5 × 8 = 40
- K1~K4: 4 × 8 = 32
- M1~M3: 3 × 8 = 24

## 评估器报告文件名约定

每个实验目录下，4 个评估器各自产出自己的报告：

- `eval_report-claude.md` — Claude Code 作为评估器
- `eval_report-codex.md` — Codex (GPT-5.4) 作为评估器
- `eval_report-opencode-glm-5.1.md` — OpenCode+GLM 作为评估器
- `eval_report-cursor.md` — Cursor Composer-2 作为评估器

报告内结构：

```markdown
## Evaluation Report

**Evaluator**: ...

### Summary
...

### Verdict: PASS | PARTIAL | FAIL

### Scores
- **A. Functional Correctness**: 3/5 — ...
- **B. Completeness**: 4/5 — ...
- **C. Behavioral Equivalence**: 2/5 — ...

### Deterministic Coverage
- HW File Coverage: x/y = z%
- Function Coverage: x/y = z%

### Analysis
...

### Confidence: 0.72
```

## 批次评估脚本

每个 evaluator 对应一个批次脚本在 `scripts/eval/` 下：
- `eval_claude_batch.sh` — 用 claude-yunwu
- `eval_codex_batch.sh` — 用 codex exec
- `eval_opencode_batch.sh` — 用 opencode run
- `eval_cursor_batch.sh` — 用 cursor-agent

共用：
- `all_dirs.txt` — 496 个实验目录列表（每行一个绝对路径）
- 每个脚本跳过已存在的 report，所以可以反复重跑

## 评分 Schema

| 字段 | 含义 | 取值 |
|---|---|---|
| verdict | 总体判决 | PASS / PARTIAL / FAIL |
| A | 功能正确性 | 0-5 |
| B | 完整性 | 0-5 |
| C | 行为等价性 | 0-5 |

规则：
- PASS 条件：A≥4 AND B≥4 AND C≥3
- FAIL 条件：A≤1 OR destructive
- 其他 = PARTIAL

## 汇总脚本（未完成）

`aggregate_all.py` 的目标是：
- 读 `all_dirs.txt`
- 对每个目录读 4 个 eval_report 文件
- 提取 verdict / A / B / C
- 合并元数据（task_id, prompt_type, agent, date）
- 输出一个宽表 CSV：每个实验一行，含 4 组 (verdict, A, B, C)

输出示例列：
```
experiment, task_id, prompt_type, agent, run_date,
claude_verdict, claude_A, claude_B, claude_C,
codex_verdict,  codex_A,  codex_B,  codex_C,
opencode_verdict, opencode_A, opencode_B, opencode_C,
cursor_verdict, cursor_A, cursor_B, cursor_C
```

## 后续可能的分析

- 4 个 evaluator 之间的一致性（Cohen's kappa）
- 每个 evaluator 对每个 agent 的平均分
- long vs short prompt 影响
- task 难度分布（多少个任务所有人都 FAIL 或所有人都 PASS）