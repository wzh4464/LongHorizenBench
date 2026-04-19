**Summary**: 为昇腾 NPU 实现 ReduceSumV2 自定义算子，支持沿指定轴对 tensor 进行求和规约，需要处理多种规约模式和数据类型。

**Proposal**: 实现完整的 ReduceSumV2 算子，包含模块化的 kernel 设计（支持 atomic reduce 和 aligned reduce 两种模式）、aclnn API 封装、完整的 host 端逻辑（tiling/shape 推断/算子注册）、示例和测试。
