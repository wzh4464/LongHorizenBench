# T17: Ruff

**Summary**: Ruff 目前的许多配置选项只能通过配置文件设置，无法通过命令行覆盖。本任务要求实现 CLI 配置覆盖功能，允许用户通过 `--config KEY=VALUE` 的形式在命令行中指定或覆盖任意配置选项，使用户无需修改配置文件即可调整 Ruff 的行为。

**Motivation**: 当前 Ruff 用户面临两个痛点：(1) 某些配置选项没有对应的 CLI flag，只能通过 `pyproject.toml` 或 `ruff.toml` 设置；(2) 用户有时需要临时覆盖某个配置选项进行单次运行，但不想修改配置文件。这在 CI/CD 流水线、脚本化使用、以及快速调试场景中尤为不便。许多类似工具（如 Cargo）支持通过 `--config` 选项传递配置覆盖，Ruff 也应提供此能力。

**Proposal**: 扩展 `--config` 参数使其能够接受两种类型的输入：(1) 配置文件路径（原有功能）；(2) TOML 格式的 `KEY=VALUE` 配置覆盖。配置覆盖的优先级高于所有配置文件。同时需要处理 `--config` 与 `--isolated` 的交互逻辑：指定配置文件与 `--isolated` 冲突，但配置覆盖与 `--isolated` 可以共存。

**Design Details**:

1. 参数解析重构：修改 `args.rs` 中 `--config` 参数的定义。将其从 `Option<PathBuf>` 改为 `Vec<SingleConfigArgument>`，支持多次指定。引入 `SingleConfigArgument` 枚举类型，区分文件路径和配置覆盖两种情况。

2. 配置参数解析器：实现 `ConfigArgumentParser` 作为 clap 的自定义 value parser。解析逻辑：如果参数包含 `=` 且可以解析为有效的 TOML 键值对，则视为配置覆盖；否则视为文件路径。使用 `toml` crate 解析配置覆盖字符串。

3. 配置聚合结构：创建 `ConfigArguments` 结构体管理所有配置来源。包含三个字段：`config_file`（可选的配置文件路径）、`overrides`（`--config KEY=VALUE` 覆盖）、`per_flag_overrides`（专用 flag 覆盖如 `--line-length`）。实现优先级：per_flag_overrides > overrides > config_file。

4. 与 isolated 模式的交互：移除 `--config` 与 `--isolated` 的 clap 层面冲突声明。在解析后检查：如果同时指定了 `--isolated` 和配置文件路径，则报错；如果指定了 `--isolated` 和配置覆盖，则允许（覆盖仍然生效）。

5. 命令集成：更新 `CheckCommand` 和 `FormatCommand` 使用新的 `ConfigArguments` 类型。修改 `resolve.rs` 中的配置解析逻辑，在构建最终配置时应用覆盖。

6. Options 转换：实现从 TOML 键值对到 `Options` 结构的转换。利用现有的 `ruff_workspace::options::Options` 类型和 `Configuration::from_options` 方法。

7. 错误处理：为无效的 TOML 语法、不存在的配置键、类型不匹配等情况提供清晰的错误消息。

8. 文档更新：更新 `docs/configuration.md` 说明新的 `--config` 用法和优先级规则。

## Requirement
https://github.com/astral-sh/ruff/issues/8368
