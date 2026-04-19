# run-k-benchmark Skill: Multi-Agent Parallel Execution

Team lead 准备所有实验目录，agents 直接在各自 session 中并行执行 benchmark 编码任务。

## 快速开始

```bash
/run-k-benchmark K1:short,K1:long,K2:short,K2:long
```

这会：
1. Team lead 复制 4 个 repo 到 experiment 目录
2. Team lead 写入 hook 文件和 metadata
3. 创建 team + 4 个 tasks
4. 启动 4 个 agents（并行运行）
5. 每个 agent 直接在其 experiment 目录中编码

## 架构

```
/run-k-benchmark K3:short,K3:long,K4:short,K4:long
     ↓
[Phase 1: Team Lead 准备]
     ↓
1. 解析 4 个任务规范
2. 复制 4 个 repo → experiment/
3. 写入 auto_answer.py + settings.local.json × 4
4. 写入 run_metadata.json × 4
5. TeamCreate + TaskCreate × 4
     ↓
[Phase 2: Agent 并行执行]
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ agent-k3-s   │ agent-k3-l   │ agent-k4-s   │ agent-k4-l   │
│ 直接编码     │ 直接编码     │ 直接编码     │ 直接编码     │
│ (no subprocess) │ (no subprocess) │ (no subprocess) │ (no subprocess) │
└──────────────┴──────────────┴──────────────┴──────────────┘
```

## 关键设计决策

| 决策 | 说明 |
|------|------|
| Lead 负责初始化 | 所有 repo 复制、hook 写入、metadata 创建由 lead 完成 |
| Agent 直接执行 | Agent 在自身 session 中编码，不启动子进程 `claude` |
| 禁止 Memory | Agent 禁止 memory 工具，专注任务执行 |
| Hook 自动答题 | Lead 预先在每个实验目录写入 hook 配置 |

## 任务规范格式

`<TASK>:<TYPE>`

| 示例 | 说明 |
|------|------|
| `K1:short` | K1 的 short 提示 |
| `K1:long` | K1 的 long 提示 |
| `K1:short,K1:long,K2:short,K2:long` | K1-K2 全组合（4 agents） |

## 配置（硬编码）

| 设置 | 值 |
|------|-----|
| Model | opus |
| Permission Mode | bypassPermissions |
| Auto-reply | 第一个选项 (hook) |
| 并行数 | N = 任务数 |

## 与单脚本对比

| 方面 | 单脚本 (run_k_benchmark.sh) | Agent Teams |
|------|---------------------------|-------------|
| 并行 | 顺序或 & | 真并行 |
| 初始化 | 每个 task 自己 setup | Lead 统一 setup |
| 执行 | 子进程 claude | Agent 直接编码 |
| 监控 | 合并输出 | 独立 agent |
| 资源 | 单进程 | 多 agent 并行 |

## 最佳实践

1. **开发调试**: `/run-k-benchmark K1:short`
2. **批量运行**: `/run-k-benchmark K1:short,K1:long,K2:short,K2:long`
3. **全量运行**: `/run-k-benchmark K1:short,K1:long,...,K4:short,K4:long`

## 扩展

skill 的 task spec parser 支持通用格式，可扩展到：
- C1-C5 (CANN)
- M1-M3 (MindSpeed)
- T01-T50 (通用任务)
