# Long-Horizon Task 学术定义与本基准任务分类

## 一、学术定义（2024-2026 年主流基准）

### SWE-Bench Pro (2025, Scale AI) — 代码基准中最权威的 long-horizon 定义

| 指标 | 阈值 |
|------|------|
| 最少修改行数 | **≥10 LOC** （< 10 LOC 的任务被当作 trivial 删除） |
| 平均修改行数 | **107.4 行** |
| 平均涉及文件数 | **4 文件** |
| 人力完成时间 | **"hours to days"** |
| 总任务数 | 1,865 个 |

**关键摘录：**
> "We exclude trivial edits (<10 LOC) and retain only tasks that require substantial, multi-file modifications."

来源：[arXiv:2509.16941](https://arxiv.org/abs/2509.16941)

### METR 时间窗口定义

来自 METR 2025 年报告 [Measuring AI Ability to Complete Long Tasks](https://metr.org/measuring-ai-ability-to-complete-long-tasks/):

| 模型 | 50% 成功率对应的人类耗时 |
|------|-----------------------|
| GPT-4 | ~5 分钟 |
| Claude 3.5 Sonnet | ~15-30 分钟 |
| Claude 3.7 Sonnet | ~1 小时 |
| o1 | ~1.5 小时 |

**通常"长周期"任务**：需要人类投入 **30 分钟到几天** 的代码工作。以这个角度看，本项目中所有任务都是长周期范围。

### NL2Repo-Bench (2026)
定义：repository-level 任务，要求从自然语言生成完整可安装的仓库，含测试。

## 评估"是否属于长程任务"的三条标准

1. **行数标准**（SWE-Bench Pro）：GT diff ≥ 10 行，最好 ≥ 100 行。
2. **多文件标准**：HW 文件数 ≥ 2。
3. **时间标准**（METR）：人类专家工作时间 ≥ 15 分钟。

---

## 二、本基准 62 个任务的分类

基于上述标准分类（GT_lines < 50 或 HW_files == 1 视为非严格长程任务）：

### ❌ 不满足"长程任务"定义的任务

| Task | GT lines | HW files | 理由 |
|------|---------|---------|------|
| **C1** | 17 | 1 | ≥10 LOC但单文件，且接近 SWE-Bench Pro "trivial" 阈值 |
| **T10** | 482 | **1** | 单文件修改不满足多文件标准（尽管行数够多）|

### ⚠️ 边界任务（符合最低要求但不典型）

| Task | GT lines | HW files | 理由 |
|------|---------|---------|------|
| M1 | 74 | 3 | 只有 74 行、3 文件，边界情况 |
| C2 | 107 | 4 | 正好达到 SWE-Bench Pro 平均值（107 行、4 文件），是最小合格长程任务 |
| M2 | 低 | - | 行数较少 |

### ✅ 典型 long-horizon 任务（绝大多数）

- **60/62** 任务满足 >= 10 LOC 且多文件
- **C1** (17 行, 1 HW 文件) 和 **T10** (482 行但 1 HW 文件) 是唯二有争议的

---

## 三、如果严格按 SWE-Bench Pro 标准筛选

| 筛选门槛 | 本数据集保留任务数 | 被删除 |
|----------|-----------------|--------|
| GT_lines ≥ 10 AND HW_files ≥ 2 | 60/62 | C1, T10 |
| GT_lines ≥ 100 AND HW_files ≥ 4 | 约 55/62 | C1, C2, M1, M2, T10, T37 |
| 强要求：GT_lines ≥ 100 AND HW_files ≥ 4 AND 多语言文件 | 约 45/62 | + 多 |

---

## 四、建议

- 如果定位为 "standard long-horizon benchmark"：**严格排除 C1 和 T10**（这 2 个违反多文件或 > 10 LOC 的要求）
- 如果定位更严格：M1/M2 (74/199 行) 也应考虑标为 "short-horizon" 对照组
- 剩余 60 个任务属于合格的长程任务，覆盖 ≥ 数百行、跨多文件、涉及多类目（C/K/M/T）

## 参考文献

- METR (2026) — ["Measuring AI Ability to Complete Long Tasks"](https://metr.org/)
- SWE-Bench Pro (2024) — arxiv 2509.16941
- OpenAI / Anthropic agent benchmark standards (2025)
