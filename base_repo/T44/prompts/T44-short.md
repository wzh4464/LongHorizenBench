**Summary**: PEP 667 解决了 Python 中 `frame.f_locals` 和 `locals()` 内建函数在处理局部变量命名空间时的长期不一致问题。该 PEP 将 `frame.f_locals` 从返回快照字典改为返回一个写透（write-through）代理对象，使得对 `f_locals` 的修改能够立即反映到实际的局部变量中，同时使 `locals()` 在优化作用域中返回独立的快照副本。

**Proposal**: 对于优化作用域（函数），将 `frame.f_locals` 改为返回新的 `FrameLocalsProxy` 代理类型的实例。该代理实现 `collections.abc.Mapping` 接口，对代理的写入会立即反映到底层变量中。同时修改 `locals()` 内建函数，使其在优化作用域中返回独立的字典快照。添加新的 C API 函数 `PyEval_GetFrameLocals()`、`PyEval_GetFrameGlobals()`、`PyEval_GetFrameBuiltins()` 以提供更清晰的语义。
