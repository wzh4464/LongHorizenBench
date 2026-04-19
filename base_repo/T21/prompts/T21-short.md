**Summary**: CPython 当前使用基于 LL(1) 文法的解析器来解析 Python 源代码。PEP 617 提出用基于 PEG（解析表达式文法）的新解析器替换现有解析器。新解析器能够直接生成 AST，消除中间 CST 的开销，支持左递归语法，并为未来的语法扩展提供更大的灵活性。

**Proposal**: 实现一个基于 PEG 的新解析器，该解析器使用记忆化（Packrat 解析）来保证线性时间复杂度，支持左递归，并通过语法动作（grammar actions）直接构建 AST 节点。同时提供 `-X oldparser` 命令行选项和 `PYTHONOLDPARSER` 环境变量，允许用户在过渡期间切换回旧解析器。
