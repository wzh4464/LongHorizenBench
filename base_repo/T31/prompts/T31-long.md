# T31: Envoy Proxy

**Summary**: Envoy 作为高性能的服务网格 Sidecar 代理，虽然使用现代 C++ 保证了高性能，但也增加了扩展开发的难度。当前 Envoy 支持 Lua 和 WASM 扩展，但在某些场景存在性能和功能局限性。本任务提出为 Envoy 添加 GoLang HTTP Filter 扩展能力，允许用户通过 Go 语言开发高性能的 L7 过滤器插件，无需重新编译 Envoy 即可动态加载。

**Motivation**: 云原生生态系统中 Go 语言拥有丰富的 SDK 和库支持，许多服务网格用户更熟悉 Go 而非 C++。虽然 WASM 提供了扩展能力，但在某些场景下存在内存复制开销和功能限制。Go 扩展可以直接利用 Go 的云原生生态（如 Dapr、MOSN），避免 WASM 的序列化/反序列化开销，同时比 Lua 提供更完善的类型系统和工具链支持。这使得 Envoy 能够更好地服务于需要快速迭代业务逻辑的场景。

**Proposal**: 实现一个 Envoy contrib 扩展模块，包含 C++ 侧的 HTTP Golang Filter 和 Go 侧的 SDK。C++ Filter 通过 CGO 机制加载和调用 Go 编译的动态链接库（.so），Go SDK 提供 StreamFilter 接口供用户实现自定义过滤逻辑。配置通过 protobuf 定义，支持指定动态库路径、插件名称和插件配置。

**Design Details**:

1. Protobuf API 定义：在 `api/contrib/envoy/extensions/filters/http/golang/v3alpha/` 目录下创建 BUILD 和 golang.proto 文件，定义 Config 消息类型，包含 library_id、library_path、plugin_name、plugin_config 和 merge_policy 字段。

2. DSO (Dynamic Shared Object) 加载层：在 `contrib/golang/filters/http/source/common/dso/` 下实现动态库加载机制，包括 dso.h/dso.cc 定义 DSO 类管理动态库生命周期，api.h 声明 C 接口函数签名，libgolang.h 提供 Go 运行时初始化接口。

3. C++ Filter 实现：在 `contrib/golang/filters/http/source/` 下实现核心过滤器逻辑：
   - golang_filter.h/cc：实现 StreamDecoderFilter 和 StreamEncoderFilter 接口
   - processor_state.h/cc：管理请求/响应处理状态机
   - config.h/cc：实现 FilterConfigFactory
   - cgo.cc：CGO 桥接层，处理 C++ 到 Go 的调用

4. Go SDK 实现：在 `contrib/golang/filters/http/source/go/` 下提供 Go 侧开发框架：
   - pkg/api/：定义 StreamFilter 接口（包含 DecodeHeaders, DecodeData, EncodeHeaders, EncodeData 等方法）和相关类型
   - pkg/http/：实现 filter manager、配置解析、CGO 回调实现
   - pkg/utils/：字符串和内存操作工具函数
   - main.go 和 export.go：导出符号供 C++ 侧调用

5. Bazel 构建配置：更新 `contrib/contrib_build_config.bzl` 注册新扩展，更新 `bazel/dependency_imports.bzl` 添加 Go 依赖，更新 `bazel/exported_symbols.txt` 导出必要符号。

6. 单元测试和集成测试：在 `contrib/golang/filters/http/test/` 下编写测试用例，包括 DSO 加载测试、Filter 配置测试、Filter 功能测试，以及 test_data 目录下的示例 Go 插件（echo、passthrough）。

7. 文档：在 `docs/root/configuration/http/http_filters/` 下添加 golang_filter.rst 文档，说明配置方式和使用示例。

8. 元数据和变更日志：更新 `contrib/extensions_metadata.yaml` 添加扩展元数据，更新 `changelogs/current.yaml` 记录新功能。

## Requirement
https://github.com/envoyproxy/envoy/issues/15152
