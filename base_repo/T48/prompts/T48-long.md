# T48 — Template literal types and key remapping in mapped types (TypeScript)

## Source

GitHub issue [microsoft/TypeScript#12754](https://github.com/microsoft/TypeScript/issues/12754) and the related design notes for template literal types and `as` clauses in mapped types.

## Background

TypeScript users have long requested a way to express types whose names are derived from other types — for instance, "for every property `K` of `T`, give me a getter named `get${K}`" — without resorting to runtime tricks or explicit per-property declarations.

Two related features address this:

1. **Template literal types** — string-literal types built from other string-literal types and embedded type expressions, much like JavaScript template literals at the value level.
2. **Key remapping in mapped types** — a mapped type may include an `as <NewKey>` clause that transforms each key during the mapping.

The two features compose: template literal types provide the building blocks for naming, and `as` clauses on mapped types provide the place to apply that naming.

---

## Template literal types

A template literal type has the form

```ts
type T = `prefix-${X}-suffix`
```

where `X` is a type. Behaviour:

- If `X` is a literal string type, the result is the literal string formed by substitution.
- If `X` is a union of literal strings, the result is the union of the substituted strings.
- If `X` is a generic parameter, the type is left unevaluated and assigned later.
- Numeric, bigint, and boolean literal types are coerced to their string representation when substituted.

Four intrinsic generic types are introduced for case manipulation on string literal types:

- `Uppercase<S>` — converts each character of `S` to upper case.
- `Lowercase<S>` — converts each character of `S` to lower case.
- `Capitalize<S>` — converts the first character of `S` to upper case.
- `Uncapitalize<S>` — converts the first character of `S` to lower case.

These behave as identities on generics that have not yet been substituted.

## Pattern inference on template literal types

When a template literal type appears in a position where TypeScript performs inference (e.g. a conditional type or a function-argument check), TypeScript can infer type parameters that occur inside the literal:

```ts
type ExtractName<T> = T extends `Hello, ${infer N}!` ? N : never
```

## Mapped-type `as` clause (key remapping)

A mapped type may now include an `as` clause that re-names the keys produced by the iteration:

```ts
type Getters<T> = {
  [K in keyof T as `get${Capitalize<string & K>}`]: () => T[K]
}
```

Semantics:

- The expression after `as` is evaluated as a type for each `K`. Its result becomes the new key.
- If the result is `never`, the key is dropped from the result type. This is how property filtering works.
- All other rules of mapped types (modifiers, distribution over unions, homomorphism) continue to apply unchanged.

## Built-in intrinsic helpers

Implementing template literal types adds four intrinsic types that operate on string-literal types: `Uppercase<S>`, `Lowercase<S>`, `Capitalize<S>`, `Uncapitalize<S>`. They behave as their names suggest at the type level.

---

## Implementation task

Modify the TypeScript compiler so that:

1. The parser accepts template literal type syntax and the `as` clause in mapped types.
2. The checker assigns the documented semantics: template literal types produce string-literal unions when their interpolations are themselves string-literal unions, are subtypes of `string`, and participate in inference via pattern matching on `infer`.
3. The four intrinsic helpers (`Uppercase`, `Lowercase`, `Capitalize`, `Uncapitalize`) are recognised by the checker.
4. Mapped types accept an `as` clause; when the clause evaluates to `never` for some key, that key is dropped from the resulting type.
5. The standard library type definitions are updated to expose the four intrinsic string-manipulation types.
6. Tests cover: template literal subtyping, mapped-type key remapping, the four intrinsic types, inference on template literal patterns, and interaction with existing features (conditional types, generics, distribution).

## Acceptance

- The new syntax parses, checks, and emits without regressions on the existing test suite.
- The four intrinsic string types behave as specified on string literal type inputs.
- Mapped types with `as` clauses correctly include or omit keys based on the clause result.
- Inference using `infer` inside a template literal type binds the inferred portion to the corresponding string literal slice.
