# T15: OpenJDK - macOS/AArch64 移植 (JEP 391)

## Summary

Apple 宣布将 Mac 产品线从 x64 迁移到基于 ARM 的 Apple Silicon (AArch64)。本任务需要将 OpenJDK 移植到 macOS/AArch64 平台，使 Java 应用能够在 Apple Silicon Mac 上原生运行，而无需通过 Rosetta 2 模拟 x64 代码。

## Motivation

Apple 于 2020 年开始在 Mac 上使用自研的 Apple Silicon (M1) 芯片，该芯片基于 AArch64 架构。虽然 Rosetta 2 可以模拟运行 x64 版本的 JDK，但存在以下问题：

- **性能损失**：模拟运行比原生运行有显著性能开销
- **兼容性风险**：某些 JVM 特性可能在模拟环境下工作异常
- **未来不确定性**：Apple 可能在未来版本中降低或移除 Rosetta 2 支持

macOS/AArch64 原生移植可以：
- 发挥 Apple Silicon 的全部性能潜力
- 确保完整的 JDK 功能支持
- 为长期在 Apple 平台上运行 Java 提供保障

## Proposal

基于现有的 linux/aarch64、macos/x86_64 和 windows/aarch64 移植代码，实现 macOS/AArch64 平台支持：

1. 添加 bsd_aarch64 平台的 os_cpu 层实现
2. 支持 macOS AArch64 特有的 ABI 调用约定
3. 实现 W^X (Write XOR Execute) 内存保护机制
4. 移植 Serviceability Agent 到 macOS/AArch64
5. 更新构建系统以支持新平台

## Design Details

1. **构建系统适配**：更新 `make/autoconf/build-aux/config.guess` 正确识别 arm64 架构；修改 `make/autoconf/flags.m4` 为 AArch64 设置正确的 `MACOSX_VERSION_MIN` (11.00.00)；更新 `make/autoconf/jvm-features.m4` 禁用不支持的特性（AOT、CDS）。

2. **os_cpu 层实现**：创建 `src/hotspot/os_cpu/bsd_aarch64/` 目录；基于 linux_aarch64 实现，适配 BSD/macOS 特定 API；实现 `os_bsd_aarch64.cpp` 处理信号、线程栈、上下文获取等。

3. **ABI 调用约定**：在 `interpreterRT_aarch64.cpp` 中处理 macOS 特有的参数传递方式；更新 `sharedRuntime_aarch64.cpp` 实现正确的调用包装器；适配 macOS 的浮点参数传递和返回值处理。

4. **寄存器约定**：在 `globalDefinitions_aarch64.hpp` 中定义 `R18_RESERVED`，因为 macOS 保留 x18 寄存器供平台使用；更新所有 AArch64 代码路径避免使用 x18 寄存器。

5. **W^X 实现**：实现基于 `pthread_jit_write_protect_np` 的 W^X 模式切换；在 `thread.hpp/.cpp` 中添加线程本地的 W^X 状态管理；Java 线程执行 Java 或 native 代码时使用 execute-only 模式，执行 VM 代码时使用 write-only 模式。

6. **SafeFetch 处理**：在 `safefetch.inline.hpp` 中处理需要临时切换到 execute 模式的情况；更新 stub 生成器支持 W^X 模式切换。

7. **Serviceability Agent**：创建 `BsdAARCH64ThreadContext.java` 和 `BsdAARCH64CFrame.java`；更新 `BsdCDebugger.java` 和 `BsdThreadContextFactory.java` 支持 AArch64；修改 `libsaproc` 的 native 代码支持 AArch64 寄存器和调试。

8. **代码签名**：更新 `NativeCompilation.gmk` 使用 `-f` 标志强制重新签名；macOS AArch64 要求所有代码必须签名才能执行。

9. **编译器警告处理**：在 `Awt2dLibraries.gmk` 中添加针对 AArch64 clang 的警告抑制；处理 HarfBuzz 等第三方库在 AArch64 上的编译警告。

10. **测试适配**：更新 `CompressedClassPointers.java` 等测试适配新平台；确保 GTest 和 JTreg 测试在 macOS/AArch64 上正常运行；更新 SA 相关测试支持新平台的调试格式。

## Requirement

https://openjdk.org/jeps/391
