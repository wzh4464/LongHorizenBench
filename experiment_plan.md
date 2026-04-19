# ASE 2026 Paper 2 — Experiment Plan

## 1. Task Registry (Frozen)

| ID | Repo | Source Repo Path | GT Commit | Parent Commit | Complexity | Files | Lines | Lang |
|----|------|-----------------|-----------|---------------|-----------|-------|-------|------|
| C1 | cann-ops-adv | `/home/jie/codes/cann-ops-adv` | `888d214` | `f722d9d` | Low | 1 | +3/-3 | C++ |
| C2 | cann-ops | `/home/jie/codes/cann-ops` | `a8b1e873` | `83a20f8d` | Low | 4 | +9/-24 | C++ |
| C3 | torch_npu | `/home/jie/codes/torch_npu` | `94260135a` | `eed8f282` | Medium | 9 | +637/-145 | Python |
| C4 | cann-ops | `/home/jie/codes/cann-ops` | `a4abcf27` | `f016f674` | Medium | 24 | +1,273 | C++/AscendC |
| C5 | cann-ops | `/home/jie/codes/cann-ops` | `3bf6bea9` | `eeb9289c` | High | 27 | +3,372 | C++/AscendC |
| M1 | MindSpeed | `/home/jie/codes/MindSpeed` | `e455517` | `47a5482` | Low | 3 | +19/-8 | Python |
| M2 | MindSpeed | `/home/jie/codes/MindSpeed` | `596b96b` | `cc7f2e1f` | Medium | 6 | +150/-1 | Python |
| M3 | MindSpeed | `/home/jie/codes/MindSpeed` | `102c3f3` | `6919aae8` | High | 10 | +1,115/-113 | Python |
| K3 | kubernetes | `/home/jie/codes/kubernetes` | PR #132807 | TBD | Medium | 49 | +11,107 | Go |

> C3: NPU Graph op handlers 从硬编码 dispatch 重构为 Registry + Template Method 模式。9 文件含 5 源码 + 1 测试 + 2 JSON schema + 1 init。有新增（handlers 模块）也有重构（graphs.py 300 行重写），真正的 Medium 复杂度。

---

## 2. Experiment Matrix

### 2.1 Agent Configurations

| Config ID | Agent | Model | Harness | 备注 |
|-----------|-------|-------|---------|------|
| A1 | Claude Code | Sonnet | None | 已完成 7 tasks × 2 prompts（无 C3） |
| A2 | Claude Code | Opus 4.6 | None | 需新跑 8 tasks |
| A3 | Claude Code | Opus 4.6 | Loops (语法/结构验证迭代) | 需新跑 8 tasks，论文核心对比组 |

> A1 vs A2 = 模型能力对比（Sonnet vs Opus），A2 vs A3 = Harness 效果对比（干净变量）
> OpenCode+GLM5 仅用 K3 已有数据作补充说明，不再全面跑
> ⚠️ 无 Ascend 编译环境：A3 Loops 不使用编译反馈，改用语法检查 + 结构验证（见 §4.3）

### 2.2 Prompt Granularity

| Prompt ID | 描述 | 来源 |
|-----------|------|------|
| short | 一句话任务描述 | `experiment_prompts.md` Short Prompt |
| long | 详细计划含目录/文件/逻辑要求 | `experiment_prompts.md` Long Prompt |

### 2.3 Full Matrix

每个 cell = 1 次实验 = 1 个独立实验仓库 + 1 份 eval_report

| Task | A1-short | A1-long | A2-short | A2-long | A3-short | A3-long |
|------|:--------:|:-------:|:--------:|:-------:|:--------:|:-------:|
| C1 | ✅ done | ✅ done | 🔲 new | 🔲 new | 🔲 new | 🔲 new |
| C2 | ✅ done | ✅ done | 🔲 new | 🔲 new | 🔲 new | 🔲 new |
| C3 | — | — | 🔲 new | 🔲 new | 🔲 new | 🔲 new |
| C4 | ✅ done | ✅ done | 🔲 new | 🔲 new | 🔲 new | 🔲 new |
| C5 | ✅ done | ✅ done | 🔲 new | 🔲 new | 🔲 new | 🔲 new |
| M1 | ✅ done | ✅ done | 🔲 new | 🔲 new | 🔲 new | 🔲 new |
| M2 | ✅ done | ✅ done | 🔲 new | 🔲 new | 🔲 new | 🔲 new |
| M3 | ✅ done | ✅ done | 🔲 new | 🔲 new | 🔲 new | 🔲 new |
| K3 | ✅ (GLM5) | ✅ (GLM5) | ✅ done | ✅ done | ✅ done | ✅ done |

**总计**：14 A1 已完成 + 32 新实验 (A2×16 + A3×16) = 46 实验（+ K3 已有 6 个 = 52）
**最小可投稿集**：A2 + A3 各 8 tasks × long prompt only = 16 新实验
**C3 无 A1 数据**：C3 仅跑 A2/A3（论文核心对比），A1 Sonnet 数据可选补

---

## 3. Repo Setup Protocol

### 3.1 命名约定

```
/home/jie/codes/{source_repo}-{task_id}-{config}-{prompt}
```

示例：
- `cann-ops-C4-A2-long` — C4 任务，Opus 4.6 无 Harness，详细 prompt
- `MindSpeed-M2-A3-short` — M2 任务，Opus 4.6 + Loops，简短 prompt

> 已有 A1 实验仍用旧命名（`cann-ops-C4-long`），不改

### 3.2 创建实验仓库

```bash
# 通用模板
create_experiment_repo() {
    local SRC_REPO=$1     # e.g., /home/jie/codes/cann-ops
    local TASK_ID=$2      # e.g., C4
    local CONFIG=$3       # e.g., A2
    local PROMPT=$4       # e.g., long
    local PARENT=$5       # e.g., f016f674

    local DEST="/home/jie/codes/$(basename $SRC_REPO)-${TASK_ID}-${CONFIG}-${PROMPT}"

    # 克隆并 checkout 到 parent commit
    git clone --no-checkout "$SRC_REPO" "$DEST"
    cd "$DEST"
    git checkout "$PARENT"

    echo "Created: $DEST at $PARENT"
}
```

### 3.3 批量创建脚本

```bash
#!/bin/bash
# setup_experiments.sh

CONFIGS=("A2" "A3")
PROMPTS=("short" "long")

# Task definitions: source_repo task_id parent_commit
TASKS=(
    "/home/jie/codes/cann-ops-adv C1 f722d9d"
    "/home/jie/codes/cann-ops C2 83a20f8d"
    "/home/jie/codes/torch_npu C3 eed8f282"
    "/home/jie/codes/cann-ops C4 f016f674"
    "/home/jie/codes/cann-ops C5 eeb9289c"
    "/home/jie/codes/MindSpeed M1 47a5482"
    "/home/jie/codes/MindSpeed M2 cc7f2e1f"
    "/home/jie/codes/MindSpeed M3 6919aae8"
)

for task_line in "${TASKS[@]}"; do
    read -r SRC TASK PARENT <<< "$task_line"
    for config in "${CONFIGS[@]}"; do
        for prompt in "${PROMPTS[@]}"; do
            DEST="/home/jie/codes/$(basename $SRC)-${TASK}-${config}-${prompt}"
            if [ -d "$DEST" ]; then
                echo "SKIP: $DEST already exists"
                continue
            fi
            git clone --no-checkout "$SRC" "$DEST"
            git -C "$DEST" checkout "$PARENT"
            echo "CREATED: $DEST"
        done
    done
done
```

---

## 4. Agent Execution Protocol

### 4.1 执行环境

| Config | 启动命令 | 模型 | 特殊设置 |
|--------|---------|------|---------|
| A2 | `claude --model opus` | claude-opus-4-6 | 无 |
| A3 | `claude --model opus` | claude-opus-4-6 | 开启 Loops（编译反馈迭代）|

### 4.2 执行步骤

对每个实验仓库：

```
1. cd /home/jie/codes/{repo}-{task}-{config}-{prompt}
2. 启动 Claude Code（对应 config 模型）
3. 粘贴对应 prompt（从 experiment_prompts.md 取 short 或 long）
4. 等待 agent 完成（不干预）
5. agent 结束后，不 commit，保留 uncommitted 状态
```

### 4.3 A3 (Loops) 的特殊处理

无 Ascend 编译环境，Loops harness 改用**语法检查 + 结构验证**替代编译反馈。

#### 验证命令（按语言）

| 语言 | 验证命令 | 检查内容 |
|------|---------|---------|
| C++ (CANN) | `find src/contrib/math/exp -name '*.cpp' -o -name '*.h' \| head -50` + 人工检查结构 | 文件是否齐全、目录结构是否正确、头文件引用是否存在 |
| Python (MindSpeed/torch_npu) | `python -m py_compile <file>` + `python -c "import ast; ast.parse(open('<file>').read())"` | 语法正确性 |
| Python (MindSpeed/torch_npu) | `cd <repo> && python -m pytest --collect-only 2>&1` | 测试文件是否可发现 |
| Go (K3) | `go vet ./...` + `go build ./...` | 编译 + 静态检查 |

#### A3 Loops 协议（无编译环境版）

1. Agent 完成首次实现
2. 执行对应语言的验证命令
3. 将验证错误反馈给 agent（语法错误、缺失文件、import 错误等）
4. Agent 修复后再次验证
5. 最多迭代 3 轮，或验证通过则停止
6. 记录每轮反馈内容和 agent 响应

> 论文中需明确说明：A3 Harness 为"语法/结构验证循环"而非完整编译，属于轻量级 harness。这与 K3 已有数据中的 Go 编译反馈形成对比，可作为 harness 强度的额外分析维度。

### 4.4 记录要求

每次实验需记录：
- 开始/结束时间
- Token 消耗（从 Claude Code session 提取）
- 迭代轮数（A3 only）
- Agent 是否中途报错/放弃
- 最终 `git status` 输出

---

## 5. Evaluation Protocol (基于 diff-eval)

### 5.1 核心思路

每个实验仓库的评估等价于一次 diff-eval：
- **Base commit** = parent commit（实验仓库的 HEAD）
- **Generated patch** = `git diff HEAD` + untracked files（排除 `.serena/`, `.claude/`）
- **Ground truth patch** = `git diff parent..GT_commit`（在源仓库中）
- **Requirements** = `experiment_prompts.md` 中对应的 prompt

### 5.2 单次评估流程

```bash
REPO="/home/jie/codes/{experiment_repo}"
SRC="/home/jie/codes/{source_repo}"
PARENT="{parent_commit}"
GT="{gt_commit}"

# Step 1: 提取 generated patch
git -C "$REPO" diff HEAD > /tmp/generated.patch
git -C "$REPO" ls-files --others --exclude-standard \
    | grep -v '^\.\(serena\|claude\)' > /tmp/generated_untracked.txt

# Step 2: 提取 ground truth patch
git -C "$SRC" diff "$PARENT".."$GT" > /tmp/ground_truth.patch

# Step 3: 文件级对比
git -C "$REPO" diff HEAD --name-only > /tmp/gen_files.txt
cat /tmp/generated_untracked.txt >> /tmp/gen_files.txt
git -C "$SRC" diff "$PARENT".."$GT" --name-only > /tmp/gt_files.txt

# Step 4: 计算 coverage
comm -12 <(sort /tmp/gen_files.txt) <(sort /tmp/gt_files.txt) > /tmp/overlap.txt
echo "Coverage: $(wc -l < /tmp/overlap.txt) / $(wc -l < /tmp/gt_files.txt)"
```

### 5.3 自动化评估脚本

```bash
#!/bin/bash
# eval_all.sh — 批量运行 diff-eval 评估

RESULTS_DIR="/home/jie/EvoScientist/eval_results"
mkdir -p "$RESULTS_DIR"

# 任务定义: experiment_repo source_repo parent gt_commit task_id config prompt
EXPERIMENTS=(
    # A1 已完成（eval 已有，此处仅跑 coverage stats 对齐）
    "cann-ops-adv-C1-long cann-ops-adv f722d9d 888d214 C1 A1 long"
    "cann-ops-adv-C1-short cann-ops-adv f722d9d 888d214 C1 A1 short"
    "cann-ops-C2-long cann-ops 83a20f8d a8b1e873 C2 A1 long"
    "cann-ops-C2-short cann-ops 83a20f8d a8b1e873 C2 A1 short"
    "cann-ops-C4-long cann-ops f016f674 a4abcf27 C4 A1 long"
    "cann-ops-C4-short cann-ops f016f674 a4abcf27 C4 A1 short"
    "cann-ops-C5-long cann-ops eeb9289c 3bf6bea9 C5 A1 long"
    "cann-ops-C5-short cann-ops eeb9289c 3bf6bea9 C5 A1 short"
    "MindSpeed-M1-long MindSpeed 47a5482 e455517 M1 A1 long"
    "MindSpeed-M1-short MindSpeed 47a5482 e455517 M1 A1 short"
    "MindSpeed-M2-long MindSpeed cc7f2e1f 596b96b M2 A1 long"
    "MindSpeed-M2-short MindSpeed cc7f2e1f 596b96b M2 A1 short"
    "MindSpeed-M3-long MindSpeed 6919aae8 102c3f3 M3 A1 long"
    "MindSpeed-M3-short MindSpeed 6919aae8 102c3f3 M3 A1 short"
    # A2/A3 新实验（跑完后追加，命名如 torch_npu-C3-A2-long 等）
)

for exp_line in "${EXPERIMENTS[@]}"; do
    read -r EXP_REPO SRC_REPO PARENT GT TASK CONFIG PROMPT <<< "$exp_line"

    REPO="/home/jie/codes/$EXP_REPO"
    SRC="/home/jie/codes/$SRC_REPO"
    OUT="$RESULTS_DIR/${TASK}-${CONFIG}-${PROMPT}"

    mkdir -p "$OUT"

    # Generated file list
    {
        git -C "$REPO" diff HEAD --name-only 2>/dev/null
        git -C "$REPO" ls-files --others --exclude-standard 2>/dev/null \
            | grep -v '^\.\(serena\|claude\)'
    } | sort -u > "$OUT/gen_files.txt"

    # Ground truth file list
    git -C "$SRC" diff --name-only "$PARENT".."$GT" 2>/dev/null \
        | sort -u > "$OUT/gt_files.txt"

    # Coverage stats
    OVERLAP=$(comm -12 "$OUT/gen_files.txt" "$OUT/gt_files.txt" | wc -l)
    GT_COUNT=$(wc -l < "$OUT/gt_files.txt")
    GEN_COUNT=$(wc -l < "$OUT/gen_files.txt")

    # Line stats
    GEN_ADD=$(git -C "$REPO" diff HEAD --numstat 2>/dev/null | awk '{s+=$1}END{print s+0}')
    GEN_DEL=$(git -C "$REPO" diff HEAD --numstat 2>/dev/null | awk '{s+=$2}END{print s+0}')
    GT_ADD=$(git -C "$SRC" diff --numstat "$PARENT".."$GT" 2>/dev/null | awk '{s+=$1}END{print s+0}')
    GT_DEL=$(git -C "$SRC" diff --numstat "$PARENT".."$GT" 2>/dev/null | awk '{s+=$2}END{print s+0}')

    # Save summary
    cat > "$OUT/coverage.json" << EOFJ
{
    "task": "$TASK",
    "config": "$CONFIG",
    "prompt": "$PROMPT",
    "gen_files": $GEN_COUNT,
    "gt_files": $GT_COUNT,
    "overlap_files": $OVERLAP,
    "coverage_rate": $(echo "scale=4; $OVERLAP / $GT_COUNT" | bc 2>/dev/null || echo "0"),
    "gen_lines_added": $GEN_ADD,
    "gen_lines_deleted": $GEN_DEL,
    "gt_lines_added": $GT_ADD,
    "gt_lines_deleted": $GT_DEL
}
EOFJ

    echo "$TASK-$CONFIG-$PROMPT: $OVERLAP/$GT_COUNT files covered"
done
```

### 5.4 语义评估（人工 + LLM 辅助）

数据级 coverage 只是第一步。对每个实验还需 diff-eval 的语义评估：

```
对每个实验仓库，执行 Claude Code 中的 /diff-eval 流程：

输入：
  - Repo path: /home/jie/codes/{experiment_repo}
  - Ground truth: git diff {parent}..{gt_commit} in source repo
  - Requirements: experiment_prompts.md 中对应 prompt

输出 eval_report.md，包含：
  - A/B/C 评分 (0-5)
  - Verdict (PASS/PARTIAL/FAIL)
  - 文件级覆盖表
  - Requirements checklist
  - 失败根因分析
```

### 5.5 Scoring Rubric（统一标准）

直接使用 diff-eval 的评分标准：

| 维度 | 描述 | 0-5 量表 |
|------|------|---------|
| **A. Functional Correctness** | 是否正确解决了问题/实现了功能 | 0=完全错误 → 5=语义完全正确 |
| **B. Completeness & Coverage** | 是否覆盖了所有需要的文件/逻辑/测试 | 0=严重缺失 → 5=完全覆盖 |
| **C. Behavioral Equivalence** | 与 Ground Truth 的行为等价程度 | 0=完全偏离 → 5=语义等价 |

Verdict 判定规则：
- **PASS**: A≥4 AND B≥4 AND C≥3
- **FAIL**: A≤1 OR 引入破坏性变更
- **PARTIAL**: 其他情况

### 5.6 已有 A1 数据

A1 的 14 个实验已用 diff-eval 评估，评分直接复用（`experiment_results.md`）。A2/A3 新实验同样使用 diff-eval，评估方法一致，可直接对比。

---

## 6. 数据收集 Schema

### 6.1 per-run record

```json
{
    "task_id": "C4",
    "config": "A2",
    "prompt": "long",
    "repo_path": "/home/jie/codes/cann-ops-C4-A2-long",
    "start_time": "2026-03-19T10:00:00",
    "end_time": "2026-03-19T10:45:00",
    "duration_min": 45,
    "token_input": 50000,
    "token_output": 12000,
    "iterations": 1,
    "agent_error": false,
    "scores": {
        "A_functional": 4,
        "B_completeness": 4,
        "C_equivalence": 3
    },
    "verdict": "PASS",
    "coverage": {
        "gen_files": 21,
        "gt_files": 24,
        "overlap": 21,
        "rate": 0.875
    }
}
```

### 6.2 Aggregation Table (论文 Table 2)

| Task | Complexity | A1-short | A1-long | A2-short | A2-long | A3-short | A3-long |
|------|-----------|---------|---------|---------|---------|---------|---------|
| C1 | Low | P 5/5/5 | P 5/5/5 | ... | ... | ... | ... |
| C2 | Low | Pa 3/2/1 | P 5/4/4 | ... | ... | ... | ... |
| ... | ... | ... | ... | ... | ... | ... | ... |

Legend: P=PASS, Pa=PARTIAL, F=FAIL, 数字=A/B/C scores

---

## 7. 特殊文件处理

### 7.1 排除项（不计入 coverage）

| 文件类型 | 示例 | 处理 |
|---------|------|------|
| 工具目录 | `.serena/`, `.claude/` | 排除 |
| Binary | `compress_activation_coloured.png` (M3) | 排除，单独标注 |
| 空文件 | `__init__.py`, `.gitkeep` | 计入但不比较内容 |
| 自动生成 | protobuf `*.pb.go`, openapi (K3) | 排除，单独统计 |

### 7.2 M3 特殊处理

M3 的 10 个 GT 文件中：
- 1 个 binary PNG — 排除，评估分母为 9
- 1 个空 `__init__.py` — 计入但仅检查是否创建
- 1 个文件删除 (`compress-dense.md`) — 检查 agent 是否也删除

---

## 8. Priority & Timeline

### Phase 0: 准备 [W1: 3/18-3/24]

1. **写 C3 experiment prompts** — short + long（参考 `94260135a` diff 内容）
2. **创建实验仓库** — 运行 `setup_experiments.sh`，生成 32 个新仓库
3. **写 `eval_all.sh`** — coverage stats 自动化脚本
4. **补跑 A1 × C3** — C3-A1-short + C3-A1-long（可选，补齐 A1 行）

### Phase 1: 核心实验 [W2-W3: 3/25-4/7]

优先级排序（按论文价值/实验时间 ratio）：

**Round 1（A2 vs A3, long prompt only — 最小可投稿集）**：
1. A2-long × 8 tasks — 无 Harness 对照组
2. A3-long × 8 tasks — Harness+详细 prompt，预期最好结果
3. 每完成一个 run，立即跑 diff-eval 评估

**Round 2（补 short prompt — 增强统计力）**：
4. A2-short × 8 tasks
5. A3-short × 8 tasks

> 如果时间不够：Round 2 仅选 C2/C4/M1/M3 四个代表性 task（覆盖所有复杂度）

### Phase 2: 分析 [W4: 4/8-4/14]

1. 汇总 aggregation table（合并 A1/A2/A3 所有数据）
2. 失败根因分类（failure taxonomy）
3. Harness delta 分析：A2 vs A3 每个 task 的提升量
4. 模型能力对比：A1(Sonnet) vs A2(Opus) 同 prompt 同 task

### Phase 3: 论文撰写 [W5: 4/14-4/20]

1. 填充 Results 表格和图
2. RCA + Harness Engineering 章节
3. Threats, Industrial Context, Data Availability

### Phase 4: 润色提交 [4/20-4/23]

---

## 9. 预估工作量

| 活动 | 数量 | 单次耗时 | 总计 |
|------|------|---------|------|
| 写 C3 prompts + 创建仓库 | 1 + 32 | 2h + 脚本 | ~2.5h |
| 运行 A2 实验 | 16 | 15-60 min | ~10h |
| 运行 A3 实验 | 16 | 30-90 min (含验证迭代) | ~16h |
| diff-eval 评估 (A2+A3) | 32 | 10 min | ~5.5h |
| 汇总分析 + failure taxonomy | 1 | 4h | 4h |
| **总计** | | | **~38h** |

> A2/A3 同一 task 的 short/long 可串行跑（共享仓库理解），不同 task 可并行（不同终端）
> Round 1 (long only, 16 runs) 约 2 天 wall-clock；Round 2 (short, 16 runs) 约 1.5 天

---

## 10. 风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| 无 Ascend 编译环境 | A3 所有 C++/AscendC 任务无法做编译反馈 | 统一使用语法/结构验证循环（§4.3）；论文明确标注 harness 强度 |
| Opus token 成本高 | 32 runs × 大 context 开销大 | Round 1 先跑 long (更高论文价值)，Round 2 short 按需补 |
| M3 binary 文件始终无法生成 | A2/A3 同样会缺 PNG | 评估时排除，论文中作为 limitation 讨论 |
| 某些实验 agent 报错/超时 | 缺数据 | 记录为 "agent error"，verdict = FAIL，保留在结果中 |
| C3 无 A1 基线 | A1 行 C3 列为空 | 可选补跑 A1×C3；或论文注明 C3 仅参与 A2/A3 对比 |
| A3 harness 强度不一致（Python 语法检查 vs Go 编译） | 跨语言 harness 效果不严格可比 | 论文 Threats 中讨论；K3(Go) 有编译级 harness 数据可做对比分析 |
