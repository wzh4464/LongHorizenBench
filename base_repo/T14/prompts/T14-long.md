# T14: OpenJDK - macOS Metal 渲染管线 (JEP 382)

## Summary

Apple 已弃用 macOS 上的 OpenGL，并推荐使用 Metal 作为替代的图形 API。本任务需要为 Java 2D 实现一个基于 Apple Metal API 的内部渲染管线，作为 macOS 上现有 OpenGL 管线的替代方案，确保 Java GUI 应用在未来 macOS 版本上能够继续正常运行。

## Motivation

macOS 上的 Java 2D 渲染当前使用 OpenGL API，但存在以下问题：

- **OpenGL 已被弃用**：Apple 在 macOS 10.14 中弃用了 OpenGL，未来版本可能移除支持
- **性能不稳定**：在某些 macOS 版本上，OpenGL 实现存在性能问题
- **维护负担**：Apple 不再积极维护 OpenGL 驱动

Metal 是 Apple 推出的现代图形 API，具有以下优势：
- 更好的硬件利用率和性能
- 活跃的开发和支持
- 更好的与 macOS 系统集成

## Proposal

实现一个完整的 Metal 渲染管线，与现有 OpenGL 管线并存：

1. 添加 Metal 框架依赖和构建系统支持
2. 实现 Metal 版本的 Java 2D 渲染操作（绘制、填充、位图传输等）
3. 实现 Metal 版本的文本渲染
4. 实现 Metal 着色器和管线状态管理
5. 通过命令行参数 `-Dsun.java2d.metal=true` 启用 Metal 管线

## Design Details

1. **构建系统配置**：在 `make/autoconf/toolchain.m4` 中检测 `metal` 和 `metallib` 工具；更新 `make/modules/java.desktop/lib/Awt2dLibraries.gmk` 添加 Metal framework 链接；配置 Metal 着色器编译步骤，生成 `.metallib` 文件。

2. **Metal 上下文管理**：实现 `MTLContext` 类（Java 和 Native 层），管理 Metal device、command queue 和 render state；实现 `MTLGraphicsConfig` 作为图形配置的 Metal 实现。

3. **Surface 和 Layer**：实现 `MTLSurfaceData` 管理 Metal texture 和 drawable；实现 `MTLLayer` 作为 CAMetalLayer 的包装，处理窗口内容渲染。

4. **渲染操作实现**：实现 `MTLRenderer` 处理基本绘制操作（线条、矩形、多边形）；实现 `MTLMaskFill` 处理带遮罩的填充操作；实现 `MTLBlitLoops` 处理位图传输操作。

5. **文本渲染**：实现 `MTLTextRenderer` 处理字形缓存和文本绘制；实现 `MTLGlyphCache` 管理字形纹理缓存。

6. **着色器实现**：创建 `shaders.metal` 包含所有渲染所需的 Metal 着色器；实现 `MTLPipelineStatesStorage` 管理编译后的管线状态对象。

7. **编码器管理**：实现 `EncoderManager` 管理 Metal command encoder 的生命周期；优化 encoder 切换，减少状态变更开销。

8. **图像操作**：实现 `MTLDrawImage` 处理图像绘制；实现 `MTLBufImgOps` 处理缓冲图像操作（卷积、查找表等）。

9. **合成和裁剪**：实现 `MTLComposite` 处理 Porter-Duff 合成模式；实现 `MTLClip` 处理裁剪区域；实现 `MTLTransform` 处理变换矩阵。

10. **运行时切换**：在 `MacOSFlags.java` 中实现 Metal 管线的启用逻辑；更新 `CGraphicsDevice` 和 `CGraphicsConfig` 支持动态选择渲染管线；确保 OpenGL 仍为默认选项，Metal 需显式启用。

## Requirement

https://openjdk.org/jeps/382
