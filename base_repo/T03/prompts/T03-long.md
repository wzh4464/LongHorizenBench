# T03: Apache Kafka

## Requirement
https://cwiki.apache.org/confluence/display/KAFKA/KIP-460%3A+Admin+Leader+Election+RPC

---

**Summary**: KIP-460 扩展 Kafka Admin API，提供统一的 leader election 接口。新增 `electLeaders` API 支持两种选举类型：PREFERRED（首选副本选举）和 UNCLEAN（非清洁选举，在没有同步副本时选举第一个活跃副本）。同时引入新的 ElectLeaders RPC 协议，废弃原有的 electPreferredLeaders API，并提供 kafka-leader-election.sh 命令行工具。

**Motivation**: 当前用户触发非清洁 leader election 需要修改主题或 broker 配置（unclean.leader.election.enable），这存在安全隐患——用户可能忘记禁用配置，导致后续自动触发非清洁选举造成数据丢失。提供一次性的 API 调用方式更加安全可控。同时，现有 electPreferredLeaders API 命名和设计较为局限，无法扩展支持其他选举类型。

**Proposal**: 引入新的 `electLeaders(ElectionType, Set<TopicPartition>, ElectLeadersOptions)` Admin API，通过 ElectionType 枚举区分选举类型。实现新的 ElectLeaders RPC 协议（替代 ElectPreferredLeaders），在 Controller 层实现两种选举逻辑。废弃旧 API 但保持向后兼容，新 CLI 工具 kafka-leader-election.sh 替代 kafka-preferred-replica-election.sh。

**Design Details**:

1. ElectionType 枚举（clients/src/main/java/org/apache/kafka/common/ElectionType.java）：定义 PREFERRED（值 0）和 UNCLEAN（值 1）两种选举类型。PREFERRED 选举首选副本（副本列表第一个）为 leader，UNCLEAN 在 ISR 为空时选举任意活跃副本。

2. 协议消息定义（clients/src/main/resources/common/message/）：创建 ElectLeadersRequest.json 和 ElectLeadersResponse.json。Request 包含 election_type 字段和 topic_partitions 列表；Response 包含顶层 error_code（用于集群授权错误）和每分区结果。

3. Request/Response 类（clients/src/main/java/org/apache/kafka/common/requests/）：实现 ElectLeadersRequest 和 ElectLeadersResponse 类，处理协议版本兼容、序列化/反序列化。旧版本（v0）仅支持 PREFERRED 类型以保持兼容。

4. Admin API 扩展（clients/src/main/java/org/apache/kafka/clients/admin/）：
   - 在 AdminClient 接口添加 `electLeaders` 方法
   - 实现 ElectLeadersOptions 和 ElectLeadersResult 类
   - 将 electPreferredLeaders 标记为 @Deprecated，内部委托到 electLeaders
   - 实现 ElectPreferredLeadersResult 包装类保持旧 API 兼容

5. KafkaAdminClient 实现：在 KafkaAdminClient 中实现 electLeaders 逻辑，构造 ElectLeadersRequest 发送到 Controller，处理响应并填充 ElectLeadersResult。

6. 错误码扩展（Errors.java）：添加 ELECTION_NOT_NEEDED（当分区已有 leader 且选举不必要）和 ELIGIBLE_LEADERS_NOT_AVAILABLE（UNCLEAN 选举时没有活跃副本）错误码。

7. Controller 层实现（core/src/main/scala/kafka/controller/）：
   - 扩展 KafkaController 处理 ElectLeaders 请求
   - 实现 Election.scala 中的选举逻辑，区分 PREFERRED 和 UNCLEAN 模式
   - UNCLEAN 模式下忽略主题配置，直接根据请求执行选举
   - 更新 PartitionStateMachine 支持两种选举触发方式

8. Server 端请求处理（KafkaApis.scala）：添加 handleElectLeaders 方法路由请求到 Controller，处理授权检查和响应构造。

9. 延迟操作（DelayedElectLeader.scala）：实现延迟选举操作类，支持选举的异步完成和超时处理。

10. CLI 工具：
    - 创建 bin/kafka-leader-election.sh（Linux）和 bin/windows/kafka-leader-election.bat（Windows）
    - 实现 LeaderElectionCommand.scala 命令行解析，支持 --election-type、--topic、--partition、--all-topic-partitions 等参数
    - 废弃 kafka-preferred-replica-election.sh

11. ZooKeeper 集成（KafkaZkClient.scala）：更新 ZK 路径操作以支持新的选举记录存储和读取。

12. 测试：
    - KafkaAdminClientTest 添加 electLeaders 单元测试
    - AdminClientIntegrationTest 添加端到端集成测试
    - PartitionStateMachineTest 添加选举逻辑测试
    - RequestResponseTest 验证协议序列化
