**Summary**: Kubernetes 当前对环境变量名的校验规则严格遵循 C_IDENTIFIER 模式（字母/数字/下划线/点/短横线，不能以数字开头），这导致许多实际可用的环境变量名被 apiserver 拒绝。KEP-4369 提出放宽环境变量名校验规则，允许几乎所有可打印 ASCII 字符（除 `=` 外）作为环境变量名。

**Motivation**: 现有的环境变量名校验基于正则 `[-._a-zA-Z][-._a-zA-Z0-9]*`，拒绝以数字开头的名称以及包含空格、特殊符号等字符的名称。然而 Linux 内核本身并不限制环境变量名中的字符（只要不含 `=` 和 NUL），许多第三方软件（如 .NET runtime、某些监控 agent）使用不符合 C_IDENTIFIER 的环境变量名。当用户通过 ConfigMap/Secret 的 envFrom 注入这些键时，kubelet 会静默跳过"无效"键并产生 Warning Event，导致应用行为不符合预期且难以排查。放宽校验规则可以消除这种不必要的限制，同时保持 `=` 字符的禁止（因为它是环境变量赋值分隔符）。

**Proposal**: 通过 `RelaxedEnvironmentVariableValidation` feature gate 控制新的宽松校验规则。在 apimachinery 的 validation 包中新增宽松校验函数，在 apiserver 的 Pod 校验逻辑中根据 feature gate 状态选择严格或宽松规则校验 `env[].name` 和 `envFrom[].prefix`。同时移除 kubelet 中对来自 ConfigMap/Secret 的环境变量名的客户端校验和过滤逻辑，确保宽松规则下所有键都能被正确注入。需要添加 feature gate 定义、Pod 校验选项扩展、ratcheting 支持、以及相应的单元测试和 e2e 测试。

**Design Details**:

1. Feature Gate 定义：在 kube_features 中注册 `RelaxedEnvironmentVariableValidation` feature gate，初始阶段为 Alpha（默认关闭）。

2. 宽松校验函数：在 apimachinery 的 validation 包中新增 `IsRelaxedEnvVarName` 函数。该函数检查每个字符是否为可打印 ASCII 字符且不为 `=`，空字符串视为无效。错误消息应明确说明宽松规则的字符范围。

3. API 校验层改造：
   - 在 PodValidationOptions 中新增 `AllowRelaxedEnvironmentVariableValidation` 布尔字段
   - ValidateEnv 和 ValidateEnvFrom 函数根据该选项决定调用 `IsEnvVarName`（严格）还是 `IsRelaxedEnvVarName`（宽松）
   - ValidateEnvFrom 需要接受 PodValidationOptions 参数（当前不接受），以便传递宽松校验选项

4. Ratcheting（向后兼容保护）：当已有 Pod 使用了宽松规则的环境变量名时（即已通过 relaxed 校验但未通过 strict 校验的名称已存在于旧 PodSpec 中），即使 feature gate 关闭，更新操作也应允许保留这些名称。实现方式：在构建 PodValidationOptions 时，遍历新旧 PodSpec 中所有容器（包括 init 容器和 ephemeral 容器）的 env name 和 envFrom prefix，判断是否需要启用宽松校验。

5. Kubelet 侧改造：移除 `makeEnvironmentVariables` 函数中对 ConfigMap 和 Secret envFrom 键名的客户端校验逻辑——当前实现会对每个键调用 `IsEnvVarName`，跳过不合规的键并发出 Warning Event。宽松规则下这些键应被直接注入，无需客户端过滤。

6. API 类型文档更新：更新 EnvVar 的 Name 字段注释，说明在 feature gate 开启和关闭两种情况下的校验规则差异。

7. 测试：
   - 单元测试：覆盖 `IsRelaxedEnvVarName` 的合法/非法用例；覆盖 ValidateEnv 和 ValidateEnvFrom 在宽松/严格模式下的行为差异；覆盖 ratcheting 场景（旧 Pod 已使用宽松名称时的更新行为）
   - Kubelet 测试：验证 feature gate 开启后 ConfigMap/Secret envFrom 不再跳过以数字开头的键名
   - E2E 测试：标记 `RelaxedEnvironmentVariableValidation` feature tag，验证 Pod 可以使用各种可打印 ASCII 字符作为环境变量名；验证 ConfigMap/Secret envFrom 的 prefix 可以以数字开头
