# T42: CPython - PEP 810 Lazy Imports

**Summary**: PEP 810 引入了显式延迟导入（Lazy Imports）语法，通过 `lazy` 软关键字允许开发者将特定的 import 语句标记为延迟执行。当使用 `lazy import module` 或 `lazy from module import name` 时，模块不会在 import 语句处立即加载，而是创建一个 `LazyImportType` 代理对象，在首次访问该名称时才真正加载模块。

**Motivation**: 大型 Python 应用程序的启动时间和内存消耗是常见的性能瓶颈。许多模块在程序启动时被导入，但可能在整个运行过程中从未被使用。延迟导入机制允许开发者显式标记可以延迟加载的模块，从而：
1. **减少启动时间**：实际测试显示命令行工具可减少 50-70% 的启动时间
2. **降低内存占用**：大型应用可节省 30-40% 的内存
3. **保持语义明确**：通过显式的 `lazy` 关键字，代码的行为清晰可预测

**Proposal**: 在 Python 语法中添加 `lazy` 软关键字，支持 `lazy import` 和 `lazy from ... import` 语句。引入新的 `types.LazyImportType` 类型作为延迟导入的代理对象。提供全局控制机制（命令行选项 `-X lazy_imports` 和环境变量 `PYTHON_LAZY_IMPORTS`）以及运行时 API（`sys.set_lazy_imports()`、`sys.get_lazy_imports()`、`sys.set_lazy_imports_filter()`、`sys.get_lazy_imports_filter()`）来控制延迟导入行为。同时添加 `ImportCycleError` 异常用于处理延迟导入引起的循环导入错误。

**Design Details**:

1. **语法扩展（Grammar）**：修改 `Grammar/python.gram`，为 import 语句添加可选的 `lazy` 前缀。`lazy` 作为软关键字，仅在 import 语句前有特殊含义，其他地方仍可作为普通标识符使用。需要处理 `lazy import module`、`lazy from module import names` 等形式，但不支持 `lazy from module import *`。

2. **AST 扩展**：修改 `Parser/Python.asdl`，在 `Import` 和 `ImportFrom` AST 节点中添加 `is_lazy` 字段。更新 `Parser/action_helpers.c` 中的 AST 构建代码。

3. **LazyImportObject 实现**：创建 `Objects/lazyimportobject.c`，实现 `LazyImportType` 类型。该代理对象存储原始 import 语句的信息，在首次访问时触发实际的模块加载（reification）。需要处理属性访问、比较操作等，并在 reification 时正确设置全局命名空间。

4. **编译器修改**：
   - 修改 `Python/symtable.c` 添加延迟导入的符号表处理
   - 修改 `Python/compile.c` 和 `Python/codegen.c` 生成延迟导入的字节码
   - 添加新的字节码指令或修改现有 `IMPORT_NAME`/`IMPORT_FROM` 指令以支持延迟语义

5. **字节码解释器修改**：修改 `Python/bytecodes.c` 和 `Python/ceval.c`，实现延迟导入的运行时行为。当执行延迟 import 时，创建 `LazyImportType` 对象而非立即导入模块。

6. **运行时控制 API**：
   - 在 `Python/sysmodule.c` 中实现 `sys.set_lazy_imports()`、`sys.get_lazy_imports()`、`sys.set_lazy_imports_filter()`、`sys.get_lazy_imports_filter()`
   - 定义 `PyImport_LazyImportsMode` 枚举和相关 C API
   - 修改 `Python/initconfig.c` 处理命令行选项和环境变量

7. **ImportCycleError 异常**：在 `Objects/exceptions.c` 中添加 `ImportCycleError` 异常类，作为 `ImportError` 的子类，用于报告延迟导入导致的循环导入错误。更新异常层次结构文档。

8. **types 模块更新**：在 `Lib/types.py` 和 `Modules/_typesmodule.c` 中暴露 `LazyImportType` 类型，使用户可以通过 `types.LazyImportType` 检测延迟导入对象。

9. **文档更新**：
   - 更新 `Doc/reference/simple_stmts.rst` 添加 lazy imports 章节
   - 更新 `Doc/reference/lexical_analysis.rst` 添加 `lazy` 软关键字说明
   - 更新 `Doc/library/sys.rst` 添加新 API 文档
   - 更新 `Doc/using/cmdline.rst` 添加命令行选项说明
   - 更新 `Doc/whatsnew/3.15.rst` 添加新特性说明

10. **测试**：在 `Lib/test/test_import/` 下创建 `test_lazy_imports.py` 及相关测试数据文件，全面测试延迟导入的语法解析、运行时行为、全局模式控制、过滤器功能、错误处理等场景。
