**Summary**: Envoy 作为高性能的服务网格 Sidecar 代理，虽然使用现代 C++ 保证了高性能，但也增加了扩展开发的难度。当前 Envoy 支持 Lua 和 WASM 扩展，但在某些场景存在性能和功能局限性。本任务提出为 Envoy 添加 GoLang HTTP Filter 扩展能力，允许用户通过 Go 语言开发高性能的 L7 过滤器插件，无需重新编译 Envoy 即可动态加载。

**Proposal**: 实现一个 Envoy contrib 扩展模块，包含 C++ 侧的 HTTP Golang Filter 和 Go 侧的 SDK。C++ Filter 通过 CGO 机制加载和调用 Go 编译的动态链接库（.so），Go SDK 提供 StreamFilter 接口供用户实现自定义过滤逻辑。配置通过 protobuf 定义，支持指定动态库路径、插件名称和插件配置。
