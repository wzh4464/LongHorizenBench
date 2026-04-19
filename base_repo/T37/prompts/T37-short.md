**Summary**: JEP 476 提出引入模块导入声明（Module Import Declarations）功能，允许开发者通过 `import module M;` 语法导入一个模块导出的所有包。这是一个预览特性，旨在简化模块化程序中的导入语句，特别是在学习和原型开发阶段。

**Proposal**: 引入新的导入语法 `import module M;`，该语句将导入模块 M 直接或间接导出的所有公共顶级类和接口。这是一个预览特性，需要通过 `--enable-preview` 启用。同时更新 JShell 默认启动脚本以使用新的模块导入功能。
