# T33: OpenJDK

**Summary**: Java 的 `final` 字段本意是表示不可变，但当前反射 API（`Field.set`）和 JNI 允许修改 final 字段的值。JEP 500 提出逐步限制对 final 字段的修改能力，在过渡期内通过警告、命令行选项和 JFR 事件帮助开发者识别和修复依赖此行为的代码，最终目标是让 final 真正意味着不可变。

**Motivation**: final 字段的不可变性对于 JVM 优化（如常量折叠、内联）和程序正确性至关重要。然而，当前可以通过 `Field.setAccessible(true)` 后调用 `Field.set()` 修改 final 实例字段，也可以通过 JNI `SetField` 函数修改任意 final 字段。这破坏了 final 的语义保证，阻碍了 JIT 优化，也是潜在的安全隐患。需要一个渐进的迁移路径，让用户有时间更新代码。

**Proposal**: 为反射修改 final 字段引入可配置的行为模式（allow/warn/debug/deny），通过命令行选项 `--sun-misc-unsafe-memory-access` 和模块系统的 `--add-opens` 控制。同时增加 JFR 事件记录 final 字段修改，帮助诊断问题。对于特殊的"可变静态 final 字段"（如 `System.in/out/err`）保持允许修改。JNI 侧增加警告日志和检查。

**Design Details**:

1. 命令行参数处理：在 `src/hotspot/share/runtime/arguments.cpp` 中解析新的命令行选项，支持配置 final 字段修改的行为模式。在 `src/java.base/share/classes/sun/launcher/` 下更新启动器帮助信息和属性文件。

2. 核心 API 修改：
   - `java.lang.reflect.Field`：修改 `set()` 方法，在修改 final 字段时根据配置发出警告或抛出异常
   - `java.lang.reflect.AccessibleObject`：更新 `setAccessible()` 的行为和文档
   - `java.lang.invoke.MethodHandles`：更新 `unreflectSetter` 对 final 字段的处理
   - 添加文档 `doc-files/MutationMethods.html` 说明变更

3. 可变静态 final 字段识别：
   - `src/hotspot/share/runtime/fieldDescriptor.cpp/hpp`：添加 `is_mutable_static_final()` 方法识别特殊字段（System.in/out/err）
   - `src/hotspot/share/ci/ciField.cpp`：更新 JIT 常量折叠逻辑，使用新的判断方法

4. 模块系统集成：
   - `java.lang.Module` 和 `java.lang.ModuleLayer`：支持模块级别的配置
   - `jdk.internal.module.ModuleBootstrap` 和 `Modules`：启动时处理相关配置
   - `jdk.internal.access.JavaLangAccess` 和 `JavaLangReflectAccess`：内部访问接口更新

5. JFR 事件：
   - 在 `jdk.internal.event` 和 `jdk.jfr` 包下添加 `FinalFieldMutationEvent` 类
   - 更新 `JDKEvents.java`、`MirrorEvents.java`、`PlatformEventType.java` 注册新事件
   - 修改 `default.jfc` 和 `profile.jfc` 配置文件

6. JNI 检查增强：
   - `src/hotspot/share/prims/jni.cpp`：在 `SetField`/`SetStaticField` 系列函数中添加 final 字段修改的日志记录
   - `src/hotspot/share/prims/jniCheck.cpp`：添加 final 字段修改的警告检查

7. 测试用例：在 `test/jdk/java/lang/reflect/Field/` 下添加完整的测试覆盖：
   - `mutateFinals/MutateFinalsTest.java`：核心功能测试
   - `mutateFinals/FinalFieldMutationEventTest.java`：JFR 事件测试
   - `cli/CommandLineTest.java`：命令行选项测试
   - `jar/ExecutableJarTest.java`：可执行 JAR 场景测试
   - `jni/JNIAttachMutatorTest.java`：JNI 场景测试
   - `modules/`：模块系统相关测试

8. HotSpot JNI 测试：在 `test/hotspot/jtreg/runtime/jni/mutateFinals/` 下添加原生测试。

## Requirement
https://openjdk.org/jeps/500
