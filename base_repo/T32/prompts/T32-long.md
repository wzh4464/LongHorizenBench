# T32: OpenJDK

**Summary**: ZGC 是 HotSpot JVM 中的低延迟垃圾收集器，当前实现为非分代收集器，每次 GC 都需要遍历整个对象图。JEP 439 提出实现分代 ZGC（Generational ZGC），将堆划分为年轻代和老年代，使 ZGC 能够更快地回收内存，更好地支持高分配率、大存活集或资源受限的工作负载。

**Motivation**: 非分代 ZGC 在每次垃圾收集时都需要遍历整个堆，这对于大存活集的应用会造成较大开销。分代假设（大多数对象生命周期很短）表明，将堆划分为年轻代和老年代可以显著提高 GC 效率。分代 ZGC 可以更频繁地收集年轻代（这里存放大部分短命对象），而较少收集老年代，从而减少 CPU 开销、降低分配停顿风险、减少堆内存需求，同时保持 ZGC 的低延迟特性。

**Proposal**: 实现分代 ZGC 作为现有 ZGC 的演进版本。通过 `-XX:+ZGenerational` 标志启用（需配合 `-XX:+UseZGC`）。为确保平稳过渡，初期同时保留两个版本：非分代 ZGC 保持在 `gc/z` 目录，分代 ZGC 的遗留代码重命名为 `gc/x`（类名前缀从 Z 改为 X）。未来计划弃用并移除非分代版本，届时分代 ZGC 将成为默认选项。

**Design Details**:

1. 目录结构重组：将非分代 ZGC 代码从 `gc/z` 复制到 `gc/x` 目录，所有类名和文件名前缀从 Z 改为 X（如 ZGC -> XGC, ZBarrier -> XBarrier）。这涉及 HotSpot 各平台目录下的实现（aarch64, x86, ppc, riscv）以及操作系统相关代码（linux, bsd, windows, posix）。

2. 分代 ZGC 核心实现：在 `gc/z` 目录下实现分代收集逻辑，包括：
   - 年轻代和老年代的内存管理
   - 代际间引用的记录和处理（记忆集）
   - 晋升策略（对象从年轻代晋升到老年代）
   - 分代并发标记和重定位算法

3. 地址视图（Address Views）更新：分代 ZGC 引入新的地址元数据位布局。更新 `zAddress.cpp/hpp` 和相关内联文件，处理分代指针着色方案。每个平台需要相应的实现（aarch64, x86, ppc, riscv）。

4. 屏障实现：为各平台实现分代写屏障和读屏障：
   - `zBarrierSetAssembler_*.cpp/hpp`：汇编级屏障实现
   - C1 和 C2 编译器集成：`c1/zBarrierSetC1.cpp`, `c2/zBarrierSetC2.cpp`
   - 解释器屏障：更新模板表和宏汇编器

5. 构建系统更新：
   - 修改 `make/hotspot/lib/JvmFeatures.gmk` 支持同时编译 `gc/z` 和 `gc/x`
   - 更新 `make/hotspot/gensrc/GensrcAdlc.gmk` 包含两套 AD 文件
   - 添加条件编译宏 `INCLUDE_ZGC` 控制代码包含

6. 运行时集成：
   - C1 LIRAssembler 更新：条件判断使用 `UseZGC && !ZGenerational` 区分版本
   - 更新全局变量和类型定义支持分代模式
   - 修改 stub 生成器支持分代屏障

7. 平台特定实现：为 aarch64、x86_64、ppc64、riscv64 四个平台分别实现：
   - 地址解码/编码逻辑
   - 屏障汇编代码
   - AD 文件（编译器后端匹配规则）
   - nmethod 入口屏障

8. 测试：验证分代 ZGC 和非分代 ZGC 都能正常工作，通过 tier1-8 测试套件。

## Requirement
https://openjdk.org/jeps/439
