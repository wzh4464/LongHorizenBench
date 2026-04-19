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
