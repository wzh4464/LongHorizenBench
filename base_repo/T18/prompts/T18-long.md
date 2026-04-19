# T18: Vitess

**Summary**: Vitess 代码库中存在大量分散的配置管理方式，缺乏统一的框架。本任务要求基于 viper 库实现一套标准化的配置管理框架（viperutil），提供类型安全的配置值定义、动态配置重载、以及可自动化的配置文档生成能力。

**Motivation**: Vitess 是一个庞大的代码库，配置管理方式多样且缺乏一致性。开发者在添加新配置时不知道应该放在哪里、如何定义；用户在查找配置选项时也难以找到完整的文档。当前的全局 viper 单例使用方式存在几个问题：(1) 配置值的访问缺乏编译时类型安全；(2) 配置键名分散在代码各处，容易出现拼写错误；(3) 难以自动生成配置文档；(4) viper 本身不是线程安全的，动态配置更新可能导致竞态条件。

**Proposal**: 在 `go/viperutil` 包中实现配置管理框架。提供 `Configure[T]` 泛型函数用于声明配置值，返回类型安全的 `Value[T]` 对象。支持静态和动态两种配置模式：静态配置在启动时加载一次，动态配置可以响应配置文件变化实时更新。通过 `sync.Viper` 包装器解决 viper 的线程安全问题。

**Design Details**:

1. 核心 API 设计：实现 `viperutil.Configure[T](key string, options Options[T]) Value[T]` 函数。`Options` 结构包含：`Default`（默认值）、`FlagName`（关联的 flag 名）、`EnvVars`（环境变量列表）、`Aliases`（键别名）、`Dynamic`（是否动态）、`GetFunc`（自定义获取函数）。

2. Value 类型：定义 `Value[T]` 接口，提供 `Get() T` 方法获取当前值，`Default() T` 方法获取默认值。静态值在首次 `Get` 时从 viper 读取并缓存；动态值每次 `Get` 都从 viper 读取。

3. GetFunc 自动推断：在 `get_func.go` 中实现 `GetFuncForType[T]` 函数。使用反射为常见类型（string、int、bool、duration、slice 等）自动生成 getter。对于不支持的类型，在测试时 panic 提示开发者提供自定义 GetFunc。

4. 动态配置与线程安全：在 `internal/sync/sync.go` 中实现 `sync.Viper` 包装器。为每个动态配置值分配 `sync.RWMutex`。当检测到配置文件变化时，锁定所有动态值的写锁进行更新。值的 `Get` 方法使用读锁保护。

5. 注册表管理：在 `internal/registry/registry.go` 中维护所有已注册配置值的注册表。提供遍历能力用于生成文档和调试。

6. Flag 绑定：实现 `viperutil.BindFlags(values ...Bindable)` 函数。由于 `Configure` 通常在 `var` 块中调用（早于 flag 注册），flag 绑定需要延迟到 `servenv.OnParse` 钩子中执行。

7. 配置加载：实现 `viperutil.LoadConfig` 函数作为配置加载入口。搜索配置文件、绑定环境变量、启动文件监视（如果有动态配置）。

8. 调试支持：在 `debug/` 子包中实现配置调试端点。提供 HTTP handler 展示当前所有配置值及其来源。

9. 集成示例：更新 `go/trace/trace.go` 等模块使用新框架。将现有的 flag 定义和 viper 使用迁移到 `viperutil.Configure` 模式。

10. 文档：创建 `doc/viper/viper.md` 说明框架的设计原理、使用方法和最佳实践。

## Requirement
https://github.com/vitessio/vitess/issues/11788
