**Summary**: torch_npu 的 NPU Graph 模块中，算子的 capture/update 逻辑通过大量硬编码 if/elif 分发，难以维护和扩展。需要重构为可插拔的 Registry + Template Method 架构。

**Proposal**: 抽取算子处理逻辑为独立的 Handler 类，通过注册表实现算子到 handler 的映射，`_GraphDispatchMode` 仅保留通用的 stream/event/task-group 编排作为 template method skeleton。
