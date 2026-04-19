**Summary**: G1 垃圾收集器当前在 JNI 关键区（critical region）期间无法执行垃圾回收，导致线程因等待 GC Locker 而出现长时间延迟。JEP 423 提出实现 Region Pinning 机制，允许 G1 在包含被 JNI 固定对象的 region 上跳过疏散（evacuation），从而在 JNI 关键区期间仍能执行 GC，减少延迟。

**Proposal**: 在 G1 中实现 Region Pinning 机制，为每个 HeapRegion 添加固定对象计数器，修改 Collection Set 选择逻辑将包含固定对象的 region 标记为不可疏散，在疏散过程中对固定 region 中的非固定对象进行原地标记，移除 GC Locker 相关的等待逻辑，并实现固定 region 的生命周期管理。
