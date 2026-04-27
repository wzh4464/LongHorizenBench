# T25: CPython — PEP 798 Unpacking in Comprehensions

## Summary

PEP 798 "Unpacking in Comprehensions" extends comprehension and generator
syntax so that iterable and mapping unpacking (`*` and `**`) may appear in
the element position. The proposal mirrors the existing unpacking allowed in
list, set, and dict displays.

After this change the following expressions are valid:

```
[*it for it in lists]              # list comprehension flattening
{*s for s in sets}                 # set comprehension union
(*it for it in iterables)          # generator expression flattening
{**d for d in dicts}               # dict comprehension merging
```

The reference for this task is PEP 798. Do not access the network — the
information needed is captured below.

## 1. Motivation

Comprehensions are one of the most-used Python constructs, but they only
allow a single scalar element per iteration. Common patterns such as
"flatten a list of lists" or "merge a sequence of dictionaries" require
falling back to nested comprehensions, `itertools.chain.from_iterable`, or
explicit loops. The PEP argues these idioms are common enough that
unpacking them with `*` and `**` inside comprehensions parallels the
already-supported unpacking inside list/set/dict displays.

## 2. New syntax

The new forms are:

```
[ *iterable_expr  for ... ]             # list comprehension
{ *iterable_expr  for ... }             # set comprehension
{ **mapping_expr   for ... }            # dict comprehension
( *iterable_expr  for ... )             # generator expression
```

Inside a comprehension element:

- A single starred expression `*EXPR` produces zero or more elements per
  iteration; `EXPR` must be iterable at runtime.
- For dict comprehensions, `**EXPR` produces zero or more `key: value`
  pairs; `EXPR` must be a mapping.
- Mixing starred and non-starred elements is allowed in the *element*
  position only (not in target lists), e.g. `[a, *bs, c for ...]`.

The unpacking semantics are the same as in displays (`[*a, *b]`,
`{**a, **b}`).

## 3. Semantics

For list/set/tuple/generator comprehensions, the element `*EXPR` is
equivalent to extending the result with `iter(EXPR)`. For dict
comprehensions, `**EXPR` merges `EXPR` into the result. For sets, duplicate
elements collapse as usual.

Asynchronous comprehensions (`async def` scope) preserve the same semantics:

```python
[x async for it in aiter() async for x in it]   # already legal
[*it async for it in aiter()]                    # new, equivalent
```

## Behavioural notes

- `*expr` is only allowed at the element position of a list, set, generator
  or tuple comprehension. It is a `SyntaxError` anywhere else (e.g.
  `[*x, y for ...]`).
- `**expr` is only allowed at the element position of a dict comprehension.
- Existing semantics of generator expressions (lazy evaluation, single-use)
  are preserved. The starred form yields each unpacked element one at a
  time.
- Star-unpacking interacts with `if` filter clauses normally: the filter
  applies per outer iteration, not per inner element.
- Comprehensions that need to materialise nested iterables in a `**`
  context must follow the standard mapping protocol.

## Implementation scope

The implementation must:

1. Extend the grammar of comprehensions to allow `*expr` (and `**expr` for
   dicts) at the element position, while keeping the existing rejection of
   bad combinations (`*` outside element position, mixing types, etc.).
2. Generate appropriate bytecode that iterates over each unpack target and
   appends/extends the accumulator. The bytecode shape should match the
   existing handling of `*`/`**` in display syntax.
3. Reject syntactically invalid combinations with clear `SyntaxError`
   messages (e.g. `**` in a list comprehension, double-stars in generator
   expression, mismatched containers).
4. Update `ast` so that the new element types are representable and
   round-trippable through `ast.parse` / `ast.unparse`.
5. Add tests for comprehensions, generator expressions, async comprehensions,
   and assignment targets, plus error cases.

## Acceptance criteria

- All four comprehension flavours (list, set, dict, generator) accept star
  unpacking targets per the description above.
- Existing comprehension behaviour without unpacking is unchanged.
- The standard `test_grammar`, `test_compile`, `test_ast`, and the new
  comprehension test additions all pass.
- `ast.unparse(ast.parse(src))` round-trips comprehensions that use the new
  syntax.
- Error cases produce informative `SyntaxError` messages.
