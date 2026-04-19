**Summary**: KIP-595 提出为 Kafka 元数据仲裁实现一个基于 Raft 的共识协议。该协议采用 Kafka 风格的 pull-based 复制模型，通过 Vote、BeginQuorumEpoch、EndQuorumEpoch 和 Fetch 四个核心 RPC 实现 leader 选举和日志复制，同时引入 DescribeQuorum API 用于监控仲裁状态。这是 Kafka 去除 ZooKeeper 依赖（KIP-500）的关键组件。

**Proposal**: 创建一个独立的 `raft` 模块，实现完整的 Raft 协议栈，包括四个 RPC 协议的消息定义和请求处理、QuorumState 状态机管理、基于文件的持久化存储、KafkaRaftClient 主控制器、以及与 Kafka 网络层的集成。通过 feature flag 和配置参数控制 Raft 行为，支持 voter 和 observer 两种角色。
