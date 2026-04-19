# T20: CPython

**Summary**: PEP 695 提出了 Python 类型参数的新语法，允许使用 `class Foo[T]:` 和 `def bar[T](x: T) -> T:` 的形式直接在类和函数定义中声明类型参数，同时引入 `type` 语句用于定义类型别名。本任务要求在 CPython 解释器中实现这一新语法。

**Motivation**: Python 现有的泛型定义方式存在多个问题：(1) 需要显式导入 `TypeVar`、`Generic` 等类型；(2) 类型变量在全局作用域定义但语义仅在泛型上下文中有效，容易造成混淆；(3) 协变（covariant）和逆变（contravariant）概念对大多数开发者来说过于复杂；(4) 类型参数的顺序规则不直观；(5) 代码冗余，需要重复写类型变量名称。新语法与 TypeScript、Rust 等现代语言保持一致，更加简洁直观。

**Proposal**: 扩展 Python 语法支持类型参数声明。在类和函数定义中添加可选的 `[T, U, ...]` 类型参数列表。引入 `type Name[T] = ...` 语句用于定义泛型类型别名。类型参数支持上界（`T: SomeType`）和约束（`T: (Type1, Type2)`）。实现惰性求值机制避免前向引用问题。

**Design Details**:

1. 语法扩展：修改 `Grammar/python.gram` 添加类型参数语法。扩展 `class_def`、`function_def` 规则支持 `[type_params]`。添加 `type_alias`、`type_params`、`type_param` 等新规则。

2. AST 扩展：更新 `Parser/Python.asdl` 定义新的 AST 节点。添加 `TypeAlias` 语句节点、`TypeVar`/`TypeVarTuple`/`ParamSpec` 类型参数节点。为 `FunctionDef`、`AsyncFunctionDef`、`ClassDef` 添加 `typeparams` 字段。

3. AST 处理：更新 `Python/ast.c` 实现 AST 构建。修改 `Python/ast_opt.c` 处理 AST 优化。更新 `Lib/ast.py` 添加 Python 层面的 AST 支持。

4. 符号表：修改 `Python/symtable.c` 和 `Include/internal/pycore_symtable.h`。类型参数在类体和函数体内可见，但在装饰器和默认参数中不可见。实现类型参数的特殊作用域规则。

5. 编译器：更新 `Python/compile.c` 生成字节码。为 `type` 语句和类型参数生成适当的指令。可能需要添加新的操作码（更新 `Lib/opcode.py`、`Python/opcode_targets.h`）。

6. 运行时类型对象：在 `Objects/typevarobject.c` 中实现 TypeVar、TypeVarTuple、ParamSpec、TypeAliasType 类型。创建 `Include/internal/pycore_typevarobject.h` 定义内部接口。更新 `Modules/_typingmodule.c` 暴露这些类型。

7. 函数对象扩展：修改 `Include/cpython/funcobject.h` 和 `Objects/funcobject.c`。添加 `func_typeparams` 字段存储函数的类型参数。

8. typing 模块更新：更新 `Lib/typing.py` 与新语法集成。确保 `TypeVar`、`Generic` 等现有类型与新语法兼容。

9. 惰性求值：类型别名的值、类型变量的上界和约束采用惰性求值。仅在访问 `__value__`、`__bound__` 等属性时才实际计算，避免前向引用问题。

10. 测试：添加 `Lib/test/test_type_params.py` 测试新语法。添加 `Lib/test/test_type_aliases.py` 测试 type 语句。更新 `Lib/test/test_ast.py`、`Lib/test/test_typing.py` 等现有测试。

## Requirement
https://peps.python.org/pep-0695/
