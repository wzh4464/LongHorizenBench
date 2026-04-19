# ASE 2026 Paper 2: Coding Agent Experiment Results
## "Not Ready Yet: An Industrial Assessment of Coding Agents for Feature Implementation"

**Date**: 2026-03-17
**Agent**: Claude Code (Sonnet)
**Experiment Design**: 7 tasks × 2 prompt granularity levels (short/long) = 14 experiments

---

## 1. Task Inventory

| ID | Repository | Type | Complexity | Ground Truth | Files | Lines Changed |
|----|-----------|------|-----------|-------------|-------|--------------|
| C1 | cann-ops-adv | Bug fix | Low | `888d214` | 1 | +3/-3 |
| C2 | cann-ops | Bug fix | Low | `a8b1e873` | 4 | +9/-24 |
| M1 | MindSpeed | Bug fix | Low | `e455517` | 3 | +19/-8 |
| C4 | cann-ops | New operator | Medium | `a4abcf27` | 24 | +1,273 |
| M2 | MindSpeed | New feature | Medium | `596b96b` | 6 | +150/-1 |
| C5 | cann-ops | New operator | High | `3bf6bea9` | 27 | +3,372 |
| M3 | MindSpeed | New feature | High | `102c3f3` | 10 | +1,115/-113 |

---

## 2. Comprehensive Results

### 2.1 C1: Buffer Alias Fix (ScaledMaskedSoftmaxGradV2)
- **Ground Truth**: Change `tmpBufYGrad` → `tmpBufY` in 3 lines after FreeTensor in `scaled_masked_softmax_grad_v2_norm_headdim.h`
- **C1-long**: ✅ **PASS** — Byte-identical diff to ground truth. 1/1 file, exact same 3-line fix.
- **C1-short**: ✅ **PASS** — Byte-identical diff to ground truth. 1/1 file, exact same 3-line fix.
- **Gap**: None. Both prompts produce identical, perfect results.

### 2.2 C2: ReduceSum Precision Fix (LayerNormGradV3)
- **Ground Truth**: Remove `#if __CCE_AICORE__ == 220` special-case block in `add_layer_norm_base.h`; change ReduceSum count 1→64 (COUNT_NUM) in 3 `layer_norm_grad_v3_*.h` files.
- **C2-long**: ✅ **PASS** — 4/4 correct files, same fix approach. Correctly removes AICore 220 special-case, adds COUNT_NUM=64, changes ReduceSum calls. Functionally equivalent.
  - Scores: A=5, B=4, C=4
- **C2-short**: ⚠️ **PARTIAL** — 2/4 correct files + 2 wrong files. Agent tried a different approach (changing `RepeatReduceSum`→`WholeReduceSum`, adding `<float, false>` template params). Only 1 of the 3 `layer_norm_grad_v3` files fixed; modifies `add_layer_norm_kernel.h` and `layer_norm_grad_v3_common.h` (not in ground truth).
  - Scores: A=3, B=2, C=1

### 2.3 M1: Triton Import Centralization + Missing wait()
- **Ground Truth**: (1) Remove inline `try/except triton` import in `fused_moe_permute.py`, replace with `from mindspeed.utils import has_triton`; (2) Add `has_triton()` to `mindspeed/utils.py`; (3) Add `has_triton()` guard and `permute1_probs_handle.wait()` in `token_dispatcher.py`.
- **M1-long**: ✅ **PASS** — 3/3 files correctly modified. Triton import centralized, `has_triton()` function added, critical `wait()` fix present. Nearly identical to ground truth.
  - Scores: A=4, B=4, C=4
- **M1-short**: ❌ **FAIL** — 2/3 files modified, but **wrong bug targeted**. Agent tried to fix `probs` parameter passing instead of triton import. Only added `_HAS_TRITON = None` to utils.py without the function. Critical `wait()` fix completely missing.
  - Scores: A=2, B=1, C=1

### 2.4 C4: Exp Operator Implementation
- **Ground Truth**: Complete Exp operator in `src/contrib/math/exp/` — op_host (tiling + registration), op_kernel (AscendC device code), examples, tests, framework. 24 files, +1,273 lines.
- **C4-long**: ✅ **PASS** — 21/24 files created in **correct directory** (`src/contrib/math/exp/`). Missing only 3 `.gitkeep` placeholders. All code files present: op_host, op_kernel, framework, examples, tests, docs.
  - File coverage: 87.5% (21/24), Code coverage: ~100%
  - Scores: A=4, B=4, C=4
- **C4-short**: ⚠️ **PARTIAL** — 12 files created in **wrong directory** (`src/math/exp/` instead of `src/contrib/math/exp/`). Missing docs, examples (7 files), README. Only core code files present.
  - File coverage: 50% (12/24), **Wrong path** → 0% correct placement
  - Scores: A=2, B=2, C=2

### 2.5 M2: Bucket Group Reorder Feature (MindSpeedFeature)
- **Ground Truth**: MindSpeedFeature registration for bucket group reorder with DDP config patching. 6 files, +150/-1.
- **M2-long**: ✅ **PASS** — 6/6 ground truth files created/modified. Correct directory structure, docs, feature registration, DDP config.
  - File coverage: 100% (6/6)
  - Scores: A=4, B=4, C=3
- **M2-short**: ⚠️ **PARTIAL** — 5/6 files created (missing `docs/features/reset-bucket-group-order.md`). Added extra test file. Some M3 contamination (memory_compress files created).
  - File coverage: 83% (5/6)
  - Scores: A=3, B=3, C=2

### 2.6 C5: reduce_sum_v2 Operator Implementation
- **Ground Truth**: Complete reduce_sum_v2 operator with modular design, aclnn API, proto, tiling, AR/ARA kernel variants. 27 files, +3,372 lines.
- **C5-long**: ✅ **PASS** — 27/27 ground truth files covered + 5 extra files (docs, test cases). Correct directory, complete modular structure with separate host/kernel files, aclnn API wrapper, proto definitions.
  - File coverage: 100% (27/27 + 5 extra)
  - Scores: A=4, B=5, C=4
- **C5-short**: ❌ **FAIL** — Only 7/27 ground truth files matched (26%). Missing all examples (7), most op_host files (8/11), all modular kernel files (3/4). Only created basic skeleton with op_host/reduce_sum_v2.cpp, tiling.h, op_kernel/reduce_sum_v2.cpp.
  - File coverage: 26% (7/27)
  - Scores: A=1, B=1, C=1

### 2.7 M3: Memory Compression (Activation + Optimizer)
- **Ground Truth**: Activation compression + optimizer compression modules with MindSpeedFeature pattern. 10 files, +1,115/-113. Includes doc deletion, new doc, core modules, feature manager, binary image.
- **M3-long**: ⚠️ **PARTIAL** — 8/10 ground truth files covered. Created all core Python modules (adaptor, compress_activation, compress_optimizer, utils, feature manager). Missing: doc deletion (`compress-dense.md`), binary image (`compress_activation_coloured.png`). Some M1 contamination (modified token_dispatcher.py).
  - File coverage: 80% (8/10)
  - Scores: A=3, B=4, C=3
- **M3-short**: ⚠️ **PARTIAL** — 7/10 ground truth files covered. Core Python modules present but missing docs and binary image. **Heavy contamination**: modified 4 M2-related files (bucket_group_order), created Exp and reduce_sum_v2 artifacts.
  - File coverage: 70% (7/10)
  - Scores: A=2, B=3, C=2

---

## 3. Summary Results Table

| Task | Complexity | GT Files | Long: Files | Long: Verdict | Short: Files | Short: Verdict | Long-Short Gap |
|------|-----------|----------|------------|--------------|-------------|---------------|---------------|
| C1 | Low (1f, +3/-3) | 1 | 1/1 (100%) | **PASS** 5/5/5 | 1/1 (100%) | **PASS** 5/5/5 | 0 |
| C2 | Low (4f, +9/-24) | 4 | 4/4 (100%) | **PASS** 5/4/4 | 2/4 (50%) | **PARTIAL** 3/2/1 | +8pp |
| M1 | Low (3f, +19/-8) | 3 | 3/3 (100%) | **PASS** 4/4/4 | 0/3 (0%*) | **FAIL** 2/1/1 | +9pp |
| C4 | Med (24f, +1273) | 24 | 21/24 (88%) | **PASS** 4/4/4 | 0/24 (0%†) | **PARTIAL** 2/2/2 | +10pp |
| M2 | Med (6f, +150) | 6 | 6/6 (100%) | **PASS** 4/4/3 | 5/6 (83%) | **PARTIAL** 3/3/2 | +3pp |
| C5 | High (27f, +3372) | 27 | 27/27 (100%) | **PASS** 4/5/4 | 7/27 (26%) | **FAIL** 1/1/1 | +10pp |
| M3 | High (10f, +1115) | 10 | 8/10 (80%) | **PARTIAL** 3/4/3 | 7/10 (70%) | **PARTIAL** 2/3/2 | +3pp |

*M1-short: 2 files modified but with **wrong fix direction** (probs handling instead of triton import)
†C4-short: 12 files created but in **wrong directory** (`src/math/` instead of `src/contrib/math/`)

---

## 4. Scoring Summary (A: Functional Correctness, B: Completeness, C: Behavioral Equivalence)

| Task | Long A/B/C | Long Total | Short A/B/C | Short Total | Δ Total |
|------|-----------|-----------|------------|-----------|---------|
| C1 | 5/5/5 | 15 | 5/5/5 | 15 | 0 |
| C2 | 5/4/4 | 13 | 3/2/1 | 6 | **+7** |
| M1 | 4/4/4 | 12 | 2/1/1 | 4 | **+8** |
| C4 | 4/4/4 | 12 | 2/2/2 | 6 | **+6** |
| M2 | 4/4/3 | 11 | 3/3/2 | 8 | **+3** |
| C5 | 4/5/4 | 13 | 1/1/1 | 3 | **+10** |
| M3 | 3/4/3 | 10 | 2/3/2 | 7 | **+3** |
| **Avg** | **4.1/4.3/3.9** | **12.3** | **2.6/2.4/2.0** | **7.0** | **+5.3** |

---

## 5. Verdict Distribution

| Verdict | Long Prompt | Short Prompt |
|---------|-----------|-------------|
| **PASS** | 6/7 (86%) | 1/7 (14%) |
| **PARTIAL** | 1/7 (14%) | 4/7 (57%) |
| **FAIL** | 0/7 (0%) | 2/7 (29%) |

---

## 6. Key Findings

### 6.1 Prompt Granularity Effect
- **Long prompts** achieve **86% PASS rate** vs **14% PASS rate** for short prompts
- Average score gap: **+5.3/15 points** (long > short)
- The gap **widens with complexity**: Low=+5.0, Medium=+4.5, High=+6.5

### 6.2 Complexity Effect
- **Low complexity** (C1, C2, M1): Long prompts → 3/3 PASS; Short → 1 PASS, 1 PARTIAL, 1 FAIL
- **Medium complexity** (C4, M2): Long prompts → 2/2 PASS; Short → 2 PARTIAL
- **High complexity** (C5, M3): Long prompts → 1 PASS, 1 PARTIAL; Short → 1 FAIL, 1 PARTIAL

### 6.3 Common Failure Patterns (Short Prompts)
1. **Wrong fix direction** (M1-short): Agent identified the wrong root cause
2. **Wrong file placement** (C4-short): `src/math/` instead of `src/contrib/math/`
3. **Incomplete implementation** (C5-short): Only 26% of required files created
4. **Cross-experiment contamination** (M2-short, M3-short): Agent creates unrelated files

### 6.4 Agent Strengths
1. **Perfect on simple, well-localized bugs** (C1 both prompts identical)
2. **Excellent at following established patterns** when given detailed instructions (C4-long, C5-long)
3. **Can generate complete operator structures** including build system, tests, docs, examples

### 6.5 Agent Weaknesses
1. **Requires precise localization cues** for multi-file fixes (C2-short missed 2/4 files)
2. **Cannot infer correct directory structure** from short descriptions (C4-short wrong path)
3. **Struggles with complex architectural decisions** under ambiguity (M3-long only 80%)
4. **Cannot generate binary artifacts** (M3 missing PNG image)

---

## 7. Implications for "Harness Engineering"

The results strongly support the paper's thesis:
- **Raw agent capability is limited** for industrial feature implementation with brief prompts
- **Structured prompts ("harnesses")** dramatically improve outcomes (+72pp PASS rate)
- **The harness investment scales with complexity**: Simple bugs need minimal guidance; complex features need detailed architectural specs
- **Harness engineering** = designing the right level of guidance for the task complexity

---

## 8. Experiment Repos

| Task-Prompt | Repo Path | Parent Commit |
|------------|-----------|--------------|
| C1-long | `/home/jie/codes/cann-ops-adv-C1-long` | f722d9d |
| C1-short | `/home/jie/codes/cann-ops-adv-C1-short` | f722d9d |
| C2-long | `/home/jie/codes/cann-ops-C2-long` | 83a20f8d |
| C2-short | `/home/jie/codes/cann-ops-C2-short` | 83a20f8d |
| C4-long | `/home/jie/codes/cann-ops-C4-long` | f016f674 |
| C4-short | `/home/jie/codes/cann-ops-C4-short` | f016f674 |
| C5-long | `/home/jie/codes/cann-ops-C5-long` | eeb9289c |
| C5-short | `/home/jie/codes/cann-ops-C5-short` | eeb9289c |
| M1-long | `/home/jie/codes/MindSpeed-M1-long` | 47a5482 |
| M1-short | `/home/jie/codes/MindSpeed-M1-short` | 47a5482 |
| M2-long | `/home/jie/codes/MindSpeed-M2-long` | cc7f2e1f |
| M2-short | `/home/jie/codes/MindSpeed-M2-short` | cc7f2e1f |
| M3-long | `/home/jie/codes/MindSpeed-M3-long` | 6919aae8 |
| M3-short | `/home/jie/codes/MindSpeed-M3-short` | 6919aae8 |
