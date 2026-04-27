# T42: CPython - PEP 810 Explicit Lazy Imports

## Requirement (PEP 810 - inlined; no external network access required)

PEP 810 introduces an explicit `lazy import` syntax for Python modules. The
existing `import` statement always evaluates the imported module eagerly;
the new `lazy import` form defers the actual import until the imported name
is first used. This reduces startup time for applications that import many
optional or rarely-used modules, while preserving today's `import`
semantics for everything that is not annotated `lazy`.

## Motivation

Real-world Python startup is dominated by transitive imports that may
never be exercised at runtime — CLI tools that load large optional
dependencies behind subcommands, plugin systems that touch every plugin
during discovery, etc. Implementations have long resorted to ad-hoc
lazy-import shims, but those are fragile, hard to reason about, and easy
to mis-use. PEP 810 gives the language a single, explicit, opt-in syntax
that delivers the optimisation reliably.

## Syntactic surface

`lazy` becomes a soft keyword that legally precedes only `import` and
`from … import` statements at module scope. All four spellings are
permitted:

```
lazy import os
lazy import os.path as p
lazy from os import path
lazy from os import path as p
```

Imports inside function bodies and class bodies are unaffected: they
remain eager, even if textually preceded by `lazy`. The grammar must
reject `lazy` in any other position.

## Semantics

A `lazy import` produces a binding to a *lazy proxy* in the surrounding
module's namespace. Reading the proxy triggers the actual import, which:

1. Performs the same import machinery as the eager statement would.
2. Replaces the binding in the module namespace with the resolved object.
3. Returns the resolved object to the original caller as if it had been
   imported eagerly.

Concurrent reads from multiple threads must observe the same fully
imported object (the proxy must use double-checked locking or an
equivalent mechanism). If the deferred import raises, subsequent reads
raise the same exception until the exception is explicitly cleared via
`importlib.invalidate_caches()` and a re-attempted access.

`from a.b import c` defers to first access of `c`. The `a.b` module must
load lazily as well (i.e. the deferred import covers both the package
import and the attribute lookup).

The standard `__getattr__`/`__class__` of a module observe the proxy as
the module attribute until first access; tools that want the live object
should call `getattr(module, "name")`, which triggers the import.

## Affected machinery

The implementation must:

1. Add new opcodes that perform lazy import in place of `IMPORT_NAME`
   when the source `lazy_import` flag is set; emit them from the
   compiler when it sees the `lazy` keyword.
2. Add a `LazyImportType` (or equivalent proxy object) that represents an
   unresolved import in module dictionaries. Reading the proxy triggers
   the import, replaces the module-dict entry, and returns the resolved
   value.
3. Wire `lazy import` through the existing import system so that hooks,
   `sys.modules`, finders, and loaders behave identically to an eager
   import once resolution occurs.

## Tests and docs

- Tests cover: module-level `import lazy x`, `from x import y` lazy form,
  failure paths, threading races, interaction with `__init__.py`, and
  interaction with `importlib.reload`.
- Documentation covers the language reference (the new `lazy` keyword) and
  the import system reference.

## Acceptance

* Existing test suite passes with no regressions.
* `lazy import foo` defers the module load until the name is first used.
* Failing lazy imports surface the original exception at use site.
* Reflection (`sys.modules`, `inspect.getmodule`) returns the resolved
  module after the lazy proxy has been triggered.
