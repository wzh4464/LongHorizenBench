# T38: Kubernetes Manifest-Based Admission Control Config

## Requirement
https://github.com/kubernetes/enhancements/blob/master/keps/sig-api-machinery/5793-manifest-based-admission-control-config/README.md

---

**Summary**: KEP-5793 提出为 kube-apiserver 添加基于文件清单（manifest）的准入控制配置功能。该功能允许通过文件系统上的清单文件配置准入 webhooks 和策略，这些策略在 API server 启动时加载，独立于 Kubernetes API 存在，无法通过 API 修改或删除。

**Motivation**: 当前 Kubernetes 的策略执行主要通过 API 对象实现（如 ValidatingAdmissionPolicy、MutatingWebhookConfiguration 等）。这种方式存在几个关键缺陷：

1. **启动时间差**：策略在 API 对象创建并被动态准入控制器读取后才生效，在集群初始化期间存在策略未生效的窗口期。
2. **自我保护缺失**：webhook 和 policy 配置对象本身不受 webhook 准入控制保护（为避免循环依赖），有足够权限的恶意或误操作用户可以删除关键准入策略。
3. **etcd 依赖**：当前准入配置依赖 etcd 可用性，如果 etcd 不可用或损坏，准入策略可能无法正确加载。

**Proposal**: 扩展 `AdmissionConfiguration` 资源，添加 `staticManifestsDir` 字段来指定包含准入配置的清单文件目录。这些清单文件在 API server 启动时加载，并在运行时监控文件变化动态重新加载。清单配置的策略在 API 配置的策略之前评估，提供平台级别的保护。

**Design Details**:

1. **扩展 AdmissionConfiguration Schema**：
   - 为 `WebhookAdmissionConfiguration` 添加 `staticManifestsDir` 字段
   - 为 `ValidatingAdmissionPolicyConfiguration` 添加 `staticManifestsDir` 字段
   - 为 `MutatingAdmissionPolicyConfiguration` 添加 `staticManifestsDir` 字段
   - 更新 `staging/src/k8s.io/apiserver/pkg/admission/plugin/webhook/config/apis/webhookadmission/` 下的类型定义

2. **创建 Policy Config API 类型**：
   - 在 `staging/src/k8s.io/apiserver/pkg/admission/plugin/policy/config/apis/policyconfig/` 下创建新的 API 类型
   - 定义 internal 类型（`types.go`）和 v1 版本类型
   - 实现 `register.go` 和 `install/install.go` 用于 scheme 注册

3. **实现清单加载器（Manifest Loader）**：
   - 在 `staging/src/k8s.io/apiserver/pkg/admission/plugin/manifest/` 下创建通用加载器
   - 实现从目录读取 YAML/JSON 文件的功能
   - 实现文件内容的解码、默认值填充和验证
   - 按字母顺序处理文件以保证确定性行为

4. **实现 Webhook 清单加载**：
   - 在 `staging/src/k8s.io/apiserver/pkg/admission/plugin/webhook/manifest/` 下创建 webhook 特定的加载器
   - 支持 `ValidatingWebhookConfiguration` 和 `MutatingWebhookConfiguration`
   - 验证只允许 URL 类型的 clientConfig（不支持 Service 引用）

5. **实现 Policy 清单加载**：
   - 在 `pkg/admission/plugin/policy/manifest/loader/` 下创建 policy 加载器
   - 支持 `ValidatingAdmissionPolicy`、`ValidatingAdmissionPolicyBinding`
   - 支持 `MutatingAdmissionPolicy`、`MutatingAdmissionPolicyBinding`
   - 验证不允许 `paramKind` 和 `paramRef`

6. **实现复合策略源（Composite Policy Source）**：
   - 在 `staging/src/k8s.io/apiserver/pkg/admission/plugin/policy/generic/` 下创建 `composite_policy_source.go`
   - 合并清单配置和 API 配置
   - 确保清单配置优先评估

7. **实现文件监控和动态重载**：
   - 使用 fsnotify 监控文件变化
   - 添加轮询回退机制（默认 1 分钟间隔）
   - 计算文件内容哈希用于变更检测
   - 验证失败时保留上一个有效配置

8. **命名和冲突解决**：
   - 强制清单对象名称必须以 `.static.k8s.io` 后缀结尾
   - 在 strategy 层阻止 REST API 创建带此后缀的对象
   - 更新 `pkg/registry/admissionregistration/*/strategy.go` 添加验证

9. **添加静态后缀验证**：
   - 在 `pkg/apis/admissionregistration/validation/` 下创建 `static_suffix.go`
   - 实现检查 `.static.k8s.io` 后缀的验证函数

10. **添加 Feature Gate**：
    - 在 `staging/src/k8s.io/apiserver/pkg/features/kube_features.go` 中注册 `ManifestBasedAdmissionControlConfig`
    - 在 `pkg/features/kube_features.go` 中同步添加

11. **添加指标和审计**：
    - 在 `staging/src/k8s.io/apiserver/pkg/admission/plugin/manifest/metrics/` 下添加指标
    - 记录重载计数和时间戳
    - 记录当前配置哈希用于漂移检测

12. **更新准入初始化器**：
    - 更新 `pkg/kubeapiserver/admission/initializer.go`
    - 更新 `staging/src/k8s.io/apiserver/pkg/admission/initializer/`
    - 传递清单目录配置到各准入插件

13. **编写测试**：
    - 为加载器编写单元测试
    - 为文件监控和重载编写测试
    - 为复合源编写测试
    - 添加集成测试验证端到端功能
