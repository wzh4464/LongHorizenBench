# T22: CPython

**Summary**: Python 当前的异常处理机制一次只能传播一个异常。PEP 654 提出引入 `ExceptionGroup` 和 `BaseExceptionGroup` 两个新的标准异常类型，用于同时表示和传播多个不相关的异常，并新增 `except*` 语法来专门处理异常组。

**Motivation**: 在多个并发任务失败、批量回调执行、重试逻辑等场景中，程序可能需要同时报告多个不相关的错误。asyncio、Trio 等异步框架在多个任务同时失败时难以优雅地传播所有异常；pytest 等测试框架在多个 fixture 或 teardown 失败时也面临类似问题；socket 连接尝试多个地址时可能收集多个失败原因。现有的单一异常模型无法满足这些需求，开发者被迫使用各种变通方案（如将异常存入列表），但这些方案既不标准也不够健壮。

**Proposal**: 引入 `ExceptionGroup` 和 `BaseExceptionGroup` 类来封装多个异常，提供 `subgroup()` 和 `split()` 方法按条件分割异常组。新增 `except*` 语法来匹配和处理异常组中的特定类型，未匹配的异常自动重新抛出。同时更新 AST、字节码和编译器以支持新语法。

**Design Details**:

1. 扩展 AST 定义：在 `Parser/Python.asdl` 中添加 `TryStar` 语句类型，其结构与 `Try` 类似但语义不同。同时更新 `Include/internal/pycore_ast.h` 中的枚举和结构体定义。

2. 修改语法规则：在 `Grammar/python.gram` 中添加 `except_star_block` 规则来解析 `except*` 子句，更新 `try_stmt` 规则以支持 `TryStar` 语法。添加语法验证确保同一 try 块中不能混用 `except` 和 `except*`。

3. 实现 ExceptionGroup 类：在 `Objects/exceptions.c` 中实现 `ExceptionGroup` 和 `BaseExceptionGroup` 类型，包括构造函数、`subgroup()`、`split()` 等方法，以及异常组的嵌套和递归处理逻辑。

4. 添加新字节码指令：在 `Lib/opcode.py` 和 `Python/opcode_targets.h` 中定义 `JUMP_IF_NOT_EG_MATCH`（异常组匹配跳转）和 `PREP_RERAISE_STAR`（准备重新抛出未匹配异常）等新指令。

5. 更新编译器：修改 `Python/compile.c` 以生成 `TryStar` 语句的字节码，包括异常组的拆分、匹配、处理和重新抛出逻辑。实现与普通 try/except 不同的控制流。

6. 修改求值循环：在 `Python/ceval.c` 中实现新字节码指令的执行逻辑，处理异常组的匹配、拆分和重组操作。

7. 更新 AST 优化器和符号表：修改 `Python/ast_opt.c` 和 `Python/symtable.c` 以正确处理 `TryStar` 节点的遍历和分析。

8. 扩展 ast 模块：更新 `Lib/ast.py` 以支持 `TryStar` 节点的解析和反解析（unparse），确保 `ast.dump()` 和 `ast.unparse()` 正确处理新语法。

9. 更新文档：修改 `Doc/library/ast.rst` 和 `Doc/library/dis.rst`，添加 `TryStar` 类和新字节码指令的文档说明。在 `Doc/whatsnew/3.11.rst` 中记录此功能。

10. 编写测试用例：在 `Lib/test/` 下添加 `test_except_star.py` 和 `test_exception_group.py`，覆盖异常组的创建、嵌套、拆分、`except*` 语法的各种场景、与普通异常的交互等。

## Requirement
https://peps.python.org/pep-0654/
