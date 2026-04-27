# T11 — Decorator Metadata

## Source proposal

TC39 proposal: "Decorator Metadata" (https://github.com/tc39/proposal-decorator-metadata).
The proposal extends the Stage 3 "Decorators" proposal with a way for decorators to store and observe metadata on the class they decorate.

The summary below is taken faithfully from the proposal README; nothing about the host implementation (compiler, parser, emit code, file layout) is dictated by the proposal.

---

## 1. Motivation

Decorators frequently need to record information about a class, method, field, or accessor that other parts of a program will read back later. Common examples are dependency injection frameworks, ORM bindings, validation libraries, and serialization libraries. Without a built-in metadata channel, every framework invents its own (e.g. a side-table keyed on the class), which is fragile and incompatible across libraries.

The decorator metadata proposal therefore extends the decorators proposal with an officially blessed metadata channel that is accessible:

- to every decorator while it runs (via the `context` argument); and
- to user code at runtime (via a well-known symbol on the class).

## 2. The `context.metadata` property

Every decorator receives a `context` object as its second argument. That object is extended with a new `metadata` property:

```js
function dec(value, context) {
  // context.metadata is a fresh object the first time a decorator on this class
  // runs; the same object is shared by every decorator applied to the class
  // and to its members.
  context.metadata.someKey = "some value";
}
```

Properties of `context.metadata`:

- It is a plain object.
- It is **the same object** for every decorator applied to one class declaration (class itself, its methods, fields, accessors, and getters/setters).
- Its prototype chain is the metadata object of the parent class, if any. If the class has no decorated parent, the prototype is `null`.
- It is created lazily — the first decorator that runs for a class triggers its creation.

## 3. The `Symbol.metadata` slot on the class

After a class is decorated, its accumulated `metadata` object is exposed under a well-known symbol:

```js
@dec
class C {}

C[Symbol.metadata] // the metadata object
```

If no decorators on the class (or on any of its members) run, `C[Symbol.metadata]` is not set. Inheritance follows the normal prototype chain of the constructor: a subclass that adds nothing inherits its parent's metadata via the prototype.

## 4. Inheritance semantics

```js
@parentDec
class P {}

@childDec
class C extends P {}

Object.getPrototypeOf(C[Symbol.metadata]) === P[Symbol.metadata]
```

A decorator on `C` can read everything the parent's decorators wrote (via the prototype chain), and can override entries by writing to `context.metadata` directly.

## Implementation

You are working in a TypeScript compiler repository that already implements TC39 stage-3 decorators. Add support for decorator metadata so that:

1. Each decorator's `context` argument has a `metadata` property — a plain object shared by every decorator on the same class.
2. After all decorators on a class have run, the class is given a `[Symbol.metadata]` slot pointing at that same object.
3. The prototype-chain-based inheritance semantics described above are honoured: when a class extends another decorated class, its metadata object's prototype is the parent class's metadata object.
4. Update the public type declarations (`lib.*.d.ts`) so that the decorator-context interfaces expose `metadata`, and the global `SymbolConstructor` exposes `metadata`.
5. Add tests that demonstrate metadata sharing among co-applied decorators, prototype inheritance, and `Symbol.metadata` exposure on the class.

## Acceptance criteria

- `tsc` compiles a decorated class targeting `esnext` and emits code that, at runtime, exposes `Class[Symbol.metadata]` and gives every decorator's `context.metadata` a reference to the same object.
- The metadata object of a subclass has the parent's metadata object as its `[[Prototype]]`.
- The compiler's existing decorator tests continue to pass.
- New tests cover the metadata behaviour described above.

## Out of scope

- The proposal does not specify how a host (e.g. TypeScript) chooses to store metadata when targeting environments that lack `Symbol.metadata`. Any reasonable polyfill or downlevel emit strategy is acceptable as long as observable semantics match the proposal.
