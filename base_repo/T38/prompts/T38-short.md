**Summary**: KEP-5793 提出为 kube-apiserver 添加基于文件清单（manifest）的准入控制配置功能。该功能允许通过文件系统上的清单文件配置准入 webhooks 和策略，这些策略在 API server 启动时加载，独立于 Kubernetes API 存在，无法通过 API 修改或删除。

**Proposal**: 扩展 `AdmissionConfiguration` 资源，添加 `staticManifestsDir` 字段来指定包含准入配置的清单文件目录。这些清单文件在 API server 启动时加载，并在运行时监控文件变化动态重新加载。清单配置的策略在 API 配置的策略之前评估，提供平台级别的保护。
