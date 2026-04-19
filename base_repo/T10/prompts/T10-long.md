**Summary**: Presto 的 `UnnestOperator` 是 CPU 消耗排名前五的算子之一，当前实现采用逐行处理方式构建输出块，性能存在较大优化空间。本提案要求重构 `BenchmarkUnnestOperator` 基准测试类，使其能够更全面地测试各种 unnest 场景，为后续的向量化优化提供可靠的性能基准。

**Motivation**: UnnestOperator 用于展开数组、Map 和嵌套结构，在处理复杂数据类型的查询中被频繁使用。当前的基准测试存在以下问题：(1) 测试场景有限，无法覆盖各种嵌套类型组合；(2) 输入数据生成逻辑复杂且难以维护；(3) 测试参数不够灵活，难以探索不同配置下的性能特征。重构基准测试是进行后续向量化优化（如批量填充 DictionaryBlock、紧凑循环复制等）的必要前置步骤。

**Proposal**: 重构 `BenchmarkUnnestOperator` 类：(1) 使用 `PageAssertions.createPageWithRandomData` 替代自定义的输入生成逻辑，简化代码并提高可维护性；(2) 扩展测试参数以覆盖更多场景，包括不同的复制列类型、多种嵌套类型组合、以及 withOrdinality 选项；(3) 将 benchmark 方法移到类的前面以提高可读性；(4) 调整 JMH 配置参数以获得更准确的测量结果。

**Design Details**:

1. 移除自定义 InputGenerator：删除 `InputGenerator` 内部类及其所有方法（`produceBlock`、`produceStringBlock`、`produceIntBlock`、`produceArrayBlock`、`produceMapBlock`、`produceRowBlock`、`generateRandomString`）。这些方法由 `PageAssertions.createPageWithRandomData` 工具方法替代。

2. 简化 BenchmarkData 状态类：将 `BenchmarkContext` 重命名为 `BenchmarkData`（符合 JMH 命名惯例）。移除 `stringLengths` 和 `nestedLengths` 参数，因为新的随机数据生成方法不需要这些配置。简化类型解析逻辑。

3. 扩展测试参数：
   - `replicateType`: 从 `varchar` 扩展为支持 `bigint` 和 `varchar`
   - `nestedType`: 从有限的三种类型扩展为更多组合：`array(varchar)`、`array(integer)`、`map(varchar,varchar)`、`array(row(varchar,varchar,varchar))`、`array(array(varchar))`、`array(bigint)|array(bigint)`、`array(varchar)|array(varchar)`
   - 添加 `withOrdinality` 布尔参数测试带序号输出的场景
   - 使用管道符 `|` 分隔支持多个 unnest 列

4. 简化通道构建逻辑：将原来的单一 `channelsBuilder` 拆分为 `replicatedChannelsBuilder` 和 `unnestChannelsBuilder`，分别管理复制列和 unnest 列的通道索引。类似地拆分类型构建器。

5. 使用 PageAssertions 生成测试数据：在 setup 方法中调用 `createPageWithRandomData(types, positionsPerPage, false, false, primitiveNullsRatio, rowNullsRatio, false, ImmutableList.of())` 生成测试页面。这提供了与现有测试框架一致的随机数据生成能力。

6. 调整 JMH 配置：
   - 将输出时间单位从 `TimeUnit.SECONDS` 改为 `TimeUnit.MICROSECONDS`
   - 将预热迭代从 20 次减少到 8 次
   - 将测量迭代从 20 次减少到 8 次
   - 添加 `@BenchmarkMode(Mode.AverageTime)` 注解明确测量模式

7. 代码结构调整：将 `@Benchmark unnest` 方法移到类的开头位置（在 `BenchmarkData` 之前），提高代码可读性。更新导入语句，移除不再使用的导入（如 `Random`、`Arrays`、`checkArgument` 等），添加新需要的导入（如 `PageAssertions`、`ArrayList`、`BenchmarkMode`、`Mode`）。

8. 修正 OperatorFactory 引用：将 `UnnestOperatorFactory` 改为 `UnnestOperator.UnnestOperatorFactory`，使用正确的内部类引用方式。
