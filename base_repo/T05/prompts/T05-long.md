# T05 — `__ptrauth` type qualifier (Clang)

## Requirement — self-contained specification

Reference: the LLVM RFC "RFC: pointer authentication, `__ptrauth` qualifier" on the LLVM Discourse, plus the Clang documentation page on Pointer Authentication. Both describe a user-facing language feature; nothing in the spec dictates a particular file layout in the compiler.

The repository is a snapshot of `llvm/llvm-project` from before the qualifier was implemented. Add the qualifier as a Clang language extension, wherever inside the Clang source tree is appropriate.

---

## 1. Motivation

ARMv8.3-A and later support Pointer Authentication Codes (PAC): a CPU can sign a pointer (mixing in a key and a 64-bit discriminator) and verify it on use. Apple's arm64e ABI, kernel hardening on Linux and XNU, and several language ABIs already use PAC instructions to harden indirect control flow and selected data pointers.

Clang already exposes the LLVM `ptrauth` intrinsics (`__builtin_ptrauth_sign`, `__builtin_ptrauth_auth`, etc.) and emits them automatically for vtables and a few ABI-mandated locations on arm64e. What is missing is a way for ordinary C/C++ source code to declare "this pointer is signed with the following schema" and have the compiler insert sign/auth/resign automatically at every load and store. That is what the `__ptrauth` qualifier provides.

---

## Qualifier syntax

```c
T * __ptrauth(key, address, discriminator) p;
```

- `key` — an integer constant expression naming an ABI key (the standard names `ptrauth_key_*` come from `<ptrauth.h>`).
- `address` — `0` or `1`. When `1`, the storage address of `p` is mixed into the discriminator (address diversity).
- `discriminator` — a 16-bit integer constant expression used as an extra discriminator.

`__ptrauth` is a type qualifier (sibling of `const`, `volatile`, `restrict`, address-space qualifiers). It attaches to the pointer being qualified, not to the pointee:

```c
int * __ptrauth(IA, 1, 42) p;   // p is a signed pointer to int
```

It can appear on:

- variables and fields of pointer type;
- pointer members of structs and unions;
- pointer-typed array elements;
- pointer typedefs (the qualifier propagates).

It does **not** apply to function-pointer call sites directly; it qualifies the storage that holds a function pointer.

## Semantics

- Reading from a `__ptrauth`-qualified lvalue produces the unsigned ("authenticated") pointer value. The compiler inserts an authentication check using the declared key and discriminator. On authentication failure the resulting value traps when dereferenced (per ARMv8.3 PAC semantics).
- Writing a value into a `__ptrauth`-qualified lvalue signs that value with the declared schema before storing.
- Copying between two `__ptrauth` lvalues with **identical** schemas is a direct memcpy of the already-signed bits — no resign needed.
- Copying between two `__ptrauth` lvalues with **different** schemas requires a resign (auth with the source schema, then sign with the destination schema). The compiler emits this automatically.
- Address-of a `__ptrauth`-qualified object yields a pointer to a `__ptrauth`-qualified type; the qualifier is part of the pointee type and propagates through pointer arithmetic exactly like `const`/`volatile`.

## Conversions and compatibility

- Two pointer types with `__ptrauth` qualifiers are compatible only if their schemas (key, address-discriminated bit, and integer discriminator) are identical.
- An unqualified pointer is **not** implicitly convertible to a `__ptrauth`-qualified pointer (and vice versa) — the conversion changes whether the bit pattern is signed, so it must be explicit (e.g. via a cast that triggers a resign).
- Casts between two `__ptrauth` pointer types with different schemas emit a resign sequence (auth under the source schema, sign under the destination schema).
- Implicit conversions that drop the qualifier (e.g. assigning to a plain `T*`) authenticate the value.

## Targets and ABI

The qualifier is supported on targets whose ABI defines pointer authentication (currently ARMv8.3-A AArch64 with the `pauth` feature). On other targets the qualifier is parsed but produces a diagnostic when sign/auth would actually be required.

## Tests

The change should ship with tests covering:

- parsing and printing of qualified types (single qualifier, on typedef, in template args);
- the diagnostic for an unsupported target;
- assignment / copy between identical schemas (no resign);
- assignment between different schemas (resign);
- assignment between qualified and unqualified pointer types;
- IR emission verifying that loads emit `llvm.ptrauth.auth` and stores emit `llvm.ptrauth.sign` with the schema's key and blended discriminator;
- C++ overloading: two functions differing only in `__ptrauth` schema are distinct overloads.

## 2. Implementation Task

Add the `__ptrauth` type qualifier to Clang:

1. Recognise `__ptrauth(key, address, discriminator)` in the type qualifier parser. It binds like `const`/`volatile` and attaches to a pointer type.
2. Represent the qualifier on the type (alongside other type qualifiers) so that it survives template instantiation, typedef stripping, and printing.
3. Enforce schema-equality rules in the type system: two `__ptrauth`-qualified pointer types are compatible only if all three schema components match.
4. At codegen time, emit an automatic auth+sign (resign) sequence when assigning between differently-qualified pointer types, and emit sign-on-store / auth-on-load for ordinary access through a qualified l-value.
5. Update the public driver/feature flags so the qualifier is rejected with a clear diagnostic on targets that do not support pointer authentication.

## Acceptance criteria

- `tools/clang -fsyntax-only` accepts `__ptrauth` declarations as described.
- Code generation produces the expected `llvm.ptrauth.*` intrinsic calls at every load/store/resign point.
- Cross-schema assignments without an explicit cast either resign automatically (when both sides are `__ptrauth`-qualified pointers) or are rejected with a diagnostic (when only one side is qualified and the other is a plain pointer).
- The qualifier is rejected with a clear diagnostic when the target does not support pointer authentication.
