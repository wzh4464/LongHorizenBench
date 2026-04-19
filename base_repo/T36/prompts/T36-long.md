# T36: OpenJDK Sequenced Collections

## Requirement
https://openjdk.org/jeps/431

---

**Summary**: JEP 431 提出在 Java Collections Framework 中引入新的接口来表示具有定义遇到顺序（encounter order）的集合。这些集合具有明确定义的第一个元素、第二个元素，依此类推，直到最后一个元素。新接口提供统一的 API 来访问集合的首尾元素，以及以逆序处理集合元素。

**Motivation**: Java Collections Framework 缺乏一种集合类型来表示具有定义遇到顺序的元素序列。它也缺乏一套统一的操作来处理这类集合。这是一个长期存在的痛点：

1. `List` 和 `Deque` 都定义了遇到顺序，但它们没有共同的超类型。
2. `Set` 通常不定义遇到顺序，但某些子类型（如 `LinkedHashSet` 和 `SortedSet`）确实定义了遇到顺序。
3. 获取集合首尾元素的操作不一致：`List.get(0)` vs `Deque.getFirst()`；`List.get(list.size()-1)` vs `Deque.getLast()`。
4. 获取逆序视图的方式也不统一：`NavigableSet.descendingSet()` vs `Deque.descendingIterator()`，而 `List` 完全没有逆序遍历的简便方法。

**Proposal**: 引入三个新接口 `SequencedCollection`、`SequencedSet` 和 `SequencedMap`，并将它们插入到现有的集合类层次结构中。这些接口定义了统一的方法来访问首尾元素和获取逆序视图。现有的实现类（如 `ArrayList`、`LinkedHashSet`、`TreeMap` 等）将实现这些新接口。

**Design Details**:

1. **定义 SequencedCollection 接口**：创建 `java.util.SequencedCollection<E>` 接口，扩展 `Collection<E>`。添加方法：`addFirst(E)`、`addLast(E)`、`getFirst()`、`getLast()`、`removeFirst()`、`removeLast()`、`reversed()`。这些方法应有合理的默认实现或抛出 `UnsupportedOperationException`。

2. **定义 SequencedSet 接口**：创建 `java.util.SequencedSet<E>` 接口，扩展 `SequencedCollection<E>` 和 `Set<E>`。重写 `reversed()` 方法以返回 `SequencedSet<E>`。

3. **定义 SequencedMap 接口**：创建 `java.util.SequencedMap<K,V>` 接口，扩展 `Map<K,V>`。添加方法：`firstEntry()`、`lastEntry()`、`pollFirstEntry()`、`pollLastEntry()`、`putFirst(K,V)`、`putLast(K,V)`、`reversed()`、`sequencedKeySet()`、`sequencedValues()`、`sequencedEntrySet()`。

4. **修改现有接口层次结构**：
   - `List` 扩展 `SequencedCollection`
   - `Deque` 扩展 `SequencedCollection`
   - `SortedSet` 扩展 `SequencedSet`
   - `NavigableSet` 继承自 `SortedSet`（已有）
   - `SortedMap` 扩展 `SequencedMap`
   - `NavigableMap` 继承自 `SortedMap`（已有）

5. **更新具体实现类**：为 `ArrayList`、`LinkedList`、`ArrayDeque`、`LinkedHashSet`、`LinkedHashMap`、`TreeSet`、`TreeMap`、`ConcurrentSkipListSet`、`ConcurrentSkipListMap`、`CopyOnWriteArrayList` 等类添加新方法的实现。对于某些类（如 `ArrayList`），需要覆盖默认实现以提供更高效的版本。

6. **创建逆序视图类**：实现内部类来支持 `reversed()` 方法返回的逆序视图。这些视图类需要正确委托所有操作到底层集合，同时反转遇到顺序。主要包括：
   - `ReverseOrderListView` 用于 `List`
   - `ReverseOrderDequeView` 用于 `Deque`
   - `ReverseOrderSortedSetView` 用于 `SortedSet`
   - `ReverseOrderSortedMapView` 用于 `SortedMap`

7. **更新 Collections 工具类**：为 `Collections` 类添加方法来创建不可修改的 sequenced collection 包装器。更新现有的 `unmodifiable*` 和 `synchronized*` 包装器以支持新接口。

8. **更新 ImmutableCollections**：确保通过 `List.of()`、`Set.of()`、`Map.of()` 等工厂方法创建的不可变集合正确实现新接口。

9. **添加数组反转支持**：在 `jdk.internal.util.ArraysSupport` 中添加辅助方法来支持数组元素的原地反转操作。

10. **编写测试**：为新接口和方法编写全面的单元测试，包括基本功能测试、边界条件测试、逆序视图测试、以及与现有功能的兼容性测试。
