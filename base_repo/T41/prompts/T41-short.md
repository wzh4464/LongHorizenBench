**Summary**: PEP 793 提出了一种新的 C 扩展模块初始化机制 `PyModExport`，用于替代现有的 `PyInit_*` 入口函数。新机制通过返回 slots 数组而非 module 对象，消除了对静态分配 `PyObject` 实例的依赖，从而解决了普通 Python 构建与 free-threaded 构建之间的二进制兼容性问题。

**Proposal**: 引入新的模块导出钩子 `PyModExport_<NAME>`，该函数返回 `PyModuleDef_Slot*` 类型的 slots 数组而非模块对象。同时提供新的 API 函数 `PyModule_FromSlotsAndSpec()` 和 `PyModule_Exec()` 用于从 slots 数组创建和执行模块，以及 module token 机制用于可靠的模块身份验证。所有新 API 将加入 Limited API（稳定 ABI）。
