# T21: CPython

**Summary**: CPython 当前使用基于 LL(1) 文法的解析器来解析 Python 源代码。PEP 617 提出用基于 PEG（解析表达式文法）的新解析器替换现有解析器。新解析器能够直接生成 AST，消除中间 CST 的开销，支持左递归语法，并为未来的语法扩展提供更大的灵活性。

**Motivation**: 现有的 LL(1) 解析器存在多个限制：(1) LL(1) 文法限制迫使许多语法规则使用不自然的形式表达，例如禁止左递归导致算术表达式等规则必须改写；(2) 解析过程需要先生成 CST 再转换为 AST，造成内存开销和维护复杂性；(3) 解析树的形状与 AST 生成代码高度耦合，导致隐式逻辑散布在编译器各处；(4) 某些语义限制（如命名表达式的使用范围）必须延迟到 AST 阶段才能处理，而非在解析阶段。PEG 解析器通过有序选择和直接 AST 生成能够解决这些问题。

**Proposal**: 实现一个基于 PEG 的新解析器，该解析器使用记忆化（Packrat 解析）来保证线性时间复杂度，支持左递归，并通过语法动作（grammar actions）直接构建 AST 节点。同时提供 `-X oldparser` 命令行选项和 `PYTHONOLDPARSER` 环境变量，允许用户在过渡期间切换回旧解析器。

**Design Details**:

1. 创建 PEG 语法文件：在 `Grammar/python.gram` 中定义完整的 Python 语法，使用 PEG 语法规则（包括有序选择、前向查看、重复操作符等），并为每个规则附加语法动作来直接生成 AST 节点。

2. 实现 PEG 解析器生成器：在 `Tools/peg_generator/` 目录下实现 pegen 工具，能够从 `.gram` 文件生成 C 代码。包括 tokenizer、grammar parser、first sets 计算、C 代码生成器等模块。

3. 生成解析器 C 代码：使用 pegen 工具从 `python.gram` 生成 `Parser/pegen/parse.c`，该文件包含完整的 PEG 解析器实现，包括记忆化缓存和左递归处理。

4. 实现 PEG 解析器核心运行时：在 `Parser/pegen/` 目录下实现 `pegen.c`、`peg_api.c` 等核心文件，提供解析器的运行时支持，包括 tokenizer 集成、错误处理、内存管理等。

5. 集成字符串字面量解析：实现 `parse_string.c` 和 `parse_string.h`，处理各类字符串字面量（普通字符串、f-string、bytes 等）的解析逻辑。

6. 修改编译管道接口：更新 `Include/pegen_interface.h` 和相关头文件，定义 PEG 解析器的公共 API。修改 `Python/pythonrun.c` 和 `Python/compile.c` 以集成新解析器。

7. 添加解析器切换机制：在 `Include/cpython/initconfig.h` 中添加配置选项，在 `Python/initconfig.c` 中实现 `-X oldparser` 和 `PYTHONOLDPARSER` 的处理逻辑，允许运行时选择解析器。

8. 更新构建系统：修改 `Makefile.pre.in`、`PCbuild/*.vcxproj` 等构建文件，添加 PEG 解析器相关文件的编译规则，并设置从 `.gram` 文件重新生成解析器代码的构建目标。

9. 添加 `_peg_parser` 测试模块：实现 `Modules/_peg_parser.c`，提供 Python 层面测试 PEG 解析器的接口，支持解析字符串并返回 AST。

10. 编写测试用例：在 `Lib/test/` 目录下添加 `test_peg_parser.py` 和 `test_peg_generator/` 测试包，覆盖 PEG 解析器的各种语法场景、错误处理、以及与旧解析器的行为一致性验证。

## Requirement
https://peps.python.org/pep-0617/
