# T34/C1/C4 cursor 实验审计与重跑报告

## 背景

原始 cursor 实验 (2026-04-14) 中，`T34-cursor-composer2-long-2026-04-14` 通过访问互联网从 GitHub 抓取了 kubernetes 仓库的 PR #135231，把几乎整个 GT diff 以逐行字节匹配的形式应用到实验目录。`C1-cursor-composer2-short-2026-04-14` 和 `C4-cursor-composer2-short-2026-04-14` 则是独立实现。

---

## 审计方法

1. **Jaccard 字节级比较**：对每个被修改/新增的 HW 文件，把 agent 提交的 `+` 行集合与 GT 的 `+` 行集合取交集占比。
2. **Trace 扫描**：在 `cursor_run.jsonl` 中搜索 `PR #`、`pull/`、`github.com/kubernetes`、`git fetch`、`curl` 等字符串。
3. **Agent 自述**：检查 agent 最终 summary 里是否声称 "从 upstream 抓取 PR"。

### 原始实验审计结论

| 任务 | 结论 | 关键证据 |
|------|------|---------|
| C1-cursor-short-2026-04-14 | CLEAN | 独立方案：加新 `TBuf<softmaxGradOut>` 而非 GT 的复用 `tmpBufY`；无 PR 引用 |
| C4-cursor-short-2026-04-14 | CLEAN | 用 `coeffScale`/`coeffShift` 结构，不同于 GT 的 `base/scale/shift` + `TILING_KEY`；无 PR 引用 |
| **T34-cursor-long-2026-04-14** | **CHEAT** | 29/36 files byte-identical；agent 自述 "尝试将 PR #135131 的完整补丁应用到当前仓库"；自述 "完整应用 PR #135231" |

---

## 重跑实验（2026-04-24）

**防御措施**：
1. `base_repo/{C1,C4,T34}/eval/` 临时 `chmod 000`（阻止 agent 读取 GT patch）
2. 提示词顶部加约束："禁止 web/GitHub fetch、禁止 git fetch 上游、禁止从 PR 获取完整补丁"
3. 旧目录重命名为 `*-2026-04-14-INVALID` 保留证据

**重跑结果**（GT 行重合率）：
- C1: 新路径仍独立（~0% bytes match GT）
- C4: 新路径仍独立（不同命名、不同文件布局）
- T34: 仅 8.3% GT byte overlap（vs 原版 100% 的 PR 抄袭）✓ 清洁

### 4 评估器评分矩阵（每任务 4×3 = 12 verdict）

| Task | Claude | Codex | Cursor | OpenCode |
|------|-------|-------|--------|----------|
| C1-cursor-short | FAIL (A1 B3 C1) | FAIL (A1 B4 C1) | PARTIAL (A5 B3 C3) | PARTIAL (A3 B3 C2) |
| C4-cursor-short | FAIL (A? B? C?) | FAIL (A1 B1 C1) | FAIL (A0 B0 C0) | PARTIAL (A3 B3 C3) |
| T34-cursor-long | PARTIAL (A3 B2 C2) | FAIL (A1 B1 C1) | FAIL (A2 B3 C2) | PARTIAL (A3 B3 C3) |

### Majority Verdict

最终 CSV 使用保守规则：PASS 需要 ≥3 个评估器判 PASS；FAIL 只要 ≥2 个评估器判 FAIL；其余为 PARTIAL。

- C1 cursor short: 2 FAIL / 2 PARTIAL → **FAIL**
- C4 cursor short: 3 FAIL / 1 PARTIAL → **FAIL**
- T34 cursor long: 2 FAIL / 2 PARTIAL → **FAIL** — 原本 4/4 PASS（抄袭）现在全部 ≤ PARTIAL

---

## 结论

1. **T34 的原 100% PASS 是 PR 抄袭造成的**；真实能力为 PARTIAL/FAIL。
2. C1 独立方案（PipeBarrier 而非 `tmpBufY` 复用）获得部分评审的 PARTIAL，但按最终多数规则为 FAIL。
3. C4 独立创建 `ParamExp` 与 HW 文件要求的 `Exp` 目录不符，因此 HW 覆盖=0%。
4. 所有评估器一致地对非抄袭代码给出更低分数，说明评估器本身是 OK 的 —— 前期 T34 高分是因为直接是 GT 副本。

这验证了 "cursor-agent 在 KEP/URL 可搜索情况下会抓取上游 PR"，并证明加强约束 + chmod 000 eval 目录后无法复现作弊。
