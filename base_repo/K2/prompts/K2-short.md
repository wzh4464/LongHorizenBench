**Summary**: Kubernetes 的 Job 控制器目前只在所有 Pod 成功完成时才将 Indexed Job 标记为成功。KEP-3998 提出 SuccessPolicy，允许用户定义基于部分索引成功的提前完成条件（如"索引 0-3 中任意 2 个成功即视为完成"），满足 MPI/科学计算等场景中 leader-worker 模式的需求。

**Proposal**: 在 batch/v1 API 中新增 SuccessPolicy 类型及相关字段，通过 `JobSuccessPolicy` feature gate 控制。在 Job 控制器中实现 SuccessPolicy 的匹配逻辑：当 Indexed Job 的已成功索引满足任一规则时，添加 `SuccessCriteriaMet` 中间条件，终止剩余 Pod，最终转为 `Complete` 状态。同时需要完善 API 校验、策略层 feature-gating、以及相应的单元测试和集成测试。
