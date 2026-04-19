**Summary**: MindSpeed 的 MoE overlap alltoall_seq token dispatcher 在训练过程中产生 NaN 值，疑似异步通信操作与 triton 融合路径存在竞态条件。

**Proposal**: 排查 token dispatcher 的异步通信和融合计算路径，修复 NaN 根因。
