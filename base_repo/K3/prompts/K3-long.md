**Summary**: Kubernetes 的 image volume 功能在挂载 OCI image 作为 volume 时，不会在 Pod 状态中暴露 image 的 digest 信息。KEP-5365 提出在 `VolumeMountStatus` 中添加 image digest 信息，使用户和控制器能够确认 volume 实际挂载的 image 版本。

**Motivation**: 当用户通过 `spec.volumes[].image.reference` 使用 tag（如 `myimage:latest`）挂载 image volume 时，实际拉取的 image 可能随时间变化。当前 Kubernetes 不在 Pod status 中记录实际挂载的 image digest，导致用户和安全控制器无法确认运行中的 Pod 使用的是哪个具体 image 版本。这在安全审计、合规检查和 rollback 决策中是一个关键的可观察性缺失。

**Proposal**: 通过 `ImageVolumeWithDigest` feature gate 控制，在 Pod status 的 `VolumeMountStatus` 中添加嵌套的 volume 状态结构（包含 image reference 和 digest），在 kubelet 中通过 CRI runtime 查询 image digest 并填充到 Pod status，同时实现 feature gate 关闭时的字段剥离逻辑、API validation、以及相应的测试。

**Design Details**:

1. API 类型扩展：在 `VolumeMountStatus` 中添加一个嵌套结构体来承载 volume 状态信息。该结构体包含一个 image 子结构，存储 image reference（带 digest 的完整引用）。需要同时更新内部类型（`pkg/apis/core`）和外部类型（`staging/.../api/core/v1`），以及对应的 conversion、deepcopy 和 protobuf 定义。

2. Feature Gate：注册 `ImageVolumeWithDigest` feature gate，Alpha 阶段默认关闭。所有新字段的写入和暴露都必须受 feature gate 控制。

3. 字段剥离逻辑（Drop Logic）：当 feature gate 关闭时，API server 需要在 Pod create/update 时剥离新增字段。但如果已有数据中该字段非空（ratcheting 场景），应保留以避免数据丢失。需要在 Pod preparation/strategy 层实现此逻辑。

4. API Validation：在 Pod status validation 中增加对新字段的校验——验证 image reference 格式合法，且仅在 image volume mount 上出现。

5. Kubelet 实现：kubelet 在生成 Pod status 时，需要查询 CRI runtime 获取 image volume 的实际 image reference（含 digest）。这涉及：
   - 扩展 kuberuntime 模块，添加从 CRI image status 获取 digest 的能力
   - 在 Pod status 生成路径中，为每个 image volume mount 填充 digest 信息
   - 将 CRI 返回的 image reference 映射到 `VolumeMountStatus` 的新字段

6. CRI API 扩展：可能需要在 CRI proto 定义中增加 image digest 相关字段，以支持 kubelet 查询 image volume 的 digest 信息。

7. 生成代码：更新后需要重新生成 OpenAPI spec、client-go apply configurations、protobuf 代码等。

8. 测试：需要覆盖 feature gate 开/关场景的单元测试、字段剥离逻辑测试、validation 测试、以及 kubelet 层的 image digest 填充测试。
