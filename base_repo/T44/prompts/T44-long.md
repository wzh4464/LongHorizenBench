# T44: CPython - PEP 667 Consistent Views of Namespaces

**Summary**: PEP 667 解决了 Python 中 `frame.f_locals` 和 `locals()` 内建函数在处理局部变量命名空间时的长期不一致问题。该 PEP 将 `frame.f_locals` 从返回快照字典改为返回一个写透（write-through）代理对象，使得对 `f_locals` 的修改能够立即反映到实际的局部变量中，同时使 `locals()` 在优化作用域中返回独立的快照副本。

**Motivation**: 当前的 `frame.f_locals` 行为存在严重的不一致性：
1. **类作用域 vs 函数作用域的差异**：在类作用域中修改 `f_locals` 会影响局部变量，但在函数作用域中不会
2. **快照问题**：函数中的 `f_locals` 返回的是缓存的快照字典，对其修改不会反映到实际变量
3. **调试器困境**：当前行为使得调试器（如 pdb）无法可靠地修改被调试函数的局部变量
4. **隐式同步**：多次访问 `f_locals` 可能返回同一个共享字典，导致难以预测的行为

**Proposal**: 对于优化作用域（函数），将 `frame.f_locals` 改为返回新的 `FrameLocalsProxy` 代理类型的实例。该代理实现 `collections.abc.Mapping` 接口，对代理的写入会立即反映到底层变量中。同时修改 `locals()` 内建函数，使其在优化作用域中返回独立的字典快照。添加新的 C API 函数 `PyEval_GetFrameLocals()`、`PyEval_GetFrameGlobals()`、`PyEval_GetFrameBuiltins()` 以提供更清晰的语义。

**Design Details**:

1. **FrameLocalsProxy 类型实现**：
   - 在 `Include/cpython/frameobject.h` 中定义 `PyFrameLocalsProxyObject` 结构体
   - 在 `Include/cpython/pyframe.h` 中声明 `PyFrameLocalsProxy_Type` 和 `PyFrameLocalsProxy_Check` 宏
   - 在 `Objects/frameobject.c` 中实现 `FrameLocalsProxy` 类型，包括映射协议方法（`__getitem__`、`__setitem__`、`__contains__`、`__len__`、`__iter__` 等）

2. **写透语义实现**：
   - 代理对象持有对 frame 对象的引用
   - 读取操作直接从 frame 的 fastlocals 数组获取值
   - 写入操作直接修改 fastlocals 数组中的对应槽位
   - 对于闭包变量（cell variables），修改会传播到闭包中

3. **Frame 结构修改**：
   - 在 `Include/internal/pycore_frame.h` 中，将 `f_fast_as_locals` 字段替换为 `f_extra_locals`（用于存储用户通过 f_locals 添加的额外键）
   - 修改 `_PyFrame_GetLocals()` 函数签名，移除 `include_hidden` 参数
   - 添加 `_PyFrame_HasHiddenLocals()` 辅助函数
   - 移除 `_PyFrame_FastToLocalsWithError()` 和 `_PyFrame_LocalsToFast()` 函数

4. **C API 新增函数**：
   - 在 `Include/ceval.h` 中声明 `PyEval_GetFrameLocals()`、`PyEval_GetFrameGlobals()`、`PyEval_GetFrameBuiltins()`
   - 在 `Python/ceval.c` 中实现这些函数
   - `PyEval_GetFrameLocals()` 返回一个新的字典（等同于 Python 的 `locals()`）
   - 更新 `Doc/data/stable_abi.dat` 和 `Misc/stable_abi.toml` 将新函数添加到稳定 ABI

5. **locals() 内建函数修改**：
   - 在 `Python/bltinmodule.c` 中修改 `builtin_locals_impl()`
   - 对于优化作用域，返回 `dict(frame.f_locals)` 而非共享字典
   - 每次调用返回独立的快照

6. **Intrinsics 修改**：修改 `Python/intrinsics.c` 中的 `INTRINSIC_LOCALS` 实现，确保与新的 `locals()` 语义一致。

7. **sys._getframe().f_locals 行为**：确保 `sys._getframe().f_locals` 返回代理对象，且每次访问返回新的代理实例（`frame.f_locals is frame.f_locals` 返回 `False`，但内容相等）。

8. **测试更新**：
   - 在 `Lib/test/test_frame.py` 中添加 `TestFrameLocals` 测试类，全面测试代理对象的行为
   - 测试作用域（函数、类、闭包）、字典操作、删除限制、非字符串键等场景
   - 添加 C API 测试（使用 ctypes）
   - 更新 `Lib/test/test_listcomps.py` 中的列表推导式 f_locals 测试
   - 移除 `Lib/test/test_peepholer.py` 中不再适用的测试

9. **sysmodule 更新**：修改 `Python/sysmodule.c` 中的 frame 大小计算，反映新的 frame 结构。

10. **文档和 NEWS**：在 `Misc/NEWS.d/` 中添加变更说明，标明这是 PEP 667 的实现。
