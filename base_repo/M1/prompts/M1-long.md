**Summary**: MindSpeed 的 MoE overlap alltoall_seq token dispatcher 在训练过程中产生 NaN 值，疑似异步通信操作与 triton 融合路径存在竞态条件。

**Motivation**: 在启用 MoE overlap 和 alltoall_seq 通信模式时，部分训练步骤输出 NaN。经初步排查，问题出在 token permutation 阶段：当 triton 融合路径被激活时，异步操作的数据可能在计算完成前被读取。此外，triton 的可用性检测分散在多处且存在副作用（import 时触发编译），应统一管理。

**Proposal**: 排查 token dispatcher 的异步通信和融合计算路径，修复 NaN 根因。

**Design Details**:

1. Triton 可用性管理问题：当前代码在多个模块中通过 try/except 直接 import triton 来判断可用性。这种方式有两个问题：(a) import triton 本身有副作用（触发 JIT 编译环境检测），不应在 module load 时执行；(b) 可用性判断分散，不同模块可能得到不一致的结果。应提供统一的工具函数，通过全局变量缓存结果，避免重复 import。

2. 融合路径的条件检查问题：token dispatcher 的 permutation 逻辑中，融合计算路径的激活条件不完整——未检查所有必要的前置依赖是否满足，导致在不满足条件时仍进入融合路径。

3. 异步操作竞态条件：融合路径中，某个异步通信操作启动后，后续代码直接使用了该操作的输出数据，但缺少必要的同步等待。这导致数据在通信完成前被读取，产生 NaN。

4. 修复应确保：统一的依赖检测、完整的条件守卫、以及必要的异步同步点。
