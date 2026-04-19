**Summary**: Presto 的 `UnnestOperator` 是 CPU 消耗排名前五的算子之一，当前实现采用逐行处理方式构建输出块，性能存在较大优化空间。本提案要求重构 `BenchmarkUnnestOperator` 基准测试类，使其能够更全面地测试各种 unnest 场景，为后续的向量化优化提供可靠的性能基准。

**Proposal**: 重构 `BenchmarkUnnestOperator` 类，使用 `PageAssertions.createPageWithRandomData` 替代自定义输入生成逻辑，扩展测试参数以覆盖更多场景包括不同复制列类型和嵌套类型组合，调整 JMH 配置参数以获得更准确的测量结果。
