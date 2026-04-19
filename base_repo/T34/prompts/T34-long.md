# T34: Kubernetes

**Summary**: Kubernetes 调度器当前的调度算法时间复杂度为 O(Pod 数量 x 节点数量)，在大规模集群和批量调度场景下性能成为瓶颈。KEP-5598 提出实现机会主义批处理（Opportunistic Batching）机制，通过 Pod 调度签名和结果缓存，让具有相同调度特征的 Pod 可以复用前一个 Pod 的调度结果，显著提升批量调度性能。

**Motivation**: 在 ML 训练、批处理任务等场景中，常常需要调度大量相似的 Pod（相同的资源请求、节点亲和性等）。当前调度器为每个 Pod 独立执行完整的过滤和评分流程，即使这些 Pod 会得到相同的调度结果。这在"单 Pod 单节点"的批量环境中尤为低效。通过识别调度等价的 Pod 并复用调度结果，可以大幅减少重复计算，提升调度吞吐量。

**Proposal**: 引入三个核心组件：(1) Pod 调度签名机制，捕捉影响调度决策的 Pod 属性；(2) 批处理结果缓存，存储上一次调度的可行节点列表；(3) 节点提示机制，让后续相同签名的 Pod 直接尝试缓存的最优节点。通过 `OpportunisticBatching` feature gate 控制，Beta 阶段默认启用。

**Design Details**:

1. Feature Gate 注册：在 `pkg/features/kube_features.go` 中注册 `OpportunisticBatching` feature gate，设置版本和默认状态。

2. Framework 接口扩展：在 `pkg/scheduler/framework/interface.go` 中添加新接口：
   - `SignPod(ctx, pod, recordStats) PodSignature`：为 Pod 生成调度签名
   - `GetNodeHint(ctx, pod, state, cycleCount) (hint, signature)`：获取节点提示
   - `StoreScheduleResults(ctx, signature, hintedNode, chosenNode, otherNodes, cycleCount)`：存储调度结果
   - `SortedScoredNodes` 接口：返回排序后的节点列表

3. SignPlugin 接口：定义插件签名接口，让各调度插件贡献签名片段：
   - 在 `staging/src/k8s.io/kube-scheduler/framework/` 下定义 `SignPlugin` 接口和 `SignFragment` 类型
   - `signers.go`：实现签名合并和管理逻辑

4. 插件签名实现：为各调度插件实现 `SignPod` 方法：
   - `imagelocality`：基于容器镜像名称生成签名
   - `nodeaffinity`：基于节点亲和性规则生成签名
   - `nodeports`：基于端口需求生成签名
   - `noderesources/fit.go` 和 `balanced_allocation.go`：基于资源请求生成签名
   - `nodename`, `nodeunschedulable`, `nodevolumelimits`, `tainttoleration`：各自的签名逻辑
   - `volumebinding`, `volumezone`, `volumerestrictions`：存储相关签名

5. 不可签名场景处理：某些复杂场景标记 Pod 为不可签名：
   - `interpodaffinity`：Pod 间亲和/反亲和
   - `podtopologyspread`：拓扑分布约束
   - `dynamicresources`：DRA 资源声明（返回 Unschedulable 状态）

6. 批处理运行时实现：在 `pkg/scheduler/framework/runtime/` 下：
   - `batch.go`：实现批处理核心逻辑，包括签名缓存、节点提示验证、结果存储
   - `framework.go`：集成批处理逻辑到调度框架

7. 调度主循环集成：在 `pkg/scheduler/schedule_one.go` 中：
   - 调度开始时调用 `GetNodeHint` 获取节点提示
   - 如果有有效提示，优先评估该节点，通过则直接返回
   - 提示失败则降级到正常调度流程
   - 调度完成后调用 `StoreScheduleResults` 缓存结果

8. 指标和监控：在 `pkg/scheduler/metrics/metrics.go` 中添加批处理相关指标，追踪命中率、跳过的节点数等。

9. 测试：
   - `pkg/scheduler/framework/runtime/batch_test.go`：单元测试
   - `pkg/scheduler/schedule_one_test.go`：调度流程测试
   - `test/integration/scheduler/batch/`：集成测试
   - 各插件目录下的签名测试

## Requirement
https://github.com/kubernetes/enhancements/blob/master/keps/sig-scheduling/5598-opportunistic-batching/README.md
