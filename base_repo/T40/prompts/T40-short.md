**Summary**: KEP-4317 提出引入 Pod Certificates 功能，包括一个新的 `PodCertificateRequest` API 类型和 `podCertificate` 投射卷源（projected volume source）。该功能允许 kubelet 自动为 Pod 请求和管理 X.509 证书，使得向集群中每个 Pod 安全地、自动地交付证书变得可行。

**Proposal**: 引入 `PodCertificateRequest` API 类型作为精简版的 `CertificateSigningRequest`，专门用于 Pod 证书签发并包含 Pod 身份信息；同时引入 `podCertificate` 投射卷源，指示 kubelet 代表 Pod 处理密钥生成、证书请求和续期。
