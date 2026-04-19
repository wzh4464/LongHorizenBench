**Summary**: MindSpeed 需要内存压缩特性的迭代升级——从原有的首节点 MLP 激活值压缩，扩展为各节点按 transformer layer 的激活值压缩及 AdamW 一二阶动量压缩。

**Proposal**: 实现完整的内存压缩模块，包含 activation 压缩（基于 saved_tensors_hooks）、optimizer 状态压缩、以及与 Megatron 训练循环的适配，通过 MindSpeedFeature 模式集成。
