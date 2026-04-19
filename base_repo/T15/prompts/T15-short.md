**Summary**: Apple 宣布将 Mac 产品线从 x64 迁移到基于 ARM 的 Apple Silicon (AArch64)。本任务需要将 OpenJDK 移植到 macOS/AArch64 平台，使 Java 应用能够在 Apple Silicon Mac 上原生运行，而无需通过 Rosetta 2 模拟 x64 代码。

**Proposal**: 基于现有的 linux/aarch64、macos/x86_64 和 windows/aarch64 移植代码实现 macOS/AArch64 平台支持，添加 bsd_aarch64 平台的 os_cpu 层实现，支持 macOS AArch64 特有的 ABI 调用约定，实现 W^X 内存保护机制，移植 Serviceability Agent，并更新构建系统以支持新平台。
