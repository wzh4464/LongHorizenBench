# T37: OpenJDK Module Import Declarations

## Requirement
https://openjdk.org/jeps/476

---

**Summary**: JEP 476 提出引入模块导入声明（Module Import Declarations）功能，允许开发者通过 `import module M;` 语法导入一个模块导出的所有包。这是一个预览特性，旨在简化模块化程序中的导入语句，特别是在学习和原型开发阶段。

**Motivation**: 当使用第三方库或 Java 核心库时，开发者经常需要编写大量的导入语句。例如，使用 `java.base` 模块中的各种类时，需要分别导入 `java.util.*`、`java.io.*`、`java.math.*` 等多个包。这在以下场景中尤其繁琐：

1. 学习和教学：初学者需要理解包的概念才能正确导入类，增加了学习曲线。
2. 原型开发：快速开发时，频繁地添加导入语句打断了开发流程。
3. 脚本和小程序：简单程序中导入语句可能比实际代码还长。
4. 使用 JShell：交互式环境中，用户希望尽快开始编写代码。

**Proposal**: 引入新的导入语法 `import module M;`，该语句将导入模块 M 直接或间接导出的所有公共顶级类和接口。这是一个预览特性，需要通过 `--enable-preview` 启用。同时更新 JShell 默认启动脚本以使用新的模块导入功能。

**Design Details**:

1. **扩展 Preview Feature 枚举**：在 `PreviewFeature.java` 中添加 `MODULE_IMPORTS` 枚举值，关联 JEP 476，标记为预览状态。

2. **更新 Source.Feature 枚举**：在 `Source.java` 中添加 `MODULE_IMPORTS` 特性，指定它在 JDK 23 中作为预览特性引入。

3. **修改 Parser（JavacParser）**：扩展 `parseImportDeclaration()` 方法以识别 `import module` 语法。当遇到 `import` 后跟 `module` 关键字时，解析模块名称并创建相应的 AST 节点。

4. **扩展 JCTree AST 节点**：创建新的 `JCModuleImport` 类来表示模块导入声明。该节点应包含模块名称信息，并实现 `ImportTree` 接口。

5. **更新 ImportTree 接口**：在 `com.sun.source.tree.ImportTree` 中添加 `isModule()` 方法，用于区分普通导入和模块导入。该方法需要标记 `@PreviewFeature` 注解。

6. **修改 TypeEnter（语义分析）**：更新 `handleImports()` 方法以处理模块导入。当处理 `JCModuleImport` 时，需要：
   - 查找指定的模块
   - 验证当前模块能够读取目标模块
   - 遍历模块导出的所有包
   - 将每个导出包中的公共类型导入到当前编译单元的作用域

7. **更新 Check 类**：修改 `checkImportsResolvable()` 和 `checkImportedPackagesObservable()` 方法以正确处理模块导入声明，跳过对 `JCModuleImport` 的传统导入检查。

8. **更新 TreeDiffer 和 TreeCopier**：添加对 `JCModuleImport` 节点的访问方法，确保 AST 比较和复制功能正常工作。

9. **更新 Pretty 打印器**：实现 `JCModuleImport` 节点的漂亮打印，正确输出 `import module ...;` 格式。

10. **更新 TreeMaker**：添加创建 `JCModuleImport` 节点的工厂方法。

11. **添加编译器诊断消息**：在 `compiler.properties` 中添加相关的错误和警告消息，如模块未找到、模块不可读等。

12. **更新 JShell**：修改 JShell 的默认启动脚本和 Eval 类，使其在预览模式下自动导入 `java.base` 模块。

13. **编写测试用例**：添加正向测试（正确使用模块导入）、负向测试（错误用法的诊断）、以及与 JShell 集成的测试。
