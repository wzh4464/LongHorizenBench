**Summary**: ScaledMaskedSoftmaxGradV2 算子在高阶 API 升级后 UT 报错，原因是 ComputeSoftmaxGrad 函数中存在 tensor 生命周期违规——某个 buffer 在释放后仍被后续计算引用。

**Motivation**: 高阶 API 新版本增加了 tensor 生命周期校验机制。此前未被检测到的 use-after-free 现在会触发运行时错误。该算子的 NormHeadDim 变体在反向传播计算中，先释放了一个输入 tensor 的 queue 资源，但后续三步计算（梯度计算、scale-mask、类型转换）仍通过该 tensor 的 cast buffer 继续访问底层内存。

**Proposal**: 定位 ComputeSoftmaxGrad 中 FreeTensor 调用后仍在使用已释放内存的代码段，将引用替换为仍然存活的等价 buffer。

**Design Details**:

1. 根因分析：在 ComputeSoftmaxGrad 的计算流程中，输入 yGrad 经过 cast 产生了一个 float 类型的临时 buffer。当 yGrad 对应的 queue 资源被 FreeTensor 释放后，该临时 buffer 的底层内存也随之失效。但后续代码在三个连续操作中继续使用这个临时 buffer 作为输入或输出参数。

2. 修复策略：分析数据流，找到另一个在 FreeTensor 之后仍然存活且 shape/dtype 兼容的 buffer，将这三处引用替换过去。需要确保替换后的 buffer 在这些操作中作为输入/输出的语义正确（即不会覆盖后续还需要的数据）。

3. 影响范围：仅涉及 NormHeadDim 变体的反向计算函数，不影响前向计算和其他变体。
