**Summary**: Kubernetes 的授权子系统目前不考虑请求中的 field selector 和 label selector，这意味着授权器无法区分"列出所有 Pod"和"列出特定节点上的 Pod"。KEP-4601 提出在授权检查中传递 field/label selector 信息，使授权器能够基于 selector 做出更细粒度的决策，同时增强 Node authorizer 以利用 selector 限制节点只能访问与自身相关的资源。

**Motivation**: 当前 Kubernetes 的授权模型只能基于 resource/verb/namespace/name 做访问控制，无法表达"仅允许列出自身节点上的 Pod"这类基于 selector 的细粒度策略。这对 Node authorizer 尤其重要——kubelet 在 list/watch Pod 和 ResourceSlice 时通常使用 field selector 限定 `spec.nodeName`，但授权层无法区分有 selector 和无 selector 的请求，因此只能给予节点过于宽泛的 list/watch 权限。此外，webhook authorizer 无法将 selector 信息传递给外部策略引擎，限制了自定义授权策略的表达能力。CEL 表达式中的 `authorizer` 变量也缺乏 selector 支持，无法在 admission policy 的 match condition 中检查 selector 相关的授权结果。

**Proposal**: 通过两个 feature gate 控制——`AuthorizeWithSelectors`（apiserver 级别，控制整体 selector 授权支持）和 `AuthorizeNodeWithSelectors`（kube 级别，控制 Node authorizer 的 selector 感知行为，依赖前者）。在 authorization API 的 ResourceAttributes 中新增 fieldSelector 和 labelSelector 字段，扩展 authorizer 接口以暴露 selector 信息，在请求处理链中解析 selector 并传入授权检查。

**Design Details**:

1. API 类型扩展：
   - 在 apimachinery 的 meta/v1 中新增 `FieldSelectorRequirement` 类型（包含 Key/Operator/Values），定义 `FieldSelectorOperator` 常量（In/NotIn/Exists/DoesNotExist），以及对应的验证函数 `ValidateFieldSelectorRequirement`，支持 `AllowUnknownOperatorInRequirement` 选项（用于 SubjectAccessReview 允许较新客户端的未知操作符通过验证）
   - 同步更新 `LabelSelectorValidationOptions`，增加 `AllowUnknownOperatorInRequirement` 选项
   - 在 `labels.Requirements` 上添加 `String()` 方法，在 `labels.Requirement` 上添加 `ValuesUnsorted()` 方法
   - 在 authorization API 的内部类型和 v1/v1beta1 版本中，为 ResourceAttributes 新增 `FieldSelector *FieldSelectorAttributes` 和 `LabelSelector *LabelSelectorAttributes` 字段
   - `FieldSelectorAttributes` 和 `LabelSelectorAttributes` 各包含 `RawSelector`（原始字符串）和 `Requirements`（解析后的结构化需求列表），两者互斥
   - v1beta1 版本的 selector 类型直接引用 v1 版本的类型定义
   - 更新 deepcopy 和 conversion 生成代码

2. Authorizer 接口扩展：
   - 在 `authorizer.Attributes` 接口中新增 `GetFieldSelector() (fields.Requirements, error)` 和 `GetLabelSelector() (labels.Requirements, error)` 方法
   - 在 `authorizer.AttributesRecord` 结构体中新增 `FieldSelectorRequirements`/`FieldSelectorParsingErr` 和 `LabelSelectorRequirements`/`LabelSelectorParsingErr` 字段，并实现接口方法

3. 请求信息和授权过滤器：
   - 在 `RequestInfo` 结构体中新增 `FieldSelector` 和 `LabelSelector` 字符串字段
   - 定义 `verbsWithSelectors`（list/watch/deletecollection）集合
   - 在 `NewRequestInfo` 中，当 feature gate 启用时，从 URL query 参数中提取 fieldSelector 和 labelSelector 到 RequestInfo，但跳过通过路径前缀指定 verb 的请求（deprecated verb-via-path 机制）
   - 在 `GetAuthorizerAttributes` 中，当 feature gate 启用时，将 RequestInfo 中的原始 selector 字符串解析为 `fields.Requirements` 和 `labels.Requirements`，存入 AttributesRecord

4. SubjectAccessReview 端点：
   - 在三个 REST 端点（SubjectAccessReview/SelfSubjectAccessReview/LocalSubjectAccessReview）的 Create 方法中，当 feature gate 未启用时清除 selector 字段
   - 更新 `ResourceAttributesFrom` helper 函数，当 feature gate 启用时解析 selector（支持 RawSelector 和 Requirements 两种输入格式），将其转换为 authorizer 内部表示
   - 实现 `labelSelectorAsSelector` 和 `fieldSelectorAsSelector` 转换函数，处理操作符映射（label 的 In/NotIn/Exists/DoesNotExist，field 的 In 映射为 Equals、NotIn 映射为 NotEquals）
   - 转换过程中跳过无法识别的操作符但保留已识别的部分（因为 requirements 是 AND 关系，跳过意味着更宽泛的检查，仍然安全）
   - 实现 `BuildEvaluationError` 函数，将授权评估错误和 selector 解析错误合并到 status.evaluationError 字段

5. Authorization API 验证：
   - 新增 `validateResourceAttributes`、`validateFieldSelectorAttributes`、`validateLabelSelectorAttributes` 函数
   - 验证规则：rawSelector 和 requirements 不可同时指定；指定了 selector 对象但两者均为空时报错；调用 apimachinery 的 `ValidateFieldSelectorRequirement`/`ValidateLabelSelectorRequirement` 验证每个 requirement，允许未知操作符

6. Node Authorizer 扩展（受 `AuthorizeNodeWithSelectors` feature gate 控制）：
   - 注册 `podResource` 和 `nodeResource` 变量
   - 新增 `authorizeNode` 方法：处理节点对 Node API 对象的访问——允许 create/update/patch（委托给 NodeRestriction admission plugin 做细粒度控制），get/list/watch 通过图遍历检查
   - 新增 `authorizePod` 方法：get 通过图遍历检查；list/watch 要求 field selector 中包含 `spec.nodeName=<nodeName>` 才允许（或有 name 限定时通过图遍历检查）；允许 create/delete（用于 mirror pod）、status update/patch、eviction create
   - 修改 `authorizeResourceSlice`：list/watch/deletecollection 从无条件允许改为要求 field selector 中包含 `nodeName=<nodeName>`

7. Webhook Authorizer 扩展：
   - 新增 `resourceAttributesFrom` 函数替代内联构造，当 feature gate 启用时将 authorizer attributes 中的 selector requirements 转换回 API 类型并包含在 webhook 请求中
   - 实现 `fieldSelectorToAuthorizationAPI` 和 `labelSelectorToAuthorizationAPI` 转换函数，将内部 selector requirements 转换为 API 的 `FieldSelectorRequirement`/`LabelSelectorRequirement`
   - v1 到 v1beta1 转换时传递 selector 字段

8. CEL 授权库扩展：
   - 新增 `AuthzSelectors` CEL 库（`k8s.authzSelectors`），提供 `fieldSelector(string)` 和 `labelSelector(string)` 两个 ResourceCheck 方法，用于在 CEL 表达式中附加 selector 到授权检查
   - 在 `resourceCheckVal` 中新增 `fieldSelector` 和 `labelSelector` 字段，在 `Authorize` 方法中解析并传入 authorizer
   - CEL 编译器中新增 AST 分析逻辑，检测表达式是否使用了 `fieldSelector`/`labelSelector`，在 `CompilationResult` 中记录 `UsesFieldSelector`/`UsesLabelSelector`
   - `ResourceAttributes` CEL 类型定义中有条件地（基于 feature gate）添加 `fieldSelector` 和 `labelSelector` 字段
   - `convertObjectToUnstructured` 新增 `includeFieldSelector`/`includeLabelSelector` 参数，仅在需要时转换 selector 数据
   - `CELMatcher` 结构体新增 `UsesFieldSelector`/`UsesLabelSelector` 标记，传递给数据转换函数

9. CEL 环境基础设施：
   - 在 `VersionedOptions` 中新增 `FeatureEnabled func() bool` 字段，用于基于 feature gate 控制 CEL 库的可用性
   - `AuthzSelectors` 库注册为 v1.31 引入的 versioned option，FeatureEnabled 绑定到 `AuthorizeWithSelectors` feature gate
   - `filterAndBuildOpts` 方法新增 `honorFeatureGateEnablement` 参数：NewExpressions 环境检查 feature gate，StoredExpressions 环境忽略 feature gate
   - 使用 `sync.Once` + `atomic.Value` 追踪 authz selectors 库的初始化和启用状态，供集成测试验证
   - 将 validating admission plugin 中的 composition environment 从 package-level 变量改为 `sync.Once` 延迟初始化，确保 feature gate 在 CEL 环境构建前已设置

10. Caching Authorizer 更新：
    - 更新缓存键构造逻辑，包含 field selector requirements 和 label selector 字符串表示（labels.Requirements 含私有字段，使用 String() 方法序列化）
    - 确保不同 selector 的授权请求不会命中相同的缓存条目

11. 测试覆盖：
    - Authorization API 验证测试：field/label selector 的各种有效/无效组合（both specified、neither specified、unknown operator、missing key、missing values、forbidden values）
    - Node authorizer 测试：Pod list/watch 需要 spec.nodeName selector、Node get/list/create/update/patch/status、ResourceSlice 需要 nodeName selector
    - Webhook authorizer 测试：验证 selector 信息正确传递给 webhook 请求
    - CEL 授权库测试：fieldSelector/labelSelector 函数的编译和运行
    - Caching authorizer 测试：selector 作为缓存键的独立性
    - RequestInfo 测试：selector 从 URL query 参数中正确提取
    - 授权过滤器测试：selector 解析和传递
    - 集成测试：AuthzSelectors CEL 库在 feature gate 启用/禁用时的行为
    - 集成测试：webhook 配置中使用 selector 的 match condition 的端到端流程
