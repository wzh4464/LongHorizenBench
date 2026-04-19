# T45: OpenJDK - JEP 388 Windows/AArch64 Port

**Summary**: JEP 388 将 JDK 移植到 Windows/AArch64 平台。该移植工作基于已有的 Linux/AArch64 移植（JEP 237），扩展支持 Windows 10 和 Windows Server 2016 操作系统上的 AArch64 架构。移植包括模板解释器、C1 和 C2 JIT 编译器，以及各种垃圾收集器（Serial、Parallel、G1、Z、Shenandoah）。

**Motivation**: 随着新的消费级和服务器级 AArch64（ARM64）硬件的发布，Windows/AArch64 已成为一个重要的平台。为了满足最终用户需求，需要为该平台提供原生 JDK 支持，而非依赖 x86 模拟运行。

**Proposal**: 基于现有的 Linux/AArch64 代码，进行必要的修改以支持 Windows 平台。主要工作包括：将 AArch64 内存模型扩展到 Windows、解决 MSVC 编译器问题、为 AArch64 移植添加 LLP64（64位长整型和指针）支持、在 Windows 上进行 CPU 特性检测，以及修改构建脚本以更好地支持交叉编译和 Windows 工具链。

**Design Details**:

1. **构建系统配置（autoconf）**：
   - 修改 `make/autoconf/basic.m4`，添加 `BASIC_EVAL_BUILD_DEVKIT_VARIABLE` 宏以支持构建平台特定的 devkit 变量
   - 修改 `make/autoconf/flags-cflags.m4`，为 Windows/AArch64 添加 CPU 定义（`-D_ARM64_ -Darm64`）
   - 修改 `make/autoconf/flags-ldflags.m4`，调整链接器标志以支持 AArch64
   - 修改 `make/autoconf/jvm-features.m4`，限制 AOT、Graal、JVMCI 特性仅在 Linux/AArch64 上可用（Windows/AArch64 暂不支持）

2. **工具链配置**：
   - 修改 `make/autoconf/toolchain.m4`，为 Windows 构建工具链添加 AArch64 支持
   - 添加 `BUILD_DEVKIT_VS_INCLUDE` 和 `BUILD_DEVKIT_VS_LIB` 变量处理
   - 实现 Windows 上的链接器（link.exe）检测和验证
   - 修改 `make/autoconf/toolchain_windows.m4` 添加 Visual Studio sysroot 标志设置

3. **AArch64 汇编器和寄存器定义**：
   - 修改 `src/hotspot/cpu/aarch64/register_aarch64.hpp`，添加对 Windows 平台 x18 寄存器的特殊处理（Windows 使用 x18 作为 TEB 指针）
   - 修改 `src/hotspot/cpu/aarch64/register_aarch64.cpp` 和 `register_definitions_aarch64.cpp` 相应更新
   - 修改 `src/hotspot/cpu/aarch64/assembler_aarch64.hpp` 和 `assembler_aarch64.cpp`
   - 修改 `src/hotspot/cpu/aarch64/macroAssembler_aarch64.cpp` 和 `macroAssembler_aarch64.hpp`

4. **Windows/AArch64 平台特定代码**：
   - 创建 `src/hotspot/os_cpu/windows_aarch64/` 目录下的平台特定文件：
     - `os_windows_aarch64.cpp` 和 `os_windows_aarch64.hpp`：操作系统接口
     - `atomic_windows_aarch64.hpp`：原子操作
     - `copy_windows_aarch64.inline.hpp`：内存复制
     - `thread_windows_aarch64.cpp` 和 `thread_windows_aarch64.hpp`：线程管理
     - `icache_windows_aarch64.hpp`：指令缓存刷新
     - `globals_windows_aarch64.hpp`：全局定义
     - `vm_version_windows_aarch64.cpp`：CPU 特性检测
     - `unwind_windows_aarch64.hpp`：异常展开

5. **LLP64 数据模型支持**：
   - 修改 `src/hotspot/share/utilities/globalDefinitions_visCPP.hpp`，确保正确处理 Windows 的 LLP64 数据模型（long 是 32 位，指针是 64 位）
   - 修改 `src/hotspot/cpu/aarch64/globalDefinitions_aarch64.hpp`

6. **JNI 和运行时支持**：
   - 修改 `src/hotspot/share/prims/jni.cpp` 添加 Windows/AArch64 支持
   - 修改 `src/hotspot/os/windows/os_windows.cpp` 添加 AArch64 特定代码路径

7. **HotSpot Agent（SA）支持**：
   - 修改 `src/jdk.hotspot.agent/share/classes/sun/jvm/hotspot/HotSpotAgent.java`
   - 添加 `src/jdk.hotspot.agent/share/classes/sun/jvm/hotspot/debugger/windbg/aarch64/` 目录下的调试器支持类
   - 添加 `src/jdk.hotspot.agent/share/classes/sun/jvm/hotspot/runtime/win32_aarch64/` 目录下的运行时访问类
   - 修改 `src/jdk.hotspot.agent/windows/native/libsaproc/sawindbg.cpp`

8. **G1 和 Shenandoah GC 支持**：修改 `src/hotspot/cpu/aarch64/gc/shenandoah/shenandoah_aarch64.ad` 确保 GC 相关代码在 Windows 上正确工作。

9. **Java 基础库支持**：
   - 修改 `src/java.base/windows/native/libjava/java_props_md.c` 添加 AArch64 架构识别
   - 修改 `src/jdk.attach/windows/classes/sun/tools/attach/AttachProviderImpl.java`

10. **Windows DevKit 脚本**：更新 `make/devkit/createWindowsDevkit2017.sh` 和 `createWindowsDevkit2019.sh`，添加对 AArch64 工具的支持。
