# Implement PEP 750 Template Strings (`t-strings`) in CPython

## Summary

PEP 750 introduces template strings, a new kind of string literal prefixed
with `t` (lower- or upper-case). A `t"..."` expression evaluates to a
`Template` object containing both the literal text segments and the
interpolation expressions (with optional `!conversion` and
`:format_spec`). Unlike f-strings, template strings do **not** eagerly
build a single `str`; the user receives a structured value that can be
inspected, transformed, and rendered safely (HTML escaping, SQL parameter
binding, log redaction, etc.).

The required runtime API is exposed under `string.templatelib` and adds
`Template`, `Interpolation`, and a small set of helpers, plus accompanying
grammar / compiler / opcode / typing / pickling / docs work.

## 2. Public Python API

Module `string.templatelib`:

- `class Template`
  - `strings: tuple[str, ...]` — the literal text fragments, length `n+1`
    for `n` interpolations.
  - `interpolations: tuple[Interpolation, ...]` — the interpolations.
  - `values: tuple[Any, ...]` — convenience tuple of the evaluated
    interpolation values (same length as `interpolations`).
  - Iteration yields literal `str` and `Interpolation` items in the order
    they appear.
  - Pickleable; equality compares structurally.

- `class Interpolation`:
  - Attributes: `value`, `expression: str`, `conversion: str | None`,
    `format_spec: str | None`.
  - Constructed by the compiler for each interpolated `{expr}` slot.

- Helper / iteration:
  - `Template.__iter__` yields the alternating sequence of literal strings
    and `Interpolation` instances.

The PEP also adds a tiny pure-Python helper `string.templatelib.t` that
constructs a `Template` from raw parts (used internally by the compiler).

## Lexer / Parser

Template strings reuse the f-string token machinery:

- A new prefix `t"…"` (and `T"…"`) selects a template string. Combinations
  with `r` (`rt"…"`, `tr"…"`) are accepted; `b` (bytes) is not.
- Inside the literal, `{expr}` interpolations behave exactly as in
  f-strings, including `!s/!r/!a` conversions and `:format_spec` (which may
  itself contain interpolations).
- Doubled braces `{{` and `}}` produce literal braces.

A new AST node `TemplateStr` is introduced. Each `TemplateStr` carries the
parsed sequence of `Constant` (literal `str`) and `Interpolation` nodes.

## 3. Compiler / bytecode

A `t"…"` literal compiles to:

1. Build the literal string parts.
2. For each interpolation, evaluate the expression; if a conversion or
   format spec is present, evaluate them too.
3. Emit a new opcode `BUILD_TEMPLATE` which constructs the
   `string.templatelib.Template` from a tuple of strings, a tuple of
   interpolations, and the interpolation values.

The compiler must generate `BUILD_INTERPOLATION` to build each
`Interpolation` instance and `BUILD_TEMPLATE` to assemble the final
`Template`.

The opcodes `BUILD_TEMPLATE` and `BUILD_INTERPOLATION` are added to the
opcode table.

## 4. Library surface

`string.templatelib.Template` is a sequence-like value carrying:

- `args` — flat tuple alternating string segments and `Interpolation`
  values.
- `strings` — convenience tuple of the literal segments only.
- `values` — convenience tuple of `Interpolation.value` for each
  interpolation.
- `interpolations` — tuple of `Interpolation` instances (no literals).

`Interpolation`:

- `value`
- `expression: str` — the source code of the substitution expression
- `conversion: str | None` — one of `"s"`, `"r"`, `"a"`, or `None`
- `format_spec: str` — the (already-formatted) format specifier text

Both classes are immutable and hashable; `Template` is iterable and
indexable like a tuple.

## 5. Concrete deliverables

- Grammar entries to recognise `t"..."` literals, including the same
  prefix rules as `f"..."` (case-insensitive `t`, allowed combination with
  `r`, `b` is forbidden).
- Tokenizer support producing the equivalent of `FSTRING_START`,
  `FSTRING_MIDDLE`, `FSTRING_END` tokens for the new prefix.
- Compiler support emitting the new opcodes.
- Bytecode interpreter changes implementing `BUILD_INTERPOLATION` and
  `BUILD_TEMPLATE`.
- A new `string.templatelib` module with `Template` and `Interpolation`
  exposed publicly.
- AST nodes (`TemplateStr`, `Interpolation`) with `unparse` round-tripping.
- Tests covering the new tokens, AST round-trip, opcode behaviour,
  `Template` construction, indexing, iteration, and concatenation, plus the
  forbidden prefix combinations.
- Documentation updates for the language reference and for the new
  `string.templatelib` module.

## Acceptance criteria

- `t"hello"` returns a `Template` with no interpolations.
- `t"hello {name}"` returns a `Template` with one interpolation whose value
  matches `name`.
- `Template + str`, `str + Template`, and `Template + Template` are all
  defined and produce a `Template`.
- `Template` round-trips through `ast.parse(...)` / `ast.unparse(...)`.
- The new `Template` and `Interpolation` types pickle correctly.
- The PEP's published examples work without modification.
