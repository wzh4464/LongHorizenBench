# Experiment Prompts for ASE 2026 Paper 2

> Prompt 设计原则：对齐 K8s KEP 模式
> - **Long** = 完整需求/设计文档（Summary + Motivation + Proposal + Design Details），描述 WHAT 和 WHY，不给出具体文件路径和实现细节
> - **Short** = 仅 Summary + Proposal（不含 Design Details），模拟简要需求描述

---

## C1: ScaledMaskedSoftmaxGradV2 Buffer Alias Fix (Low)
Repo: cann-ops-adv | Ground Truth: 888d214 | Parent: f722d9d

### Short Prompt

**Summary**: ScaledMaskedSoftmaxGradV2 算子在高阶 API 升级后 UT 报错，原因是 ComputeSoftmaxGrad 函数中存在 tensor 生命周期违规——某个 buffer 在释放后仍被后续计算引用。

**Proposal**: 定位 ComputeSoftmaxGrad 中 FreeTensor 调用后仍在使用已释放内存的代码段，将引用替换为仍然存活的等价 buffer。

### Long Prompt

**Summary**: ScaledMaskedSoftmaxGradV2 算子在高阶 API 升级后 UT 报错，原因是 ComputeSoftmaxGrad 函数中存在 tensor 生命周期违规——某个 buffer 在释放后仍被后续计算引用。

**Motivation**: 高阶 API 新版本增加了 tensor 生命周期校验机制。此前未被检测到的 use-after-free 现在会触发运行时错误。该算子的 NormHeadDim 变体在反向传播计算中，先释放了一个输入 tensor 的 queue 资源，但后续三步计算（梯度计算、scale-mask、类型转换）仍通过该 tensor 的 cast buffer 继续访问底层内存。

**Proposal**: 定位 ComputeSoftmaxGrad 中 FreeTensor 调用后仍在使用已释放内存的代码段，将引用替换为仍然存活的等价 buffer。

**Design Details**:

1. 根因分析：在 ComputeSoftmaxGrad 的计算流程中，输入 yGrad 经过 cast 产生了一个 float 类型的临时 buffer。当 yGrad 对应的 queue 资源被 FreeTensor 释放后，该临时 buffer 的底层内存也随之失效。但后续代码在三个连续操作中继续使用这个临时 buffer 作为输入或输出参数。

2. 修复策略：分析数据流，找到另一个在 FreeTensor 之后仍然存活且 shape/dtype 兼容的 buffer，将这三处引用替换过去。需要确保替换后的 buffer 在这些操作中作为输入/输出的语义正确（即不会覆盖后续还需要的数据）。

3. 影响范围：仅涉及 NormHeadDim 变体的反向计算函数，不影响前向计算和其他变体。

---

## C2: add_layer_norm Precision Bug Fix (Low)
Repo: cann-ops | Ground Truth: a8b1e873 | Parent: 83a20f8d

### Short Prompt

**Summary**: add_layer_norm 和 layer_norm_grad_v3 算子在特定硬件上存在精度问题。ReduceSum 相关的计算路径产生不正确的结果。

**Proposal**: 移除有问题的硬件特殊处理分支，统一 ReduceSum 的调用方式；同时修正 ReduceSum 的 count 参数以确保计算精度。

### Long Prompt

**Summary**: add_layer_norm 和 layer_norm_grad_v3 算子在特定硬件上存在精度问题。ReduceSum 相关的计算路径产生不正确的结果。

**Motivation**: 在 AI Core 220 平台上，ReduceSum 的一个特殊优化路径（使用 GetAccVal 替代标准 ReduceSum）被发现存在精度问题。此外，layer_norm_grad_v3 的多个变体中 ReduceSum 的 count 参数设置为 1，不满足精度要求。这两个问题共同导致了 layer normalization 及其梯度计算的数值不稳定。

**Proposal**: 移除有问题的硬件特殊处理分支，统一 ReduceSum 的调用方式；同时修正 ReduceSum 的 count 参数以确保计算精度。

**Design Details**:

1. add_layer_norm 的 ReduceSum 优化路径问题：当前实现针对特定 AI Core 类型做了条件编译优化，使用了替代的累加值获取方式。该优化引入了精度问题。修复方向是移除该条件分支，统一使用标准的 ReduceSum + 取首元素的方式，牺牲少量性能换取精度正确性。

2. layer_norm_grad_v3 的 count 参数问题：ReduceSum API 的 count 参数控制规约的精度行为。当前多个变体中 count 均设置为 1，不满足精度要求，应使用满足精度需求的较大值，并定义统一的常量避免 magic number。

3. 影响范围：涉及 add_layer_norm 的基础实现和 layer_norm_grad_v3 的三个变体。修改不改变算子接口，仅影响内部计算精度。

---

## C3: NPU Graph Op Handlers Registry Refactor (Medium)
Repo: torch_npu | Ground Truth: 94260135a | Parent: eed8f282

### Short Prompt

**Summary**: torch_npu 的 NPU Graph 模块中，算子的 capture/update 逻辑通过大量硬编码 if/elif 分发，难以维护和扩展。需要重构为可插拔的 Registry + Template Method 架构。

**Proposal**: 抽取算子处理逻辑为独立的 Handler 类，通过注册表实现算子到 handler 的映射，`_GraphDispatchMode` 仅保留通用的 stream/event/task-group 编排作为 template method skeleton。

### Long Prompt

**Summary**: torch_npu 的 NPU Graph 模块中，算子的 capture/update 逻辑通过大量硬编码 if/elif 分发，难以维护和扩展。需要重构为可插拔的 Registry + Template Method 架构。

**Motivation**: 当前 `_GraphDispatchMode` 类中，`__torch_dispatch__` 方法包含大量针对不同算子的硬编码分支（IFA 特殊处理、简单 NPU 算子、default 等）。每次新增算子支持都需要修改核心分发逻辑，违反开闭原则。随着 NPU Graph 支持的算子类型增多，这种模式的维护成本越来越高，且容易引入回归 bug。

**Proposal**: 抽取算子处理逻辑为独立的 Handler 类，通过注册表实现算子到 handler 的映射，`_GraphDispatchMode` 仅保留通用的 stream/event/task-group 编排作为 template method skeleton。

**Design Details**:

1. Handler 基类设计：定义一个抽象基类，包含三个核心生命周期 hook——capture 阶段的参数预处理和记录、update 阶段的参数替换、以及 update 后的清理操作。采用 stateless 设计。基类提供合理的默认实现（以弱引用方式保存 tensor 参数、根据 schema 名替换 tensor 等），简单算子只需继承即可。

2. 注册机制：提供装饰器支持单个或多个算子名注册到全局 dict。重复注册应发出 warning 而非报错。对于未注册的算子，framework 应有 fallback 行为。

3. Handler 分类：
   - IFA（Incremental Flash Attention）handler：需要特殊的 capture 逻辑（处理函数替换和 IFA 特有的参数）和特殊的 update 逻辑（IFA 专用参数的更新）
   - 简单 NPU 算子 handler：仓库中已有的简单 NPU 算子，使用基类默认行为即可
   - 需要覆盖 `_GraphDispatchMode` 中当前所有硬编码的算子分支

4. 核心分发逻辑改造：dispatch mode 的分发/更新方法改为从注册表查找 handler 并调用对应生命周期 hook，stream/event/task-group 的通用编排保留在 mode 中。

5. 公开 API：Handler 基类和注册装饰器作为公开 API 导出，允许下游用户注册自定义算子的 handler。需更新公开 API 注册表和 schema。

6. 测试：注册机制的单元测试——覆盖常见注册场景（单名/多名）、异常处理（重复注册、未注册算子的 fallback）、测试间隔离。

---

## C4: Exp Operator Implementation (Medium)
Repo: cann-ops | Ground Truth: a4abcf27 | Parent: f016f674

### Short Prompt

**Summary**: 为昇腾 NPU 实现 Exp（指数函数）自定义算子，支持 `base^(scale*x+shift)` 计算，覆盖 float16/float32/bfloat16 数据类型。

**Proposal**: 参照仓库中已有算子的标准结构，在 contrib 目录下实现完整的 Exp 算子，包括 host 端（算子定义、tiling、shape 推断）、device 端（AscendC kernel）、示例程序和测试。

### Long Prompt

**Summary**: 为昇腾 NPU 实现 Exp（指数函数）自定义算子，支持 `base^(scale*x+shift)` 计算，覆盖 float16/float32/bfloat16 数据类型。

**Motivation**: 当前 CANN 算子库缺少独立的 Exp 算子。虽然部分融合算子内部包含指数运算，但没有支持自定义 base/scale/shift 参数的通用 Exp 实现。多个下游模型（如 attention score 的 temperature scaling、自定义激活函数）需要此能力。

**Proposal**: 参照仓库中已有算子的标准结构，在 contrib 目录下实现完整的 Exp 算子，包括 host 端（算子定义、tiling、shape 推断）、device 端（AscendC kernel）、示例程序和测试。

**Design Details**:

1. 算子规格：
   - 输入：x (REQUIRED)，支持 DT_FLOAT16 / DT_FLOAT / DT_BF16，FORMAT_ND
   - 输出：y (REQUIRED)，与输入同 dtype 和 format
   - 属性：base (float, optional, default=-1.0 表示自然底数 e), scale (float, optional, default=1.0), shift (float, optional, default=0.0)
   - 目标平台：ascend910b

2. Host 端设计：
   - 算子注册：定义输入/输出/属性，绑定 tiling 函数和 shape 推断函数
   - Tiling 策略：基于 UB 大小和核数计算数据分片（大核/小核分别处理不同数据量）。bfloat16 需要额外的中间 buffer 用于 cast 到 float 计算
   - Shape 推断：输出 shape 与输入相同

3. Device 端设计：
   - 使用 AscendC 编程模型实现 CopyIn → Compute → CopyOut 三级流水线
   - Compute 阶段：先算 scale*x+shift，若 base 非自然底数则乘以 log(base)，最后执行 Exp 运算
   - bfloat16 处理：先 Cast 到 float 计算，再 Cast 回 bfloat16

4. 示例和测试：
   - 提供 C++ 驱动程序调用 aclnn 接口
   - Python 数据生成脚本（numpy 生成输入并计算参考输出）和验证脚本
   - pytest 测试用例覆盖不同 dtype 和属性组合

5. 参考：仓库中已有的 math 类算子（如 abs、add 等）提供了标准目录结构和实现模式，应遵循一致的代码组织方式。

---

## C5: reduce_sum_v2 Operator (High)
Repo: cann-ops | Ground Truth: 3bf6bea9 | Parent: eeb9289c

### Short Prompt

**Summary**: 为昇腾 NPU 实现 ReduceSumV2 自定义算子，支持沿指定轴对 tensor 进行求和规约，需要处理多种规约模式和数据类型。

**Proposal**: 实现完整的 ReduceSumV2 算子，包含模块化的 kernel 设计（支持 atomic reduce 和 aligned reduce 两种模式）、aclnn API 封装、完整的 host 端逻辑（tiling/shape 推断/算子注册）、示例和测试。

### Long Prompt

**Summary**: 为昇腾 NPU 实现 ReduceSumV2 自定义算子，支持沿指定轴对 tensor 进行求和规约，需要处理多种规约模式和数据类型。

**Motivation**: 现有的 ReduceSum 算子不满足某些场景对性能和功能的要求（如大 tensor 的多轴规约、特定内存布局优化）。ReduceSumV2 需要提供更灵活的规约策略，支持 atomic reduce（适合小 tensor 或跨核协作）和 aligned reduce（适合大 tensor 连续规约），并提供标准的 aclnn API 供框架层调用。

**Proposal**: 实现完整的 ReduceSumV2 算子，包含模块化的 kernel 设计（支持 atomic reduce 和 aligned reduce 两种模式）、aclnn API 封装、完整的 host 端逻辑（tiling/shape 推断/算子注册）、示例和测试。

**Design Details**:

1. 算子规格：
   - 输入：x (REQUIRED)，支持多种数据类型
   - 输出：y (REQUIRED)，shape 根据规约轴确定
   - 属性：axes (list of int)，keepdims (bool)
   - 目标平台：ascend910b

2. Host 端架构：
   - aclnn API 层：对外提供标准的 aclnn 调用接口（GetWorkspaceSize + 执行），内部处理参数校验和 tiling 数据准备
   - 算子注册：定义 op proto、绑定 tiling 和 shape 推断
   - Tiling 策略：根据输入 shape、规约轴、可用核数选择 atomic reduce (AR) 或 aligned reduce (ARA) 模式；计算每个核的数据分片和 workspace 需求
   - Shape 推断：根据输入 shape、axes 和 keepdims 计算输出 shape

3. Device 端架构（模块化 kernel）：
   - 公共工具层：kernel 工具函数（index 计算、内存管理等）
   - AR (Atomic Reduce) kernel：多核通过原子操作协作完成规约，适合规约维度较小的场景
   - ARA (Aligned Reduce Accumulate) kernel：单核/少核完成连续内存上的规约，适合规约维度较大的场景
   - 入口 kernel：根据 tiling 参数选择 AR 或 ARA 路径

4. 示例和测试：
   - C++ 示例程序通过 aclnn 接口调用算子
   - Python 数据生成和验证脚本
   - pytest 测试覆盖不同 shape、axes、dtype 组合

5. 参考：仓库中已有的 math 类算子提供了标准的目录结构、aclnn API 封装模式和 kernel 组织方式。

---

## M1: alltoall_seq NaN Bug Fix (Low)
Repo: MindSpeed | Ground Truth: e455517 | Parent: 47a5482

### Short Prompt

**Summary**: MindSpeed 的 MoE overlap alltoall_seq token dispatcher 在训练过程中产生 NaN 值，疑似异步通信操作与 triton 融合路径存在竞态条件。

**Proposal**: 排查 token dispatcher 的异步通信和融合计算路径，修复 NaN 根因。

### Long Prompt

**Summary**: MindSpeed 的 MoE overlap alltoall_seq token dispatcher 在训练过程中产生 NaN 值，疑似异步通信操作与 triton 融合路径存在竞态条件。

**Motivation**: 在启用 MoE overlap 和 alltoall_seq 通信模式时，部分训练步骤输出 NaN。经初步排查，问题出在 token permutation 阶段：当 triton 融合路径被激活时，异步操作的数据可能在计算完成前被读取。此外，triton 的可用性检测分散在多处且存在副作用（import 时触发编译），应统一管理。

**Proposal**: 排查 token dispatcher 的异步通信和融合计算路径，修复 NaN 根因。

**Design Details**:

1. Triton 可用性管理问题：当前代码在多个模块中通过 try/except 直接 import triton 来判断可用性。这种方式有两个问题：(a) import triton 本身有副作用（触发 JIT 编译环境检测），不应在 module load 时执行；(b) 可用性判断分散，不同模块可能得到不一致的结果。应提供统一的工具函数，通过全局变量缓存结果，避免重复 import。

2. 融合路径的条件检查问题：token dispatcher 的 permutation 逻辑中，融合计算路径的激活条件不完整——未检查所有必要的前置依赖是否满足，导致在不满足条件时仍进入融合路径。

3. 异步操作竞态条件：融合路径中，某个异步通信操作启动后，后续代码直接使用了该操作的输出数据，但缺少必要的同步等待。这导致数据在通信完成前被读取，产生 NaN。

4. 修复应确保：统一的依赖检测、完整的条件守卫、以及必要的异步同步点。

---

## M2: Reset Bucket Group Order (Medium)
Repo: MindSpeed | Ground Truth: 596b96b | Parent: cc7f2e1f

### Short Prompt

**Summary**: 在大模型训练中，模型定义顺序与执行顺序不一致（常见于重定义 transformer 组件或多模态模型），导致开启 overlap param gather 后出现精度问题和计算通信串行。

**Proposal**: 实现 bucket group 重排功能，使 DDP 的 bucket 顺序匹配模型实际执行顺序，从而恢复 overlap param gather 的性能收益。

### Long Prompt

**Summary**: 在大模型训练中，模型定义顺序与执行顺序不一致（常见于重定义 transformer 组件或多模态模型），导致开启 overlap param gather 后出现精度问题和计算通信串行。

**Motivation**: Megatron 0.12.1 解决了顺序不一致导致的精度问题，但计算和通信串行的性能问题仍然存在。当 bucket group 的顺序与模型执行顺序不匹配时，overlap param gather 无法有效地将通信和计算重叠，吞吐量显著下降。在模型定义顺序和执行顺序混乱的场景下，需要在 DDP 初始化时重排 bucket group，使其匹配实际的执行顺序。

**Proposal**: 实现 bucket group 重排功能，使 DDP 的 bucket 顺序匹配模型实际执行顺序，从而恢复 overlap param gather 的性能收益。

**Design Details**:

1. 功能设计：在 DistributedDataParallel 初始化阶段，根据模型的实际执行顺序对 bucket group 进行重排。重排逻辑应在 param gather 的 overlap 准备阶段执行，确保后续的通信操作按正确顺序发起。

2. 配置扩展：需要扩展 DDP 的配置，增加控制该功能的开关参数。通过 CLI 参数暴露给用户，让用户可以选择是否启用重排。

3. 集成方式：遵循 MindSpeed 的 Feature 注册模式（MindSpeedFeature 子类），通过 features_manager 统一管理。需要注册 feature、添加 CLI 参数、实现核心逻辑、更新文档。

4. 文档：提供 feature 使用说明，包括启用方式、适用场景、预期效果。

---

## M3: Memory Compression (High)
Repo: MindSpeed | Ground Truth: 102c3f3 | Parent: 6919aae8

### Short Prompt

**Summary**: MindSpeed 需要内存压缩特性的迭代升级——从原有的首节点 MLP 激活值压缩，扩展为各节点按 transformer layer 的激活值压缩及 AdamW 一二阶动量压缩。

**Proposal**: 实现完整的内存压缩模块，包含 activation 压缩（基于 saved_tensors_hooks）、optimizer 状态压缩、以及与 Megatron 训练循环的适配，通过 MindSpeedFeature 模式集成。

### Long Prompt

**Summary**: MindSpeed 需要内存压缩特性的迭代升级——从原有的首节点 MLP 激活值压缩，扩展为各节点按 transformer layer 的激活值压缩及 AdamW 一二阶动量压缩。

**Motivation**: 大模型训练的显存占用是核心瓶颈。原有的激活值压缩特性仅支持首节点的 MLP 模块，覆盖面有限。迭代升级需要：(a) 将压缩范围扩展到所有节点的 transformer layer 激活值；(b) 新增 optimizer 状态（AdamW 一二阶动量）压缩；(c) 支持异步压缩/解压以最小化性能开销。在保留原有特性和使用方法的前提下增加新功能。

**Proposal**: 实现完整的内存压缩模块，包含 activation 压缩（基于 saved_tensors_hooks）、optimizer 状态压缩、以及与 Megatron 训练循环的适配，通过 MindSpeedFeature 模式集成。

**Design Details**:

1. Activation 压缩：
   - 利用 PyTorch 的 `saved_tensors_hooks` 机制，在前向传播保存 activation 时自动触发压缩，在反向传播需要 activation 时自动解压
   - 支持异步 stream codec：压缩/解压操作在独立的 CUDA stream 上执行，与计算 stream overlap
   - Simulation-based overlap 调度：通过模拟运行分析各 layer 的压缩/解压时间，优化调度策略以最大化 overlap 效果
   - 这是本特性的核心模块，复杂度最高

2. Optimizer 状态压缩：
   - 在 optimizer.step() 之前解压状态，step() 之后重新压缩
   - 支持 AdamW 的一阶动量（momentum）和二阶动量（variance）压缩

3. 通用工具层：
   - 压缩/解压算法封装
   - Tensor 序列化工具（处理不连续 tensor、不同 dtype 的统一压缩接口）
   - 统计和日志（压缩率、时间开销等监控信息）

4. 适配层：
   - 与 Megatron 训练循环集成的适配代码
   - 处理 pipeline parallelism、tensor parallelism 下的压缩行为

5. Feature 注册：遵循 MindSpeedFeature 模式，提供 CLI 参数控制压缩功能的开关和配置。

6. 文档更新：替换旧的压缩特性文档，提供新版本的使用说明和配置参考。
