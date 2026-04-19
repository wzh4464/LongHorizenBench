**Summary**: Apple 已弃用 macOS 上的 OpenGL，并推荐使用 Metal 作为替代的图形 API。本任务需要为 Java 2D 实现一个基于 Apple Metal API 的内部渲染管线，作为 macOS 上现有 OpenGL 管线的替代方案，确保 Java GUI 应用在未来 macOS 版本上能够继续正常运行。

**Proposal**: 实现一个完整的 Metal 渲染管线与现有 OpenGL 管线并存，添加 Metal 框架依赖和构建系统支持，实现 Metal 版本的 Java 2D 渲染操作和文本渲染，实现 Metal 着色器和管线状态管理，通过命令行参数启用 Metal 管线。
