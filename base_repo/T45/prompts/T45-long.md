# T45: OpenJDK - JEP 388 (Windows/AArch64 Port)

## Requirement (inlined)

*Source:* OpenJDK JEP 388 "Windows/AArch64 Port". This file reproduces the self-contained requirements; the agent does not need to fetch the spec.

### Summary

Port the JDK to Windows/AArch64. Although porting work itself is not technically difficult, the build, test, and infrastructure work to integrate is significant.

### Goals

Provide a working AArch64 build of the JDK on Windows. Reuse the existing AArch64 codepaths (already used by Linux/AArch64) to the extent possible.

### Non-Goals

- This JEP does NOT introduce any new public Java APIs.
- This JEP does not change the Windows ABI rules: the Windows on ARM64 ABI as defined by Microsoft must be followed.

### Motivation

Windows on ARM has shipped a consumer-grade developer device (Windows on ARM laptops). Running the JDK on these devices currently requires the x86 emulation layer, which is slower and has higher memory pressure than a native port. A native Windows/AArch64 port lets Java applications run efficiently on these machines.

### Description

This is primarily a porting effort. The bulk of the work covers:

1. **Build system** — recognise the new platform triple in the JDK build configuration, select the right toolchain on Windows hosts.
2. **HotSpot assembler / runtime** — most of the AArch64 codegen is shared with the Linux/AArch64 port; new platform-specific files cover the Windows-on-ARM64 ABI details (calling convention shape, register preservation, stack frame layout / unwind metadata, structured exception handling integration, TLS access).
3. **Native libraries** — adjust JNI interface and native libraries (`libjli`, `libjvm`, `libjava`, `libnio`, etc.) so that AArch64 + Windows is a valid build target.
4. **Tests / CI** — extend the test infrastructure so Windows/AArch64 is in the matrix.

Key technical items explicitly called out:

- Follow the Microsoft Windows-on-ARM64 ABI exactly: parameter passing in `x0..x7`, `v0..v7`; integer return in `x0`/`x1`; floating return in `v0`/`v1`; callee-saved/caller-saved register split per the ABI.
- Frame-pointer chain must be set up so that Windows-specific stack unwinding, structured exception handling, and debugger walks succeed.
- JIT-emitted code must publish unwind data via `RtlAddFunctionTable` / equivalent so that Windows can unwind through generated frames.
- Reuse Linux/AArch64 macro assembler logic where possible; only the OS layer should diverge.

### Implementation plan

1. **Build / triplet plumbing.** Add the Windows/AArch64 triplet through the JDK build system. Cross-compilation from x64 Windows must produce a working `bin/java.exe`.
2. **Serviceability.** Add Windows/AArch64-specific code paths covering thread, OS, and CPU support; reuse the Linux/AArch64 versions as a template and replace POSIX-only calls (`mmap`, `pthread`) with their Windows equivalents (`VirtualAlloc`, Win32 thread API).
3. **Code generation.** Adjust the macro assembler ABI helpers (argument passing, prologue/epilogue, register-preservation masks) for the Windows AArch64 ABI; leave the bulk of the AArch64 instruction emission unchanged.
4. **Native libraries.** Update build files so each native library compiles for the new triplet. Update HotSpot stubs that hard-code Linux/x64 system calls.
5. **Testing.** Run `tier1`+`tier2` jtreg suites on a Windows-on-ARM64 host; CI lanes are added.

## Acceptance Criteria

- `configure --openjdk-target=aarch64-unknown-microsoft-windows && make images` produces a working JDK image on Windows on AArch64.
- HotSpot jtreg `tier1` passes on Windows/AArch64.
- `java -version` reports `aarch64` on Windows on ARM hardware.
- An existing AArch64 port (Linux or macOS) and an existing Windows port (x64) both continue to build and pass `tier1`.