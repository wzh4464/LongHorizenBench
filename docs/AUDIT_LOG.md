# 作弊审计日志

本表记录对疑似 GT 泄露的 (task, agent, prompt, date) 实验的人工审计。方法见 `.claude/skills/cheat-audit/SKILL.md`。

## 2026-03 批次 (cursor-composer2 初审)

| 实验 | 结论 | 证据 |
|------|------|------|
| `C1-cursor-composer2-short-2026-04-14` | ✔ 干净 | Agent 增加新 `TBuf<...> softmaxGradOutTmpBuffer` 并分配独立 UB；GT 则复用现存 `tmpBufY`。路径不同，逐行无一致。 |
| `C4-cursor-composer2-short-2026-04-14` | ✔ 干净 | Agent 实现用 `coeffScale/coeffShift` (ln(base) 预折叠)；GT 用 `base/scale/shift` + `SetTilingKey` 分支 kernel；kernel 行数与形状都不一致。 |
| `T34-cursor-composer2-long-2026-04-14` | ✘ **INVALID（抄袭）** | 结果 agent 明文在 `claude_run.jsonl` 写 "尝试将 PR #135231 的完整 patch 应用到当前仓库"。对 35 个 HW 文件中有 29 个文件的 +added 行 Jaccard = 1.00（字节级一致），剩余几个是 new-file（batch.go / signers.go / batch_test.go / ...）仍然字节相同。该实验重跑。|

## 处理结果

- **T34-cursor-long** 原始 PASS 已从最终统计中剔除，并于 2026-04-24 在加强约束后重跑。
- 同批次复核的 **C1-cursor-short** 和 **C4-cursor-short** 也一并重跑；三者在最终 `reports/eval_scores_v2_long.csv` 中均为非 PASS。
- 后续凡是 Kubernetes/KEP 相关任务，都应默认进行 trace 扫描和 upstream PR 泄漏审计。
