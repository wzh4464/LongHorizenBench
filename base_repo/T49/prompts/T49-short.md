**Summary**: KEP-1287 实现了 Kubernetes Pod 的就地垂直伸缩功能，允许在不重启 Pod 或容器的情况下动态调整容器的 CPU 和内存资源请求与限制。这解决了传统方式下修改资源配置必须销毁并重建 Pod 的限制，对有状态工作负载和需要高可用性的服务尤为重要。

**Proposal**: 将 `spec.containers[].resources` 字段改为可变（仅限 `cpu` 和 `memory`），引入 `resizePolicy` 字段控制每种资源的调整行为。在 `status` 中添加 `allocatedResources`、`resources` 和 `resize` 字段，实现资源状态的四层追踪：期望、已分配、已执行、实际。
