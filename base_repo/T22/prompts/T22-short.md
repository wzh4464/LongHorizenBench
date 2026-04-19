**Summary**: Python 当前的异常处理机制一次只能传播一个异常。PEP 654 提出引入 `ExceptionGroup` 和 `BaseExceptionGroup` 两个新的标准异常类型，用于同时表示和传播多个不相关的异常，并新增 `except*` 语法来专门处理异常组。

**Proposal**: 引入 `ExceptionGroup` 和 `BaseExceptionGroup` 类来封装多个异常，提供 `subgroup()` 和 `split()` 方法按条件分割异常组。新增 `except*` 语法来匹配和处理异常组中的特定类型，未匹配的异常自动重新抛出。同时更新 AST、字节码和编译器以支持新语法。
