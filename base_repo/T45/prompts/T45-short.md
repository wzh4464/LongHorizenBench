**Summary**: JEP 388 将 JDK 移植到 Windows/AArch64 平台。该移植工作基于已有的 Linux/AArch64 移植（JEP 237），扩展支持 Windows 10 和 Windows Server 2016 操作系统上的 AArch64 架构。移植包括模板解释器、C1 和 C2 JIT 编译器，以及各种垃圾收集器（Serial、Parallel、G1、Z、Shenandoah）。

**Proposal**: 基于现有的 Linux/AArch64 代码，进行必要的修改以支持 Windows 平台。主要工作包括将 AArch64 内存模型扩展到 Windows、解决 MSVC 编译器问题、为 AArch64 移植添加 LLP64 支持、在 Windows 上进行 CPU 特性检测，以及修改构建脚本以支持交叉编译和 Windows 工具链。
