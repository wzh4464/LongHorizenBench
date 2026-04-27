# T22: CPython — Implement PEP 654 Exception Groups and `except*`

## Requirement (PEP 654, inlined; do not fetch external sources)

PEP 654 introduces a way to raise and handle multiple unrelated exceptions
simultaneously, and a new syntactic form `except*` for handling them. The
upstream document is the only source of normative truth; everything you need
is summarized below.

## 1. Motivation

Several concurrency and resource-management patterns naturally produce more
than one exception at the same time:

- `asyncio.TaskGroup` and `asyncio.gather(...)` worker failures.
- `socket.socketpair`/multi-endpoint dial failures.
- Trio-style nursery teardown.
- `__exit__` raising while another exception is propagating.

Today Python collapses these into a single exception (often arbitrarily the
last one), losing information. Chained exceptions (`__context__`,
`__cause__`) describe causal chains, not concurrent siblings. PEP 654 adds
two builtins, `BaseExceptionGroup` and `ExceptionGroup`, that wrap a list of
inner exceptions, and a new `try ... except* T:` form whose body runs once
per matching exception leaf.

## 2. New built-in types

```
class BaseExceptionGroup(BaseException):
    def __new__(cls, message: str, exceptions: Sequence[BaseException]): ...
    message: str
    exceptions: tuple[BaseException, ...]
    def subgroup(self, condition) -> Self | None: ...
    def split(self, condition) -> tuple[Self | None, Self | None]: ...
    def derive(self, excs: Sequence[BaseException]) -> Self: ...

class ExceptionGroup(BaseExceptionGroup, Exception):
    """All contained exceptions must be Exception subclasses."""
```

Construction rules:

* `BaseExceptionGroup(msg, excs)` auto-promotes to `ExceptionGroup` if every
  element of `excs` is an `Exception`; otherwise it stays a
  `BaseExceptionGroup`.
* `ExceptionGroup(msg, excs)` rejects any non-`Exception` element with
  `TypeError`.
* The `exceptions` argument must be a non-empty sequence; an empty input
  raises `ValueError`.
* `condition` for `split`/`subgroup` is either a callable
  `(BaseException) -> bool` or an exception type / tuple of types (matched
  by `isinstance` recursively).
* `split` returns a pair `(matched, rest)`; each side may be `None` if
  empty. Both sides preserve traceback, cause, context, and notes from the
  originals; structure of nested groups is preserved.
* `derive` lets subclasses control how rebuilt groups are constructed; the
  default implementation builds a fresh `BaseExceptionGroup` /
  `ExceptionGroup` carrying the same `message`.

## 3. `except*` syntax

```
try_stmt:
      "try" ":" block
      ("except" "*" expression ["as" NAME] ":" block)+
      ["else" ":" block]
      ["finally" ":" block]
   |  ...

```

- A `try` statement may use either `except` clauses or `except*` clauses, but
  not a mixture.
- The exception expression after `except*` is evaluated with the usual rules
  (a type or tuple of types). It must not be a `BaseExceptionGroup` /
  `ExceptionGroup` subclass — that is rejected with `TypeError` at runtime.
- During exception handling the active group is split into matched and
  unmatched parts (`split`). Each `except*` clause runs at most once with the
  matched subgroup bound to the `as` name. Unmatched leaves are re-raised as
  a single combined group after all clauses run.
- Re-raising inside an `except*` clause (`raise` with no expression) re-raises
  the matched subgroup unchanged. Raising a new exception inside an
  `except*` clause causes that exception to be combined with any other raised
  / unmatched exceptions into a fresh group at the end of the `try`.
- `continue`, `break`, and `return` are disallowed inside `except*` clauses
  because the body may be entered multiple times semantically (one
  iteration per matched group). The parser must reject them.

## 4. Traceback rendering

For both regular `print_exception` and the default uncaught-exception hook,
the renderer must:

* Print `<type>: <message>` for the outer group.
* Indent each contained exception with the `  +-+- N ----` header used in
  the PEP examples, recursing through nested groups.
* Preserve `__context__` / `__cause__` chaining for each leaf.

## Runtime contract (Python level)

```python
class BaseExceptionGroup(BaseException):
    def __new__(cls, message, exceptions): ...
    message: str
    exceptions: tuple[BaseException, ...]
    def subgroup(self, condition) -> "BaseExceptionGroup | None": ...
    def split(self, condition) -> tuple["BaseExceptionGroup | None",
                                         "BaseExceptionGroup | None"]: ...
    def derive(self, excs) -> "BaseExceptionGroup": ...

class ExceptionGroup(BaseExceptionGroup, Exception):
    pass
```

`condition` may be:

* an exception type or tuple of types (matched with `isinstance`),
* or a callable `f(exc) -> bool` invoked on each leaf and on each group node.

Empty results from `subgroup`/`split` return `None`. Both methods preserve
`__traceback__`, `__cause__`, `__context__`, `__suppress_context__`, and
`__notes__` on every leaf and on the new groups they construct. `derive` is
the override hook for subclasses to customise the type of split/subgroup
outputs; the default implementation returns a `BaseExceptionGroup` (or
`ExceptionGroup` if all `excs` are `Exception`).

## `except*` semantics

```
try:
    ...
except* T1 as e1:
    handler1
except* (T2, T3):
    handler2
```

Behaviour:

1. Collect the raised exception. If it is not a group, wrap it in a
   transient `ExceptionGroup` of length 1.
2. For each `except*` clause in order, split the current group on the
   clause's type expression. If the matched subgroup is non-empty, run the
   handler with the matched group bound to the `as` name (if any). The
   un-matched remainder becomes the new "current group" for subsequent
   clauses.
3. After all clauses run, if any handlers raised new exceptions, combine
   them (and any still-unmatched remainder) into a single
   `ExceptionGroup` and re-raise. If only one exception is left and it is
   not an `ExceptionGroup`, re-raise it directly.
4. `else:` and `finally:` clauses follow the standard rules; `else` runs
   only when the entire `try` body completed without raising.

Static rules:

* `except*` and `except` cannot be mixed in the same `try`.
* `except*` cannot match `BaseExceptionGroup` / `ExceptionGroup` types.
* `continue`, `break`, and `return` are forbidden inside `except*`
  blocks.

## Implementation scope

The implementation needs to cover:

- The new builtin exceptions `BaseExceptionGroup` and `ExceptionGroup` and
  their `subgroup`/`split`/`derive` methods.
- Grammar and AST support for `except*` clauses.
- Bytecode and interpreter changes to compile and execute `try ... except*`,
  including the runtime split/merge of groups across multiple clauses.
- AST module support for the new syntax (and round-trip via `unparse`).
- Traceback rendering of nested groups in the documented `+-+- n -----` style.
- Tests for the new builtins, the new syntax, the static rejection of
  `continue`/`break`/`return` inside `except*`, and traceback rendering.
- Documentation in the language reference and what's-new.

The agent decides where in the CPython source tree to make each change; the
PEP itself does not prescribe filenames.

## Acceptance

* `BaseExceptionGroup`/`ExceptionGroup` are available as builtins with the
  documented constructor signature, methods, and pickling support.
* `try ... except* ...:` parses and executes per the semantics above and
  rejects mixed `except`/`except*` use, as well as `break`/`continue`/`return`
  inside `except*`.
* The standard test suite for exception groups and `except*` passes.
* `traceback.format_exception` renders nested groups with the PEP-654
  indentation pattern.
* Reference implementation: see PEP 654 ("Reference Implementation" section).
