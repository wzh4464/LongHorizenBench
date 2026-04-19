**Summary**: JEP 422 提出将 RISC-V 64 位架构 (riscv64) 作为 Linux 平台的新移植目标集成到 OpenJDK 中。这需要实现完整的 HotSpot JVM 后端，包括解释器、C1/C2 编译器、垃圾回收器支持、以及所有必要的平台特定代码，使 Java 能够在 RISC-V 硬件上原生运行。

**Proposal**: 在 OpenJDK HotSpot 中实现完整的 Linux/RISC-V 64 位移植，添加 RISC-V 特定的 CPU 目录结构，实现汇编器、宏汇编器、模板解释器、C1 和 C2 JIT 编译器后端，支持 G1/ZGC/Shenandoah 等垃圾回收器，以及平台相关的运行时支持代码，同时更新构建系统以识别和配置 RISC-V 目标平台。
