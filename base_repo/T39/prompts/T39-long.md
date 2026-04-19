# T39: OpenJDK Virtual Threads (Project Loom)

## Requirement
https://openjdk.org/jeps/425

---

**Summary**: JEP 425 提出引入虚拟线程（Virtual Threads）作为 Java 平台的预览特性。虚拟线程是轻量级线程，可以大幅减少编写、维护和观察高吞吐量并发应用程序的工作量。虚拟线程基于 continuation 和 scheduler 实现，允许在单个 OS 线程上运行大量虚拟线程。

**Motivation**: 传统 Java 线程（平台线程）是对操作系统线程的包装，创建和上下文切换开销较大。这导致了几个问题：

1. **线程数量限制**：由于 OS 线程开销，典型服务器能支持的并发连接数受限于线程数（通常几千个）。
2. **编程模型分裂**：为提高吞吐量，开发者被迫采用异步编程模型，但这违背了 Java 的 thread-per-request 设计理念。
3. **调试困难**：异步代码的堆栈跟踪难以理解，调试工具支持有限。
4. **代码复杂性**：回调和 Future 组合使代码难以阅读和维护。

**Proposal**: 引入虚拟线程，它们在用户态由 JVM 调度，可以在阻塞时自动挂起并释放底层平台线程。虚拟线程与现有 `Thread` API 兼容，允许现有代码无需大量修改即可受益。核心实现基于 Continuation（定界续体）机制，当虚拟线程遇到阻塞操作时，将其栈帧保存到堆上，释放载体线程执行其他虚拟线程。

**Design Details**:

1. **Continuation 基础设施**：
   - 在 HotSpot 中实现 `Continuation` 类，支持栈帧的冻结（freeze）和解冻（thaw）
   - 实现 `ContinuationEntry` 用于标记 continuation 边界
   - 在各 CPU 架构（aarch64、x86、arm、ppc、riscv、s390）下实现 continuation 相关的汇编代码

2. **栈帧管理**：
   - 实现 `StackChunk` 对象用于在堆上存储冻结的栈帧
   - 修改 `frame` 类支持堆上栈帧的遍历
   - 实现 `StackChunkFrameStream` 用于遍历 chunk 中的帧
   - 添加相对指针（relative pointers）支持，用于堆上帧的重定位

3. **JVM 运行时支持**：
   - 添加 `JVM_CurrentCarrierThread` 和 `JVM_SetCurrentThread` native 方法
   - 添加 `JVM_GetStackTrace` 用于虚拟线程栈跟踪
   - 添加 `JVM_RegisterContinuationMethods` 用于注册 continuation intrinsics
   - 实现 `JVM_VirtualThreadMountBegin/End` 和 `JVM_VirtualThreadUnmountBegin/End` 用于 JVMTI 通知

4. **监视器和同步**：
   - 修改监视器膨胀（monitor inflation）逻辑以支持虚拟线程
   - 更新 `ObjectMonitor` 追踪持有监视器的虚拟线程
   - 实现虚拟线程在 synchronized 块中的 pinning 机制
   - 添加 `held_monitor_count` 用于追踪线程持有的监视器数量

5. **C1/C2 编译器支持**：
   - 在 C1 中添加 `do_continuation_doYield` intrinsic
   - 在 C2 中添加 continuation 相关的 IR 节点
   - 修改调用指令在调用后发出 `post_call_nop` 用于栈遍历
   - 更新 `LIRAssembler` 和 `LIRGenerator` 支持 continuation

6. **解释器修改**：
   - 修改 `TemplateInterpreter` 生成 continuation enter/exit 代码
   - 更新 `InterpreterMacroAssembler` 添加虚拟线程相关操作
   - 实现解释器帧的冻结和解冻支持

7. **GC 集成**：
   - 更新各 GC（G1、Shenandoah、ZGC）的 barrier set 支持 continuation
   - 实现 `StackChunk` 的 GC 遍历和对象重定位
   - 添加 `StackChunkOop` 类封装堆上栈操作

8. **RegisterMap 和栈遍历**：
   - 实现 `SmallRegisterMap` 用于高效的寄存器映射
   - 修改 `RegisterMap` 支持堆上帧的寄存器定位
   - 更新 `frame::sender()` 方法正确处理 continuation 边界

9. **JVMTI 支持**：
   - 添加虚拟线程挂载/卸载事件
   - 更新 `GetStackTrace` 和其他线程相关 JVMTI 函数
   - 实现虚拟线程的 `SuspendThread` 支持

10. **Java 层实现**：
    - 实现 `java.lang.VirtualThread` 类
    - 实现 `jdk.internal.vm.Continuation` 类
    - 修改 `Thread` 类添加虚拟线程相关方法
    - 实现默认的 `ForkJoinPool` 作为虚拟线程调度器

11. **I/O 和网络支持**：
    - 更新 NIO channel 实现支持虚拟线程阻塞时 unmount
    - 修改 socket 操作在虚拟线程上 park 而非阻塞 OS 线程
    - 更新 `FileChannel` 和 `DatagramChannel` 等

12. **诊断和调试**：
    - 更新 `Thread.getStackTrace()` 支持虚拟线程
    - 实现 `Thread.getAllStackTraces()` 过滤虚拟线程
    - 添加 JFR 事件支持虚拟线程

13. **测试**：
    - 添加虚拟线程基本功能测试
    - 添加 continuation freeze/thaw 测试
    - 添加 JVMTI 虚拟线程事件测试
    - 添加各架构的 JIT 编译测试
