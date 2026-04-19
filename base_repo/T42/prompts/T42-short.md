**Summary**: PEP 810 引入了显式延迟导入（Lazy Imports）语法，通过 `lazy` 软关键字允许开发者将特定的 import 语句标记为延迟执行。当使用 `lazy import module` 或 `lazy from module import name` 时，模块不会在 import 语句处立即加载，而是创建一个 `LazyImportType` 代理对象，在首次访问该名称时才真正加载模块。

**Proposal**: 在 Python 语法中添加 `lazy` 软关键字，支持 `lazy import` 和 `lazy from ... import` 语句。引入新的 `types.LazyImportType` 类型作为延迟导入的代理对象。提供全局控制机制（命令行选项 `-X lazy_imports` 和环境变量 `PYTHON_LAZY_IMPORTS`）以及运行时 API（`sys.set_lazy_imports()`、`sys.get_lazy_imports()`、`sys.set_lazy_imports_filter()`、`sys.get_lazy_imports_filter()`）来控制延迟导入行为。同时添加 `ImportCycleError` 异常用于处理延迟导入引起的循环导入错误。
