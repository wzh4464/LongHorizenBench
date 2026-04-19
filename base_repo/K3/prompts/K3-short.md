**Summary**: Kubernetes 的 image volume 功能在挂载 OCI image 作为 volume 时，不会在 Pod 状态中暴露 image 的 digest 信息。KEP-5365 提出在 `VolumeMountStatus` 中添加 image digest 信息，使用户和控制器能够确认 volume 实际挂载的 image 版本。

**Proposal**: 通过 `ImageVolumeWithDigest` feature gate 控制，在 Pod status 的 `VolumeMountStatus` 中添加嵌套的 volume 状态结构（包含 image reference 和 digest），在 kubelet 中通过 CRI runtime 查询 image digest 并填充到 Pod status，同时实现 feature gate 关闭时的字段剥离逻辑、API validation、以及相应的测试。
