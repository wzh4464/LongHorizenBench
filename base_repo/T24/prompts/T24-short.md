**Summary**: CPython 当前的 `sys.settrace()` 和 `sys.setprofile()` 机制在启用调试或性能分析时会导致显著的性能下降（通常是数量级的）。PEP 669 提出引入 `sys.monitoring` 命名空间，提供一个低开销的程序监控 API。通过利用 PEP 659 的自适应解释器机制，新 API 能够使调试下的代码性能接近甚至超过未调试的 Python 3.11 版本。

**Proposal**: 引入 `sys.monitoring` 模块，定义多种监控事件（如 `PY_START`、`PY_RETURN`、`LINE`、`RAISE` 等），允许工具注册回调函数来监听特定事件。通过字节码插桩（instrumentation）机制，仅在需要监控的代码位置插入检测点，未被监控的代码完全不受影响。支持最多 6 个工具并行运行，每个工具可独立启用/禁用事件。
