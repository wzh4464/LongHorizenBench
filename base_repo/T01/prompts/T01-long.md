# T01: Apache Kafka

## Requirement
https://cwiki.apache.org/confluence/display/KAFKA/KIP-595%3A+A+Raft+Protocol+for+the+Metadata+Quorum

---

**Summary**: KIP-595 提出为 Kafka 元数据仲裁实现一个基于 Raft 的共识协议。该协议采用 Kafka 风格的 pull-based 复制模型，通过 Vote、BeginQuorumEpoch、EndQuorumEpoch 和 Fetch 四个核心 RPC 实现 leader 选举和日志复制，同时引入 DescribeQuorum API 用于监控仲裁状态。这是 Kafka 去除 ZooKeeper 依赖（KIP-500）的关键组件。

**Motivation**: Kafka 长期依赖外部 ZooKeeper 进行共识，但 Kafka 自身的日志复制协议已包含 Raft 的核心概念（单调递增的 epoch、基于 offset 的日志标识）。现有协议与标准 Raft 的主要差距在于 quorum commit 语义和 leader 选举机制。通过实现一个 "Kafka 风格的 Raft 方言"，可以在保持 pull-based 复制模型的同时获得 Raft 级别的共识保证，为元数据管理提供内置的高可用性，消除对外部协调服务的依赖。

**Proposal**: 创建一个独立的 `raft` 模块，实现完整的 Raft 协议栈。核心包括：四个 RPC 协议（Vote/BeginQuorumEpoch/EndQuorumEpoch/Fetch）的消息定义和请求处理、QuorumState 状态机管理、基于文件的持久化存储、KafkaRaftClient 主控制器、以及与 Kafka 网络层的集成。通过 feature flag 和配置参数控制 Raft 行为，支持 voter 和 observer 两种角色。

**Design Details**:

1. 协议消息定义：在 `clients/src/main/resources/common/message/` 下创建 Vote、BeginQuorumEpoch、EndQuorumEpoch、DescribeQuorum 四组请求/响应的 JSON schema，以及 LeaderChangeMessage 控制记录格式。在 `raft/src/main/resources/common/message/` 下定义 QuorumState 持久化格式。

2. API 注册：扩展 `ApiKeys` 枚举，添加 VOTE、BEGIN_QUORUM_EPOCH、END_QUORUM_EPOCH、DESCRIBE_QUORUM 四个新 API。为每个 API 实现对应的 Request/Response 类，处理序列化/反序列化和版本兼容。

3. 错误码扩展：在 `Errors` 枚举中添加 Raft 相关错误码（如 INCONSISTENT_VOTER_SET、FENCED_LEADER_EPOCH 等），用于表达共识协议特定的失败场景。

4. 控制记录支持：扩展 `ControlRecordType` 添加 LEADER_CHANGE 类型，实现 `ControlRecordUtils` 用于序列化/反序列化 leader 变更记录。扩展 `MemoryRecords` 和 `MemoryRecordsBuilder` 支持写入控制记录。

5. QuorumState 状态机：实现 `QuorumState` 类管理节点在 Unattached、Voted、Candidate、Leader、Follower 五种状态间的转换。每种状态由独立的状态类（如 `CandidateState`、`LeaderState`、`FollowerState`）封装，处理超时、投票收集、epoch 管理等逻辑。

6. 持久化层：实现 `QuorumStateStore` 接口和 `FileBasedStateStore` 实现，将当前 epoch、投票记录、已应用 offset 等关键状态持久化到文件，确保节点重启后状态恢复。

7. KafkaRaftClient 核心：实现主控制循环，处理：
   - 定时器管理（选举超时、fetch 超时）
   - 入站请求路由到相应状态处理器
   - 出站请求发送（投票请求、fetch 请求）
   - 日志复制和 commit 推进
   - Leader 变更检测和通知

8. 网络层集成：实现 `NetworkChannel` 接口和 `KafkaNetworkChannel` 实现，将 Raft 消息映射到 Kafka 网络协议。在 `SocketServer` 和 `KafkaApis` 中添加对 Raft API 的路由支持。

9. 元数据日志：实现 `ReplicatedLog` 接口和 `KafkaMetadataLog` 实现，封装 Kafka Log 类提供 Raft 所需的日志操作（append、truncate、read、snapshot）。

10. 配置与指标：定义 `RaftConfig` 配置类，包含 quorum.voters、超时参数等。实现 `KafkaRaftMetrics` 收集选举延迟、commit 延迟、复制 lag 等指标。

11. 构建配置：在 `build.gradle` 中添加 `:raft` 子项目，配置依赖、消息生成任务、checkstyle 规则。更新 `settings.gradle` 包含新模块。

12. 测试：编写全面的单元测试覆盖状态机转换、选举场景、日志复制、网络故障恢复等。实现 Mock 类（MockLog、MockNetworkChannel 等）支持确定性测试。
