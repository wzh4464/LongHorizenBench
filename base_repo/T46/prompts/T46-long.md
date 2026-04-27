# T46: OpenJDK — JEP 493: Linking Run-Time Images without JMODs

## Requirement source

JEP 493, "Linking Run-Time Images without JMODs"
(https://openjdk.org/jeps/493). Behaviour and naming below come from
that JEP. Internal class layout and file layout are not constrained
beyond what the JEP says.

## Goal

Allow `jlink` to produce a custom run-time image without needing a
separate set of JMOD files distributed with the JDK. Currently, `jlink`
needs the `jmods/` directory on the running JDK to resolve
`java.base` and other modules. This means JDK distributors who want
`jlink` to work must ship JMODs alongside the runtime, which roughly
doubles the on-disk footprint.

JEP 493 makes it possible to build a JDK whose `jlink` tool can use
modules from the *current run-time image itself* — i.e., the JDK that
is running `jlink`. Distributors who opt in can then ship a smaller
JDK that does not contain JMOD files. This task is to implement that
capability behind a build-time switch.

## Goals

- A new build configuration option (call it `--enable-linkable-runtime`)
  produces a JDK whose `jlink` can link applications using only the
  contents of the running JDK's run-time image (no JMODs required).
- When the option is not used, `jlink` continues to operate exactly as
  it does today; a JDK that ships JMODs continues to use them.
- The user-visible `jlink` command and its options remain unchanged.
  Existing build pipelines do not need updating.

## Non-goals

- Changing the format or layout of `jmod` files for users.
- Removing JMOD files from the OpenJDK distribution by default. The
  JEP only enables linking *without* JMODs; whether a particular
  distributor ships them remains their choice.
- Support for cross-OS or cross-arch linking using the new mode is not
  added (cross linking requires JMODs as today).

## Required behavior

- When configured with the new build flag, a built JDK contains
  enough metadata in its run-time image for `jlink` to materialize
  any module that the runtime ships, including `java.base`.
- When `jlink` is invoked in such a JDK and no `jmods/` directory is
  present, it consults the run-time image to obtain module content
  and produces a linked image equivalent to one created from JMOD files.
- When the JDK is built without the new option, `jlink` still requires
  the JMOD files on the module path as today, and the build is
  bit-for-bit unchanged.
- `jlink` reports a useful error when neither a JMOD file nor a
  linkable run-time image is available for a module being requested.

## Required behavior — error/edge cases

- Cross-platform linking is unchanged: `jlink` continues to require a
  matching run-time image / JMOD set for the target platform.
- The presence of class-file or resource patches in the running runtime
  (e.g., agents, system property overrides) does not corrupt the linked
  image; the linker reads from the same canonical sources used at
  build time.
- A linked image produced from a run-time image is functionally
  equivalent to one produced from JMOD files; in particular the same
  command-line options to `jlink` (such as `--add-modules`,
  `--launcher`, `--strip-debug`, `--compress`, etc.) work identically.

## Out of scope

- Removing JMOD files from JDK builds by default. That is a separate
  decision left to distributions.
- Changes to module declarations or to `jmod`. The new mode is at the
  `jlink` layer.
- Supporting third-party module formats.

## Acceptance

- A JDK build configured for the new mode (per the JEP) supports
  `jlink` runs that produce custom runtime images without requiring
  JMOD files on the module path.
- A JDK built without the option produces an image whose `jlink`
  behaves identically to a current release.
- All existing `jlink` tests pass; new tests cover the runtime-image
  source path, including error reporting when the source data is
  missing.
