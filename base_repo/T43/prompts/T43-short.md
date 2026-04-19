**Summary**: KEP-4960 提出在 Kubernetes 的容器规范中添加可配置的停止信号（Stop Signal）支持，允许用户在 Pod 定义中指定容器停止时使用的信号，而无需重新构建镜像。该特性通过在 `Container.Lifecycle` 中添加 `StopSignal` 字段实现，并在容器状态中报告实际使用的停止信号。

**Proposal**: 通过 `ContainerStopSignals` feature gate 控制，在容器的 `Lifecycle` 结构中添加 `StopSignal` 字段。该字段接受符合 Go `syscall.Signal` 格式的字符串值（如 "SIGTERM"、"SIGUSR1"）。停止信号的优先级为：容器规范中的 StopSignal > 镜像中的 STOPSIGNAL > 容器运行时默认值。同时在 `ContainerStatus` 中添加 `StopSignal` 字段以报告实际使用的停止信号。
