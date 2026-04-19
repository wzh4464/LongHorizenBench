# T43: Kubernetes - KEP-4960 Container Stop Signals

**Summary**: KEP-4960 提出在 Kubernetes 的容器规范中添加可配置的停止信号（Stop Signal）支持，允许用户在 Pod 定义中指定容器停止时使用的信号，而无需重新构建镜像。该特性通过在 `Container.Lifecycle` 中添加 `StopSignal` 字段实现，并在容器状态中报告实际使用的停止信号。

**Motivation**: 当前 Kubernetes 停止容器时使用的信号由容器镜像的 `STOPSIGNAL` 指令或容器运行时的默认值（通常是 SIGTERM）决定。这存在以下问题：
1. **灵活性不足**：用户无法在不修改镜像的情况下更改停止信号
2. **镜像依赖**：许多第三方镜像可能没有正确设置 `STOPSIGNAL`，导致容器无法优雅关闭
3. **场景限制**：某些应用程序（如需要 SIGUSR1 的自定义应用）需要特定的停止信号来执行清理操作

**Proposal**: 通过 `ContainerStopSignals` feature gate 控制，在容器的 `Lifecycle` 结构中添加 `StopSignal` 字段。该字段接受符合 Go `syscall.Signal` 格式的字符串值（如 "SIGTERM"、"SIGUSR1"）。停止信号的优先级为：容器规范中的 StopSignal > 镜像中的 STOPSIGNAL > 容器运行时默认值。同时在 `ContainerStatus` 中添加 `StopSignal` 字段以报告实际使用的停止信号。

**Design Details**:

1. **API 类型扩展**：
   - 在 `pkg/apis/core/types.go` 的 `Lifecycle` 结构体中添加 `StopSignal *string` 字段
   - 在 `staging/src/k8s.io/api/core/v1/types.go` 的外部 API 类型中添加对应字段
   - 在 `ContainerStatus` 结构体中添加 `StopSignal string` 字段用于状态报告
   - 运行 `make generate` 更新 deepcopy、conversion 和 protobuf 代码

2. **Feature Gate 注册**：在 `pkg/features/kube_features.go` 中注册 `ContainerStopSignals` feature gate，Alpha 阶段默认关闭。

3. **字段剥离逻辑（Drop Logic）**：在 `pkg/api/pod/util.go` 中实现 `dropContainerStopSignals()` 函数：
   - 当 feature gate 关闭时，剥离 `Lifecycle.StopSignal` 字段
   - 实现 `containerStopSignalsInUse()` 函数检测已有数据中是否使用了该字段（ratcheting 场景）
   - 修改 `dropPodLifecycleSleepAction()` 中的 Lifecycle nil 检查逻辑，确保考虑 StopSignal 字段

4. **API Validation**：在 `pkg/apis/core/validation/validation.go` 中添加验证逻辑：
   - 验证 `StopSignal` 值可解析为有效的信号名称
   - Linux Pod 支持标准 POSIX 信号
   - Windows Pod 仅支持 SIGTERM 和 SIGKILL
   - 要求 Pod 必须设置 `spec.os.name` 才能使用 StopSignal

5. **CRI API 扩展**：在 `staging/src/k8s.io/cri-api/pkg/apis/runtime/v1/api.proto` 中，向 `ContainerConfig` 添加 `stop_signal` 字段，使 kubelet 能够将信号配置传递给容器运行时。

6. **Kubelet 实现**：
   - 在 `pkg/kubelet/kuberuntime/kuberuntime_container.go` 中，创建容器时将 `StopSignal` 传递给 CRI
   - 在 `pkg/kubelet/kuberuntime/helpers.go` 中添加辅助函数处理信号名称解析
   - 在 `pkg/kubelet/kubelet_pods.go` 中，生成 Pod 状态时填充 `ContainerStatus.StopSignal`
   - 在 `pkg/kubelet/container/runtime.go` 中更新相关接口定义

7. **测试用例**：
   - 在 `pkg/api/pod/util_test.go` 中添加 `TestDropContainerStopSignals` 测试字段剥离逻辑
   - 在 `pkg/apis/core/validation/validation_test.go` 中添加 StopSignal 验证测试
   - 在 `pkg/kubelet/kuberuntime/kuberuntime_container_linux_test.go` 中添加 kubelet 相关测试
   - 在 `pkg/api/pod/testing/make.go` 中添加 `SetContainerLifecycle` 测试辅助函数

8. **E2E 测试**：
   - 在 `test/e2e/common/node/lifecycle_hook.go` 中添加 StopSignal 相关的端到端测试
   - 在 `test/e2e/feature/feature.go` 中注册相关特性标签

9. **OpenAPI 规范更新**：更新 `api/openapi-spec/` 下的 swagger.json 和 v3 openapi.json 文件，添加 StopSignal 字段的描述。
