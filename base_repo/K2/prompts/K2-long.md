**Summary**: Kubernetes 的 Job 控制器目前只在所有 Pod 成功完成时才将 Indexed Job 标记为成功。KEP-3998 提出 SuccessPolicy，允许用户定义基于部分索引成功的提前完成条件（如"索引 0-3 中任意 2 个成功即视为完成"），满足 MPI/科学计算等场景中 leader-worker 模式的需求。

**Motivation**: 在 HPC、MPI、科学计算等工作负载中，Indexed Job 的各索引 Pod 承担不同角色（如 index 0 是 leader）。当前 Job 只有在 `.status.succeeded >= .spec.completions` 时才算成功，无法表达"只要 leader 索引成功即可"或"N 个索引中 M 个成功即可"等语义。用户被迫在应用层自行处理提前终止，增加了复杂度。SuccessPolicy 作为 PodFailurePolicy 的对称特性，允许在 Job spec 中声明式定义成功条件，由控制器自动执行提前完成和剩余 Pod 清理。

**Proposal**: 在 batch/v1 API 中新增 SuccessPolicy 类型及相关字段，通过 `JobSuccessPolicy` feature gate 控制。在 Job 控制器中实现 SuccessPolicy 的匹配逻辑：当 Indexed Job 的已成功索引满足任一规则时，添加 `SuccessCriteriaMet` 中间条件，终止剩余 Pod，最终转为 `Complete` 状态。同时需要完善 API 校验、策略层 feature-gating、以及相应的单元测试和集成测试。

**Design Details**:

1. API 类型定义：
   - 新增 `SuccessPolicy` 结构体，包含 `Rules` 列表（最多 20 条规则，`+listType=atomic`）
   - 新增 `SuccessPolicyRule` 结构体，包含两个可选字段：`SucceededIndexes`（字符串，格式如 "0,2-5,8"，与 Job 已有的 completedIndexes 格式一致）和 `SucceededCount`（*int32，表示最少成功索引数）。每条规则至少指定其中一个
   - 在 `JobSpec` 中新增可选字段 `SuccessPolicy *SuccessPolicy`，要求仅用于 Indexed 模式，且创建后不可变
   - 新增 `JobConditionType` 常量 `SuccessCriteriaMet` 和对应的 `JobReason` 常量
   - 同步更新 internal types（pkg/apis/batch）、protobuf 定义、deepcopy 方法、OpenAPI spec

2. Feature Gate：
   - 注册 `JobSuccessPolicy` feature gate，alpha 阶段默认关闭
   - 在 API 策略层（PrepareForCreate / PrepareForUpdate）中，当 feature gate 关闭时清除 SuccessPolicy 字段（遵循已有的 PodFailurePolicy 模式，允许已存储数据的向后兼容读取）

3. API 校验：
   - 创建校验：SuccessPolicy 仅允许在 Indexed 模式下使用；Rules 不为空且不超过 20 条；每条 Rule 至少有一个字段；SucceededIndexes 需格式合法、索引在 `[0, completions)` 范围内；SucceededCount 为正整数且不超过 completions（若同时指定 SucceededIndexes，还需不超过 SucceededIndexes 覆盖的索引总数）
   - 更新校验：SuccessPolicy 字段不可变
   - 状态校验：SuccessCriteriaMet 条件的一致性约束——不能与 Failed/FailureTarget 同时为 True；非 Indexed Job 不能设置此条件；没有 SuccessPolicy 的 Job 不能有此条件；有 SuccessPolicy 的 Job 必须先有 SuccessCriteriaMet 才能设为 Complete；SuccessCriteriaMet 一旦设为 True 不可撤销
   - `validateIndexesFormat` 函数需增加返回索引总数的能力，以支持 SucceededCount 与 SucceededIndexes 的交叉校验

4. 控制器逻辑：
   - 匹配算法：遍历 SuccessPolicy 的规则列表，对每条规则检查已成功索引是否满足条件。当 SucceededIndexes 存在时，使用双指针法计算已成功索引与规则索引的交集大小；若无 SucceededCount 则要求完全覆盖，若有则要求交集大小 >= SucceededCount。仅指定 SucceededCount 时，直接比较已成功索引总数
   - 状态机集成：在 syncJob 中，优先检查是否已存在 SuccessCriteriaMet 条件（避免重复评估），若无则评估 SuccessPolicy。匹配成功时创建 SuccessCriteriaMet 中间条件，由后续流程转为最终的 Complete 条件
   - Pod 处理：当 Job 因 SuccessPolicy 完成时，剩余活跃 Pod 应被终止（移除 finalizer），但不应将其计入 failed 计数——这与 FailureTarget 导致的终止不同
   - 条件转换：SuccessCriteriaMet 作为中间条件先写入 Job status（与 FailureTarget 模式对称），finalizer 清理完成后再追加最终的 Complete 条件

5. 测试：
   - 控制器单元测试：覆盖 SuccessPolicy 匹配算法的各种组合（仅 SucceededIndexes、仅 SucceededCount、两者组合、多规则优先级、无匹配等）
   - 策略层单元测试：feature gate 开关对 SuccessPolicy 字段的影响
   - 校验单元测试：各种合法/非法输入、状态条件组合
   - 集成测试：端到端验证 Job 在 SuccessPolicy 下的完整生命周期——Pod 成功触发提前完成、剩余 Pod 被清理、条件正确设置
