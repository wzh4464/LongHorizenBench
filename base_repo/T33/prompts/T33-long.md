# T33: OpenJDK / JEP 500 — Prepare to Make `final` Mean Final

(Note: this task uses JEP 500 in the canonical CSV mapping. JEP 500
prepares the JDK to enforce immutability of `final` fields against
deep reflection, by introducing diagnostic flags and warnings that
will eventually become the default.)

## Requirement source

This task is sourced from JEP 500 ("Prepare to Make `final` Mean
Final"). All behavioural requirements are taken from that JEP. The
text of the JEP is summarized below; the agent must not invent
additional implementation details that are not in the JEP.

## Goals (per the JEP)

- Prepare the JDK and the Java ecosystem for a future change in which
  the `final` modifier on a field really does prevent that field
  from being mutated through deep reflection.
- Issue runtime warnings when deep reflection is used to mutate a
  `final` field, so that authors of libraries and applications can
  identify and remove such uses ahead of the future change.
- Provide a way for users and library authors to opt in to the new
  behaviour today, both for testing and for selectively suppressing
  warnings.
- Continue to allow Java serialization and other JDK-internal APIs
  that legitimately need to assign to `final` fields to do so without
  warnings.

## Non-goals (per the JEP)

- Removing the ability to mutate final fields entirely. That is for a
  later release.
- Changing `javac` or any source-level semantics.
- Changing the meaning of `final` in the Java language.
- Affecting normal Java code that does not use deep reflection,
  `Unsafe`, or JNI to write to final fields.

## What "deep reflection" means here

The mechanisms targeted by JEP 500 are those that bypass normal access
control to write to a `final` field:

- `java.lang.reflect.Field.setAccessible(true)` followed by `Field.set*`
- `java.lang.invoke.MethodHandles.Lookup.unreflectSetter` /
  `findSetter` etc. on a final field, used to obtain a write
  method-handle.
- `sun.misc.Unsafe` / `jdk.internal.misc.Unsafe` final-field writes.
- JNI `SetField` / `SetStaticField` family on a final field.

JEP 500 takes the position that all of these break the integrity that
the language is supposed to give `final` and so should be controlled.

## Required behaviour

The JDK introduces a new launcher option:

```
--enable-final-field-mutation=<modules>
```

with a paired option that controls whether mutation is implicitly
permitted (`ALL-UNNAMED` etc.) and a related JFR/JFR-style logging
mode. The exact set of values and the option name(s) follow the JEP:

- `--enable-final-field-mutation=ALL-UNNAMED` — opt every class loaded
  from the unnamed module (i.e., the classpath) into being allowed to
  mutate `final` fields without a warning.
- `--enable-final-field-mutation=<module>=<allow|deny>` (or the
  equivalent name used in JEP 500) — opt a specific named module in
  or out.
- A complementary `--illegal-final-field-mutation=<warn|deny|debug|allow>`
  control sets the default action when code that has not been
  explicitly enabled tries to mutate a `final` field (the JEP
  introduces this as the diagnostic / transition control).

The JEP also adds a JDK Flight Recorder event,
`jdk.FinalFieldMutation`, that records each mutation site so that
users can audit their applications.

## Behavior

1. Calling `Field.setAccessible(true)` followed by `Field.set(...)`
   on a `final` field, or any other deep-reflection or `Unsafe`-based
   path that writes a `final` instance/static field of a class loaded
   from a module/classpath that has not opted in, must raise a
   warning by default.
2. The warning identifies the field, the caller, and tells the user
   how to opt the caller's module in if the mutation is intentional.
3. With `--illegal-final-field-mutation=deny` (or equivalent),
   mutation through deep reflection on a final field throws an
   `IllegalAccessException` (for the reflective `Field.set` path) or
   the analogous error for `MethodHandle`-based writes.
4. Modules listed in `--enable-final-field-mutation=...` retain
   today's behaviour (mutation succeeds silently).
5. The JDK's own internal serialization machinery and the existing
   `--add-opens` / `--add-exports` rules continue to work; the
   restriction here is specifically about mutating `final` fields,
   not about reading or invoking them.

## Required behavior

- The new launcher option `--enable-final-field-mutation` and the
  related `--illegal-final-field-mutation` mode flag are recognized
  by the `java` launcher.
- When the JVM is started without opting in, a deep-reflection write
  to a `final` field of a non-record, non-hidden class results in
  the configured behaviour (warning by default; `deny` throws).
- The JFR event for final-field mutations is emitted whenever an
  illegal mutation is attempted, regardless of whether the JVM
  permits or rejects the mutation.
- Existing code that legitimately needs to mutate `final` fields
  (e.g. deserialization, mocking frameworks) can continue to work
  by passing the appropriate command-line option or configuring an
  opt-in via the manifest entry `Enable-Final-Field-Mutation: true`.

## Acceptance

- A program that uses `Field.setAccessible(true)` followed by
  `Field.set` on a non-record final field produces the expected
  diagnostic / exception according to `--illegal-final-field-mutation`.
- The same program, when run with
  `--enable-final-field-mutation=ALL-UNNAMED`, executes without a
  warning or exception (the legacy behavior).
- The JDK ships `jdk.FinalFieldMutation` JFR events so that recordings
  can identify offending code paths.
- Calls into `java.io.ObjectInputStream` and similar internal users
  of final-field writes continue to work because they are issued from
  code that is implicitly enabled for final field mutation.
- `MethodHandle`-based writes through `findSetter`/`Lookup` follow the
  same restrictions.
