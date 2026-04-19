# T25: CPython

**Summary**: Python 当前不允许在列表推导式、集合推导式、字典推导式和生成器表达式的表达式部分使用解包操作符（`*` 和 `**`）。PEP 798 提出扩展推导式语法，允许使用 `*expr` 来解包可迭代对象的元素，以及使用 `**expr` 在字典推导式中解包键值对。这使得合并多个可迭代对象变得更加简洁。

**Motivation**: 合并多个可迭代对象到单个对象是常见任务。虽然 `[*it1, *it2, *it3]` 可以合并已知数量的可迭代对象，但当需要合并任意数量的可迭代对象时，开发者必须使用显式循环、嵌套推导式或 `itertools.chain` 等工具，这些方案既不直观也不够优雅。例如，将多个列表展平为一个列表需要写 `list(itertools.chain.from_iterable(lists))` 或双重循环的列表推导式，而新语法允许简洁地写成 `[*lst for lst in lists]`。

**Proposal**: 扩展推导式语法，允许在表达式位置使用解包操作符。对于列表和集合推导式，`*expr` 将 expr 的每个元素添加到结果中；对于字典推导式，除了传统的 `key: value` 形式，还支持 `**expr` 形式将字典的所有键值对添加到结果中；生成器表达式中的 `*expr` 等价于对 expr 的每个元素执行 yield。

**Design Details**:

1. 修改语法规则：在 `Grammar/python.gram` 中更新推导式相关规则。引入 `flexible_expression` 允许普通表达式或带星号的解包表达式。修改 `comprehension`、`generator_expression` 等规则以使用新的表达式类型。更新 `dict_comprehension` 允许 `**expr` 形式。

2. 扩展 AST 定义：在 `Parser/Python.asdl` 中，确保 AST 能够正确表示推导式中的解包表达式。解包表达式在 AST 中表示为 `Starred` 节点（对于 `*`）或特殊的字典解包形式（对于 `**`）。

3. 更新 AST 构建：修改 `Python/ast.c` 以正确构建包含解包表达式的推导式 AST 节点。确保解包表达式仅在允许的推导式上下文中出现。

4. 修改 AST 预处理：更新 `Python/ast_preprocess.c`，在 AST 预处理阶段正确处理推导式中的解包节点，进行必要的转换和验证。

5. 更新代码生成：修改 `Python/codegen.c`，为包含解包的推导式生成正确的字节码。对于 `*expr`，生成循环遍历 expr 元素并逐个添加到结果的代码；对于字典推导式中的 `**expr`，生成遍历键值对并添加到字典的代码。

6. 添加语法错误检查：确保在非法上下文中使用解包时（如在列表推导式中使用 `**`，或在生成器表达式中使用 `**`）给出清晰的语法错误消息。

7. 更新文档：修改 `Doc/reference/expressions.rst` 中关于推导式和生成器表达式的语法描述，添加解包操作符的说明。更新 `Doc/tutorial/datastructures.rst` 和 `Doc/tutorial/classes.rst` 中的示例。

8. 更新 whatsnew：在 `Doc/whatsnew/3.15.rst` 中记录此新功能，说明语法变化和用法示例。

9. 添加 NEWS 条目：在 `Misc/NEWS.d/` 中创建新闻条目，简要描述此功能增强。

10. 编写测试用例：更新 `Lib/test/test_unpack_ex.py` 添加推导式解包的测试。更新 `Lib/test/test_exceptions.py` 确保错误情况下的异常消息正确。测试各种边界情况，如空可迭代对象、嵌套解包、与条件表达式的组合等。

## Requirement
https://peps.python.org/pep-0798/
