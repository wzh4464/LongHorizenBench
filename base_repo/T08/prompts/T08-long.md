**Summary**: JDK 的反射 API（`java.lang.reflect`）底层使用 native 代码实现方法/构造函数调用和字段访问，这导致启动性能差且难以优化。JEP 416 提出使用 `java.lang.invoke` 的 MethodHandle API 重新实现反射的核心操作，以提高性能并简化维护。

**Motivation**: 当前 JDK 反射实现存在三个主要问题：(1) Method.invoke 和 Constructor.newInstance 最初使用 native 代码实现，之后会动态生成字节码以提高性能，但这种两阶段模式增加了启动开销；(2) 字段访问（Field.get/set）始终使用 Unsafe 操作，没有经过 HotSpot 的优化路径；(3) 反射调用 Caller-Sensitive 方法（如 Class.forName）时需要特殊处理，当前实现复杂且易出错。使用 MethodHandle 重新实现可以统一代码路径、改善性能、并与现代 JVM 优化更好地集成。

**Proposal**: 使用 MethodHandle API 重新实现 `java.lang.reflect` 的 Method、Constructor 和 Field 的核心访问器：(1) 创建新的 MethodHandle 基础的 MethodAccessor 和 ConstructorAccessor 实现；(2) 创建新的 MethodHandle 基础的 FieldAccessor 实现系列（处理各种基本类型）；(3) 改进 Caller-Sensitive 方法的反射调用机制，使用适配器方法模式；(4) 更新相关类以利用 MethodHandle 的特性（如常量折叠）；(5) 确保新实现与现有行为兼容。

**Design Details**:

1. MethodHandle 基础的方法访问器：创建 `DirectMethodHandleAccessor` 类实现 `MethodAccessor` 接口，使用 MethodHandle 执行方法调用。将方法参数从 `Object[]` 转换为 MethodHandle 的参数格式，处理返回值类型转换。对于 Caller-Sensitive 方法，使用注入的调用者类进行特殊处理。

2. MethodHandle 基础的构造函数访问器：创建 `DirectConstructorHandleAccessor` 类实现 `ConstructorAccessor` 接口。使用 MethodHandle 调用构造函数，处理参数转换和异常包装。确保枚举类不能被反射创建的检查在正确时机执行。

3. MethodHandle 基础的字段访问器：创建 `MethodHandleFieldAccessorImpl` 抽象基类和一系列具体实现类（`MethodHandleBooleanFieldAccessorImpl`、`MethodHandleByteFieldAccessorImpl` 等），覆盖所有基本类型和引用类型。使用 `MethodHandle.unreflectGetter` 和 `unreflectSetter` 获取字段访问句柄。

4. 访问器工厂更新：在 `MethodHandleAccessorFactory` 中创建工厂方法，根据方法/构造函数/字段的特征选择合适的访问器实现。在 `ReflectionFactory` 中集成新的工厂，提供启用/禁用 MethodHandle 实现的开关。

5. Caller-Sensitive 适配器机制：引入 `@CallerSensitiveAdapter` 注解标记适配器方法。对于 CS 方法，在同一类中创建一个接受额外 `Class<?> caller` 参数的私有适配器方法。更新 `Class.forName`、`ClassLoader.registerAsParallelCapable` 等 CS 方法添加适配器。在 `MethodHandleImpl.BindCaller` 中检测并使用适配器方法。

6. 反射调用的调用者注入：创建 `CsMethodAccessorAdapter` 包装类，在反射调用 CS 方法时注入正确的调用者类。使用 `MethodHandleImpl.reflectiveInvoker` 获取注入调用者的方法句柄。

7. JavaLangInvokeAccess 扩展：在 `JavaLangInvokeAccess` 接口中添加新方法：`unreflectConstructor`、`unreflectField`、`findVirtual`、`findStatic`、`reflectiveInvoker`、`defineHiddenClassWithClassData`，供反射实现使用。

8. 类字段优化：将 `Method`、`Constructor`、`Field` 类中的实例字段改为 `final`，移除 `@Stable` 注解（因为 MethodHandle 的常量折叠已经提供了优化）。

9. VM 初始化顺序：添加 `VM.isJavaLangInvokeInited()` 检查，确保在 `java.lang.invoke` 模块完全初始化前使用 native 实现，避免引导循环。

10. 测试和兼容性：添加 `MethodHandleAccessorsTest` 测试新实现的正确性。更新现有反射测试以覆盖新实现路径。确保堆栈跟踪、调试信息等行为与原实现一致。
