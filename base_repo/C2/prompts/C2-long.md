**Summary**: add_layer_norm 和 layer_norm_grad_v3 算子在特定硬件上存在精度问题。ReduceSum 相关的计算路径产生不正确的结果。

**Motivation**: 在 AI Core 220 平台上，ReduceSum 的一个特殊优化路径（使用 GetAccVal 替代标准 ReduceSum）被发现存在精度问题。此外，layer_norm_grad_v3 的多个变体中 ReduceSum 的 count 参数设置为 1，不满足精度要求。这两个问题共同导致了 layer normalization 及其梯度计算的数值不稳定。

**Proposal**: 移除有问题的硬件特殊处理分支，统一 ReduceSum 的调用方式；同时修正 ReduceSum 的 count 参数以确保计算精度。

**Design Details**:

1. add_layer_norm 的 ReduceSum 优化路径问题：当前实现针对特定 AI Core 类型做了条件编译优化，使用了替代的累加值获取方式。该优化引入了精度问题。修复方向是移除该条件分支，统一使用标准的 ReduceSum + 取首元素的方式，牺牲少量性能换取精度正确性。

2. layer_norm_grad_v3 的 count 参数问题：ReduceSum API 的 count 参数控制规约的精度行为。当前多个变体中 count 均设置为 1，不满足精度要求，应使用满足精度需求的较大值，并定义统一的常量避免 magic number。

3. 影响范围：涉及 add_layer_norm 的基础实现和 layer_norm_grad_v3 的三个变体。修改不改变算子接口，仅影响内部计算精度。
