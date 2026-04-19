# T41: CPython - PEP 793 PyModExport

**Summary**: PEP 793 提出了一种新的 C 扩展模块初始化机制 `PyModExport`，用于替代现有的 `PyInit_*` 入口函数。新机制通过返回 slots 数组而非 module 对象，消除了对静态分配 `PyObject` 实例的依赖，从而解决了普通 Python 构建与 free-threaded 构建之间的二进制兼容性问题。

**Motivation**: 当前的 C 扩展模块机制存在以下问题：
1. **内存布局不兼容**：Free-threaded Python 构建与普通构建的内存布局不同。由于 `PyModuleDef` 结构历史上包含 `PyObject` 头部且需要静态分配，导致为一种构建编译的扩展模块无法在另一种构建上工作。
2. **不必要的解释器切换**：当前 Python 必须调用模块初始化钩子才能获取兼容性信息（如 `Py_mod_multiple_interpreters` 设置），这迫使在导入过程中进行不必要的解释器切换，增加了复杂性和脆弱性。
3. **模块元数据访问受限**：现有系统无法在完全初始化之前检查模块能力，使得导入机制和扩展设计都更加复杂。

**Proposal**: 引入新的模块导出钩子 `PyModExport_<NAME>`，该函数返回 `PyModuleDef_Slot*` 类型的 slots 数组而非模块对象。同时提供新的 API 函数 `PyModule_FromSlotsAndSpec()` 和 `PyModule_Exec()` 用于从 slots 数组创建和执行模块，以及 module token 机制用于可靠的模块身份验证。所有新 API 将加入 Limited API（稳定 ABI）。

**Design Details**:

1. **定义新的 slot 类型**：在 `Include/moduleobject.h` 中添加新的 slot 常量定义，包括 `Py_mod_name`、`Py_mod_doc`、`Py_mod_state_size`、`Py_mod_methods`、`Py_mod_state_traverse`、`Py_mod_state_clear`、`Py_mod_state_free`、`Py_mod_token` 等，作为 `PyModuleDef` 成员的 slot 等价物。同时更新 `_Py_mod_LAST_SLOT` 的值。

2. **修改 PyModuleObject 内部结构**：在 `Include/internal/pycore_moduleobject.h` 中重构 `PyModuleObject` 结构体，将原来的 `md_def` 字段替换为更灵活的 token 机制。添加 `md_token`、`md_token_is_def` 等字段，以及独立的 GC 钩子字段（`md_state_traverse`、`md_state_clear`、`md_state_free`）和 `md_state_size`。

3. **实现核心 API 函数**：
   - `PyModule_FromSlotsAndSpec()`：从 slots 数组和 ModuleSpec 对象创建模块，复制所有输入数据
   - `PyModule_Exec()`：执行模块的 exec slot，等同于 `PyModule_ExecDef` 但支持基于 slots 的模块
   - `PyModule_GetStateSize()`：获取模块状态大小
   - `PyModule_GetToken()`：获取模块的 token 指针

4. **实现 PyType_GetModuleByToken()**：在 `Include/object.h` 中声明并在 `Objects/typeobject.c` 中实现该函数，用于通过 token 定位模块（返回强引用），替代 `PyType_GetModuleByDef`。

5. **修改导出宏定义**：在 `Include/exports.h` 中添加 `PyMODEXPORT_FUNC` 宏，用于声明返回 `PyModuleDef_Slot*` 的函数。重构 `PyMODINIT_FUNC` 的定义以复用内部宏。

6. **更新动态加载机制**：修改 `Include/internal/pycore_importdl.h` 和 `Python/importdl.c`，支持新的 `PyModExport_*` 钩子。添加 `PyModExportFunction` 类型定义，修改 `_PyImport_GetModuleExportHooks()` 函数以同时查找新旧两种入口点。

7. **更新模块对象实现**：在 `Objects/moduleobject.c` 中实现新的 API 函数，处理 slots 数组的解析和模块创建逻辑。确保 `PyModule_GetDef()` 对基于 slots 的模块返回 `NULL`。

8. **更新 stable_abi.toml 和 stable_abi.dat**：将新的 API 函数和宏添加到稳定 ABI 定义中，标记为 Python 3.15 新增。

9. **编写测试用例**：在 `Lib/test/test_capi/test_module.py` 中添加测试，覆盖 `PyModule_FromSlotsAndSpec()`、`PyModule_Exec()`、各种 slot 类型、token 机制等功能。在 `Modules/_testcapi/module.c` 中添加相应的测试辅助函数。

10. **更新现有测试模块**：修改 `Modules/_testmultiphase.c`、`Modules/_testsinglephase.c` 等测试模块，确保与新机制兼容，并添加使用新 API 的测试示例。
