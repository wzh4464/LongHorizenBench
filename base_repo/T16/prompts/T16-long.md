# T16: OpenJDK

**Summary**: JEP 422 提出将 RISC-V 64 位架构 (riscv64) 作为 Linux 平台的新移植目标集成到 OpenJDK 中。这需要实现完整的 HotSpot JVM 后端，包括解释器、C1/C2 编译器、垃圾回收器支持、以及所有必要的平台特定代码，使 Java 能够在 RISC-V 硬件上原生运行。

**Motivation**: RISC-V 是一个开源的、免版税的 RISC 指令集架构，近年来在嵌入式系统、IoT 设备和数据中心领域获得了快速发展。随着 RISC-V 硬件（如 SiFive HiFive Unmatched 开发板）的日益普及，Java 生态系统需要为这一新兴架构提供原生支持。当前 OpenJDK 已支持 x86、ARM、PowerPC 等架构，但缺少对 RISC-V 的支持，这限制了 Java 应用在 RISC-V 平台上的部署能力。

**Proposal**: 在 OpenJDK HotSpot 中实现完整的 Linux/RISC-V 64 位移植。这包括：添加 RISC-V 特定的 CPU 目录结构、实现汇编器和宏汇编器、模板解释器、C1 和 C2 JIT 编译器后端、支持 G1/ZGC/Shenandoah 等垃圾回收器、以及平台相关的运行时支持代码。同时需要更新构建系统以识别和配置 RISC-V 目标平台。

**Design Details**:

1. 构建系统配置：更新 autoconf 配置脚本以识别 riscv64 架构。修改 `config.guess` 检测 RISC-V 平台，更新 `platform.m4` 定义 RISCV64 CPU 宏，修改 `jvm-features.m4` 为 RISC-V 启用 Shenandoah 和 ZGC 支持，在 `libraries.m4` 中为 RISC-V 链接 libatomic（因为 RISC-V 只有字大小的原子操作）。

2. 汇编器实现：在 `src/hotspot/cpu/riscv/` 下创建 RISC-V 汇编器。实现 `assembler_riscv.hpp/cpp` 定义所有 RISC-V 指令的编码，包括 RV64I 基础指令集、M/A/F/D/C 扩展指令。实现立即数加载（`li`）、地址计算等常用操作的辅助方法。

3. 宏汇编器：实现 `macroAssembler_riscv.hpp/cpp` 提供高级汇编操作。包括内存屏障、对象访问、调用约定、栈操作等。处理 RISC-V 特有的限制，如没有条件移动指令需要使用分支实现。

4. 模板解释器：实现解释器生成器 `templateInterpreterGenerator_riscv.cpp` 和模板表 `templateTable_riscv.cpp`。为每个字节码生成解释执行代码，实现方法入口、异常处理、同步等机制。

5. C1 编译器后端：在 `c1_*.cpp/hpp` 系列文件中实现 C1 轻量级 JIT 编译器。包括 LIR 生成器、线性扫描寄存器分配、代码生成。需要处理 RISC-V 的寄存器约定和调用规范。

6. C2 编译器后端：实现 AD（Architecture Description）文件 `riscv.ad` 定义指令选择规则。创建 `riscv_v.ad` 和 `riscv_b.ad` 支持向量扩展和位操作扩展。更新 `GensrcAdlc.gmk` 构建规则以包含这些 AD 文件。

7. 垃圾回收器支持：为 G1、Shenandoah、ZGC 实现 RISC-V 特定的屏障代码。创建 `gc/g1/g1BarrierSetAssembler_riscv.cpp`、`gc/shenandoah/shenandoahBarrierSetAssembler_riscv.cpp`、`gc/z/zBarrierSetAssembler_riscv.cpp` 等文件。

8. 运行时支持：实现帧布局 (`frame_riscv.cpp/hpp`)、寄存器定义 (`register_riscv.cpp/hpp`)、原生方法调用 (`sharedRuntime_riscv.cpp`)、存根生成器 (`stubGenerator_riscv.cpp`) 等核心运行时组件。

9. Serviceability Agent：在 `src/jdk.hotspot.agent/` 下添加 RISC-V 支持。实现线程上下文、栈帧解析、调试器接口等 SA 组件。

10. 测试适配：更新测试框架以支持 RISC-V 平台。修改 `Platform.java` 添加 RISC-V 检测，调整跳过不支持架构的测试用例。

## Requirement
https://openjdk.org/jeps/422
