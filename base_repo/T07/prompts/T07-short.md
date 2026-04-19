**Summary**: JDK 目前缺少一个简单的命令行 HTTP 服务器工具，用于快速提供静态文件服务。JEP 408 提出在 `jdk.httpserver` 模块中实现一个 Simple Web Server，提供开箱即用的命令行工具和可编程 API，用于测试、开发和调试目的的静态文件服务。

**Proposal**: 在 `jdk.httpserver` 模块中实现一个简单的文件服务器，提供 `jwebserver` 命令行工具和 `SimpleFileServer` 编程式 API，增强现有 API 添加 `Request` 接口和 `HttpHandlers` 工具类，支持 GET/HEAD 请求、目录列表、MIME 类型检测和可配置日志输出。
