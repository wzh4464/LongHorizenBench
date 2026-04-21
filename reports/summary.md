# V2 Evaluation Summary

Generated: 2026-04-21 23:20:42
Source CSV: `reports/eval_scores_v2_long.csv`

Coverage: 62 tasks, 4 agent configs, 496 runs, 4 evaluators, 1984 evaluator judgments.

## Short Summary
- Agent ranking by mean score: 1. codex-gpt-5_4 (1.94), 2. claude-opus-max (1.89), 3. cursor-composer2 (1.69), 4. opencode-glm51 (1.39).
- Evaluator agreement: mean pairwise kappa 0.346 (fair), raw agreement 63.4%.
- Weakest complexity tier: medium with 0.0% pass votes and 1.87 mean score.
- Prompt effect: long has the higher mean score (1.93) in this aggregate.

## Pass Rate by Agent and Prompt
| agent | prompt | runs | eval judgments | pass rate | partial rate | fail rate | mean score |
| --- | --- | --- | --- | --- | --- | --- | --- |
| claude-opus-max | short | 62 | 248 | 0.8% | 49.2% | 50.0% | 1.69 |
| claude-opus-max | long | 62 | 248 | 5.2% | 63.7% | 31.0% | 2.09 |
| codex-gpt-5_4 | short | 62 | 248 | 1.6% | 48.8% | 49.6% | 1.73 |
| codex-gpt-5_4 | long | 62 | 248 | 7.7% | 57.3% | 35.1% | 2.15 |
| cursor-composer2 | short | 62 | 248 | 3.2% | 35.1% | 61.7% | 1.41 |
| cursor-composer2 | long | 62 | 248 | 4.8% | 56.0% | 39.1% | 1.97 |
| opencode-glm51 | short | 62 | 248 | 0.4% | 29.0% | 70.6% | 1.24 |
| opencode-glm51 | long | 62 | 248 | 2.0% | 41.9% | 56.0% | 1.53 |

## Mean Score by Agent
| rank | agent | runs | eval judgments | pass rate | mean score |
| --- | --- | --- | --- | --- | --- |
| 1 | codex-gpt-5_4 | 124 | 496 | 4.6% | 1.94 |
| 2 | claude-opus-max | 124 | 496 | 3.0% | 1.89 |
| 3 | cursor-composer2 | 124 | 496 | 4.0% | 1.69 |
| 4 | opencode-glm51 | 124 | 496 | 1.2% | 1.39 |

## Evaluator Agreement
| pair | shared runs | raw agreement | Cohen kappa |
| --- | --- | --- | --- |
| claude/codex | 496 | 63.9% | 0.321 |
| claude/cursor | 496 | 74.8% | 0.525 |
| claude/glm | 496 | 67.9% | 0.398 |
| codex/cursor | 496 | 64.9% | 0.332 |
| codex/glm | 496 | 42.7% | 0.135 |
| cursor/glm | 496 | 65.9% | 0.363 |

## Complexity Breakdown
| complexity | agent | runs | eval judgments | pass rate | mean score |
| --- | --- | --- | --- | --- | --- |
| easy | claude-opus-max | 6 | 24 | 50.0% | 3.40 |
| easy | codex-gpt-5_4 | 6 | 24 | 41.7% | 3.18 |
| easy | cursor-composer2 | 6 | 24 | 37.5% | 3.01 |
| easy | opencode-glm51 | 6 | 24 | 20.8% | 2.42 |
| medium | claude-opus-max | 8 | 32 | 0.0% | 1.69 |
| medium | codex-gpt-5_4 | 8 | 32 | 0.0% | 2.01 |
| medium | cursor-composer2 | 8 | 32 | 0.0% | 2.08 |
| medium | opencode-glm51 | 8 | 32 | 0.0% | 1.70 |
| hard | claude-opus-max | 110 | 440 | 0.7% | 1.82 |
| hard | codex-gpt-5_4 | 110 | 440 | 3.0% | 1.87 |
| hard | cursor-composer2 | 110 | 440 | 2.5% | 1.59 |
| hard | opencode-glm51 | 110 | 440 | 0.2% | 1.31 |
