# T26: OpenJDK

**Summary**: JEP 483 提出了 Ahead-of-Time (AOT) 类加载与链接功能，目标是通过在 JDK 运行时启动时以 AOT 缓存的形式，加载和链接所有应用程序类来改善 Java 应用程序的启动时间。该功能通过三阶段工作流程实现：首先在试运行中记录类的使用情况，然后创建包含已加载和已链接类的 AOT 缓存，最后在生产运行中使用该缓存以跳过类加载和链接的重复工作。

**Motivation**: Java 应用程序启动时间是一个长期存在的痛点。传统的类加载和链接过程需要在每次启动时重复执行，即使是相同的类集合。CDS（Class Data Sharing）虽然可以缓存类元数据，但仍需在运行时执行类链接（验证、准备、解析）。JEP 483 通过将链接后的类状态（包括已解析的常量池条目、已初始化的静态字段等）保存到 AOT 缓存中，使应用程序能够直接使用这些预链接的类，从而显著减少启动开销。

**Proposal**: 实现 AOT 类加载与链接功能，包括：引入新的 AOT 模式（record/create/auto）控制缓存的生成和使用；扩展 CDS 基础设施以支持类链接状态的归档；实现 AOT 类初始化器以处理静态字段的缓存；添加 AOT 常量池解析器以缓存已解析的常量池条目；支持 Lambda 表达式和 invokedynamic 指令的 AOT 缓存；以及相应的测试和诊断功能。

**Design Details**:

1. AOT 模式与配置：在 `cdsConfig` 模块中实现三种 AOT 模式的支持——`record` 模式用于在试运行中记录类使用情况并生成配置文件，`create` 模式用于根据配置文件创建 AOT 缓存，`auto` 模式用于在生产运行中自动使用缓存。需要添加 `-XX:AOTMode`、`-XX:AOTConfiguration`、`-XX:AOTCache` 等命令行选项。

2. AOT 类初始化器（AOTClassInitializer）：创建新的类 `aotClassInitializer.cpp/hpp`，负责管理哪些类可以在 dump 时进行 AOT 初始化。实现 `can_archive_initialized_mirror()` 方法来判断类是否适合进行 AOT 初始化，处理类之间的初始化耦合关系，维护允许 AOT 初始化的类白名单。

3. AOT 类链接器（AOTClassLinker）：实现 `aotClassLinker.cpp/hpp`，负责在 dump 时执行类链接并记录链接状态。处理类的验证、准备、解析阶段，将链接后的状态保存到归档中，支持在运行时跳过重复的链接工作。

4. AOT 常量池解析器（AOTConstantPoolResolver）：创建 `aotConstantPoolResolver.cpp/hpp`，用于在 dump 时解析常量池条目并缓存解析结果。处理 `CONSTANT_Class`、`CONSTANT_Methodref`、`CONSTANT_Fieldref` 等条目的解析，支持 invokedynamic 和方法句柄的缓存。

5. AOT 链接类批量加载器（AOTLinkedClassBulkLoader）：实现 `aotLinkedClassBulkLoader.cpp/hpp`，在运行时从 AOT 缓存中批量加载已链接的类。优化类加载顺序以减少启动时间，处理类加载器委托和类可见性问题。

6. ConstantPool 和 CPCache 扩展：修改 `constantPool.cpp/hpp` 和 `cpCache.cpp/hpp`，添加支持 AOT 解析状态的存储和恢复。实现已解析条目的序列化和反序列化，处理运行时常量池的重建。

7. 堆归档支持（HeapShared）：扩展 `heapShared.cpp/hpp`，支持将已初始化的类镜像和相关堆对象归档。实现 `find_all_aot_initialized_classes()` 来发现需要 AOT 初始化的类，处理对象图的遍历和归档。

8. 测试框架扩展：在 `make/RunTests.gmk` 中添加 `AOT_JDK` 测试选项，支持在测试时使用 AOT 缓存。创建新的测试用例覆盖 AOT 类加载、链接、初始化的各种场景，包括 Lambda 表达式、VarHandle、自定义类加载器等。

9. Java 类支持：修改 `java.lang.invoke` 包中的相关类（如 `MethodType`、`MethodHandleNatives`、`StringConcatFactory` 等），添加 `runtimeSetup()` 方法以支持 AOT 初始化后的运行时设置。

10. 诊断与验证：实现 `CDSHeapVerifier` 来检测 AOT 初始化的潜在问题，添加日志支持（`-Xlog:cds`）用于调试，提供 `ProblemList` 文件记录已知的测试问题。

## Requirement
https://openjdk.org/jeps/483
