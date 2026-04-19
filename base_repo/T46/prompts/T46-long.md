# T46: OpenJDK - 实现 JEP 493: 无需 JMOD 文件链接运行时镜像

## Requirement

https://openjdk.org/jeps/493

## Summary

当前 JDK 的 `jlink` 工具需要依赖 `jmods` 目录中的打包模块（packaged modules）才能创建自定义运行时镜像。JEP 493 提出一种新的 jlink 模式，允许在没有 JMOD 文件的情况下，直接从运行时镜像（run-time image）进行链接，从而减少 JDK 发行版的大小（约 25%），并支持在容器场景中从基础 JDK 镜像创建应用特定的运行时。

## Motivation

在移除 JRE 概念后，常见的 JDK 发行方式仍然是包含所有模块和打包模块的完整 JDK。然而打包模块会带来额外的存储开销。在容器场景中，提供一个包含所有模块但不包含打包模块的基础 JDK 容器镜像会非常有用——这可以节省约 25% 的空间。这样的基础 JDK 容器可以用于 jlink 创建应用特定的运行时，进一步减少应用运行时镜像的大小。

当前的限制是：如果 JDK 安装中没有 jmods 目录，jlink 就无法工作。本功能旨在解除这一限制，使 jlink 能够直接从运行时镜像中的模块信息进行链接。

## Proposal

通过引入 `--enable-linkable-runtime` 构建选项和 `--generate-linkable-runtime` jlink 选项，实现一种新的运行时镜像链接模式。核心设计是添加一个 jlink 插件来跟踪 JDK 安装中不在 jimage（`lib/modules`）中的非类、非资源文件，从而能够生成包含完整链接信息的 `JRTArchive` 类。

## Design Details

1. **构建系统配置**：在 `make/autoconf/jdk-options.m4` 中添加 `--enable-linkable-runtime` 配置选项，控制是否生成可链接运行时。当启用时，默认禁用 `--keep-packaged-modules`。需要更新 `spec.gmk.template` 添加相应的变量导出。

2. **Images.gmk 修改**：在构建 JDK 镜像时，根据 `JLINK_PRODUCE_LINKABLE_RUNTIME` 变量决定是否向 jlink 传递 `--generate-linkable-runtime` 选项。

3. **ImageFileCreator 重构**：扩展 `ImageFileCreator` 类以支持运行时镜像生成模式。添加新的构造函数参数控制是否生成运行时镜像，实现从运行时镜像读取模块信息的能力。

4. **JRTArchive 实现**：创建新类 `JRTArchive`，封装运行时镜像中的模块归档信息。实现 `ResourceFileEntry` 内部类处理资源文件条目，支持从 jimage 和文件系统读取模块内容。

5. **运行时链接核心类**：在 `jdk.tools.jlink.internal.runtimelink` 包中实现：
   - `JimageDiffGenerator`：生成运行时镜像与打包模块之间的差异信息
   - `ResourceDiff`：表示资源差异的数据结构
   - `ResourcePoolReader`：从资源池读取模块信息
   - `RuntimeImageLinkException`：运行时链接异常处理
   - `LinkableRuntimeImage`：可链接运行时镜像的核心逻辑

6. **JlinkTask 和 Jlink 更新**：修改 `JlinkTask` 添加 `--generate-linkable-runtime` 选项处理逻辑，更新命令行参数解析。在 `Jlink` 类中添加相应的配置支持。

7. **TaskHelper 扩展**：在 `TaskHelper` 中添加新选项的帮助信息和资源属性，更新 `jlink.properties` 资源文件。

8. **测试框架更新**：
   - 更新 `TEST.ROOT` 文件添加运行时镜像链接相关的测试配置
   - 扩展 `Helper.java` 和 `JImageGenerator.java` 测试工具支持新功能
   - 更新 `VMProps.java` 添加可链接运行时相关的 VM 属性检测

9. **集成测试**：在 `test/jdk/tools/jlink/runtimeImage/` 目录下添加全面的测试用例：
   - 基本 jlink 测试（有/无 java.base 模块）
   - 自定义模块链接测试
   - 多跳链接测试（从运行时镜像再次 jlink）
   - 文件修改检测测试（校验和验证）
   - 系统模块测试
   - 可重现性测试

10. **现有测试适配**：更新现有的 jlink 测试（如 `ImageFileCreatorTest`、`IntegrationTest` 等）以兼容新的运行时链接模式，确保向后兼容性。
