# T50: Kubernetes - 实现动态资源分配（DRA）

## Requirement

https://github.com/kubernetes/enhancements/blob/master/keps/sig-node/3063-dynamic-resource-allocation/README.md

## Summary

KEP-3063 引入动态资源分配（Dynamic Resource Allocation, DRA）功能，提供比现有 Device Plugins 更灵活的资源管理机制。DRA 允许 Pod 请求（claim）特殊类型的资源，这些资源可以是节点级别、集群级别或任意自定义模型。通过新的 `resource.k8s.io` API 组，定义 `ResourceClaim`、`ResourceClass`、`ResourceClaimTemplate` 和 `PodScheduling` 等资源类型，实现资源的声明、分配和调度协调。

## Motivation

现有的 Device Plugins 机制存在以下限制：
- 资源必须以整数数量表示，难以描述复杂资源
- 仅支持节点本地资源
- 不支持资源共享
- 缺乏资源初始化和清理的钩子
- 无法在调度前进行资源准备

DRA 解决这些问题，支持：
- GPU/FPGA 等需要复杂配置的设备
- 网络连接的加速器
- 需要组合使用的硬件功能
- 跨 Pod 共享的资源

## Proposal

引入新的 `resource.k8s.io/v1alpha1` API 组，包含以下核心资源：
- **ResourceClass**：定义资源类型和驱动程序
- **ResourceClaim**：声明对特定资源的需求
- **ResourceClaimTemplate**：用于创建 ResourceClaim 的模板
- **PodScheduling**：协调 Pod 调度和资源分配

在 Pod 规格中添加 `resourceClaims` 字段引用 ResourceClaim，容器通过 `resources.claims` 引用需要的资源。调度器与资源驱动控制器协作，通过 PodScheduling 对象协商资源分配。

## Design Details

1. **API 类型定义**：在 `staging/src/k8s.io/api/resource/v1alpha1/` 中创建：
   - `types.go`：定义 ResourceClass、ResourceClaim、ResourceClaimTemplate、PodScheduling、AllocationResult 等类型
   - `register.go`：注册 API 类型到 scheme
   - `doc.go`：包文档

2. **内部 API 类型**：在 `pkg/apis/resource/` 中：
   - `types.go`：内部版本的类型定义
   - `register.go`：注册到 scheme
   - 在 `v1alpha1/` 子目录实现版本转换和默认值

3. **API Validation**：在 `pkg/apis/resource/validation/` 中实现：
   - ResourceClass 的验证
   - ResourceClaim 的验证（名称、参数、分配模式）
   - ResourceClaimTemplate 的验证
   - PodScheduling 的验证

4. **Core API 扩展**：在 `staging/src/k8s.io/api/core/v1/types.go` 和 `pkg/apis/core/types.go` 中：
   - 添加 `ClaimSource` 类型（引用 ResourceClaim 或 ResourceClaimTemplate）
   - 添加 `PodResourceClaim` 类型
   - 在 `PodSpec` 中添加 `ResourceClaims` 字段
   - 在 `ResourceRequirements` 中添加 `Claims` 字段

5. **Feature Gate**：在 `pkg/features/kube_features.go` 中注册 `DynamicResourceAllocation` feature gate。

6. **Registry 实现**：在 `pkg/registry/resource/` 中为每个资源类型实现：
   - `strategy.go`：创建/更新策略
   - `storage/storage.go`：REST 存储实现

7. **控制器实现**：在 `pkg/controller/resourceclaim/` 中：
   - `controller.go`：ResourceClaim 控制器，处理 claim 的生命周期
   - `uid_cache.go`：UID 缓存实现
   - `metrics/metrics.go`：控制器指标

8. **调度器插件**：在 `pkg/scheduler/framework/plugins/dynamicresources/` 中：
   - `dynamicresources.go`：实现 Filter、Reserve、PreBind 等调度阶段
   - 与资源驱动控制器通过 PodScheduling 协调
   - 更新 `plugins/names/names.go` 和 `plugins/registry.go`

9. **Kubelet 集成**：在 `pkg/kubelet/cm/dra/` 中：
   - `manager.go`：DRA 管理器实现
   - `claiminfo.go`：claim 信息管理
   - `cdi.go`：CDI（Container Device Interface）集成
   - `plugin/`：插件客户端和存储

10. **DRA 插件 API**：在 `staging/src/k8s.io/kubelet/pkg/apis/dra/v1alpha1/` 中：
    - `api.proto`：gRPC 接口定义

11. **动态资源分配库**：在 `staging/src/k8s.io/dynamic-resource-allocation/` 中：
    - `controller/`：通用控制器实现
    - `kubeletplugin/`：kubelet 插件框架
    - `resourceclaim/`：claim 处理工具

12. **RBAC 策略**：在 `plugin/pkg/auth/authorizer/rbac/bootstrappolicy/` 中：
    - 更新 `controller_policy.go` 添加控制器权限
    - 更新 `policy.go` 添加资源访问规则

13. **控制平面集成**：
    - 在 `cmd/kube-controller-manager/app/` 中注册 ResourceClaim 控制器
    - 在 `cmd/kube-apiserver/app/` 中注册 resource API
    - 在 `pkg/controlplane/instance.go` 中添加 REST 存储

14. **E2E 测试**：在 `test/e2e/dra/` 中：
    - `dra.go`：DRA 功能测试
    - `test-driver/`：测试驱动实现
    - 部署清单和示例资源
