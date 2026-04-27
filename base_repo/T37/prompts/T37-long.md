# T37: OpenJDK / JEP 476 — Module Import Declarations (Preview)

## Requirement (inlined)

*Upstream source, for reference only:* `https://openjdk.org/jeps/476`

The implementation must work offline. The specification below is authoritative for this task.

---

## Summary

JEP 476 adds a new kind of import declaration, `import module M;`, to the Java language. Such a declaration imports, transitively, every type in every package that is *directly exported* by the module `M` to the current compilation unit. This is a preview language feature: enabled only with `--enable-preview --release <n>` where `<n>` is the version containing the feature.

The feature's goal is to make experimentation, teaching and small programs easier: users of the `java.base` module, for example, can write `import module java.base;` and get access to all of `java.lang.*`, `java.util.*`, `java.nio.*`, etc. without line after line of single-type or on-demand imports.

## Motivation

Currently, when a developer wants to use many types from a module, they must list each package individually (`import java.util.*; import java.util.function.*; import java.util.concurrent.*;`) or import each type by name. For exploratory code, JShell sessions, scripts, and introductory classes this is friction that serves no functional purpose.

Java's module system already knows which packages a module exports to the unnamed module (scripts/class-path code). Letting users leverage that knowledge to import all of them with one declaration eliminates boilerplate without compromising type safety — if a name collides, the ambiguity is reported exactly as it is for star imports today.

## 3. Syntactic grammar

The grammar of `ImportDeclaration` in JLS 7.5 is extended as follows:

```
ImportDeclaration:
    SingleTypeImportDeclaration
    TypeImportOnDemandDeclaration
    SingleStaticImportDeclaration
    StaticImportOnDemandDeclaration
    ModuleImportDeclaration                 // new

ModuleImportDeclaration:
    import module ModuleName ;
```

- `ModuleName` uses the same production as in a module declaration (a dot-separated sequence of identifiers).
- A compilation unit may contain any mixture of import kinds, including multiple `import module` declarations.
- `import module` is a *soft keyword*: only the two-token sequence `import module` introduces the new form; `module` remains usable as an identifier elsewhere.

## 4. Semantic rules

1. `import module M;` makes *every* public top-level type in every package that module `M` *exports without qualification* to the current compilation unit's module (or to `ALL-UNNAMED` if the current compilation unit is not in a module) available as a type-import-on-demand.
2. If `M` requires `transitive` another module `N`, then all types exported (unqualified) by `N` are also imported.
3. Conflicts between module imports and single-type imports are resolved by the existing JLS rules for shadowing: single-type imports win, then module imports tie with type-import-on-demand, then type-import-on-demand, then java.lang.
4. `import module java.base;` is equivalent to importing every package exported by `java.base`.

### Compilation targets

- `javac --enable-preview --release <n>` must accept the new form.
- Without `--enable-preview`, `javac` must fail with `compiler.err.preview.feature.disabled`.

### Supporting API

- `javax.lang.model.element.Modifier` (no change).
- `javax.lang.model.util.Elements` — add `boolean isModuleImport(ImportTree)` to the Trees API when preview is enabled.
- `com.sun.source.tree.ImportTree` gains:
  - `boolean isModule()` — returns true for module imports (preview).
  - The `qualifiedIdentifier()` for a module import returns the module name `MemberSelectTree` ending in the module's name.

### Preview APIs to expose

- `com.sun.tools.javac.tree.JCTree.JCImport`: add a `boolean module` flag.
- `com.sun.tools.javac.code.Symbol`: resolve module imports through the module graph.
- Update `TreeMaker`, `TreeCopier`, `TreeScanner`, `TreeTranslator`, `TreeVisitor`, `TreeInfo` to handle the new form.

### Examples

```java
import module java.base;

public class Hello {
    public static void main(String[] args) {
        List<String> msgs = List.of("hi");     // imported from java.util
        System.out.println(msgs);              // System from java.lang
        Path p = Path.of(".");                 // java.nio.file from java.base
    }
}
```

```java
import module java.sql;              // imports java.sql.*, javax.sql.*
import java.util.List;               // still valid
```

Ambiguity example (must be a compile error):
```java
import module java.sql;      // contains java.sql.Date
import module java.util;     // contains java.util.Date
// Date d = ...;            // ERROR: Date is ambiguous
```

## 5. JVM / tooling behaviour

- No classfile format change: `import module` is a source-level construct only. The compiler translates it to the equivalent set of single-type imports during the `enter` phase.
- `javadoc`, `javap`, IDEs and other structured tools that walk `ImportTree` must call `ImportTree.isModule()` (new) and handle the module-import subtree.
- `--release` and `--enable-preview` flags gate the feature.

## Implementation Task

Implement module-import support end-to-end in the OpenJDK compiler and supporting tools. The compilation unit grammar change must be accompanied by:

1. **Parser / AST** (`com.sun.tools.javac.parser.JavacParser`):
   - Add `PREVIEW` token handling for `module` after `import`.
   - Produce `JCModuleImport extends JCImport` AST nodes with a `ModuleSymbol` reference and `isModule()==true`.
   - Preserve positions for error reporting.
2. **Enter / resolution** (`com.sun.tools.javac.comp.Enter`, `Resolve`, `TypeEnter`):
   - Expand `import module m;` into the transitive closure of packages exported (unqualified) by `m` and its required-transitive dependencies.
   - Mark each imported type as `Flags.MODULEIMPORT` for duplicate-import diagnostics.
   - Emit `compiler.err.preview.feature.disabled` when `--enable-preview` is absent.
3. **Preview gating** — add `PreviewFeature.Feature.MODULE_IMPORTS` and plumb it through `com.sun.tools.javac.code.Source.Feature` and `PreviewLanguageFeatures`. The class-file minor version bit set for preview must be honoured.
4. **AST / API changes** — extend `javax.lang.model.element.ModuleElement` and `javax.lang.model.util.Elements#getFileObjectsByModule` accessors are unchanged, but `JCImport` gets a new `Name module` slot; `Trees` API must expose `isModuleImport()`.
5. **Pretty printing & source retention** — the `-Xprint` output, `javadoc`, and `JShell` import tracker must reproduce the `import module` form verbatim.
6. **JShell defaults** — the interactive JShell tool auto-imports `module java.base` unless the user overrides it; the preview flag must be inferred from the launcher.
7. **Testing** — add regression tests for the preview `import module` feature covering:
   - positive compilation with `--enable-preview`;
   - failure when `--enable-preview` is omitted;
   - ambiguity errors between two module imports exporting the same simple name;
   - interaction with explicit single-type imports (the explicit one wins);
   - compile and run via `jshell` with the updated startup scripts.

## Out of scope

- Static imports of module members.
- Implicit imports of `java.base` outside JShell.
- Runtime reflection on the new `ModuleImport` symbol (none is added; module imports are a source-only construct).
