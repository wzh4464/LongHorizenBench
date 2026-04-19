**Summary**: ZGC 是 HotSpot JVM 中的低延迟垃圾收集器，当前实现为非分代收集器，每次 GC 都需要遍历整个对象图。JEP 439 提出实现分代 ZGC（Generational ZGC），将堆划分为年轻代和老年代，使 ZGC 能够更快地回收内存，更好地支持高分配率、大存活集或资源受限的工作负载。

**Proposal**: 实现分代 ZGC 作为现有 ZGC 的演进版本，通过 `-XX:+ZGenerational` 标志启用（需配合 `-XX:+UseZGC`）。为确保平稳过渡，初期同时保留两个版本：非分代 ZGC 保持在 `gc/z` 目录，分代 ZGC 的遗留代码重命名为 `gc/x`（类名前缀从 Z 改为 X）。未来计划弃用并移除非分代版本，届时分代 ZGC 将成为默认选项。
