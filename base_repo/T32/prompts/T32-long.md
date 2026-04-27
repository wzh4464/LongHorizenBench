# T32: OpenJDK / JEP 439 - Generational ZGC

## Requirement source

This task implements OpenJDK JEP 439 ("Generational ZGC"). All
behavioral requirements are sourced from the JEP itself
(https://openjdk.org/jeps/439). Implementations should match the JEP's
specified behavior; specific class layouts, file paths, and internal
identifiers are not specified by this prompt.

## Goal

Extend the Z Garbage Collector (ZGC) so that it manages the Java heap
as two generations — a young generation for newly allocated objects
and an old generation for objects that have survived enough young
collections — while preserving ZGC's existing properties (concurrent,
sub-millisecond pauses, scalable heap sizes).

## Goals (per the JEP)

- Reduce the risk of allocation stalls.
- Lower the required heap memory overhead.
- Lower the GC CPU overhead, especially for applications with the
  typical "weak generational" property where most objects die young.
- Continue to provide pause times that do not exceed one millisecond.
- Continue to support heap sizes up to many terabytes.
- Avoid introducing manual tuning: heap size and other parameters
  should not need different tuning values when the generational mode
  is enabled.
- Maintain the same source-language and platform support as
  non-generational ZGC.

## Non-goals (per the JEP)

- This is not an evolution of any non-ZGC collector (G1, Parallel,
  Serial, Shenandoah).
- Multi-generational (more than two generations) is not in scope.
- The user-visible API of ZGC must remain unchanged.

## Required behavior

- Generational ZGC must split the heap into a young and an old
  generation, with separate collection cycles for each generation.
- Young-generation collections concurrently identify and reclaim
  short-lived objects without stopping the application beyond the
  small pauses already characteristic of ZGC.
- A reference from an object in the old generation to an object in the
  young generation must be tracked (a remembered set / write-barrier
  mechanism) so the young-generation collector can find live objects
  reachable from the old generation without scanning the entire old
  generation.
- Survivors of repeated young collections are promoted (tenured) into
  the old generation. The implementation must define a promotion
  policy and adjust it to keep CPU and memory overhead reasonable.
- The full-heap collector must continue to support heaps from a few
  hundred megabytes up to multi-terabyte heaps with pause times in the
  sub-millisecond range, as in current ZGC.
- The new collector must coexist with non-generational ZGC during
  the transition. The user opts in to the generational mode via a
  command-line option (the JEP introduces `-XX:+ZGenerational`),
  defaulting to non-generational ZGC initially.

## User-facing requirements

- A new flag, `-XX:+ZGenerational`, enables Generational ZGC. Without
  it, ZGC continues to behave as the existing single-generation
  collector.
- All other ZGC options (heap size, concurrent threads, etc.)
  continue to apply.
- ZGC's external behavior (pause-time goals, heap usage reporting,
  GC log format) must remain compatible. Pause times must remain
  consistent with the existing ZGC promise (typically below 1 ms).
- ZGC's interaction with the rest of the JVM (JNI, JFR, JVMTI, etc.)
  must continue to work; in particular JFR must be able to report
  generational events.

## Acceptance criteria

- Running with `-XX:+UseZGC -XX:+ZGenerational` boots a working JVM
  whose ZGC operates as a two-generation collector.
- Allocation-heavy workloads where most objects die young show
  reduced CPU overhead and reduced allocation stalls compared to
  non-generational ZGC.
- Applications using large long-lived data sets continue to run
  without regressions in pause time or throughput.
- The existing ZGC test suite continues to pass; new tests verify
  that the generational behavior matches the JEP's stated invariants
  (young objects collected more frequently, old generation only
  scanned during major cycles, remembered set correctly tracking
  cross-generation references).
