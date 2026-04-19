# T27: CPython

**Summary**: PEP 750 引入模板字符串（t-strings），作为 f-strings 的泛化形式。与 f-strings 直接求值为字符串不同，t-strings 使用 `t` 前缀，求值后产生 `Template` 对象。该对象包含静态字符串部分和插值部分的结构化信息，允许开发者在字符串最终组合之前访问和处理这些组成部分，从而支持 HTML 转义、SQL 注入防护、结构化日志等安全关键场景。

**Motivation**: f-strings 提供了便利的字符串插值语法，但存在关键限制：无法在最终组合之前拦截和转换插值。这在 SQL 查询（注入攻击）和 HTML 生成（跨站脚本攻击）等场景中造成安全漏洞。模板字符串通过提供对静态部分和动态值的独立访问，使开发者能够实现上下文感知的安全处理函数，如自动 HTML 转义、SQL 参数化、结构化日志记录和领域特定语言支持。

**Proposal**: 在 CPython 中实现模板字符串功能，包括：在词法分析器中添加 `TSTRING_START`、`TSTRING_MIDDLE`、`TSTRING_END` token 类型；在语法解析器中支持 t-string 语法；创建新的 `Template` 和 `Interpolation` 内置类型；在 `string.templatelib` 模块中暴露这些类型的 Python 接口；支持模板字符串的拼接和迭代；以及相应的测试和文档。

**Design Details**:

1. 词法分析器扩展（Lexer）：在 `Grammar/Tokens` 中添加三个新的 token 类型——`TSTRING_START`（模板字符串开始，包含前缀和开始引号）、`TSTRING_MIDDLE`（模板字符串中间部分，包含字面文本和格式规范）、`TSTRING_END`（模板字符串结束，包含结束引号）。修改 `Parser/lexer/lexer.c` 和 `Parser/lexer/state.c` 以识别 `t` 和 `T` 前缀。

2. 语法解析器扩展（Parser）：修改 `Grammar/python.gram`，添加 t-string 相关的语法规则。实现 `tstring`、`tstring_middle`、`tstring_replacement_field`、`tstring_format_spec` 等产生式。确保 t-string 支持与 f-string 相同的表达式语法，包括 `=` 调试说明符、`!r`/`!s`/`!a` 转换说明符。

3. AST 扩展：修改 `Parser/Python.asdl`，添加 `TemplateStr` 和 `Interpolation` AST 节点类型。在 `Python/ast.c` 中实现 AST 构建逻辑，在 `Python/ast_opt.c` 中实现 AST 优化。

4. Template 对象实现：创建 `Objects/templateobject.c`，实现 `Template` 类型。该类型包含 `strings`（静态字符串元组）和 `interpolations`（插值对象元组）属性。实现 `values` 属性作为插值值的快捷访问，实现 `__iter__` 方法交替产生字符串和插值对象。支持 `+` 运算符进行模板拼接。

5. Interpolation 对象实现：创建 `Objects/interpolationobject.c`，实现 `Interpolation` 类型。该类型包含 `value`（表达式求值结果）、`expression`（原始表达式文本）、`conversion`（可选的 'r'、's'、'a' 转换类型）、`format_spec`（格式规范字符串）属性。生成对应的 clinic 文件 `Objects/clinic/interpolationobject.c.h`。

6. 代码生成器扩展：修改 `Python/codegen.c`，为 t-string 生成字节码。实现创建 `Template` 和 `Interpolation` 对象的指令序列，处理嵌套 t-string 的情况。

7. string.templatelib 模块：创建 `Lib/string/templatelib.py`，暴露 `Template` 和 `Interpolation` 类型。提供文档和类型注解，支持 `from string.templatelib import Template, Interpolation` 的导入方式。

8. tokenize 模块更新：修改 `Lib/tokenize.py`，添加对 t-string token 的支持，确保 Python 级别的词法分析工具能正确处理 t-string。

9. 测试套件：创建 `Lib/test/test_tstring.py`，覆盖 t-string 的各种使用场景。在 `Lib/test/test_string/test_templatelib.py` 中测试 `Template` 和 `Interpolation` 类型的行为。更新 `Lib/test/test_grammar.py` 和 `Lib/test/test_syntax.py` 以包含 t-string 语法测试。

10. 文档与构建：更新 `Doc/library/token.rst` 文档说明新的 token 类型。更新 `Doc/whatsnew/3.14.rst` 添加 PEP 750 的 What's New 条目。修改 `Makefile.pre.in`、`PCbuild/pythoncore.vcxproj` 等构建文件以包含新的源文件。

## Requirement
https://peps.python.org/pep-0750/
