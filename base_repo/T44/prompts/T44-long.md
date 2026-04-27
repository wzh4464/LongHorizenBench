# T44: CPython — PEP 667 Consistent Views of Namespaces

## Motivation (PEP 667)

*Source: PEP 667. Do not rely on network access to peps.python.org.*

Historically, `frame.f_locals` for a function frame returned a fresh dict
populated from the frame's "fast locals" each time it was called. Mutations
to the returned dict were not reflected back into the frame, and subsequent
reads of `frame.f_locals` would silently overwrite them. This produced a
long list of papercuts: debuggers could not reliably inspect or mutate local
variables, generators/coroutines exposed stale snapshots, and class bodies
or comprehensions had idiosyncratic differences in what `locals()` actually
contained.

PEP 667 makes `frame.f_locals` return a **write-through proxy view** of the
frame's local variables for optimised function frames. Mutations through
the proxy directly update the corresponding fast-local slot (or cell, for
closures), and the proxy reflects the live frame state on every access.
For module/class/exec frames where `f_locals` already aliased the underlying
namespace dict, behaviour is unchanged.

## Specification

- `frame.f_locals` for a function/coroutine/generator frame returns a
  proxy object whose `__getitem__`, `__setitem__`, `__delitem__`,
  `__contains__`, and iteration are backed by the frame's fast locals.
- Mutating the proxy updates the frame; reading after a mutation returns
  the updated value; the change is visible when execution resumes.
- The proxy supports the full mapping protocol (`keys`, `values`, `items`,
  `get`, `update`, `pop`, etc.) and is comparable with regular dicts via
  `==`.
- `locals()` inside a function returns a fresh `dict` snapshot of the
  proxy (so existing code that assumed snapshot semantics keeps working).
- For module / class scopes the behaviour is unchanged: `frame.f_locals`
  is the underlying namespace dict (no proxy needed).

### C API

A new C API is added so that C extensions and the interpreter can obtain
either the proxy or a snapshot dict from a frame:

```
PyObject *PyFrame_GetLocals(PyFrameObject *frame);    /* proxy or dict */
PyObject *PyEval_GetFrameLocals(void);                /* current frame */
```

The legacy `PyFrame_FastToLocalsWithError` and similar helpers are
deprecated but kept working for backward compatibility (they return a
snapshot rather than the proxy).

### Pickling / copying

The proxy is not pickleable directly; users must convert with
`dict(frame.f_locals)` first. `copy.copy` of the proxy returns a snapshot
dict.

## Implementation scope

The implementation must cover:

- A new proxy type with the documented mapping behaviour (`__getitem__`,
  `__setitem__`, `__delitem__`, `__iter__`, `__len__`, `__contains__`,
  `keys/values/items`, `update`, `pop`, `popitem`, `clear`, `setdefault`),
  reflecting and mutating frame locals through the existing fast-local
  storage.
- Updating `PyFrame_GetLocals` (and the `frame.f_locals` attribute) to
  return the proxy for optimised frames.
- Updating `locals()` semantics so that, in a function body, repeated
  `locals()` calls observe each other's writes (the proxy is shared per
  frame).
- Updating `exec()` / `eval()` so that, when no explicit globals/locals
  are provided in a function body, they receive the proxy and writes are
  visible after the call.
- Adjusting tooling: `pdb`, `bdb`, `inspect`, the trace hook, and any
  other internal users of `frame.f_locals` to keep working with the proxy.

## Acceptance criteria

- `frame.f_locals` inside a function body returns the same proxy object on
  repeated access within the same execution of the frame.
- Writing to the proxy from a debugger / tracer immediately changes the
  function's local variable when execution resumes.
- `dict(frame.f_locals)` continues to produce a snapshot.
- `exec(code, frame.f_globals, frame.f_locals)` updates locals in the
  expected way, including for closures and free variables.
- All tests in the standard library that exercise `frame.f_locals`, the
  debugger (`pdb`), and tracing infrastructure pass with the new semantics.
