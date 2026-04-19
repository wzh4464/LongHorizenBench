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
