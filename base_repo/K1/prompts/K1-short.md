**Summary**: Kubernetes 当前对环境变量名的校验规则严格遵循 C_IDENTIFIER 模式（字母/数字/下划线/点/短横线，不能以数字开头），这导致许多实际可用的环境变量名被 apiserver 拒绝。KEP-4369 提出放宽环境变量名校验规则，允许几乎所有可打印 ASCII 字符（除 `=` 外）作为环境变量名。

**Proposal**: 通过 `RelaxedEnvironmentVariableValidation` feature gate 控制新的宽松校验规则，在 apiserver 的 Pod 校验逻辑中根据 feature gate 状态选择严格或宽松规则，同时移除 kubelet 中对环境变量名的客户端校验和过滤逻辑。
