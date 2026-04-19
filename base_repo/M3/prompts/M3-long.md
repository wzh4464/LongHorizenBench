**Summary**: MindSpeed 需要内存压缩特性的迭代升级——从原有的首节点 MLP 激活值压缩，扩展为各节点按 transformer layer 的激活值压缩及 AdamW 一二阶动量压缩。

**Motivation**: 大模型训练的显存占用是核心瓶颈。原有的激活值压缩特性仅支持首节点的 MLP 模块，覆盖面有限。迭代升级需要：(a) 将压缩范围扩展到所有节点的 transformer layer 激活值；(b) 新增 optimizer 状态（AdamW 一二阶动量）压缩；(c) 支持异步压缩/解压以最小化性能开销。在保留原有特性和使用方法的前提下增加新功能。

**Proposal**: 实现完整的内存压缩模块，包含 activation 压缩（基于 saved_tensors_hooks）、optimizer 状态压缩、以及与 Megatron 训练循环的适配，通过 MindSpeedFeature 模式集成。

**Design Details**:

1. Activation 压缩：
   - 利用 PyTorch 的 `saved_tensors_hooks` 机制，在前向传播保存 activation 时自动触发压缩，在反向传播需要 activation 时自动解压
   - 支持异步 stream codec：压缩/解压操作在独立的 CUDA stream 上执行，与计算 stream overlap
   - Simulation-based overlap 调度：通过模拟运行分析各 layer 的压缩/解压时间，优化调度策略以最大化 overlap 效果
   - 这是本特性的核心模块，复杂度最高

2. Optimizer 状态压缩：
   - 在 optimizer.step() 之前解压状态，step() 之后重新压缩
   - 支持 AdamW 的一阶动量（momentum）和二阶动量（variance）压缩

3. 通用工具层：
   - 压缩/解压算法封装
   - Tensor 序列化工具（处理不连续 tensor、不同 dtype 的统一压缩接口）
   - 统计和日志（压缩率、时间开销等监控信息）

4. 适配层：
   - 与 Megatron 训练循环集成的适配代码
   - 处理 pipeline parallelism、tensor parallelism 下的压缩行为

5. Feature 注册：遵循 MindSpeedFeature 模式，提供 CLI 参数控制压缩功能的开关和配置。

6. 文档更新：替换旧的压缩特性文档，提供新版本的使用说明和配置参考。
