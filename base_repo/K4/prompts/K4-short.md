**Summary**: Kubernetes 的授权子系统目前不考虑请求中的 field selector 和 label selector，这意味着授权器无法区分"列出所有 Pod"和"列出特定节点上的 Pod"。KEP-4601 提出在授权检查中传递 field/label selector 信息，使授权器能够基于 selector 做出更细粒度的决策，同时增强 Node authorizer 以利用 selector 限制节点只能访问与自身相关的资源。

**Proposal**: 通过 `AuthorizeWithSelectors` 和 `AuthorizeNodeWithSelectors` feature gate 控制，在 authorization API 的 ResourceAttributes 中新增 fieldSelector 和 labelSelector 字段，扩展 authorizer 接口以暴露 selector 信息，在请求处理链中解析 selector 并传入授权检查。
