# T11: TypeScript - 装饰器元数据 (Decorator Metadata)

## Summary

TC39 装饰器提案在最新版本中移除了装饰器对类原型的直接访问能力，导致装饰器无法方便地为类关联元数据。本任务需要在 TypeScript 编译器中实现 TC39 Decorator Metadata 提案，使装饰器能够通过 `Symbol.metadata` 向类附加元数据信息，支持依赖注入、序列化、验证等常见使用场景。

## Motivation

在装饰器提案的早期版本中，装饰器可以访问类原型，从而能够向其附加元数据。但在最新的 Stage 3 装饰器提案中，装饰器只能访问"直接被装饰的值"（方法、字段、accessor 等），无法直接访问类本身。这限制了很多依赖元数据的场景：

- **依赖注入 (DI)**：需要记录哪些参数需要注入什么类型
- **序列化/反序列化**：需要记录字段的序列化规则
- **验证**：需要记录字段的验证规则
- **Web 组件**：需要记录属性与 DOM 属性的映射
- **声明式路由**：需要记录方法与路由的对应关系

Decorator Metadata 提案通过在装饰器上下文中提供一个共享的 `metadata` 对象，并最终将其附加到类的 `Symbol.metadata` 属性上，解决了这一问题。

## Proposal

在 TypeScript 编译器中实现 Decorator Metadata 提案：

1. 扩展装饰器上下文对象，添加 `metadata` 属性
2. 为每个被装饰的类创建一个元数据对象，该对象的原型指向父类的元数据对象（实现继承）
3. 将同一个元数据对象传递给应用于类及其所有成员的装饰器
4. 在类定义完成后，将元数据对象附加到类的 `Symbol.metadata` 属性
5. 添加 `esnext.decorators` 库定义，包含 `Symbol.metadata` 的类型声明

## Design Details

1. **扩展装饰器上下文类型定义**：在 `ESDecorateClassContext` 和 `ESDecorateClassElementContext` 接口中添加 `metadata: Expression` 字段，用于在代码生成时传递元数据引用。

2. **创建元数据对象**：在 `createClassInfo` 函数中为每个被装饰的类创建唯一的元数据标识符（`_metadata`），用于在转换过程中引用元数据对象。

3. **修改上下文对象生成**：更新 `createESDecorateClassContextObject` 和 `createESDecorateClassElementContextObject` 函数，在生成的上下文对象中包含 `metadata` 属性。

4. **实现元数据继承**：在类定义的开始位置生成创建元数据对象的代码，如果类有父类，则元数据对象的原型应指向父类的 `Symbol.metadata`。

5. **附加元数据到类**：在所有装饰器执行完毕后，将元数据对象设置为类的 `Symbol.metadata` 属性值。

6. **添加库定义文件**：创建 `lib.esnext.decorators.d.ts`，声明 `Symbol.metadata` 符号；更新 `lib.esnext.d.ts` 引用新的库文件；更新 `libs.json` 和 `commandLineParser.ts` 注册新库。

7. **更新 emit helpers**：修改 `emitHelpers.ts` 中的辅助函数，确保正确生成包含元数据的装饰器调用代码。

8. **处理类表达式和类声明**：确保无论是类表达式还是类声明，元数据对象都能正确创建和附加。需要调整 `classFields.ts` 中的临时变量处理逻辑。

9. **添加测试用例**：创建覆盖各种场景的 conformance 测试，包括：基本元数据使用、元数据继承、静态成员装饰器、私有成员装饰器等。

10. **添加评估测试**：在 testRunner 中添加运行时评估测试，验证生成的代码在运行时的正确行为。

## Requirement

https://github.com/tc39/proposal-decorator-metadata
