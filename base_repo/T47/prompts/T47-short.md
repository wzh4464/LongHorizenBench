**Summary**: JEP 514 旨在简化 Java 预先编译（Ahead-of-Time, AOT）缓存的创建流程。当前创建 AOT 缓存需要两步操作：首先运行应用程序以记录配置，然后使用配置文件创建缓存。本提案引入新的 `AOTCacheOutput` 选项，支持"一条命令"工作流——在应用程序执行期间自动完成训练运行并启动子进程组装 AOT 缓存。

**Proposal**: 实现三个核心功能：`AOTCacheOutput` 选项允许在单条命令中创建 AOT 缓存，JVM 执行训练运行后自动启动子进程组装缓存；`JDK_AOT_VM_OPTIONS` 环境变量允许在创建 AOT 缓存时传递额外的 VM 选项；在 `AOTCache`、`AOTCacheOutput` 和 `AOTConfiguration` 选项中支持 `%p` 进程 ID 替换。
