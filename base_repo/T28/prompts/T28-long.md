# T28: CPython

**Summary**: PEP 768 引入安全的外部调试器接口，允许调试器和性能分析器在不注入任意代码的情况下安全地附加到运行中的 Python 进程。该功能通过在 CPython 的求值循环中引入零开销的检查点机制，让外部工具能够请求在下一个安全执行点执行指定的 Python 脚本，从而为生产环境和高可用系统提供可靠的调试能力。

**Motivation**: 当前调试工具（如 DebugPy、Memray）尝试附加到运行中的 Python 进程时面临严峻挑战。现有方法通过 GDB/LLDB 进行不安全的代码注入，可能在内存分配或垃圾回收等关键操作期间执行，导致崩溃和解释器损坏。PEP 768 通过利用 CPython 现有的 `eval_breaker` 机制，提供一种安全的方式让外部进程在明确定义的安全点执行调试代码，且在正常执行期间零开销。

**Proposal**: 在 CPython 中实现安全的远程调试接口，包括：扩展 `PyThreadState` 结构以支持远程调试器状态；在求值循环中添加对 pending debugger call 的检查；实现 `sys.remote_exec(pid, script)` 函数用于向远程进程发送执行请求；添加环境变量和命令行选项以禁用该功能；扩展 configure 脚本以支持编译时禁用；以及相应的测试和文档。

**Design Details**:

1. PyThreadState 扩展：在 `Include/cpython/pystate.h` 中定义 `_PyRemoteDebuggerSupport` 结构体，包含 `debugger_pending_call` 标志（int32_t）和 `debugger_script_path` 缓冲区（512 字节）。将此结构体添加为 `PyThreadState` 的成员 `remote_debugger_support`。

2. PyConfig 扩展：在 `Include/cpython/initconfig.h` 的 `PyConfig` 结构体中添加 `remote_debug` 配置项（int 类型），用于控制远程调试功能的启用状态。

3. 调试偏移量表扩展：在 `Include/internal/pycore_debug_offsets.h` 中扩展 `_Py_DebugOffsets` 结构体，添加调试器相关字段的偏移量信息，使外部工具能够定位关键结构（无论 ASLR 或编译配置如何）。

4. 求值循环集成：修改 `Python/ceval_gil.c`，在 GIL 获取后检查 `debugger_pending_call` 标志。如果设置，则读取 `debugger_script_path` 并执行指定的 Python 脚本。利用现有的 `eval_breaker` 机制确保零开销——只有在 `eval_breaker` 已被设置时才会检查调试器标志。

5. sys.remote_exec 实现：在 `Python/sysmodule.c` 中实现 `sys.remote_exec(pid, script)` 函数。该函数将脚本路径写入目标进程的线程状态内存，设置 pending call 标志和 eval_breaker 位。生成对应的 clinic 文件 `Python/clinic/sysmodule.c.h`。

6. 远程调试模块：创建 `Python/remote_debugging.c`，实现跨平台的远程进程内存读写功能。在 Linux 上使用 `process_vm_writev`，在 macOS 上使用 Mach task 系统，在 Windows 上使用 `WriteProcessMemory`。

7. 配置和初始化：修改 `Python/initconfig.c`，处理 `remote_debug` 配置项的初始化和解析。实现对 `-X disable_remote_debug` 选项和 `PYTHON_DISABLE_REMOTE_DEBUG` 环境变量的支持。

8. 构建系统扩展：修改 `configure.ac`，添加 `--without-remote-debug` 选项以在编译时完全禁用该功能。更新 `pyconfig.h.in` 添加相应的宏定义。修改 `Makefile.pre.in` 和 `PCbuild/pythoncore.vcxproj` 以包含新的源文件。

9. 文档更新：在 `Doc/library/sys.rst` 中添加 `sys.remote_exec` 函数的文档。在 `Doc/using/cmdline.rst` 中记录 `-X disable_remote_debug` 选项。在 `Doc/using/configure.rst` 中记录 `--without-remote-debug` 选项。更新 `Doc/whatsnew/3.14.rst` 添加 PEP 768 的 What's New 条目。

10. 测试：在 `Lib/test/test_sys.py` 中添加 `sys.remote_exec` 的测试用例。在 `Lib/test/test_embed.py` 中测试嵌入式场景下的行为。创建跨进程调试的集成测试，验证脚本能够在目标进程中正确执行。

## Requirement
https://peps.python.org/pep-0768/
