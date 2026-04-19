# T48: TypeScript - 实现模板字面量类型和映射类型 as 子句

## Requirement

https://github.com/microsoft/TypeScript/issues/12754

## Summary

本功能为 TypeScript 引入两个重要的类型系统特性：
1. **模板字面量类型（Template Literal Types）**：类型空间中的模板字面量表达式，允许通过泛型占位符进行字符串字面量的拼接、转换和模式匹配。
2. **映射类型 `as` 子句（Mapped Type `as` Clauses）**：允许在映射类型中转换属性名称，支持过滤、重命名和生成多个属性。

这些特性使得 TypeScript 能够更精确地描述如 `${T}Changed`、`get${Capitalize<T>}` 等字符串操作模式，以及在映射类型中进行属性名转换和过滤。

## Motivation

许多 JavaScript 框架采用基于字符串的 API 约定。例如 Aurelia 框架中，当字段 `foo` 改变时，框架会尝试调用 `fooChanged()` 方法。当前 TypeScript 无法通过映射类型自动描述这种约定——无法在映射过程中对属性名进行字符串操作。

模板字面量类型填补了这一空白，允许类型系统理解并推断字符串模式操作。结合映射类型的 `as` 子句，可以实现：
- 为属性名添加前缀/后缀（如 `getFoo`、`fooChanged`）
- 基于值类型过滤属性
- 从一个属性生成多个属性

## Proposal

1. **模板字面量类型**：引入反引号语法的类型表达式，支持 `${T}` 形式的占位符，其中 T 必须是可赋值给 `string | number | boolean | bigint` 的类型。实现联合类型的分布式展开、字面量类型的字符串化、类型推断中的模式匹配。

2. **映射类型 as 子句**：在映射类型语法 `{ [P in K]: X }` 基础上，添加可选的 `as N` 子句变为 `{ [P in K as N]: X }`，其中 N 是将 P 转换后的新属性名类型。当 N 解析为 `never` 时不生成该属性（过滤功能），当 N 解析为联合类型时生成多个属性。

## Design Details

1. **类型系统扩展**：在 `types.ts` 中：
   - 添加 `TemplateLiteralType` 类型定义，包含 `texts`（字符串片段数组）、`types`（占位符类型数组）和 `casings`（大小写修饰符数组）
   - 扩展 `TypeFlags` 添加 `TemplateLiteral` 标志
   - 在 `MappedType` 中添加 `nameType` 字段支持 as 子句
   - 在 `MappedSymbol` 中添加 `keyType` 字段区分原始键类型和转换后的属性名类型

2. **解析器更新**：在 `parser.ts` 中：
   - 实现模板字面量类型的解析逻辑
   - 在映射类型解析中添加 `as` 子句的处理
   - 创建 `TemplateLiteralTypeSpan` 和相关 AST 节点

3. **扫描器更新**：在 `scanner.ts` 中添加模板字面量类型 token 的词法分析支持。

4. **节点工厂更新**：在 `nodeFactory.ts` 中：
   - 添加 `createTemplateLiteralType` 和 `createTemplateLiteralTypeSpan` 工厂方法
   - 更新 `createMappedTypeNode` 添加 `nameType` 参数

5. **类型检查器核心实现**：在 `checker.ts` 中：
   - 添加 `templateLiteralTypes` 缓存 Map
   - 实现 `getTemplateLiteralType` 函数处理模板字面量类型的解析和规范化
   - 添加 `templateConstraintType` 表示模板占位符的约束类型（`string | number | boolean | bigint`）
   - 实现模板字面量类型到类型节点的转换（`typeToTypeNodeHelper`）
   - 实现 `getNameTypeFromMappedType` 获取映射类型的 as 子句类型
   - 重构 `resolveMappedTypeMembers` 支持 as 子句的属性名转换逻辑
   - 修改 `addMemberForKeyType` 函数区分 `keyType`（原始键）和 `propNameType`（转换后的属性名）
   - 更新 `getTypeOfMappedSymbol` 使用新的 mapper 逻辑
   - 修改 `getLowerBoundOfKeyType` 支持更多类型
   - 在 `getBaseConstraintOfType` 和 `getBaseConstraint` 中添加对模板字面量类型的支持

6. **发射器更新**：在 `emitter.ts` 中添加模板字面量类型和映射类型 as 子句的代码生成逻辑。

7. **访问器更新**：在 `visitorPublic.ts` 中添加对新 AST 节点的访问支持。

8. **诊断消息**：在 `diagnosticMessages.json` 中添加模板字面量类型相关的错误消息。

9. **代码修复服务**：更新 `codefixes/` 下的相关服务以支持新的类型语法。

10. **测试用例**：添加 conformance 测试：
    - `templateLiteralTypes1.ts`：测试模板字面量类型的各种用法
    - `mappedTypeAsClauses.ts`：测试映射类型 as 子句的各种场景
