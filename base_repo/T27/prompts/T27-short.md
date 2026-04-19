**Summary**: PEP 750 引入模板字符串（t-strings），作为 f-strings 的泛化形式。与 f-strings 直接求值为字符串不同，t-strings 使用 `t` 前缀，求值后产生 `Template` 对象。该对象包含静态字符串部分和插值部分的结构化信息，允许开发者在字符串最终组合之前访问和处理这些组成部分，从而支持 HTML 转义、SQL 注入防护、结构化日志等安全关键场景。

**Proposal**: 在 CPython 中实现模板字符串功能，在词法分析器中添加 t-string 相关 token 类型，在语法解析器中支持 t-string 语法，创建新的 `Template` 和 `Interpolation` 内置类型并在 `string.templatelib` 模块中暴露 Python 接口，支持模板字符串的拼接和迭代，以及相应的测试和文档。
