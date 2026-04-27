# T26: OpenJDK — JEP 483: Ahead-of-Time Class Loading & Linking

## Requirement source

JEP 483 ("Ahead-of-Time Class Loading & Linking"), https://openjdk.org/jeps/483.
The text below paraphrases the JEP. Implementations should match the JEP's
externally visible behaviour; internal layout, file naming, and helper class
structure are not constrained beyond what the JEP says.

## Goal

Extend HotSpot so that the application's classes can be loaded and linked
ahead of time (AOT) using a cache produced from a *training run*. With a
warm cache, subsequent JVM startups skip much of the per-run class-loading
and class-linking work, reducing time to first useful work.

The mechanism builds on the existing CDS / AppCDS infrastructure; the
JEP introduces a higher-level user-facing model and command-line surface
that hides the multi-step CDS workflow.

## Non-goals

- Caching arbitrary application state beyond loaded/linked classes.
- Caching classes from user-defined class loaders (initial scope is
  built-in and AppCDS-eligible classes only).
- Altering the JVM/JLS observable behaviour of an application; the AOT
  cache must be transparent to programs that load and link classes.

## Three-step user model

The JEP defines a simple two-step workflow that a user can drive with two
new command-line options:

1. **Training run.** The application is launched in `record` mode. The JVM
   observes which classes get loaded and linked and writes that information
   to an AOT *configuration* file:
   ```
   java -XX:AOTMode=record -XX:AOTConfiguration=app.aotconf -cp app.jar com.example.App
   ```
2. **Create the AOT cache** from the configuration:
   ```
   java -XX:AOTMode=create -XX:AOTConfiguration=app.aotconf -XX:AOTCache=app.aot \
        -cp app.jar com.example.App
   ```
3. **Production run.** Subsequent runs are launched with the cache. They
   skip the read/parse/load/link work for cached classes:
   ```
   java -XX:AOTCache=app.aot -cp app.jar com.example.App
   ```

## Required command-line surface

The feature is exposed through the following command-line options on the
`java` launcher:

- `-XX:AOTMode=<mode>` — selects the AOT mode. Valid values per the JEP:
  - `off` — disabled (default).
  - `record` — write the AOT configuration during this run.
  - `create` — assemble an AOT cache from the configuration.
  - `auto` — silently use a cache if available, otherwise behave as `off`.
  - `on` — use the cache; fail (or warn, depending on diagnostics) if it
    cannot be loaded.
- `-XX:AOTConfiguration=<file>` — path to the configuration file used in
  `record` and `create` modes.
- `-XX:AOTCache=<file>` — path to the AOT cache file used in subsequent
  runs.

These options replace the more verbose CDS workflow (`-XX:DumpLoadedClassList`,
`-Xshare:dump`, `-XX:SharedClassListFile`, etc.) for typical usage; the
underlying CDS machinery still supports the older flags but the JEP
introduces the AOT options as the user-facing API.

## Required behavior

- A training run started with `-XX:AOTMode=record -XX:AOTConfiguration=foo`
  records information about loaded classes into the configuration file.
  No AOT cache is produced in this step.
- A subsequent assembly run started with `-XX:AOTMode=create
  -XX:AOTConfiguration=foo -XX:AOTCache=app.aot` consumes the
  configuration and produces an AOT cache file. The application is not
  executed in this step.
- A production run with `-XX:AOTCache=app.aot` (no `AOTMode` argument)
  uses the cache to skip the load/link work for cached classes.
- The AOT cache must be produced from the same JDK build that consumes
  it; mismatches must be detected and rejected with a clear error.
- An invalid or missing cache must not crash the JVM; on failure, the
  JVM should fall back to running without the cache, optionally warning
  the user.
- Only classes that were loaded by the JDK's built-in class loaders
  (boot, platform, application) during the training run can be cached.
  Classes from user-defined class loaders are not cached.

## Compatibility constraints (from the JEP)

- Training and production runs must use the same JDK release, the same
  CPU architecture, and the same operating system family.
- Class paths and module configurations must match between training
  and production runs (the production class path may extend the
  training one).
- Some module options (`--add-opens`, `--add-exports`,
  `--add-modules`, etc.) must match.
- JVMTI agents that rewrite classes (e.g., via `ClassFileLoadHook`)
  may invalidate the cache; the JVM must detect such cases and fall
  back to the default just-in-time class loading and linking.

## Acceptance

- The new options `-XX:AOTMode={off,record,create,auto,on}`,
  `-XX:AOTConfiguration=<file>`, and `-XX:AOTCache=<file>` are
  recognized and behave as described.
- A training run followed by a create run produces a cache file that a
  subsequent production run can consume to skip class loading and
  linking for cached classes.
- The feature is opt-in; running without these options must produce
  the same observable behavior as today.
- Existing `-Xshare`/CDS options continue to work where they did before.
- Documented incompatibilities (different JDK build, mismatched class
  path, JVMTI class transforms, etc.) cause the JVM to disable the AOT
  cache with a clear diagnostic and fall back to ordinary class loading.
