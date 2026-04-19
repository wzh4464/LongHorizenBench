**Summary**: 当前 JDK 的 `jlink` 工具需要依赖 `jmods` 目录中的打包模块（packaged modules）才能创建自定义运行时镜像。JEP 493 提出一种新的 jlink 模式，允许在没有 JMOD 文件的情况下，直接从运行时镜像（run-time image）进行链接，从而减少 JDK 发行版的大小（约 25%），并支持在容器场景中从基础 JDK 镜像创建应用特定的运行时。

**Proposal**: 通过引入 `--enable-linkable-runtime` 构建选项和 `--generate-linkable-runtime` jlink 选项，实现一种新的运行时镜像链接模式。核心设计是添加一个 jlink 插件来跟踪 JDK 安装中不在 jimage 中的非类、非资源文件，从而能够生成包含完整链接信息的 `JRTArchive` 类。
