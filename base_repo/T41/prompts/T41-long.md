# T41: CPython — PEP 793 Explicit Module Construction (`PyModExport`)

## Requirement (inlined)

Implement PEP 793, which introduces an explicit, slot-based module export
mechanism (`PyModExport`) for CPython extension modules. The reference is
PEP 793 only; everything required is captured below.

## 1. Motivation

Existing extension modules are built around either single-phase (`PyInit_*`)
or multi-phase (`PyModuleDef_Init` + `Py_mod_*` slots) initialisation. Both
share a fundamental problem: the static `PyModuleDef` object is owned by
the extension and must persist across module reloads, which has caused
ABI/lifetime issues and complicates porting between interpreter versions.

PEP 793 introduces a third pathway:

- The extension exports a `PyModExport_<name>` symbol returning a slot array.
- The interpreter, not the extension, owns the resulting `PyModuleDef` (the
  module-level state object) and lifetime.
- The slot array uses the same `PyModuleDef_Slot` mechanism already familiar
  from multi-phase init, with new slots that supply the metadata previously
  contained in a static `PyModuleDef`.

## New entry point

```
PyModuleDef_Slot *PyModExport_<modulename>(PyObject *spec);
```

The function is discovered by the loader the same way as
`PyInit_<modulename>`, but instead of returning a module object it returns a
slot array describing the module. The loader builds a `PyModuleDef`
internally from those slots and then runs the standard multi-phase
initialisation pipeline on it.

## Slot vocabulary

The PEP introduces slot ids that, taken together, supply everything that
used to live in `PyModuleDef`:

- `Py_mod_name` — the canonical module name (`const char *`).
- `Py_mod_doc` — module docstring (`const char *`).
- `Py_mod_state_size` — `Py_ssize_t` size of the per-module state.
- `Py_mod_methods` — pointer to a `PyMethodDef[]` array.
- `Py_mod_traverse`, `Py_mod_clear`, `Py_mod_free` — module-level GC hooks.
- `Py_mod_create`, `Py_mod_exec` — existing multi-phase slots, unchanged.
- `Py_mod_token` — opaque pointer used for module-state typechecks.

The slot list ends with `{0, NULL}` as today.

## Compatibility

- Modules that ship `PyInit_X` keep working unchanged.
- A module may ship both `PyInit_X` and `PyModExport_X`; the interpreter
  prefers the explicit export when present.
- Sub-interpreters and the per-interpreter GIL get the same treatment as
  multi-phase init: the interpreter is responsible for module lifetime.

## Implementation scope

* Add the new slot constants and the `PyModExport_*` discovery path in the
  loader.
* Build the implicit `PyModuleDef` from the returned slot array and route
  it through the existing multi-phase init machinery.
* Register the new symbols in the stable ABI / limited API as the PEP
  specifies.
* Provide a test extension exercising the new export, plus a regression
  test importing it and verifying state allocation, exec slots, and
  per-interpreter behaviour.

## Acceptance

- An extension module that exports only `PyModExport_<name>` imports
  successfully and reports the expected `__name__`, `__doc__`, and any
  state allocated by `Py_mod_state_size` / exec slots.
- An extension module that exports both `PyInit_<name>` and
  `PyModExport_<name>` uses the explicit export.
- Existing modules using `PyInit_*` and `PyModuleDef` are unaffected.
- The CPython test suite passes, including the new import / extension
  tests.
