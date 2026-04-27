# T10: Presto — Unnest Operator Optimisations

## Requirement — self-contained specification

*Upstream source (for reference only):* Presto issue #13751 "Improve performance of UNNEST operator" (`https://github.com/prestodb/presto/issues/13751`) and PR #14050. All context and requirements are inlined below.

---

## 1. Motivation

Presto's `UNNEST` operator is used to explode array / map-typed columns into multiple rows. It is the top-5 most frequently used operator in production Presto deployments and, historically, one of the slower ones. Profiling showed three bottlenecks in the legacy implementation (`UnnestOperator`):

1. **Per-row block construction** — each output row allocated a fresh `BlockBuilder` for each unnest column, incurring per-row boxing and bounds-check overhead.
2. **Repeated null-bit lookups** — `isNull(i)` was called multiple times on the same position, once per column, once per replicate.
3. **Inefficient replicate columns** — columns that are replicated (not unnested) were rebuilt row-by-row rather than via a `DictionaryBlock` wrapping the source column.

The goal is to replace the row-at-a-time implementation with a column-at-a-time implementation that processes entire pages at once, reuses block builders across rows, and emits dictionary-backed replicate columns.

## 2. Required algorithmic changes

### 2.1 UnnestOperator skeleton

Keep the public type signature:

```java
public final class UnnestOperator implements Operator {
    UnnestOperator(
        OperatorContext context,
        List<Type> replicateTypes,
        List<Integer> replicateChannels,
        List<Type> unnestTypes,
        List<Integer> unnestChannels,
        boolean withOrdinality);
    Page getOutput();
    void addInput(Page page);
}
```

### 2.2 Per-column unnester

Introduce an abstract `Unnester` with concrete implementations `ArrayUnnester`, `MapUnnester`, `ArrayOfRowsUnnester`. Each `Unnester` holds its own `BlockBuilder`, is reused across pages, and exposes:

```java
interface Unnester {
    int getChannelCount();                 // number of output columns
    int[] getCardinalities(Block block);   // cardinality per input row
    void processRow(int rowIndex, int cardinality, int maxCardinality);
    Block[] buildOutputBlocks();
    void reset();
}
```

Concrete implementations:

- `ArrayUnnester` — produces a single block; cardinality = array length per row.
- `ArrayOfRowsUnnester` — produces one block per row field.
- `MapUnnester` — produces two blocks (keys, values).

### 3.2 Ordinality & With-Ordinality

When the SQL uses `UNNEST(...) WITH ORDINALITY`, the operator appends a `bigint` channel with 1-based row indices. This is implemented uniformly in the operator rather than in each `Unnester`.

### 3.3 Replicated channels

`UnnestOperator` supports replicated source channels: the channels that are not being unnested are duplicated for each output row. The new implementation copies block regions in bulk (`Block.copyPositions`) instead of per-row.

## 4. Implementation Task

Refactor the Presto unnest operator and related classes:

1. Introduce the `Unnester` abstract class / interface with the three concrete implementations above.
2. Replace the per-row output loop in `UnnestOperator#getOutput` with a three-phase flow:
   - compute cardinalities,
   - compute the total output position count and allocate builders with the right capacity,
   - stream-fill builders using bulk `writeStructure` / `writeByte` etc. to avoid per-element method dispatch.
3. Replicate replicated columns via `DictionaryBlock` or `RunLengthEncodedBlock` instead of copying each row, where feasible.
4. Ordinality channel: build a `LongArrayBlock` directly with `Math.toIntExact` guard.
5. Ensure all `Unnester` implementations support both "concat" mode (single unnest) and "cross" mode (multiple unnests with equal cardinalities).

Test expectations:

- The Unnest integration tests must continue to pass.
- The unnest-operator unit tests are extended to cover replicated channels and multi-unnest.
- The Unnest microbenchmarks show a ~30-50% reduction in operator latency for common cases.

## 5. Acceptance

- Code compiles with `./mvnw -pl presto-main -am compile` and the `presto-main` unit suite passes.
- `TestUnnestOperator` extended tests cover: nested rows (array(row)), mixed null cardinalities across columns, single-row pages.
- No changes to SQL-visible semantics; `EXPLAIN` should report the same plan shape.
