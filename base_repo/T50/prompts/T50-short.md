**Summary**: KEP-3063 引入动态资源分配（Dynamic Resource Allocation, DRA）功能，提供比现有 Device Plugins 更灵活的资源管理机制。DRA 允许 Pod 请求（claim）特殊类型的资源，这些资源可以是节点级别、集群级别或任意自定义模型。通过新的 `resource.k8s.io` API 组，定义 `ResourceClaim`、`ResourceClass`、`ResourceClaimTemplate` 和 `PodScheduling` 等资源类型，实现资源的声明、分配和调度协调。

**Proposal**: 引入新的 `resource.k8s.io/v1alpha1` API 组，包含 `ResourceClass` 定义资源类型和驱动程序、`ResourceClaim` 声明对特定资源的需求、`ResourceClaimTemplate` 用于创建 ResourceClaim 的模板、`PodScheduling` 协调 Pod 调度和资源分配。在 Pod 规格中添加 `resourceClaims` 字段引用 ResourceClaim，容器通过 `resources.claims` 引用需要的资源。
