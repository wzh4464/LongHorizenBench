# T02: CPython

## Requirement
https://peps.python.org/pep-0634/

---

**Summary**: PEP 634 为 Python 3.10 引入结构化模式匹配（Structural Pattern Matching）功能。通过 `match`/`case` 语句，开发者可以将 subject 表达式与多种模式进行匹配，支持字面量、捕获、通配符、OR、序列、映射、类等模式类型，并在匹配成功时自动绑定变量。这是 Python 语言层面的重大扩展，需要修改语法解析器、AST、编译器和字节码解释器。

**Motivation**: Python 长期缺乏原生的模式匹配能力，开发者只能通过 if-elif 链或字典分发来模拟。这导致代码冗长、可读性差，尤其在处理复杂数据结构（如 AST 遍历、协议解析、状态机）时。结构化模式匹配提供了一种声明式、简洁的方式来解构和匹配数据，同时自动处理类型检查和变量绑定，显著提升代码的表达力和可维护性。

**Proposal**: 实现完整的 `match`/`case` 语句支持，包括：扩展 Python 语法（Grammar/python.gram）添加 match 语句和各类模式的产生式、扩展 AST 定义（Parser/Python.asdl）添加 Match 节点和模式节点类型、实现编译器支持将模式匹配编译为字节码、添加新的字节码指令（MATCH_MAPPING、MATCH_SEQUENCE、MATCH_KEYS、MATCH_CLASS 等）、以及在解释器中实现这些指令的执行逻辑。

**Design Details**:

1. 语法扩展（Grammar/python.gram）：添加 match_stmt、case_block、patterns、pattern 等产生式。match 语句格式为 `match subject_expr: NEWLINE INDENT case_block+ DEDENT`。支持的模式包括：literal_pattern（字面量）、capture_pattern（捕获变量）、wildcard_pattern（通配符 `_`）、or_pattern（用 `|` 连接）、sequence_pattern（列表/元组解构）、mapping_pattern（字典解构）、class_pattern（类匹配）、as_pattern（带绑定的模式）。

2. AST 扩展（Parser/Python.asdl）：添加 Match 语句节点（包含 subject 表达式和 cases 列表）、match_case 结构（包含 pattern、guard、body）、以及各类模式的 AST 节点（MatchValue、MatchSingleton、MatchSequence、MatchMapping、MatchClass、MatchStar、MatchAs、MatchOr）。

3. AST 生成代码（Parser/asdl_c.py）：更新 ASDL 编译器以支持生成新节点类型的 C 代码，包括构造函数、访问器、序列化等。

4. 字节码指令（Lib/opcode.py、Python/opcode_targets.h）：添加新指令：
   - MATCH_MAPPING：检查 TOS 是否为 Mapping 类型
   - MATCH_SEQUENCE：检查 TOS 是否为 Sequence 类型（排除 str/bytes/bytearray）
   - MATCH_KEYS：检查映射是否包含指定键并提取值
   - MATCH_CLASS：检查类实例并提取属性
   - GET_LEN：获取序列长度
   - COPY_DICT_WITHOUT_KEYS：创建排除指定键的字典副本

5. 编译器实现（Python/compile.c）：为 Match 语句和各类模式生成字节码。处理模式匹配的控制流（匹配成功跳转到 case body，失败尝试下一个 case）。实现变量捕获的作用域处理，确保捕获的变量在 match 块后可用。

6. 解释器实现（Python/ceval.c）：在主求值循环中实现新字节码指令的执行逻辑。MATCH_MAPPING 使用 `PyMapping_Check`，MATCH_SEQUENCE 检查 `collections.abc.Sequence` 注册且非 str/bytes/bytearray。

7. 类型对象扩展（Objects/*.c）：为内置类型（list、tuple、dict、set、str、bytes、int、float 等）添加 `__match_args__` 支持或相关协议方法，使其能够参与类模式匹配。

8. AST 优化（Python/ast_opt.c）：可选地对模式匹配进行编译时优化，如常量折叠、死代码消除。

9. 符号表处理（Python/symtable.c）：更新符号表分析以正确处理模式中的变量绑定，确保同一模式中变量不重复绑定。

10. 标准库支持（Lib/ast.py、Lib/collections/__init__.py、Lib/dataclasses.py）：更新 ast 模块支持新节点类型的访问和转换。确保 dataclasses 和 namedtuple 自动生成 `__match_args__`。

11. 文档更新（Doc/library/dis.rst）：为新字节码指令添加文档说明。

12. 测试（Lib/test/test_patma.py）：编写全面的测试覆盖各种模式类型、嵌套模式、guard 条件、边界情况和错误处理。
