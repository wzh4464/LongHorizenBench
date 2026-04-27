# T24: CPython — PEP 669 `sys.monitoring`

## Requirement (PEP 669)

*Source of truth: PEP 669. Do not access the network; the description below
is sufficient to implement the feature.*

PEP 669 adds a new monitoring API exposed as the `sys.monitoring` namespace.
It provides tool authors (debuggers, profilers, coverage tools) with a way
to subscribe to a fixed set of interpreter-level events without paying the
overhead that `sys.settrace`/`sys.setprofile` impose on every frame.

## 1. Motivation

`sys.settrace()` and `sys.setprofile()` impose a constant per-frame
overhead even when nothing interesting is being traced. Existing tooling
also competes for the single trace slot, making it impossible to run two
tools concurrently. PEP 669 introduces a pull-style monitoring API where
each tool registers callbacks for the events it cares about and the
interpreter only triggers them when those events occur. Tools coexist via
distinct tool IDs, and the interpreter is allowed to specialise / disable
event delivery for code objects that no tool is interested in.

## 2. Public API (`sys.monitoring`)

```
use_tool_id(tool_id, name)
free_tool_id(tool_id)
get_tool(tool_id)
set_events(tool_id, event_set)
get_events(tool_id) -> int
set_local_events(tool_id, code, event_set)
get_local_events(tool_id, code) -> int
register_callback(tool_id, event, func) -> previous_callback_or_None
restart_events()
DISABLE        # sentinel callback return value
MISSING        # sentinel "no argument" value
```

Constants on `sys.monitoring.events` (integer bitmasks):

```
PY_START   PY_RESUME    PY_RETURN   PY_YIELD   PY_THROW   PY_UNWIND
CALL       C_CALL       C_RETURN    C_RAISE
LINE       INSTRUCTION  JUMP        BRANCH
RAISE      RERAISE      EXCEPTION_HANDLED  STOP_ITERATION
NO_EVENTS
```

Tool ids: `DEBUGGER_ID = 0`, `COVERAGE_ID = 1`, `PROFILER_ID = 2`,
`OPTIMIZER_ID = 5`. Ids `3` and `4` are unused but reserved.

## 3. Callback signatures

Callbacks are registered per `(tool_id, event)` pair. Their signatures
depend on the event:

| Event                | Arguments                                |
|----------------------|------------------------------------------|
| PY_START / PY_RESUME | `(code, instruction_offset)`             |
| PY_RETURN / PY_YIELD | `(code, instruction_offset, retval)`     |
| CALL                 | `(code, instruction_offset, callable, arg0)` |
| LINE                 | `(code, line_number)`                    |
| INSTRUCTION          | `(code, instruction_offset)`             |
| JUMP / BRANCH        | `(code, instruction_offset, destination_offset)` |
| RAISE / RERAISE      | `(code, instruction_offset, exception)`  |
| EXCEPTION_HANDLED    | `(code, instruction_offset, exception)`     |
| STOP_ITERATION       | `(code, instruction_offset, exception)`     |
| C_RETURN / C_RAISE   | `(code, instruction_offset, callable, arg0)` |

A callback may return the special value `sys.monitoring.DISABLE` to indicate
that the event should not fire again for that (code object, instruction
offset) pair until `sys.monitoring.restart_events()` is called.

## 3. Behavioural rules

* `set_events(tool_id, event_set)` — global subscription for a tool.
* `set_local_events(tool_id, code, event_set)` — limits a tool's events to a
  single code object.
* `register_callback(tool_id, event, callback)` returns the previously
  registered callback (or `None`).
* Multiple tools may subscribe to the same event; the interpreter calls each
  tool's callback in tool-id order.
* When no tool subscribes to an event, the interpreter must not pay any cost
  in the hot path — this is the core motivation behind the PEP.
* `sys.settrace` and `sys.setprofile` are reframed as bridge implementations
  built on top of `sys.monitoring`; the legacy public API continues to work.

## 4. Backward compatibility

`sys.settrace` / `sys.setprofile` continue to function, layered on top of a
dedicated tool ID reserved for them. Existing debuggers and profilers should
not need to change.

## Implementation scope

Implement the `sys.monitoring` module, the per-event/per-tool dispatch in
the interpreter, and the bytecode hooks needed to fire each event. Update
`sys.settrace` and `sys.setprofile` so they keep working by registering
themselves under the legacy tool slot. Add a regression test module that
exercises every event type and the `DISABLE`/`restart_events()` flow.

The PEP does not prescribe specific filenames in CPython for the
implementation; the agent decides where the new code, tests and
documentation live.

## Acceptance

1. `import sys; sys.monitoring.use_tool_id(0, "test")` succeeds and
   `get_tool(0)` returns "test".
2. Registering callbacks for `PY_START`, `LINE`, `CALL`, `RETURN`, `RAISE`,
   `EXCEPTION_HANDLED` produces the expected event order on a test program.
3. Returning `sys.monitoring.DISABLE` from a callback prevents further
   invocations for the same `(code, offset)` pair until
   `sys.monitoring.restart_events()` is called.
4. `sys.settrace`/`sys.setprofile` still observe Python execution after the
   change.
