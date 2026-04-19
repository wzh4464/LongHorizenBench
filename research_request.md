# ASE 2026 Industry Showcase 投稿计划

## 会议信息
- 会议：ASE 2026（第 41 届 IEEE/ACM 自动化软件工程国际会议）
- 地点：Munich, Germany
- 截稿：2026-04-23 (AoE, UTC-12h)
- 通知：2026-06-21
- Camera-Ready：2026-08-03
- 投稿链接：https://ase26-industry.hotcrp.com/
- 格式：IEEE 10pt（`\\documentclass[10pt,conference]{IEEEtran}`），非盲审
- 页数：Long paper 10+2 / Short paper 5+1
- 新要求：必须包含 Data Availability Statement

## 评审标准
- Originality：推动工业实践的前沿
- Relevance：明确的工业应用价值
- Significance：相比现有工作的影响力
- Generalizability & Scalability：超越特定场景的适用性

## 对标论文（ASE 2025 Industry Showcase）
- `mundhra2025EvaluatingLLMsASML` — 工业闭源代码库 LLM 评估（ASML/TU Delft）
- `goldman2025CodeReviewComments` — LLM 代码审查效果量化（Atlassian）
- `mockus2025CodeImprovementMeta` — 代码改进工业实践（Meta）
- `liu2026EvaluatingLLMsAerospace` — LLM 能力边界评估（航天）
- `ji2025AutomatedPromptGeneration` — 自动提示生成工业验证（WeChat/Tencent）
- 共同特点：工业数据 + 系统 RQ + 可操作 findings；不强调方法创新，强调实践价值。

---

## Paper 1：MulVul 工业化 — 华为代码仓库漏洞检测实践

### 背景
MulVul（arXiv:2601.18847）是 Router-Detector 多智能体漏洞检测框架，核心组件：
- Router agent：预测 top-k 粗粒度漏洞类别
- Detector agents：针对具体 CWE 类型的专用检测
- Cross-Model Prompt Evolution：generator LLM 迭代优化提示，executor LLM 验证效果（消除自校正偏差）
- SCALE-based Contrastive Retrieval：RAG 增强 LLM 推理
- 原论文结果：PrimeVul C/C++ 上 34.79% Macro-F1（+41.5% 相对提升），130 CWE 类型
- 核心局限：仅在 PrimeVul C/C++ 上评估，未验证工业场景

### 定位与增量贡献
Industry Showcase 的增量价值：
- benchmark → 真实工业代码库的迁移验证
- C/C++ → 华为多语言仓库的扩展
- 工业级 findings：真实漏洞发现 + 误报模式分析

### 建议论文结构（Long paper 10+2）
- Introduction：MulVul 简介 + 工业部署动机（企业级代码库的独特挑战）
- Background：华为代码仓库概况（规模、语言分布、安全流程）+ MulVul 架构回顾
- Industrial Adaptation：MulVul 在华为的适配：CWE 类型调整、RAG 知识库定制、Router 重训练
- Empirical Study Design：RQ 设计 + 评估方法
- Results & Findings：核心发现 + 案例分析
- Discussion & Lessons Learned：工业部署经验、与现有静态分析工具对比
- Threats & Data Availability

### 建议 RQ
- RQ1 (Effectiveness)：MulVul 在华为真实代码库上的漏洞检测精度如何？与华为现有静态分析工具（CodeCheck 等）相比如何？
- RQ2 (Generalizability)：从 PrimeVul C/C++ 迁移到华为多语言仓库后，Router-Detector 架构的表现如何？哪些 CWE 类型迁移效果好/差？
- RQ3 (Findings)：华为代码库中发现了哪些有价值的漏洞模式？MulVul 的主要误报/漏报类型是什么？
- RQ4 (Cost-Benefit)：工业部署中的 token 消耗、延迟、人工确认成本如何？

### 核心 Selling Points
- 真实漏洞案例：若在华为仓库中发现已确认的真实漏洞，这是最强 evidence
- 与现有工具互补性：MulVul 能发现哪些 CodeCheck/Coverity 发现不了的漏洞
- 跨语言/跨仓库发现：原论文仅 C/C++；Java/Go 上结果是全新贡献
- 误报分析：工业界高度关注 false positive rate，误报分类和原因分析极有价值

### 风险与对策
- 华为数据脱敏要求 → 提前与合规团队确认可公开统计粒度；使用匿名化代码片段
- 实验规模不够大 → 聚焦典型仓库（如 OpenHarmony），确保数量级合理
- 真实漏洞发现数量少 → 转向能力分析视角：哪些类型检测好/差、原因是什么

---

## Paper 2：Coding Agent 在企业级仓库 Feature 实现中的实践

### 核心论点（v3）
Thesis：当前 Coding Agent 尚不具备独立完成企业级长程 Feature 实现的能力，但 Harness Engineering（编译反馈、迭代验证、结构化约束）是弥合差距的有效工程方向。

叙事弧线：
- 现状判断 → 证据呈现 → 根因分析 → 改进方向
- “Agent 还不行” → “最优配置仅 67%” → “哪里不行、为什么” → “Harness 有效但不够”

建议标题：
- `Not Ready Yet: An Industrial Assessment of Coding Agents for Feature Implementation and the Promise of Harness Engineering`

### 定位
工业能力评估 + 改进方向报告：在两类企业级仓库（K8s、CANN）上的系统实验，论证当前 Coding Agent 在长程 Feature 实现任务上的能力不足，分析根因，并展示 Harness Engineering 作为工程改进方向的有效性和局限。

### 核心立场
- Agent 独立完成：最优配置下仅达 67%，缺失 API 规范、feature gate、扩展性设计等工程关键环节 → 不可用于生产
- Harness Engineering 的价值：迭代验证（Loops）一致提升 13–14pp → 有效但不够，仍有 33% 差距
- 差距本质：不是“代码写得不好”，而是“缺乏工程判断”——API 设计、向后兼容、feature 生命周期管理等需要架构级思维的环节
- 与 SWE-bench 的关键区分：SWE-bench 主要是 bug fix 与小规模修改；本文关注 Feature 级实现（跨多文件、需 API 设计、feature gate、测试），工程复杂度发生质变

### Harness Engineering 定义
通过工程手段（编译反馈循环、测试验证、结构化输出约束、CI 集成）增强 Agent 执行能力的方法，区别于模型层面的改进（更大模型、微调、RLHF）。本文的 Harness (Loops) 是其一个实例。

### 已有初步数据（Kubernetes KEP-5365）
- OpenCode – GLM 5：
  - Case 1：26.7%，识别正确特性但放错位置，编译错误，无 feature gate
  - Case 2：40%，位置修正但用 flat 字段，feature gate 版本/owner 错误，无 validation 和测试
- Claude Code – Opus 4.6：
  - Case 1：26.7%，实现了完全错误的特性，与 KEP-5365 零语义重叠
  - Case 2：53.3%，feature gate 正确，含 field stripping 和单元测试；但 Kubelet 摘要获取方式错误，缺 validation 和 e2e
- CC – Opus 4.6 + Harness (Loops)：
  - Case 1：40%，部分实现正确特性，含部分测试，成功修改状态生成逻辑；无 feature gate，无 CRI API 扩展
  - Case 2：67%，feature gate 全部正确，有 field stripping 和单元测试，增加部分验证逻辑、OpenAPI 生成、client-go apply 等版本化特性，但 API 规范和扩展性与人类工程师仍有差距

### 初步发现
- 计划粒度与完成度强正相关：详细计划 vs 简述，所有 agent 提升 13–27pp，且更强模型受益更大
- 迭代验证（Loops）具有一致优势：两种输入下都取得最高分
- 语义理解仍是瓶颈：Opus 4.6 无 Harness 在 Case 1 中实现了完全错误的特性
- 67% 天花板：最优配置下 API 规范和扩展性仍有差距

### 论文结构（Long paper 10+2）
1. Introduction
2. Industrial Context
3. Study Design
4. Results: The Gap
5. Root Cause Analysis
6. Harness Engineering
7. Related Work
8. Threats + Data Availability

### RQ 设计
- RQ1 (Readiness Assessment)：当前 Coding Agent 能否独立完成企业级仓库的 Feature 实现任务？在不同 agent 配置和输入粒度下，实现完成度和工程质量如何？
- RQ2 (Failure Diagnosis)：Agent 在 Feature 实现中失败的根因是什么？哪些是模型能力问题，哪些是工程问题？
- RQ3 (Harness Effectiveness)：Harness Engineering（迭代验证、结构化输入）在多大程度上弥合了差距？其有效边界在哪里？
- RQ4 (Practical Implications)：对于企业团队，在什么条件下引入 Agent 辅助 Feature 实现是值得的？Harness Engineering 的投入产出比如何？

### 任务设计
- 总计 9 个任务：K8s 4 + CANN 5
- 语言覆盖：Go / C++ / Ascend C / Python
- 复杂度覆盖：Low → High

#### K8s 任务
- K1 / KEP-4369 / PR #123385 / 13 文件 / +1,064 / Low
- K2 / KEP-3998 / PR #123412 / 35 文件 / +3,873 / Medium
- K3 / KEP-5365 / PR #132807 / 49 文件 / +11,107 / Medium
- K4 / KEP-4601 / PR #125571 / 98 文件 / +6,794 / High

#### CANN 任务
- C1 / PR #308 / cann-ops-adv / Bug Fix / 1 文件 / +3/-3 / Low
- C2 / PR #675 / cann-ops / Bug Fix / 4 文件 / +9/-24 / Low
- C3 / PR #24373 / torch_npu / 框架适配 / 2 文件 / +41/-4 / Medium
- C4 / PR #651 / cann-ops / 新算子（Exp）/ 25 文件 / +1,173 / Medium
- C5 / PR #690 / cann-ops / 新算子（reduce_sum_v2）/ 34 文件 / +3,833 / High

### 三模式对比
- 模式 A：纯人工（Ground Truth）→ 从项目管理系统 / git history 获取实际工时
- 模式 B：Agent 独立完成 → 当前实验数据（覆盖率/实现程度评分）
- 模式 C：人机协作 → Agent 生成初稿 → 工程师修正 → 提交；记录修正时间、改动行数、改动类型

### 五维度评估框架
- 语义正确性（30%）：做对了吗？
- 代码完整性（25%）：做全了吗？
- 可编译/可运行（15%）：能跑吗？
- 测试覆盖（15%）：能验证吗？
- 代码质量（15%）：能合入吗？

### 实验变量
- Agent 配置（3）：OpenCode(GLM 5) / Claude Code(Opus 4.6) / Claude Code + Harness (Loops)
- 输入粒度（2）：简述 / 详细计划
- 任务（8–10）：K8s × 3–4；CANN × 4–5

### Threats to Validity（关键点）
- OpenCode+GLM 5 vs Claude Code+Opus 4.6 同时改变了 agent 框架与底层模型，属于产品级对比而非纯模型对比
- 论文中应将其定位为“工业界可获得 agent 工具对比”
- Claude Code vs Claude Code + Harness 的对比是干净对比，这组结论最强

### 已收集证据
- 人工工时基线：已从 git history 提取
- CANN 仓库任务选取：已完成
- K8s KEP 任务选取：已完成

### 仍需补充证据
P0（阻塞投稿）
- 团队内部 Industrial Context：团队规模、业务痛点
- 人机协作实验（至少 2–3 个 Case）

P1（显著提升质量）
- Token 成本 / API 延迟数据
- 工程师定性反馈
- CANN 任务执行：在选定 5 个 PR 上跑 agent 实验

P2（锦上添花）
- 推理衰减曲线（步骤数 vs 正确率）
- 上下文窗口饱和阈值

### Harness Engineering 章节设计
- 6.1 定义与分类：输出侧 / 输入侧 / 过程侧 Harness
- 6.2 已验证效果：Loops +13–14pp；详细计划 +13–27pp；两者组合 26.7%→67%
- 6.3 33% 差距分析：当前 harness 能解决什么，不能解决什么
- 6.4 路线图：短/中/长期 harness 类型、预期效果与实现难度

### 核心 Selling Points
- 明确的能力边界判定：首次在企业级 Feature 实现任务上系统评估 coding agent，结论清晰——“Not Ready Yet”
- 模型问题 vs 工程问题的分离
- Harness Engineering 的量化验证
- 跨仓库证据：K8s + CANN
- Harness Engineering 路线图

### 风险与对策
- 人机协作实验数据不足 → 至少保证 2–3 个 Case 有工程师参与修正记录
- CANN 任务来不及做 → 备选为聚焦 K8s，CANN 仅作 1–2 个补充
- 人工工时基线难获取 → git log 估算 + 工程师访谈
- 数据脱敏 → CANN、K8s 均为开源仓库，合规风险较低

---

## 时间线（6 周，截止 2026-04-23）
- W1：MulVul 跑通华为仓库实验；整理已有 K8s 数据并从 CANN 选任务
- W2：MulVul 收集结果、确认 Findings；Paper 2 执行 CANN 实验 + 人机协作实验（P0）
- W3：MulVul 写 Results + Findings；Paper 2 收集 Industrial Context + 人工工时基线
- W4：两篇论文都完成完整初稿
- W5：内部审阅 + 修改
- W6：最终润色 + 提交

## Data Availability Statement 指南
### 模式 A：部分公开（推荐）
The replication package, including anonymized experimental results, evaluation scripts, and the adapted prompts, is publicly available at [Zenodo DOI]. The proprietary source code from [Company] cannot be shared due to confidentiality agreements. However, we provide anonymized code snippets and statistical summaries sufficient to reproduce the analysis.

### 模式 B：仅脚本公开
Due to the proprietary nature of [Company]'s codebase, the raw data cannot be disclosed. Our evaluation framework, analysis scripts, and anonymized aggregate results are available at [Zenodo DOI]. We provide detailed descriptions of the data characteristics to support replication on similar industrial datasets.

### 模式 C：无法公开
The datasets used in this study are proprietary to [Company] and cannot be made publicly available due to intellectual property and security constraints. We provide sufficient methodological detail and aggregate statistics in this paper to enable independent replication of our approach on comparable industrial codebases.

### 最佳实践
- 创建 Zenodo 仓库并生成 DOI
- 上传：评估脚本、分析代码、匿名化实验结果、可公开提示模板、README 与复现步骤
- 在论文中明确区分可公开部分（工具、脚本、统计）与不可公开部分（源码、漏洞细节）
