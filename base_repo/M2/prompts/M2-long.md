**Summary**: 在大模型训练中，模型定义顺序与执行顺序不一致（常见于重定义 transformer 组件或多模态模型），导致开启 overlap param gather 后出现精度问题和计算通信串行。

**Motivation**: Megatron 0.12.1 解决了顺序不一致导致的精度问题，但计算和通信串行的性能问题仍然存在。当 bucket group 的顺序与模型执行顺序不匹配时，overlap param gather 无法有效地将通信和计算重叠，吞吐量显著下降。在模型定义顺序和执行顺序混乱的场景下，需要在 DDP 初始化时重排 bucket group，使其匹配实际的执行顺序。

**Proposal**: 实现 bucket group 重排功能，使 DDP 的 bucket 顺序匹配模型实际执行顺序，从而恢复 overlap param gather 的性能收益。

**Design Details**:

1. 功能设计：在 DistributedDataParallel 初始化阶段，根据模型的实际执行顺序对 bucket group 进行重排。重排逻辑应在 param gather 的 overlap 准备阶段执行，确保后续的通信操作按正确顺序发起。

2. 配置扩展：需要扩展 DDP 的配置，增加控制该功能的开关参数。通过 CLI 参数暴露给用户，让用户可以选择是否启用重排。

3. 集成方式：遵循 MindSpeed 的 Feature 注册模式（MindSpeedFeature 子类），通过 features_manager 统一管理。需要注册 feature、添加 CLI 参数、实现核心逻辑、更新文档。

4. 文档：提供 feature 使用说明，包括启用方式、适用场景、预期效果。
