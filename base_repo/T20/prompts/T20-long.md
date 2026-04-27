# T20 - CPython: PEP 695 Type Parameter Syntax

## Requirement

*Upstream source:* https://peps.python.org/pep-0695/ (implementation: https://github.com/python/cpython/pull/103764). Full specification inlined below so the agent does not need network access.

## 1. Motivation

Before PEP 695, Python generics required verbose `typing.TypeVar` bookkeeping outside the declaration site:

```python
from typing import Generic, TypeVar

T = TypeVar("T")
class Stack(Generic[T]):
    ...
```

This is awkward: TypeVars live apart from their usage, the `Generic[T]` base is pure boilerplate, and there is no natural way to bind generics to a type alias. PEP 695 adds dedicated *syntax* so that a class, function, or type alias declaration introduces its type parameters inline.

After PEP 695:

```python
class Stack[T]: ...
def first[T](xs: list[T]) -> T: ...
type IntList = list[int]
type Vector[T] = list[T]
```

## 2. Syntax

### 2.1 Generic class / function

```
class_def : 'class' NAME type_params? ['(' arglist? ')'] ':' suite
func_def  : 'def'   NAME type_params? '(' params ')' ... ':' suite
type_params : '[' type_param (',' type_param)* ']'
type_param  : ('*' | '**')? NAME (':' bound)?
```

Each type parameter may optionally include a **bound** (for simple TypeVars) or a **constraint tuple** (for TypeVars). `*T` introduces a `TypeVarTuple`; `**P` introduces a `ParamSpec`.

### 3.2 `type` alias statement

```
type Alias = expression
type Alias[T, *Ts, **P] = expression
```

- Introduces a new `TypeAliasType` object bound to `Alias` in the current scope.
- The right-hand side is lazily evaluated the first time any attribute is accessed on the alias.
- Accepts the same type parameter syntax as generic classes and functions.

### 3.3 Scoping rules

- Type parameters introduced in a `class` or `def` header are in scope within the entire class body / function body, including annotations.
- Type parameters are *not* in scope of the default values of preceding parameters (to avoid forward references).
- `type T = ...` creates a `TypeAliasType` whose RHS is evaluated lazily; the alias itself is usable immediately.

## 3. Runtime objects

- `typing.TypeVar`, `typing.TypeVarTuple`, and `typing.ParamSpec` gain a `__typing_is_unpacked_typevartuple__` attribute and related improvements to work with the new syntax.
- A new built-in (`typing.TypeAliasType` exposed via the `type` statement) represents the lazy alias object.

## 4. Implementation items

Below is a (non-exhaustive) list of the CPython source changes required:

1. the PEG grammar — new grammar rules for `type_param_seq`, `type_alias_stmt`, `generic_class_def`, `generic_func_def`.
2. the C tokenizer / the Python-level tokenizer module — soft-keyword support for `type`.
3. the bytecode compiler — emit bytecode for `TYPE_PARAMS_BEGIN/END`, `TYPE_ALIAS` opcodes; implement the new `class`/`function` codegen with a `__type_params__` attribute.
4. the symbol-table builder — symbol scopes for generic parameters.
5. the internal opcode header, the `opcode` standard-library module — new opcode definitions.
6. the `typing` standard-library module — `TypeVar`, `ParamSpec`, `TypeVarTuple` can be created from the new syntax; implement the `TypeAliasType` runtime class.
7. the type-params test module — exhaustive tests covering classes, functions, type aliases, protocols, bound/constraint variations.

## 5. Backward compatibility

- The existing `typing.TypeVar`/`Generic` syntax continues to work and remains the documented fallback.
- Bytecode compiled by older Pythons cannot use the new opcodes; use `sys.version_info` or try/except to guard.
- Runtime introspection (`typing.get_type_hints`, `inspect.get_annotations`) understands the new `__type_params__`.

## 6. Acceptance Criteria

- `class Box[T]` parses to a `ClassDef` whose `type_params` list contains one `TypeVar('T')`; `isinstance(Box.__type_params__[0], typing.TypeVar)` holds.
- `def identity[T](x: T) -> T: return x` compiles and its signature reports `identity.__type_params__` correctly.
- `type IntList = list[int]` evaluates lazily: the RHS is only evaluated when `IntList.__value__` is accessed.
- The full cpython test suite under the type-params test module, the typing test module, the grammar test module passes.
- The AST, bytecode and C-API changes match the reference implementation (PR #103764).
