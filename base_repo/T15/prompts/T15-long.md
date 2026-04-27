# T15 - OpenJDK: macOS/AArch64 Port (JEP 391)

*Upstream source:* https://openjdk.org/jeps/391 plus implementation PR https://github.com/openjdk/jdk/pull/5027. Full specification is inlined below so the implementing agent does not need internet access.

## 1. Motivation

Apple is transitioning its Mac hardware lineup from Intel x86_64 to the ARM-based Apple Silicon (AArch64). JEP 391 adds OpenJDK (HotSpot, class libraries, JDK tools, tests) support for the new `macosx-aarch64` platform so that:

- Java developers can build and run applications on Apple Silicon Macs natively without going through Rosetta 2.
- Benchmarks show AArch64 native builds are substantially faster (both CPU and I/O) than emulated x86_64 builds.
- The JDK remains a first-class citizen on Apple's platform.

Prior JEPs (237 "Linux/AArch64 Port", 388 "Windows/AArch64 Port") already introduced AArch64 code-generation and most of the VM internals. JEP 391 is about the *platform integration* of the existing AArch64 HotSpot on the Darwin/BSD OS family: signal handling, code signing, write-protected JIT pages (W^X), and Mach-O binary format.

## 2. Detailed Specification

### 2.1 Build / platform identifier

- `configure --with-native-platform=macosx-aarch64` must be supported end-to-end.
- The platform ID `os=darwin arch=aarch64` is exposed to build logic, tests and runtime.

### 2.2 Operating-system interface

Darwin imposes several distinctive requirements that the Linux/AArch64 port does not:

1. **W^X enforcement** — Apple Silicon requires a memory region to be writable *xor* executable at any given time. HotSpot must call `pthread_jit_write_protect_np()` before writing JIT output and switch the page to executable before running. All codegen paths (template interpreter, C1, C2, stubs, nmethod patching) must be audited to obey this invariant.
2. **`MAP_JIT` flag** — `mmap()` for JIT pages must include `MAP_JIT` so the kernel permits the RW<->RX toggles.
3. **Hardened runtime entitlements** — compiled binaries must ship with `com.apple.security.cs.allow-jit` and `com.apple.security.cs.allow-unsigned-executable-memory` entitlements and must be code-signed.
4. **Mach exceptions** — Darwin delivers native signals via the Mach exception mechanism before falling back to POSIX signals. The signal handler must co-operate with other debugger tools.
5. **Page sizes** — Apple Silicon Macs use 16 kB pages; the VM's page-aligned assumptions must be re-audited.

## 3. Assembler / interpreter

The `aarch64` HotSpot back-end (introduced for Linux/AArch64 in JDK 16) already covers most CPU codegen. JEP 391 reuses it but must fix three divergences:

1. **ABI** — Darwin AArch64 passes the first eight integer and floating-point arguments in registers like LP64 ELF, but passes variadic arguments on the stack (ELF keeps them in registers). JNI stubs must be adjusted.
2. **Stack guards and red zones** — Darwin reserves the top of the page for thread exceptions; the VM must enlarge its guard pages accordingly.
3. **Unwinder** — use `libunwind` keyed off the `__eh_frame` sections, not the Linux `.debug_frame` tables.

## 4. Build

`make configure --openjdk-target=aarch64-apple-darwin` must succeed. The build must produce a universal macOS DMG by combining the x86_64 and aarch64 outputs.

## 5. Implementation Items

1. Add the macOS/AArch64 HotSpot OS-CPU layer implementing thread context, signal handling, stack guards, page size queries, W^X memory protection toggles (`pthread_jit_write_protect_np`), and SP/FP register accessors.
2. Hook into HotSpot's build to recognise Apple Silicon and honour W^X during code generation.
3. Adjust code-patch routines to temporarily toggle write access via `pthread_jit_write_protect_np`.
4. Add universal binary support so the JDK can be code signed and notarised via Apple tooling.
5. Integrate with system JNI library search paths and the hardened runtime.

## 6. Acceptance Criteria

- The JDK compiles on an Apple Silicon Mac and produces a self-consistent image.
- `java -version` reports `aarch64` and runs on macOS 11+ natively.
- `jtreg tier1` and `tier2` HotSpot suites pass on macOS/aarch64.
- JIT compilation toggles write protection via the JIT write-protect APIs without causing segfaults under code patching.
- Existing macOS/x86_64 builds continue to pass their test suites (no regression).
