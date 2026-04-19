**Summary**: Kubernetes 调度器当前的调度算法时间复杂度为 O(Pod 数量 x 节点数量)，在大规模集群和批量调度场景下性能成为瓶颈。KEP-5598 提出实现机会主义批处理（Opportunistic Batching）机制，通过 Pod 调度签名和结果缓存，让具有相同调度特征的 Pod 可以复用前一个 Pod 的调度结果，显著提升批量调度性能。

**Proposal**: 引入 Pod 调度签名机制捕捉影响调度决策的 Pod 属性，实现批处理结果缓存存储上一次调度的可行节点列表，添加节点提示机制让后续相同签名的 Pod 直接尝试缓存的最优节点。通过 `OpportunisticBatching` feature gate 控制，Beta 阶段默认启用。
