**Summary**: Java 的 `final` 字段本意是表示不可变，但当前反射 API（`Field.set`）和 JNI 允许修改 final 字段的值。JEP 500 提出逐步限制对 final 字段的修改能力，在过渡期内通过警告、命令行选项和 JFR 事件帮助开发者识别和修复依赖此行为的代码，最终目标是让 final 真正意味着不可变。

**Proposal**: 为反射修改 final 字段引入可配置的行为模式（allow/warn/debug/deny），通过命令行选项 `--sun-misc-unsafe-memory-access` 和模块系统的 `--add-opens` 控制。同时增加 JFR 事件记录 final 字段修改，帮助诊断问题。对于特殊的"可变静态 final 字段"（如 `System.in/out/err`）保持允许修改，JNI 侧增加警告日志和检查。
