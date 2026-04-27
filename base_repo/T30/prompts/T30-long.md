# T30: CPython — PEP 578 Runtime Audit Hooks

## Summary

PEP 578 introduces two new runtime APIs to CPython:

1. **Audit hooks** — `sys.audit(event, *args)` raises an event that is
   delivered synchronously to all registered audit callbacks. Hooks can
   observe and abort sensitive operations such as importing modules,
   compiling code, opening files, or starting subprocesses.
2. **Verified open hook** — `io.open_code(path)` is the sanctioned entry
   point for the interpreter to load source/bytecode files. A host
   application may install a verified-open hook that intercepts every
   such read and validates the file (signature check, allow-list, etc.)
   before returning a stream.

The PEP positions these hooks as transparent integration points for
hardened deployments: anti-malware tooling, enterprise security
monitoring, and embedded interpreters that need to enforce code-loading
policies.

## 2. Audit hook API

```python
sys.audit(event: str, *args) -> None
sys.addaudithook(hook: Callable[[str, tuple], None]) -> None
```

- `sys.audit(event, *args)` synchronously invokes every registered hook
  with the event name and a tuple of positional arguments. CPython itself
  fires built-in audit events (file open, subprocess spawn, code
  compilation, `eval`/`exec`, `socket.connect`, etc.) so hooks can observe
  the same operations as third-party callers.
- `sys.addaudithook(hook)` appends a hook. Hooks cannot be removed (they
  are ordered by registration). The interpreter installs hooks per
  sub-interpreter, but native (C-level) hooks installed via
  `PySys_AddAuditHook` are global and run before any Python hooks.
- Hooks must be reentrancy-safe; they may not themselves raise to suppress
  the operation (they can raise a normal exception, which will surface to
  the caller of the audited operation).

C API equivalents:

```c
int PySys_Audit(const char *event, const char *format, ...);
int PySys_AddAuditHook(Py_AuditHookFunction hook, void *userData);
```

## 3. Verified open

```python
io.open_code(path) -> io.IOBase
```

`open_code` returns a binary stream from which the interpreter reads code
to compile. By default it behaves as `open(path, "rb")`. A host can install
a verified-open hook via `PyFile_SetOpenCodeHook` (C API) so that all
imports, `runpy`, and explicit calls to `open_code` route through the hook
before the bytes are handed to the compiler. The hook may sign-check, log,
or refuse the open.

## Required event coverage

At minimum the implementation must emit audit events from the following
operations (per the PEP table):

- `open` (any file opened via `open()`, `os.open`, etc.)
- `compile` (compilation of source via `compile()` or import)
- `exec` (execution of compiled objects)
- `import` (start and end of module import)
- `socket.connect`, `socket.bind`, `socket.listen`
- `subprocess.Popen`
- `os.system`, `os.exec*`, `os.posix_spawn*`, `os.fork`
- `urllib.Request`
- `winreg.OpenKey` / equivalent registry access on Windows

The full list lives in the PEP; the implementation should follow it.

## Public C API additions

- `int PySys_Audit(const char *event, const char *format, ...)`
- `int PySys_AddAuditHook(Py_AuditHookFunction hook, void *userdata)`
- `int PyFile_SetOpenCodeHook(Py_OpenCodeHookFunction handler, void *userdata)`
- `PyObject* PyFile_OpenCode(const char *path)`

## Reference behaviour

- Hooks installed before main are persistent across subinterpreters.
- Hooks installed at runtime via `sys.addaudithook` are per-interpreter and
  cannot be removed.
- Once an audit hook returns, the audited operation proceeds; if it raises,
  the caller receives that exception.

## 4. Backwards compatibility

The new comprehension syntax is purely additive — nothing previously
accepted changes meaning. Audit hooks may observe events that previously
went unobserved; this is intentional.

## Implementation scope

Provide:
- The `Py_AuditHookFunction` type and `PySys_AddAuditHook` /
  `PySys_Audit` C entry points.
- The Python-level helpers `sys.audit`, `sys.addaudithook` and a way to
  query whether any hook is registered for an event.
- Audit calls inserted at all the call sites listed in PEP 578 (open,
  compile, exec, eval, ctypes calls, socket connect, etc.).
- An "open code" hook (`io.open_code` / `PyFile_OpenCode`) for the import
  machinery to load source and bytecode through.
- Documentation listing the events and arguments and a regression test
  suite that asserts each documented event is emitted.

## Acceptance

- The published audit events listed in the PEP are all emitted with the
  documented argument shapes.
- A registered audit hook receives every event raised after registration.
- `io.open_code` routes through the verified-open hook when one is
  installed.
- Existing tests pass; new tests covering each audit event pass.
