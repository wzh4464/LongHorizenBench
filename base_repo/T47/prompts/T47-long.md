# T47: OpenJDK — JEP 514: Ahead-of-Time Cache Command-Line Ergonomics

## Requirement source

This task implements the user-visible behavior described by JEP 514
("Ahead-of-Time Command-Line Ergonomics"), which simplifies the
process of creating an AOT cache for the HotSpot JVM. The full text
of the JEP is at https://openjdk.org/jeps/514. The text below
paraphrases that JEP; do not introduce internal class names, file
paths, or behaviors that are not described there.

## Background

The AOT cache (introduced by JEP 483) is created in a separate
training run and then used in subsequent runs of the application.
Today this requires two distinct JVM invocations:

```
java -XX:AOTMode=record -XX:AOTConfiguration=app.aotconf -cp app.jar Main
java -XX:AOTMode=create -XX:AOTConfiguration=app.aotconf -XX:AOTCache=app.aot -cp app.jar
```

That is inconvenient and leaves a temporary configuration file that
the user has to manage. JEP 514 introduces a one-step workflow that
performs both the training run and the cache assembly in a single
invocation.

## Goals

- Allow a user to create an AOT cache with a single `java` invocation.
- Avoid requiring the user to manage the intermediate AOT configuration
  file.
- Preserve all the existing options and modes from JEP 483; this is
  syntactic sugar/ergonomics, not a new mechanism.

## Required behavior

The launcher must accept a new option that specifies an AOT cache
output path. When this option is given:

- The JVM runs the application normally as if in `record` mode (so that
  classes are loaded and observed during the run).
- When the application exits, the JVM internally drives the second
  ("create") phase using the data captured during the run, producing
  the AOT cache file at the path supplied to the new option.
- The intermediate configuration is managed by the JVM itself and is
  not surfaced to the user.

The behavior must be equivalent to running:

```
java -XX:AOTMode=record -XX:AOTConfiguration=<tmp>.aotconf ... <Main>
java -XX:AOTMode=create -XX:AOTConfiguration=<tmp>.aotconf -XX:AOTCache=<out>
```

but with the user only writing one command line.

## Compatibility / Non-goals

- The existing two-step workflow (`-XX:AOTMode=record` and
  `-XX:AOTMode=create`) must continue to work unchanged.
- The cache produced by the one-step workflow must be interchangeable
  with one produced by the two-step workflow given the same inputs.
- This JEP does not change what is stored in the cache, only how the
  user produces it.

## Acceptance

- A single invocation of the JVM with the new option produces a usable
  AOT cache that, when supplied via `-XX:AOTCache=` to a subsequent
  run, has the same effect as a cache produced by the two-step
  `record`/`create` workflow.
- The two-step workflow continues to work without changes.
- All existing AOT cache tests continue to pass.
- A failure during training (e.g., the application crashes) should
  cause the one-step invocation to leave a clear, well-defined state
  (no half-written cache, exit status reflects the failure).
