**Summary**: TC39 装饰器提案在最新版本中移除了装饰器对类原型的直接访问能力，导致装饰器无法方便地为类关联元数据。本任务需要在 TypeScript 编译器中实现 TC39 Decorator Metadata 提案，使装饰器能够通过 `Symbol.metadata` 向类附加元数据信息，支持依赖注入、序列化、验证等常见使用场景。

**Proposal**: 在 TypeScript 编译器中实现 Decorator Metadata 提案，扩展装饰器上下文对象添加 metadata 属性，为每个被装饰的类创建元数据对象并支持继承链，将元数据对象传递给类及其成员的装饰器，在类定义完成后附加到 Symbol.metadata 属性，并添加相应的库定义文件。
