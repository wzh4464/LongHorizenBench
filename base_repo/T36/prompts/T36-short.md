**Summary**: JEP 431 提出在 Java Collections Framework 中引入新的接口来表示具有定义遇到顺序（encounter order）的集合。这些集合具有明确定义的第一个元素、第二个元素，依此类推，直到最后一个元素。新接口提供统一的 API 来访问集合的首尾元素，以及以逆序处理集合元素。

**Proposal**: 引入三个新接口 `SequencedCollection`、`SequencedSet` 和 `SequencedMap`，并将它们插入到现有的集合类层次结构中。这些接口定义了统一的方法来访问首尾元素和获取逆序视图。现有的实现类（如 `ArrayList`、`LinkedHashSet`、`TreeMap` 等）将实现这些新接口。
