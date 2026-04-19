**Summary**: JDK 目前缺少一个简单的命令行 HTTP 服务器工具，用于快速提供静态文件服务。JEP 408 提出在 `jdk.httpserver` 模块中实现一个 Simple Web Server，提供开箱即用的命令行工具和可编程 API，用于测试、开发和调试目的的静态文件服务。

**Motivation**: 开发人员在测试、原型验证和临时文件共享时，经常需要一个简单的 HTTP 服务器来提供静态文件服务。当前 JDK 虽然有 `com.sun.net.httpserver` 包提供底层 HTTP 服务器 API，但使用起来需要编写大量样板代码。其他语言（如 Python 的 `python -m http.server`）早已提供了类似的便捷工具。JEP 408 旨在填补这一空白，同时增强现有 HTTP 服务器 API 的可用性。

**Proposal**: 在 `jdk.httpserver` 模块中实现一个简单的文件服务器：(1) 提供 `jwebserver` 命令行工具，可通过 `java -m jdk.httpserver` 启动；(2) 创建 `SimpleFileServer` 类提供编程式 API 来创建文件服务器、文件处理器和输出过滤器；(3) 增强现有 API，添加 `Request` 接口、`HttpHandlers` 工具类、以及 `Headers` 和 `Filter` 的新工厂方法；(4) 支持 GET 和 HEAD 请求、目录列表、MIME 类型检测和可配置的日志输出。

**Design Details**:

1. 命令行入口点：在 `jdk.httpserver` 模块的 `module-info.java` 中声明 main class。创建 `sun.net.httpserver.simpleserver.Main` 类处理命令行参数（绑定地址、端口、根目录、输出级别等），解析参数并启动服务器。在构建系统中配置模块的 main class 属性。

2. `SimpleFileServer` 公共 API：创建 `com.sun.net.httpserver.SimpleFileServer` 类，提供三个静态工厂方法：
   - `createFileServer(InetSocketAddress, Path, OutputLevel)` - 创建完整的文件服务器
   - `createFileHandler(Path)` - 创建文件处理器，可集成到现有服务器
   - `createOutputFilter(OutputStream, OutputLevel)` - 创建日志输出过滤器
   定义 `OutputLevel` 枚举（NONE、INFO、VERBOSE）控制日志输出详细程度。

3. 文件处理器实现：创建 `sun.net.httpserver.simpleserver.FileServerHandler` 类实现 `HttpHandler` 接口。处理 GET/HEAD 请求，对其他方法返回 405。实现目录路径到文件系统路径的安全映射（防止路径遍历攻击）。生成 HTML 格式的目录列表。通过 `URLConnection.getFileNameMap()` 进行 MIME 类型检测。

4. 输出过滤器实现：创建 `sun.net.httpserver.simpleserver.OutputFilter` 类作为后处理过滤器。实现 Common Logfile Format 格式的 INFO 级别输出。实现包含请求/响应头的 VERBOSE 级别输出。

5. `Request` 接口：创建 `com.sun.net.httpserver.Request` 接口，提供 HTTP 请求状态的不可变视图。包含 `getRequestURI()`、`getRequestMethod()`、`getRequestHeaders()` 方法。提供 `with(String, List<String>)` 默认方法用于添加请求头。让 `HttpExchange` 实现此接口。

6. `HttpHandlers` 工具类：创建 `com.sun.net.httpserver.HttpHandlers` 类，提供静态工厂方法：
   - `handleOrElse(Predicate<Request>, HttpHandler, HttpHandler)` - 条件处理器组合
   - `of(int, Headers, String)` - 创建返回固定响应的处理器

7. `Headers` 类增强：添加 `Headers(Map<String, List<String>>)` 构造函数支持从 Map 创建可变 Headers。添加 `Headers.of(String...)` 和 `Headers.of(Map<String, List<String>>)` 静态工厂方法创建不可变 Headers。创建 `sun.net.httpserver.UnmodifiableHeaders` 内部类实现不可变 Headers。

8. `Filter` 类增强：添加 `Filter.adaptRequest(String, UnaryOperator<Request>)` 静态方法，创建请求适配过滤器。创建 `sun.net.httpserver.DelegatingHttpExchange` 辅助类支持请求状态的包装和适配。

9. `HttpServer`/`HttpsServer` 增强：添加 `create(InetSocketAddress, int, String, HttpHandler, Filter...)` 重载方法，支持一步创建带初始上下文的服务器。

10. 资源本地化：创建 `simpleserver.properties` 资源文件存储命令行帮助信息和错误消息。配置构建系统生成 ListResourceBundle 类。

11. 测试：为命令行工具编写正向和负向测试用例。为各 API 组件编写单元测试，覆盖正常流程和边界情况。
