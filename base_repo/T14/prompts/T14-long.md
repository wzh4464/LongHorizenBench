# T14: OpenJDK — JEP 382 New macOS Rendering Pipeline (Metal)

## Requirement (inlined)

*Upstream spec, for reference only:* OpenJDK JEP 382 "New macOS Rendering Pipeline" (https://openjdk.org/jeps/382). The summary below is sufficient for the task; do not fetch external sources.

## 1. Background

Apple deprecated OpenGL on macOS in favour of Metal. Java 2D on macOS historically used a platform-specific OpenGL-backed pipeline (in addition to the software pipeline). With OpenGL deprecated, a Metal-backed Java 2D rendering pipeline is needed so that AWT/Swing on macOS can continue to use a maintained, hardware-accelerated rendering path.

## 2. Goals

- Provide a fully functional Java 2D rendering pipeline for macOS implemented on top of Metal.
- Achieve rendering performance equivalent to or better than the existing OpenGL pipeline.
- The new pipeline must be transparent to applications: same Java 2D / AWT / Swing semantics as the OpenGL pipeline.
- Make co-existence with the OpenGL pipeline possible during transition; OpenGL remains the default while Metal stabilises.

## 3. Non-Goals

- Removing or deprecating the existing OpenGL pipeline as part of this task.
- Adding new public Java APIs (the change is internal).
- Porting to Windows or Linux Metal-equivalents (Metal is macOS-only).
- Rewriting the software pipeline.

## 4. Pipeline Overview

The new pipeline mirrors the structure of the OpenGL pipeline at a high level:

- A graphics configuration / device layer that owns a Metal device and command queue.
- A surface-data abstraction that wraps Metal textures (offscreen images, volatile images, on-screen layers backed by `CAMetalLayer`).
- A render-queue layer that batches Java 2D primitives into command buffers, mirroring the existing OpenGL render-queue design (encode-on-render-thread / flush-on-display).
- Shader programs in `.metal` source, compiled into a Metal shader library at build time, covering: solid fill, gradient paints, image blits, masked fills, text glyph rendering.
- A blit pipeline supporting Java 2D source/dest rules (Porter-Duff compositing) realised via Metal blend states.

## 5. Selection and fallback

- `-Dsun.java2d.metal=true` opts in to the Metal pipeline (the JEP defers making it default).
- If Metal initialisation fails (e.g. unsupported device), Java 2D falls back to the existing OpenGL pipeline transparently.
- The existing OpenGL pipeline (`sun.java2d.opengl`) remains supported; the JEP does not remove it.

## 6. Implementation Scope

The detailed file layout, class names, and shader names are intentionally not prescribed here — the implementer should follow the structure of Java 2D's existing OpenGL pipeline and add a parallel Metal pipeline alongside it. Substantive items:

1. Native Metal pipeline (Objective-C / Metal Shading Language) implementing context creation, surface management, blit loops, masked fills, gradients, text glyph rendering, and on-screen layer presentation.
2. Java-side classes mirroring the existing OpenGL pipeline: `GraphicsConfig`, `SurfaceData`, render queue, `BufferedRenderPipe`, mask fill / mask blit, paints, text rendering, and pipeline selection logic.
3. AWT/Swing peer integration so that windows can be backed by a `CAMetalLayer` when Metal is active, with correct resize/recreation handling.
4. Build-system updates so the new native sources, Metal shaders (compiled into a `.metallib`), and Java classes are built and packaged on macOS.