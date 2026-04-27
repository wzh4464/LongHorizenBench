# T28: CPython — PEP 768: Safe External Debugger Interface for Running Python Processes

## Summary

PEP 768 adds a first-class, low-overhead debugger attach interface to CPython.
Target version: 3.14. Upstream references: `https://peps.python.org/pep-0768/`
and PR `python/cpython#131937`. The feature allows an external process to
cause an already-running Python interpreter to execute a specified Python
script at the next safe point, without patching memory, using ptrace/LD_PRELOAD
tricks, or injecting code at random.

Tools like profilers, debuggers, and live-ops scripts previously attached by
modifying `.text` pages or hijacking threads; this was unsafe (race with GC,
SIGSEGV if the interpreter moved), platform-fragile, and required elevated
privileges. PEP 768 exposes a cooperative channel built into the runtime.

## 2. Why

- Attach a debugger (e.g. pdb, debugpy, py-spy) to a production process
  without needing a signal handler or a custom extension.
- Let tools execute `sys.remote_exec(pid, "/tmp/some_script.py")` and have
  the target interpreter run the script at a safe point.
- Keep the steady-state cost near zero — no new per-opcode check when the
  feature is idle.

## 2. Design overview

Per-interpreter state gains a small cooperative handshake:

- `PyInterpreterState` has a new `_PyRemoteDebuggerSupport` struct that
  sits at a well-known offset (so tools can find it via
  `_Py_DebugOffsets`). The struct exposes:
  - `debugger_script_path[MAX_PATH]`: a buffer the attacher fills with the
    filesystem path of a Python source file to execute.
  - `pending_call_request`: a byte the attacher sets after writing the path.
  - `eval_breaker` bit: toggles `eval_breaker` in the target thread so the
    interpreter checks for work at the next eval breaker.
- The interpreter checks `pending_call_request` at eval breakers. If set, it
  loads `debugger_script_path`, resets the flag, and (via
  `_PyEval_RunDebuggerScript`) executes the file inside the current thread
  (in `PyRun_AnyFileEx` with globals/locals from the running frame).
- Attach flow from the foreign process:
  1. Locate the target interpreter's `_Py_DebugOffsets` via
     `process_vm_readv` / `ReadProcessMemory`.
  2. Walk `_PyRuntimeState` → `interpreters` → `_PyRemoteDebuggerSupport`.
  3. Write the script path into a control structure and set the pending bit.
  4. Send a signal or write to the eval breaker so the target wakes up.

## 3. Public API

New Python-level APIs:

```
sys.remote_exec(pid: int, script: str | bytes | os.PathLike) -> None
```

A new module `_remote_debugging` provides richer access but is considered
internal.

Environment variable `PYTHON_DISABLE_REMOTE_DEBUG` (and `-X remote_debug=off`)
disables the feature. Configure-time flags `--disable-remote-debug` (or
`--without-remote-debug`) drop compilation entirely.

## 4. Core data structures

```c
// PyThreadState additions
typedef struct _pycfg_remote_debugger_support {
    Py_ssize_t max_path_length;
    int debugger_pending_call;  // 0/1, set by external attacher
    char debugger_script_path[PYTHON_REMOTE_DEBUG_SCRIPT_PATH_LEN];
} _PyRemoteDebuggerSupport;
```

Inside `PyThreadState` add `_PyRemoteDebuggerSupport remote_debugger_support`.

Also add a symbol `_Py_DebugOffsets` that encodes the offsets an external
attacher needs: offsets into `PyRuntime` → `PyThreadState` fields → the new
debug-support struct. This makes the attach code resilient to interpreter
layout changes.

## 5. Evaluation breaker integration

the bytecode interpreter / the GIL implementation add a bit to the eval breaker,
`_PY_REMOTE_DEBUG_PENDING_BIT`. When the bit is set, the interpreter handles
it in `handle_eval_breaker`: read the path to the script from
`_PyRemoteDebuggerSupport`, call `PyRun_AnyFile` or `Py_CompileStringExFlags`
to compile and execute the script inside the current frame's globals/locals.
Errors during execution are stored on a dedicated queue (so other work
doesn't stop) and surfaced via a new audit event `sys.remote_exec`.

## 6. Command-line / config interface

* `sys.remote_exec(pid, script_path)` — public entry point.
* `PYTHONREMOTEDEBUG` env variable and `-X remote_debug=on|off` flag.
* `--with-remote-debug` / `--without-remote-debug` at configure time.
* `sys.flags.remote_debug` reports the effective state.
* When disabled, `sys.remote_exec` raises `RuntimeError`.
* The target process never acts on commands from a remote process unless
  the attachment API has been invoked explicitly (cooperative model), except
  for the `SIGUSR2` handler that the `sys` module installs optionally.

## 2. Public API

- New function `sys.remote_exec(pid: int, script_path: str) -> None`
  (Python level). It writes a single absolute path to the target's
  `_PyRemoteDebuggerSupport` struct, sets the pending flag, and nudges
  the target using a platform-specific mechanism (Linux: `process_vm_writev`
  + `pidfd_send_signal`; macOS: `mach_vm_write` + Mach port; Windows:
  `WriteProcessMemory` + `QueueUserAPC`).
- Audit event `sys.remote_exec` is raised on both the caller and the
  callee.
- A new `-X disable-remote-debug` flag and matching env var
  `PYTHONDISABLEREMOTEDEBUG` turn off the handshake at interpreter start.

## 3. Interpreter changes

- Extend `PyThreadState` with `_PyRemoteDebuggerSupport remote_debugger_support`.
- Add the remote-debug helper module hosting the protocol: the worker installs a
  pending callback through `_PyEval_AddPendingCall` when the flag flips.
- Expose the relevant struct offsets via `_Py_get_remote_debug_offsets()` so
  external tools can discover them with a single symbol lookup.
- Ensure the flag is checked at every `CHECK_EVAL_BREAKER` so pending
  requests run at a safe point, never while holding internal locks.

## 5. Build flags and runtime defaults

* Default: enabled on POSIX and Windows, disabled on WASI/Emscripten.
* `./configure --disable-remote-debug` omits the feature entirely.
* `sys.flags.remote_debug` reflects the runtime setting.
* A security-sensitive audit event `sys.remote_exec` is fired each time a
  script is loaded, with the pid and the path.

## 6. Acceptance criteria

* `sys.remote_exec(pid, path)` loads and executes the script inside the
  target process at the next eval-breaker safe point.
* `make test TEST=test_remote_debugging` passes, including the
  `_testinternalcapi` tests that exercise the handshake.
* Building with `--disable-remote-debug` produces an interpreter where
  `sys.remote_exec` raises `NotImplementedError` and the ThreadState layout
  no longer contains the support struct.
* The feature introduces no measurable overhead in the default hot path; the
  CHECK_EVAL_BREAKER microbench stays within 1% of baseline.
