**Summary**: JDK 的反射 API（`java.lang.reflect`）底层使用 native 代码实现方法/构造函数调用和字段访问，这导致启动性能差且难以优化。JEP 416 提出使用 `java.lang.invoke` 的 MethodHandle API 重新实现反射的核心操作，以提高性能并简化维护。

**Proposal**: 使用 MethodHandle API 重新实现 `java.lang.reflect` 的 Method、Constructor 和 Field 的核心访问器，创建新的 MethodHandle 基础的 MethodAccessor、ConstructorAccessor 和 FieldAccessor 实现，改进 Caller-Sensitive 方法的反射调用机制，确保新实现与现有行为兼容。
