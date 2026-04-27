# T16: OpenJDK - Linux/RISC-V Port (JEP 422)

*Upstream reference:* https://openjdk.org/jeps/422 (Linux/RISC-V port). The full specification is inlined below so the agent has no reason to access the internet.

## 1. Motivation

RISC-V is an open, royalty-free RISC instruction set architecture that is quickly gaining traction in embedded, HPC, and cloud workloads. Pre-JDK-19 OpenJDK had community-maintained downstream RISC-V support but no upstream port. JEP 422 upstreams the port so that OpenJDK officially supports `linux-riscv64` as a Tier-3 platform.

Without this JEP, RISC-V adopters have to maintain forks, which drift and accumulate technical debt. With the JEP, Linux/RISC-V becomes a first-class citizen of the HotSpot ecosystem.

## 2. Scope

1. Target is the 64-bit variant (`RV64GC`, i.e. the `I`, `M`, `A`, `F`, `D` and `C` extensions plus the ZICSR/Zifencei/Zicsr profile).
2. Only Linux is supported (no FreeBSD or macOS); build target is `linux-riscv64`.
3. All HotSpot components - interpreter, C1 JIT, C2 JIT, all GC collectors (G1, Parallel, Serial, ZGC, Shenandoah), Shenandoah LRB stubs, JVMTI, Serviceability Agent - must work.
4. JNI/JFR/JCStress are fully supported.

## 3. Architecture

Introduce a new HotSpot CPU backend for RISC-V, parallel to the existing aarch64 backend. The backend provides:

- Register, stack and frame layout (RISC-V architecture description, frame and register definitions).
- An Assembler module implementing the RV64 base ISA + extensions M, A, F, D, C, Zba, Zbb, Zbc, Zbs (per the RVA20U64 profile).
- A MacroAssembler that maps HotSpot conventions (safepoints, card marks, barriers) to RISC-V instructions.
- Interpreter templates for the new architecture.
- C1 LIR lowering (RISC-V frame map, LIR assembler, runtime stubs).
- C2 match rules in the RISC-V ADL backend, ADLC-generated code.
- Stub routines for arraycopy, compiled-call helpers, safepoint polling, runtime-entry.
- Vectorisation/stub generator hooks for the RISC-V backend.

## 4. Shared code changes

- An OS/CPU glue layer for Linux/RISC-V covering thread-state, signals, and platform glue.
- Autoconf-driven configure plumbing to recognise the new architecture.
- Hotspot tests: new `@requires` tags and platform filters.

## 5. Implementation Scope

The deliverable must:

1. Compile and run the full HotSpot + JDK class library on `linux-riscv64`.
2. Pass the regression tests that do not depend on specific ISA assumptions, with the usual CI filters (`@requires` annotation where needed).
3. Provide JIT code generators (C1 and C2) producing working RISC-V 64-bit code.
4. Integrate signal handling so that deoptimization, safepoint polling, and null-pointer checks all work via OS signals.
5. Implement the JNI ABI and stack-walking so native libraries written for RV64 link and call correctly.

## 6. Acceptance Criteria

- `make images` builds a usable JDK on Linux/RISC-V.
- Running `java -version` on a RISC-V board (QEMU acceptable) prints the standard HotSpot banner.
- `java Hello`, `javac`, `jshell`, and core samples run without crash.
- The JDK tier-1 test suite and selected HotSpot tier-1 tests pass (CI-accepted skip lists permitted).
- C2 compiled output on RISC-V runs `SPECjbb2015`-style workload without miscompilation.
