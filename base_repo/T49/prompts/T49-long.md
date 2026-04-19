# T49: Kubernetes - 实现 Pod 资源就地垂直伸缩

## Requirement

https://github.com/kubernetes/enhancements/blob/master/keps/sig-node/1287-in-place-update-pod-resources/README.md

## Summary

KEP-1287 实现了 Kubernetes Pod 的就地垂直伸缩功能，允许在不重启 Pod 或容器的情况下动态调整容器的 CPU 和内存资源请求与限制。这解决了传统方式下修改资源配置必须销毁并重建 Pod 的限制，对有状态工作负载和需要高可用性的服务尤为重要。

## Motivation

当前 Kubernetes 中，Pod 的资源配置（`resources.requests` 和 `resources.limits`）是不可变的。要调整资源，必须删除并重新创建 Pod，这会导致：
- 服务中断，影响可用性
- 有状态工作负载需要复杂的迁移流程
- 批处理作业可能丢失进度
- VPA（垂直 Pod 自动伸缩器）必须通过 eviction 实现伸缩

就地伸缩允许：
- 根据负载变化动态调整资源
- 在业务低峰期释放资源供其他工作负载使用
- 在不中断服务的情况下响应 OOM 压力

## Proposal

将 `spec.containers[].resources` 字段改为可变（仅限 `cpu` 和 `memory`）。引入 `resizePolicy` 字段控制每种资源的调整行为。在 `status` 中添加 `allocatedResources`（已分配资源）、`resources`（实际生效资源）和 `resize`（伸缩状态）字段，实现资源状态的四层追踪：期望 -> 已分配 -> 已执行 -> 实际。

## Design Details

1. **API 类型扩展**：在 `staging/src/k8s.io/api/core/v1/types.go` 和 `pkg/apis/core/types.go` 中：
   - 添加 `ContainerResizePolicy` 类型，包含 `resourceName` 和 `policy`（`RestartNotRequired` 或 `RestartContainer`）字段
   - 在 `Container` 中添加 `ResizePolicy []ContainerResizePolicy` 字段
   - 在 `ContainerStatus` 中添加 `Resources` 和 `ResourcesAllocated` 字段
   - 在 `PodStatus` 中添加 `Resize PodResizeStatus` 字段（取值为 `Proposed`、`InProgress`、`Deferred`、`Infeasible`）

2. **Feature Gate 注册**：在 `pkg/features/kube_features.go` 和 `staging/src/k8s.io/apiserver/pkg/features/kube_features.go` 中注册 `InPlacePodVerticalScaling` feature gate，Alpha 阶段默认关闭。

3. **API Validation**：在 `pkg/apis/core/validation/validation.go` 中：
   - 添加对 `resizePolicy` 的验证逻辑
   - 实现资源变更的验证规则（仅允许 cpu/memory，不能改变 QoS 类别）
   - 验证 `resourcesAllocated` 和 `resources` 字段

4. **Pod 工具函数**：在 `pkg/api/pod/util.go` 和 `pkg/api/v1/pod/util.go` 中：
   - 添加资源变更检测函数
   - 实现 feature gate 关闭时的字段剥离逻辑

5. **Kubelet 核心实现**：
   - 在 `pkg/kubelet/kubelet.go` 中添加资源伸缩的协调逻辑
   - 在 `pkg/kubelet/kubelet_pods.go` 中实现 Pod 资源分配和状态同步
   - 添加资源伸缩的调度优先级逻辑

6. **容器管理器更新**：
   - 在 `pkg/kubelet/cm/` 下更新 cgroup 管理器支持动态资源调整
   - 修改 `helpers_linux.go`、`cgroup_manager_linux.go` 支持 cgroup 限制的动态更新
   - 更新 `pod_container_manager_linux.go` 处理 Pod 级别的资源变更
   - 在 `cpumanager/policy_static.go` 和 `memorymanager/policy_static.go` 中添加静态策略 Pod 的伸缩限制

7. **Kuberuntime 实现**：在 `pkg/kubelet/kuberuntime/` 中：
   - 修改 `kuberuntime_container.go` 和 `kuberuntime_container_linux.go` 实现容器资源更新
   - 在 `kuberuntime_manager.go` 中添加资源伸缩的协调逻辑
   - 更新 `labels.go` 添加资源相关的标签
   - 实现 `helpers.go` 和 `helpers_linux.go` 中的资源计算辅助函数

8. **容器运行时接口**：在 `pkg/kubelet/container/` 中：
   - 更新 `runtime.go` 添加资源更新接口
   - 修改 `helpers.go` 支持资源状态查询

9. **状态管理器**：在 `pkg/kubelet/status/` 中：
   - 更新 `status_manager.go` 同步资源伸缩状态到 API server
   - 在 `state/` 子目录实现资源状态的本地持久化（checkpoint）

10. **调度器支持**：在 `pkg/scheduler/` 中：
    - 更新 `framework/types.go` 添加资源伸缩相关的数据结构
    - 修改 `framework/plugins/noderesources/fit.go` 支持伸缩资源的调度评估
    - 更新 `internal/queue/scheduling_queue.go` 处理资源伸缩 Pod 的重新调度

11. **QoS 和 Eviction**：
    - 在 `pkg/kubelet/qos/policy.go` 中更新 QoS 类别计算
    - 在 `pkg/kubelet/eviction/helpers.go` 中添加资源伸缩的驱逐考虑

12. **ResourceQuota 支持**：在 `pkg/quota/v1/evaluator/core/pods.go` 和 `staging/src/k8s.io/apiserver/pkg/admission/plugin/resourcequota/controller.go` 中更新配额计算逻辑。

13. **PLEG 更新**：在 `pkg/kubelet/pleg/` 中更新 Pod 生命周期事件生成器以支持资源变更事件。

14. **E2E 测试**：在 `test/e2e/node/pod_resize.go` 中添加全面的端到端测试用例。
