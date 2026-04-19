**Summary**: ScaledMaskedSoftmaxGradV2 算子在高阶 API 升级后 UT 报错，原因是 ComputeSoftmaxGrad 函数中存在 tensor 生命周期违规——某个 buffer 在释放后仍被后续计算引用。

**Proposal**: 定位 ComputeSoftmaxGrad 中 FreeTensor 调用后仍在使用已释放内存的代码段，将引用替换为仍然存活的等价 buffer。
