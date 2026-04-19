# T40: Kubernetes Pod Certificates

## Requirement
https://github.com/kubernetes/enhancements/blob/master/keps/sig-auth/4317-pod-certificates/README.md

---

**Summary**: KEP-4317 提出引入 Pod Certificates 功能，包括一个新的 `PodCertificateRequest` API 类型和 `podCertificate` 投射卷源（projected volume source）。该功能允许 kubelet 自动为 Pod 请求和管理 X.509 证书，使得向集群中每个 Pod 安全地、自动地交付证书变得可行。

**Motivation**: `certificates.k8s.io` API 组提供了在 Kubernetes 集群内请求 X.509 证书的灵活机制，但实际将证书交付给工作负载的实现留给了用户。当前存在以下问题：

1. **承载令牌依赖**：现有方案通常依赖 bearer token 进行身份验证，这降低了 mTLS 的安全性优势。
2. **第三方签名器实现困难**：安全实现第三方签名器需要深入理解 Kubernetes 安全模型，否则可能破坏节点隔离边界。
3. **证书生命周期管理复杂**：应用开发者需要自行处理密钥生成、证书请求、续期等复杂逻辑。

**Proposal**: 引入两个核心组件：
1. `PodCertificateRequest` API 类型 - 一个精简版的 `CertificateSigningRequest`，专门用于 Pod 证书签发，包含 Pod 身份信息
2. `podCertificate` 投射卷源 - 指示 kubelet 代表 Pod 处理密钥生成、证书请求和续期

**Design Details**:

1. **定义 PodCertificateRequest API 类型**：
   - 在 `staging/src/k8s.io/api/certificates/v1alpha1/` 下创建类型定义
   - Spec 字段包括：`signerName`、`podName`、`podUID`、`serviceAccountName`、`serviceAccountUID`、`nodeName`、`nodeUID`、`maxExpirationSeconds`、`stubPKCS10Request`
   - Status 字段包括：`conditions`、`certificateChain`、`issuedAt`、`notBefore`、`notAfter`、`beginRefreshAt`
   - 在 `pkg/apis/certificates/` 下创建 internal 类型

2. **实现 PodCertificateRequest 验证**：
   - 在 `pkg/apis/certificates/validation/` 下添加验证逻辑
   - 验证公钥类型（支持 RSA3072、RSA4096、ECDSAP256、ECDSAP384、ECDSAP521、ED25519）
   - 验证 PKCS#10 CSR 签名（持有证明）
   - 验证证书链格式（如果已签发）
   - 验证 `maxExpirationSeconds` 范围（最小 3600 秒，最大 7862400 秒）
   - 确保所有 Spec 字段不可变

3. **实现 PodCertificateRequest Storage**：
   - 在 `pkg/registry/certificates/podcertificaterequest/` 下创建 strategy 和 storage
   - 实现 `PrepareForCreate` 和 `PrepareForUpdate`
   - 实现 status 子资源的 strategy
   - 注册到 certificates.k8s.io API 组

4. **更新 Node Restriction 准入插件**：
   - 在 `plugin/pkg/admission/noderestriction/` 中添加 `PodCertificateRequest` 验证
   - 验证 namespace/pod/service account/node 信息与实际 Pod 匹配
   - 确保 Pod 已调度到指定节点
   - 确保 Pod 处于 Pending 或 Running 状态
   - 验证请求来自对应节点的 `system:node:xxx` 用户

5. **更新 Node Authorizer**：
   - 在 `plugin/pkg/auth/authorizer/node/` 中添加 `PodCertificateRequest` 授权逻辑
   - 允许节点为其上的 Pod 创建 `PodCertificateRequest`
   - 允许节点读取其创建的 `PodCertificateRequest`

6. **扩展 Pod API**：
   - 在 `pkg/apis/core/types.go` 中添加 `PodCertificateVolumeSource` 类型
   - 在 `ProjectedVolumeSource` 中添加 `podCertificate` 字段
   - 在 `staging/src/k8s.io/api/core/v1/` 下同步添加外部类型

7. **实现 Pod 验证**：
   - 在 `pkg/apis/core/validation/` 中添加 `podCertificate` 卷的验证
   - 验证 signerName 格式
   - 验证必需字段

8. **实现 Kubelet PodCertificateManager**：
   - 在 `pkg/kubelet/podcertificate/` 下创建管理器
   - 实现密钥对生成（支持多种密钥类型）
   - 实现 `PodCertificateRequest` 创建和监控
   - 实现证书续期逻辑（在 `beginRefreshAt` 时间开始续期）
   - 将证书和密钥写入 tmpfs 卷

9. **更新 Projected Volume 插件**：
   - 在 `pkg/volume/projected/` 中添加 `podCertificate` 源的处理
   - 调用 `PodCertificateManager` 获取证书
   - 将密钥和证书链写入容器文件系统

10. **添加 Feature Gate**：
    - 在 `pkg/features/kube_features.go` 中注册 `PodCertificateRequests` feature gate
    - 控制 `PodCertificateRequest` API 存储的启用
    - 控制 kubelet 中证书管理功能的启用

11. **实现证书清理控制器**：
    - 在 `pkg/controller/certificates/cleaner/` 下创建 `PodCertificateRequest` 清理器
    - 删除已过期或已完成的请求
    - 删除关联 Pod 已删除的请求

12. **更新 RBAC Bootstrap 策略**：
    - 在 `plugin/pkg/auth/authorizer/rbac/bootstrappolicy/` 中添加相关角色和绑定
    - 为 kubelet 添加 `podcertificaterequests` 的 create/get/watch 权限
    - 为签名器控制器添加 `podcertificaterequests/status` 的 update 权限和 signer 的 sign 权限

13. **编写测试**：
    - 添加 API 验证的单元测试
    - 添加 Node Restriction 准入的测试
    - 添加 Node Authorizer 的测试
    - 添加 PodCertificateManager 的单元测试和集成测试
    - 添加 Projected Volume 的集成测试
