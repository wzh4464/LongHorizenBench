# T24: CPython

**Summary**: CPython 当前的 `sys.settrace()` 和 `sys.setprofile()` 机制在启用调试或性能分析时会导致显著的性能下降（通常是数量级的）。PEP 669 提出引入 `sys.monitoring` 命名空间，提供一个低开销的程序监控 API。通过利用 PEP 659 的自适应解释器机制，新 API 能够使调试下的代码性能接近甚至超过未调试的 Python 3.11 版本。

**Motivation**: 开发者不应该为使用调试器和性能分析器付出过高的性能代价。现有的 `sys.settrace()` 机制会在每条 Python 指令执行时调用 trace 函数，即使用户只关心少数特定事件（如函数调用或异常），这种"全量"监控导致严重的性能损耗。Python 开发者应该能够像 C++ 和 Java 开发者一样，在调试器下以接近全速运行程序。

**Proposal**: 引入 `sys.monitoring` 模块，定义多种监控事件（如 `PY_START`、`PY_RETURN`、`LINE`、`RAISE` 等），允许工具注册回调函数来监听特定事件。通过字节码插桩（instrumentation）机制，仅在需要监控的代码位置插入检测点，未被监控的代码完全不受影响。支持最多 6 个工具并行运行，每个工具可独立启用/禁用事件。

**Design Details**:

1. 定义监控事件类型：在 `Include/cpython/code.h` 中定义 `PY_MONITORING_EVENTS`（16 种事件）和 `PY_MONITORING_UNGROUPED_EVENTS`（14 种基本事件）。事件包括：PY_START、PY_RESUME、PY_RETURN、PY_YIELD、CALL、LINE、INSTRUCTION、JUMP、BRANCH、STOP_ITERATION、RAISE、EXCEPTION_HANDLED 等。

2. 扩展代码对象结构：在 `PyCodeObject` 中添加 `_co_monitoring` 字段（指向 `_PyCoMonitoringData` 结构）和 `_co_instrumentation_version` 字段。`_PyCoMonitoringData` 包含本地监控设置、活跃监控设置、以及每指令的工具位图和原始 opcode 存储。

3. 实现插桩机制：创建 `Python/instrumentation.c`，实现字节码插桩的核心逻辑。当监控被激活时，将目标指令替换为 `INSTRUMENTED_*` 版本；当监控被禁用时，恢复原始指令。使用版本号确保代码对象的插桩状态与全局监控设置同步。

4. 添加插桩字节码：在 `Python/bytecodes.c` 中为需要监控的 opcode 添加 `INSTRUMENTED_` 前缀版本，这些版本在执行时会检查并触发相应的监控回调。更新 `Lib/opcode.py` 和 `Python/opcode_targets.h`。

5. 修改求值循环：更新 `Python/ceval.c` 和 `Python/ceval_macros.h`，移除旧的 `use_tracing` 字段检查，改为基于插桩字节码的事件触发机制。优化热路径，确保未被监控的代码不产生额外开销。

6. 实现 sys.monitoring 模块：在 `Python/instrumentation.c` 中导出 Python API，包括 `register_callback()`、`set_events()`、`get_events()`、`set_local_events()` 等函数。定义工具 ID 常量（DEBUGGER、PROFILER、OPTIMIZER 等）。

7. 更新解释器状态：修改 `Include/internal/pycore_interp.h` 和 `Include/internal/pycore_pystate.h`，添加全局监控状态结构。在 `_PyInterpreterState` 中存储每个工具的事件回调和启用状态。

8. 实现 legacy tracing 兼容层：创建 `Python/legacy_tracing.c`，将 `sys.settrace()` 和 `sys.setprofile()` 映射到新的监控 API。确保现有使用 trace/profile 的代码继续工作。

9. 更新帧对象：修改 `Include/internal/pycore_frame.h` 和 `Objects/frameobject.c`，添加 `f_last_traced_line` 字段用于 LINE 事件去重，调整栈指针管理逻辑以支持监控期间的栈状态检查。

10. 编写测试用例：创建 `Lib/test/test_monitoring.py`，覆盖所有事件类型、多工具并行、动态启用/禁用、与 legacy tracing 的交互、性能基准测试等场景。

## Requirement
https://peps.python.org/pep-0669/
