# T09: OpenJDK — JEP 423 Region Pinning for G1

## Requirement source

JEP 423 ("Region Pinning for G1") on https://openjdk.org/jeps/423 .
The text below paraphrases that specification; do not invent
implementation details that are not implied by it.

## Goals (from the JEP)

- Eliminate stalls of Java threads caused by JNI critical regions when
  G1 is in use.
- Implement region pinning in G1 so that JNI critical regions do not
  prevent the rest of the heap from being collected.
- Avoid regressions in throughput, latency, or memory footprint when no
  JNI critical region is active.

## Non-goals

- Region pinning for collectors other than G1.
- Changes to the JNI critical-region API itself.

## Background (paraphrased)

Java code may enter a JNI critical region via `GetPrimitiveArrayCritical`,
`GetStringCritical`, etc. While inside such a region, the JVM must keep
the underlying object at a fixed address until the matching `Release...`
call. Today, G1 deals with this by disabling garbage collection entirely
while any thread is inside a critical region (the so-called GC-locker).
This means a long critical region can stall every Java thread that
needs allocation and trigger out-of-memory errors even when most of the
heap is reclaimable.

Pinning, used by Shenandoah and ZGC, lets the collector run while the
critical regions are live: the regions containing pinned objects are
simply excluded from evacuation, but everything else is collected
normally.

## Goal of this task

Extend G1 so that JNI critical regions no longer rely on the GC-locker /
disable-GC mechanism. Instead, the regions that contain objects locked by
active JNI critical sections are pinned, the rest of the heap is
collected as usual, and only the pinned regions are skipped during
evacuation.

## Behavioural requirements

- Maintain a per-region count of how many objects in that region are
  currently the target of an active JNI critical section. Each
  `GetPrimitiveArrayCritical`/`GetStringCritical` (and equivalent)
  increments this counter on the region of the referenced object;
  the matching `Release*Critical` decrements it.
- A region whose count is greater than zero is "pinned". A pinned
  region must not be relocated, evacuated, or have its objects moved.
  Both young and old generation regions can become pinned.
- When a young collection or mixed collection encounters a pinned
  region, that region is left in place. For young collections this
  must still produce correct results: pinned young regions remain
  reachable as roots from the rest of the heap.
- Concurrent marking and old-generation reclamation continue to work
  on non-pinned regions while some regions are pinned.
- Once a region's pin count returns to zero it again becomes a
  candidate for the next collection (subject to the usual G1
  policies).
- The existing GC-locker-based path may remain as a fallback for full
  GCs that have to relocate every region (e.g., heap shrink or
  diagnostic full GCs), but normal young/mixed cycles must no longer
  block on JNI critical sections.

## Required behavior

- A Java thread entering a JNI critical region (via `GetPrimitiveArrayCritical`,
  `GetStringCritical`, etc.) does not block waiting for an in-progress
  garbage collection, and conversely, a garbage collection started while a
  thread is in a critical region is not stalled until that thread exits the
  region. Both can make progress concurrently.
- Pinned regions are correctly accounted for in heap-occupancy and
  eden/survivor sizing computations.
- Heap dumps, GC logs, and JFR/runtime monitoring should reflect that
  regions are pinned (region state visible in standard diagnostic output).
- The change is transparent to existing JNI applications: no API change,
  just better latency characteristics under JNI critical sections.

## Goals (verbatim, paraphrased from the JEP)

- Java threads should never have to wait for a G1 collection to finish
  because of JNI critical sections in other threads.
- G1 should be able to do GC while threads are inside JNI critical
  regions, by leaving the regions that contain critical objects in
  place rather than moving them.
- No regression in pause-time targets when no JNI critical region is
  active.
- No regression in steady-state throughput.

## Non-goals (from the JEP)

- This work targets G1 only. Other collectors (Parallel, Serial,
  Shenandoah, ZGC) are out of scope.
- It does not add new JNI APIs or change critical-region semantics
  visible to the application.

## Acceptance criteria

- Threads entering and leaving JNI critical regions no longer
  block GC, and GC threads no longer block on JNI critical
  regions.
- A young collection running while a JNI critical region is held in
  the young generation succeeds: the pinned young region(s) are
  excluded from evacuation and become "kept" (treated similarly to
  evacuation-failure regions); the remaining young regions are
  collected.
- A full GC running while a JNI critical region is held in the old
  generation succeeds: the pinned region is left untouched, and the
  remaining old regions are reclaimed/compacted as usual.
- Existing JNI critical-region semantics are preserved, including the
  rules around what is permitted inside a critical section.
- All existing G1 tests pass.
