# T36: OpenJDK — JEP 431 Sequenced Collections

## Requirement

*Upstream source, for reference only:* `https://openjdk.org/jeps/431`

The agent must implement this task without fetching any URL; the full specification needed for a complete implementation is inlined below.

## Summary

Introduce a set of new collection interfaces and default methods for collections that have a well-defined encounter order. Today, the Java Collections Framework lacks a collection type that represents a sequence of elements with a defined encounter order, along with a common set of operations that apply to such sequences. The absence makes otherwise straightforward operations awkward: there is no way to ask a `LinkedHashSet` for its last element without an iterator walk; and `List` has no common supertype with `Deque` despite sharing semantics (indexable, insertion-ordered).

## Motivation

Java's collections have accumulated idiosyncratic ways of getting to the first, last, or reverse view of a sequence:

| Collection         | First                    | Last                   | Reversed                              |
|--------------------|--------------------------|------------------------|---------------------------------------|
| `List`             | `get(0)`                 | `get(size()-1)`        | `Collections.reverse(copy)`           |
| `Deque`            | `getFirst()`             | `getLast()`            | `iterator()` vs `descendingIterator()`|
| `LinkedHashSet`    | `iterator().next()`      | *no direct method*     | *no direct method*                    |
| `SortedSet`        | `first()`                | `last()`               | `descendingSet()` (inconsistent name) |
| `LinkedHashMap`    | `entrySet().iterator()…` | *nothing*              | *nothing*                             |
| `SortedMap`        | `firstKey()`             | `lastKey()`            | *nothing symmetric*                   |

This JEP introduces three interfaces:

### `SequencedCollection<E>`
Extends `Collection<E>`. Adds:
- `SequencedCollection<E> reversed()` — a reverse-ordered *view* (live).
- `void addFirst(E e)`, `void addLast(E e)` — optional operations.
- `E getFirst()`, `E getLast()` — throw `NoSuchElementException` on empty.
- `E removeFirst()`, `E removeLast()` — likewise.

### `SequencedSet<E>`
A `SequencedCollection` that is also a `Set`. Adds:
- `SequencedSet<E> reversed()` returning a `SequencedSet<E>`.
- Inherits the other operations; if duplicates would be introduced by `addFirst`/`addLast`, an implementation may move the element (LinkedHashSet semantics) or throw `UnsupportedOperationException` (TreeSet semantics unless a comparator enforces ordering compatible with insertion).

### `SequencedMap<K,V>`
Adds:
- `SequencedMap<K,V> reversed()`.
- `Map.Entry<K,V> firstEntry()`, `lastEntry()`, `pollFirstEntry()`, `pollLastEntry()`.
- `V putFirst(K, V)`, `V putLast(K, V)` — optional.
- `SequencedSet<K> sequencedKeySet()`, `SequencedCollection<V> sequencedValues()`, `SequencedSet<Map.Entry<K,V>> sequencedEntrySet()`.

### Retrofits in the existing hierarchy

- `List<E> extends SequencedCollection<E>`; new default impls for `addFirst`, `addLast`, `getFirst`, `getLast`, `removeFirst`, `removeLast`, `reversed()`.
- `Deque<E> extends SequencedCollection<E>` (no semantic change, just the super-interface).
- `LinkedHashSet<E> implements SequencedSet<E>` (which `extends SequencedCollection<E>`, `Set<E>`); `reversed()` returns a view.
- `SortedSet<E>`, `NavigableSet<E>` get `SequencedSet<E>` as a super-interface.
- `LinkedHashMap<K,V> implements SequencedMap<K,V>`.
- `SortedMap<K,V>`, `NavigableMap<K,V>` get `SequencedMap<K,V>` as a super-interface.
- `Collections` gains `unmodifiableSequencedCollection`, `unmodifiableSequencedSet`, `unmodifiableSequencedMap`.

### API contract for `reversed()`
- Must be a *view*: changes in the original are visible, and vice versa if supported by the backing collection.
- Iteration order, `first()/last()`, and `addFirst/addLast` are swapped relative to the original.
- `reversed().reversed()` must return a collection semantically equivalent to the original (implementations may return `this` for efficiency).

### Behavioural constraints
- `addFirst` / `addLast` on an unmodifiable collection must throw `UnsupportedOperationException`.
- For `SequencedSet`, `addFirst(E)` on an element already present must move it to the front (and symmetrically for `addLast`).
- For `SequencedMap`, `putFirst`, `putLast` semantics mirror the above.

## Implementation Scope

Implement across:
- Add three new public interfaces `java.util.SequencedCollection`, `java.util.SequencedSet`, `java.util.SequencedMap`.
- Update `java.util.List`, `java.util.Deque`, `java.util.SortedSet`, `java.util.NavigableSet`, `java.util.LinkedHashSet`, `java.util.LinkedHashMap`, `java.util.SortedMap`, `java.util.NavigableMap`, `java.util.TreeMap`, `java.util.TreeSet` to implement or extend the new types.
- Provide reversed views as nested classes (`ReverseOrderListView`, `ReverseOrderMap`, etc.).
- Update `java.util.Collections.unmodifiable*` to return the new interface types.
- Update `Arrays.asList` to return a `SequencedCollection` view.
- Spec updates in the corresponding `package-info.java` / javadoc.
- jtreg regression tests covering ordering invariants, reversed views, and retrofit compatibility.

## Acceptance criteria

* Existing code depending on `List`, `Deque`, `LinkedHashSet`, `LinkedHashMap`, `TreeSet`, `TreeMap`, `SortedSet`, `NavigableSet`, `SortedMap`, `NavigableMap` continues to compile and run.
* Methods `addFirst`, `addLast`, `getFirst`, `getLast`, `removeFirst`, `removeLast`, `reversed()`, `firstEntry()`, `lastEntry()`, `pollFirstEntry()`, `pollLastEntry()`, `putFirst`, `putLast`, `sequencedKeySet`, `sequencedValues`, `sequencedEntrySet`, `reversed()` exist and behave as specified.
* `Collections.unmodifiableSequencedCollection`, `unmodifiableSequencedSet`, `unmodifiableSequencedMap` exist and delegate correctly.
* `javadoc` builds without warnings for the new interfaces.
* All JCK / jtreg tests covering `java.util` collections continue to pass.
