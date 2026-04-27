# T39: OpenJDK JEP 425 — Virtual Threads (Preview)

## Requirement (inlined from JEP 425)

*Upstream source, for reference only:* https://openjdk.org/jeps/425

All information needed to complete this task is reproduced below. The agent must not fetch any external URL.

## Summary

Introduce virtual threads to the Java Platform. Virtual threads are lightweight threads that dramatically reduce the effort of writing, maintaining, and observing high-throughput concurrent applications. The familiar `java.lang.Thread` API is preserved; the JVM, the standard library, and the tools are extended so that a `Thread` can be one of two kinds:

* A **platform thread** — a traditional `Thread` bound to a single OS thread for its entire lifetime. This is the pre-JEP-425 behaviour.
* A **virtual thread** — a thread implemented by the JVM on top of a small pool of *carrier* platform threads. A virtual thread captures a carrier thread only while it is runnable; when it blocks on I/O or synchronisation, it unmounts and returns the carrier to the pool.

This preview feature makes the thread-per-request programming model viable for high-concurrency server workloads without sacrificing throughput.

*Upstream reference (do not fetch):* https://openjdk.org/jeps/425

## Motivation

Developers have long faced a choice between two concurrency styles on the JVM:

1. **Thread-per-task** — simple, debuggable, and natural with `InputStream`, `Thread.sleep`, blocking `Socket`, etc. but the platform thread is an expensive resource so the model does not scale past a few thousand concurrent tasks.
2. **Asynchronous / reactive** — scales to millions of operations but forces a different programming style (callbacks, `CompletableFuture`, reactive streams) and confuses debugging, profiling, and stack traces.

Virtual threads let synchronous, blocking code scale to millions of concurrent tasks. The JVM automatically parks a blocked virtual thread and reuses the carrier platform thread for another ready virtual thread.

## Key design points

### 3.1 Model

- `java.lang.Thread` gets a factory `Thread.ofVirtual()` and a direct helper `Thread.startVirtualThread(Runnable)`.
- `Executors.newVirtualThreadPerTaskExecutor()` creates an executor that starts a new virtual thread for each submitted task.
- Virtual threads are **daemon** by default, cannot be placed in thread groups (they all belong to the placeholder `VirtualThreads` group), and ignore `setPriority`.

### Scheduler

A virtual thread's carrier is a platform thread managed by a default `ForkJoinPool`-based scheduler. When a virtual thread blocks on a supported operation (I/O, `Thread.sleep`, `LockSupport.park`, `Object.wait`, `ReentrantLock`, etc.) it *unmounts* from its carrier, freeing it for another virtual thread. The scheduler later *mounts* the resumed virtual thread onto any free carrier. This transition is invisible to the programmer.

### 3.3 Continuations

Internally, virtual threads rely on `jdk.internal.vm.Continuation` and the HotSpot machinery for stack freezing/thawing. The VM manipulates the stack in chunks (`StackChunk`) stored on the Java heap, so context switches are cheap.

### 3.4 I/O integration

The following JDK facilities are aware of virtual-thread unmounting so they do not pin the carrier:

- `java.net.Socket`, `ServerSocket`, `DatagramSocket`
- `java.nio.channels.*`
- `java.io.Reader`, `Writer`, `PipedInputStream`, `PipedOutputStream`
- `java.util.concurrent.locks.*` and `synchronized` (only when no native frame is on stack)
- `Thread.sleep`, `Thread.join`
- `Object.wait`, `notify`

When a virtual thread is blocked on a monitor held by another thread, or on native code, or on a `synchronized` block containing a blocking call, the carrier thread is "pinned" and cannot be reused. Diagnostics (`-Djdk.tracePinnedThreads=short|full`) must be available to flag these situations.

### 3.2 New Java API surface

```
java.lang.Thread.Builder             // fluent builder, base of OfPlatform / OfVirtual
java.lang.Thread.Builder.OfPlatform  // for platform threads
java.lang.Thread.Builder.OfVirtual   // for virtual threads
java.lang.Thread.startVirtualThread(Runnable)
java.lang.Thread.ofVirtual() / ofPlatform()
java.lang.Thread.isVirtual()
java.util.concurrent.Executors.newVirtualThreadPerTaskExecutor()
java.util.concurrent.ThreadFactory.virtualThreadFactory()
```

`Thread.Builder` must be a `static interface` on `Thread`. `OfVirtual.factory()` returns a `ThreadFactory` that spawns a new unstarted virtual thread on each `newThread(...)`.

### Supporting JVM changes

1. **Continuation support** — enhance `jdk.internal.vm.Continuation` with new native entry points `enter0`, `doYield`, `pin`, `unpin`; add the HotSpot `zBarrier` and `objectMonitor` cooperation to avoid pinning.
2. **Stack chunking** — allocate continuations on the Java heap as `StackChunk` objects; integrate with ZGC, G1, and Parallel GC barriers so chunks can be traced and relocated.
3. **ForkJoinPool carrier pool** — `java.util.concurrent.ForkJoinPool` adds a method `commonPool().forkJoinWorkerThreadFactory()` variant that labels its workers as `CarrierThread` for JFR events and thread dumps.
4. **JFR / jcmd** — `jcmd Thread.dump_to_file -format=json` includes virtual threads. `-format=plain` prints them interleaved with carrier threads.

### Library-level API

```
java.lang.Thread.ofVirtual()                      // factory
java.lang.Thread.startVirtualThread(Runnable r)   // convenience
java.lang.Thread.Builder.OfVirtual#name(String)
java.lang.Thread.Builder.OfVirtual#factory()
java.util.concurrent.Executors#newVirtualThreadPerTaskExecutor()
java.util.concurrent.StructuredTaskScope         // accompanying preview
```

### Observability

- `Thread.isVirtual()` must return `true` for threads created through any virtual-thread API.
- `ThreadGroup.list()` on the virtual-threads group returns an empty enumeration (virtual threads are not enumerated).
- JFR events `jdk.VirtualThreadStart`, `jdk.VirtualThreadEnd`, `jdk.VirtualThreadPinned`, `jdk.VirtualThreadSubmitFailed`.

## Implementation Scope

1. **`java.base`**
   - Add `java.lang.VirtualThread` (package-private) in the `java.lang` package.
   - Extend `java.lang.Thread` with virtual-thread factory methods.
   - Introduce `jdk.internal.vm.Continuation`, `ContinuationScope`.
   - Add `ThreadContainer`, `ThreadContainers` for structured grouping.
   - Plumb `Executors.newVirtualThreadPerTaskExecutor()` and `Executors.newThreadPerTaskExecutor(...)` variants.

2. **HotSpot**
   - Implement `Continuation_JvmtiOps`, `StackChunkOop`, `StackChunkKlass`.
   - Update GC barriers (G1, Parallel, Serial, Z) to understand stack chunks.
   - Add `JvmtiExt::set_thread_carrier()` / notifications.
   - Update `Thread::current()` and thread-local handshakes.

3. **JDK tools / diagnostics**
   - Extend `jcmd Thread.dump` with `-format=json` and `-virtual` filters.
   - Add `-Djdk.tracePinnedThreads=short|full` command-line option.
   - Add `jdk.JfrHub::threadStart` event so that flight-recorder captures virtual threads.

4. **Preview flag**

Virtual threads are introduced as a preview feature: `--enable-preview` must be passed at both compile- and run-time; `java --version` must print `VirtualThreads (preview)` when listing enabled previews.

## Acceptance

- `try (var exec = Executors.newVirtualThreadPerTaskExecutor())` successfully runs 10 million short tasks on a laptop without exhausting the heap.
- The JDK virtual-thread test suite under the standard JDK test tree passes.
- `Thread.ofVirtual().start(r)`, `Thread.ofVirtual().unstarted(r).start()`, and `Thread.ofVirtual().factory().newThread(r)` all return virtual threads.
- `Thread.currentThread().isVirtual()` reports `true` when called from a virtual thread.
- `jcmd <pid> Thread.print` lists both platform and virtual threads, marking virtual ones.

## Out of scope

- Removing carrier-thread pinning on every blocking syscall (a follow-up JEP, handled later).
- Structured concurrency (`StructuredTaskScope`) — separate preview JEP.
- ForkJoinPool integration other than using it as the default carrier scheduler.
