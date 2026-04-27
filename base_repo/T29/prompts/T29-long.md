# T29: OpenJDK — JEP 516: Ahead-of-Time Object Caching for Any GC

## Requirement source

JEP 516 ("Ahead-of-Time Object Caching for Any GC"),
https://openjdk.org/jeps/516. The text below paraphrases the JEP. The
implementation should match the behavior described in the JEP; do not
hard-code internal class or file names beyond what the JEP explicitly
says.

## Goal

Extend the AOT cache (introduced by JEP 483, "Ahead-of-Time Class Loading
& Linking") so that the cached Java objects can be used by any HotSpot
garbage collector, including ZGC. Today the AOT cache stores objects in a
GC-specific format and is therefore unusable with ZGC, which has its own
representation of object references. The change introduces a neutral,
GC-independent format and a sequential ("streamed") loading mode so that
ZGC and other collectors can consume the same cache.

## Goals (per the JEP)

- Make the AOT object cache usable with all HotSpot collectors,
  including ZGC. AOT class loading and linking is no longer restricted to
  serial/parallel/G1.
- Decouple the AOT cache from any single GC's object reference encoding.
- Preserve the start-up benefit of JEP 483 to the extent reasonable; the
  new mechanism should approach the existing speed-up.
- Allow the JVM to ship with built-in AOT cache content for the JDK that
  any supported GC can read.

## Non-goals

- Replacing the existing GC-specific (mapped) caching path entirely.
  The mapped path remains as an option for the configurations where it
  works best.
- Caching arbitrary user objects beyond what AOT cache already handles.

## Background

JEP 483 caches a snapshot of loaded classes and a small set of
associated heap objects (interned strings, the `Class` mirrors, etc.).
That snapshot is mapped directly into the Java heap by the running GC.
Object references in the snapshot are encoded using the running GC's
pointer representation (compressed OOPs, etc.). This approach works for
collectors that share a pointer/heap layout but is incompatible with
ZGC, which has a fundamentally different reference representation. As a
result, the existing AOT cache cannot be combined with ZGC.

## Required behavior

- A new GC-agnostic object encoding for the AOT cache is added.
  Object references in the cached snapshot are stored as indices or
  identifiers that are independent of the running GC.
- At cache load time, the JVM reads cached objects sequentially and
  materializes them by allocating in the running collector's heap and
  fixing up references. Because allocation and fix-up happen at runtime,
  any GC that supports normal Java object allocation can host the
  cache.
- ZGC must be able to use AOT caches produced under this scheme.
- Existing collectors (Serial, Parallel, G1) must keep working. They
  may continue to use the mapped path or use the streamed path; both
  are supported.
- The user-visible command-line surface introduced by JEP 483
  (`-XX:AOTMode`, `-XX:AOTConfiguration`, `-XX:AOTCache`) is unchanged.
- Choice between mapped and streamed object loading is automatic. The
  JEP describes a heuristic: by default the cache is created in a form
  that can be streamed; collectors that support direct mapping may opt
  in to map it instead.

## Non-goals (from the JEP)

- This JEP does not change the AOT cache user interface, classes, or
  contents beyond what is required for the new format.
- It does not introduce new tuning knobs that users have to set in
  normal use.

## Acceptance criteria

- Running with ZGC (or any GC that previously could not use the AOT
  cache) and loading a cache produced by another GC works and yields
  the documented startup-time benefit. Running with a mapping-capable
  GC (e.g., G1) on a cache also continues to work.
- A cache produced on one supported GC is loadable by every supported
  GC.
- Existing AOT cache tests continue to pass.
- No regression in startup time for collectors that previously
  supported the AOT cache.
- ZGC + AOT cache produces a measurable startup-time improvement over
  ZGC without an AOT cache.
