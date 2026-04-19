**Summary**: 在大模型训练中，模型定义顺序与执行顺序不一致（常见于重定义 transformer 组件或多模态模型），导致开启 overlap param gather 后出现精度问题和计算通信串行。

**Proposal**: 实现 bucket group 重排功能，使 DDP 的 bucket 顺序匹配模型实际执行顺序，从而恢复 overlap param gather 的性能收益。
