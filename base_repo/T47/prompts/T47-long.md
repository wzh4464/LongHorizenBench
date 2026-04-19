# T47: OpenJDK - 实现 JEP 514: AOT 命令行易用性改进

## Requirement

https://openjdk.org/jeps/514

## Summary

JEP 514 旨在简化 Java 预先编译（Ahead-of-Time, AOT）缓存的创建流程。当前创建 AOT 缓存需要两步操作：首先运行应用程序以记录配置（`-XX:AOTMode=record -XX:AOTConfiguration=...`），然后使用配置文件创建缓存（`-XX:AOTMode=create`）。本提案引入新的 `AOTCacheOutput` 选项，支持"一条命令"工作流——在应用程序执行期间自动完成训练运行并启动子进程组装 AOT 缓存。

## Motivation

当前的两步 AOT 缓存创建流程对用户来说较为繁琐：
1. 需要两次独立的 JVM 调用
2. 需要管理中间配置文件
3. 增加了构建脚本和 CI/CD 流程的复杂性

"一条命令"工作流可以显著简化这一过程，让用户只需在正常运行应用时添加一个选项即可自动生成 AOT 缓存。此外，通过环境变量支持额外的 VM 选项，可以为 AOT 缓存组装阶段提供更灵活的配置。

## Proposal

实现以下三个核心功能：
1. **`AOTCacheOutput` 选项**：允许在单条命令中创建 AOT 缓存。JVM 执行训练运行后自动启动子进程组装缓存。
2. **`JDK_AOT_VM_OPTIONS` 环境变量**：允许在创建 AOT 缓存时传递额外的 VM 选项。
3. **`%p` 替换支持**：在 `AOTCache`、`AOTCacheOutput` 和 `AOTConfiguration` 选项中支持 `%p` 进程 ID 替换。

## Design Details

1. **CDS 配置扩展**：在 `cdsConfig.cpp` 和 `cdsConfig.hpp` 中添加对新 AOT 工作流的支持。实现配置状态的跟踪和管理，区分单步（onestep）和两步（twostep）工作流模式。

2. **新增 CDS 全局选项**：在 `cds_globals.hpp` 中定义 `AOTCacheOutput` 相关的 VM 选项标志，包括路径存储和模式控制。

3. **参数处理更新**：在 `arguments.cpp` 和 `arguments.hpp` 中：
   - 解析 `AOTCacheOutput` 选项
   - 实现 `%p` 进程 ID 替换逻辑
   - 处理 `JDK_AOT_VM_OPTIONS` 环境变量
   - 添加选项冲突检测和错误处理

4. **Filemap 修改**：在 `filemap.cpp` 中更新 AOT 缓存文件的创建和管理逻辑，支持新的输出路径选项。

5. **Metaspace 共享更新**：在 `metaspaceShared.cpp` 和 `metaspaceShared.hpp` 中实现子进程启动逻辑。当使用 `AOTCacheOutput` 时，在训练运行完成后自动启动 Java 子进程组装 AOT 缓存。

6. **系统字典共享**：在 `systemDictionaryShared.cpp` 中更新类加载和共享相关的逻辑以支持新工作流。

7. **Java 层 CDS 支持**：在 `java.base` 模块的 `CDS.java` 中添加 Java 层面的 AOT 缓存支持，包括从 Java 代码启动子进程的能力。

8. **文档更新**：更新 `java.md` 手册页，添加新选项的说明和使用示例。

9. **构建系统更新**：在 `RunTests.gmk` 中：
   - 添加 `TRAINING` 参数支持，区分 `onestep` 和 `twostep` 模式
   - 修改 `SetupAOT` 宏以支持新的训练模式
   - 更新 `JTREG_AOT_JDK` 处理逻辑

10. **测试更新**：
    - 更新 `doc/testing.md` 和 `doc/testing.html` 添加 AOT_JDK 测试模式的文档
    - 在 `test/hotspot/jtreg/TEST.groups` 中添加 AOT 相关测试组
    - 添加新的测试用例验证单步工作流和环境变量功能
    - 更新 `CDSAppTester.java` 测试工具类
    - 创建 `test/setup_aot/TestSetupAOT.java` 测试程序
