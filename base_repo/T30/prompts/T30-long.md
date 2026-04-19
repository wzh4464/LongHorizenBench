# T30: CPython

**Summary**: PEP 578 引入 Python 运行时审计钩子机制，使测试框架、日志框架和安全工具能够监控并可选地限制运行时采取的操作。该功能提供两个主要 API：审计钩子（用于观察任意运行时事件）和验证打开钩子（专门用于模块导入系统），使安全监控工具能够检测和响应可能被恶意代码利用的敏感操作。

**Motivation**: 在监控 Python 应用程序时存在两个关键挑战。首先是有限的上下文：系统级监控可以检测到操作发生，但缺乏理解触发原因的能力。其次是审计绕过：Python 应用程序可以绕过传统监控工具，例如使用 `urllib.request` 进行网络操作不会被命令行工具监控捕获。PEP 578 通过在运行时关键点触发审计事件，让安全工具能够观察 Python 级别的操作。

**Proposal**: 在 CPython 中实现运行时审计钩子机制，包括：添加 `sys.audit()` 函数和 `sys.addaudithook()` 函数用于 Python 级别的审计；提供 `PySys_Audit()` 和 `PySys_AddAuditHook()` C API 用于 C 扩展；实现 `io.open_code()` 和 `PyFile_SetOpenCodeHook()` 用于验证代码打开操作；在运行时关键位置添加审计事件调用；以及相应的测试和文档。

**Design Details**:

1. 审计钩子 C API：在 `Python/sysmodule.c` 中实现 `PySys_Audit(const char *event, const char *format, ...)` 函数，用于触发审计事件。实现 `PySys_AddAuditHook(Py_AuditHookFunction hook, void *userData)` 函数，用于注册审计钩子。钩子函数类型为 `int (*)(const char *event, PyObject *args, void *userData)`。更新 `Include/sysmodule.h` 声明这些 API。

2. 审计钩子 Python API：在 `Python/sysmodule.c` 中实现 `sys.audit(event, *args)` 函数，用于从 Python 代码触发审计事件。实现 `sys.addaudithook(hook)` 函数，用于从 Python 代码注册审计钩子。生成对应的 clinic 文件。

3. 验证打开钩子 API：在 `Objects/fileobject.c` 中实现 `PyFile_SetOpenCodeHook(Py_OpenCodeHookFunction handler, void *userData)` 函数。在 `Lib/io.py` 和 `Lib/_pyio.py` 中实现 `io.open_code(path)` 函数，作为 `open(abspath(str(pathlike)), 'rb')` 的安全替代。更新 `Include/fileobject.h` 和 `Include/cpython/fileobject.h` 声明 C API。

4. 运行时状态扩展：修改 `Include/internal/pycore_pystate.h`，在解释器状态中添加审计钩子列表。确保钩子只能添加不能移除，异常会导致运行时终止（有意设计）。

5. 内置函数审计事件：在 `Python/bltinmodule.c` 中为 `compile()`、`exec()`、`eval()` 添加审计事件调用。在 `Objects/codeobject.c` 中为 `code.__new__` 添加审计事件。在 `Objects/funcobject.c` 中为 `function.__new__` 添加审计事件。

6. 文件和 I/O 审计事件：在 `Modules/_io/fileio.c` 和 `Modules/_io/_iomodule.c` 中为文件打开操作添加审计事件。在 `Modules/posixmodule.c` 中为 `os.open` 等操作添加审计事件。

7. 网络和外部资源审计事件：在 `Modules/socketmodule.c` 中为 socket 操作添加审计事件。在 `Lib/urllib/request.py` 中为 URL 请求添加审计事件调用。

8. ctypes 审计事件：在 `Modules/_ctypes/_ctypes.c` 中为 `ctypes.dlopen` 添加审计事件。在 `Modules/_ctypes/callproc.c` 中为 `ctypes.dlsym` 和 `ctypes.cdata` 添加审计事件。

9. 导入系统集成：修改 `Python/import.c` 和 `Lib/importlib/_bootstrap_external.py`，使用 `io.open_code()` 打开模块文件。在 `Lib/zipimport.py` 中同样使用验证打开钩子。

10. 测试和文档：创建 `Lib/test/test_audit.py`，覆盖审计钩子的各种使用场景。在 `Doc/c-api/sys.rst` 中添加 C API 文档。在 `Doc/library/sys.rst` 中添加 Python API 文档。在 `Doc/library/functions.rst` 中为内置函数添加审计事件说明。更新 `Doc/howto/instrumentation.rst` 描述 DTrace/SystemTap 集成。

## Requirement
https://peps.python.org/pep-0578/
