**Summary**: G1 垃圾收集器当前在 JNI 关键区（critical region）期间无法执行垃圾回收，导致线程因等待 GC Locker 而出现长时间延迟。JEP 423 提出实现 Region Pinning 机制，允许 G1 在包含被 JNI 固定对象的 region 上跳过疏散（evacuation），从而在 JNI 关键区期间仍能执行 GC，减少延迟。

**Motivation**: 当 Java 线程进入 JNI 关键区（通过 GetPrimitiveArrayCritical 等函数）时，它获得了直接访问 Java 堆中数组数据的指针。当前 G1 使用 GC Locker 机制在此期间阻止所有 GC 活动，因为对象移动会使 JNI 指针失效。然而，这种全局阻止策略在高并发场景下会导致严重的 GC 延迟，特别是当多个线程频繁使用 JNI 关键区时。Region Pinning 提供了一种更细粒度的解决方案：只跳过包含被固定对象的 region 的疏散，其他 region 的 GC 照常进行。

**Proposal**: 在 G1 中实现 Region Pinning 机制：(1) 为每个 HeapRegion 添加固定对象计数器，在对象被 JNI 固定/解固定时增减；(2) 修改 Collection Set 选择逻辑，将包含固定对象的 region 标记为不可疏散；(3) 在疏散过程中，对于固定 region 中的非固定对象进行原地标记而不移动；(4) 移除 GC Locker 相关的等待和触发 GC 逻辑；(5) 实现固定 region 的生命周期管理，确保长期固定的 region 不会无限期保留在 Collection Set 候选列表中。

**Design Details**:

1. HeapRegion 固定计数：在 `HeapRegion` 类中添加 `_pinned_object_count` 原子计数器。实现 `increment_pinned_object_count()` 和 `decrement_pinned_object_count()` 方法。添加 `has_pinned_objects()` 方法检查 region 是否包含固定对象。

2. G1CollectedHeap 固定接口：重新实现 `pin_object` 和 `unpin_object` 方法，改为增减目标对象所在 region 的固定计数，而不是使用 GC Locker。添加类型检查确保只有 typeArray 可以被固定（这是 JNI 规范允许的类型）。

3. 移除 GC Locker 依赖：从 `G1CollectedHeap::attempt_allocation_slow` 和 `attempt_allocation_humongous` 中移除 GC Locker 检查和等待逻辑。从 `do_full_collection`、`do_collection_pause_at_safepoint` 等方法中移除 GC Locker 检查。简化分配失败后的重试逻辑。

4. Region Attribute 扩展：在 `G1HeapRegionAttr` 中添加固定状态标志位。创建 `set_is_pinned` 和相关方法。在将 region 注册到 Collection Set 时记录其固定状态。

5. Collection Set 选择修改：在 `G1Policy::select_candidates_from_marking` 和 `select_candidates_from_retained` 中添加固定 region 的处理逻辑。将固定的 marking candidates 移动到 retained candidates 以保持混合 GC 进度。对于长期固定的 retained candidates，在一定次数后从候选列表中移除。

6. 疏散失败处理增强：扩展 `G1EvacFailureRegions` 类区分固定导致的跳过和分配失败导致的疏散失败。添加 `_regions_pinned` 和 `_regions_alloc_failed` 位图。更新 `record` 方法接受失败原因参数。

7. 年轻代 region 处理：年轻代固定 region 仍然留在 Collection Set 中，但跳过疏散。在 `G1YoungCollector` 中处理固定年轻 region 的特殊逻辑。固定 region 中非固定对象保持原地，只更新标记。

8. GC Phase Times 更新：在 `G1GCPhaseTimes` 中添加固定相关的统计信息：固定 region 数量、因固定跳过的字节数等。在 GC 日志中报告固定相关信息。

9. 全局参数：添加 `G1NumCollectionsKeepPinned` 参数控制固定 region 在 retained candidates 中保留的最大 GC 次数。

10. 测试：编写测试验证 JNI 关键区期间 GC 可以正常执行。测试固定 region 的疏散跳过逻辑。测试长期固定 region 的候选列表清理逻辑。
