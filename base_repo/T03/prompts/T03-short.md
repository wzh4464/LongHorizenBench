**Summary**: KIP-460 扩展 Kafka Admin API，提供统一的 leader election 接口。新增 `electLeaders` API 支持两种选举类型：PREFERRED（首选副本选举）和 UNCLEAN（非清洁选举，在没有同步副本时选举第一个活跃副本）。同时引入新的 ElectLeaders RPC 协议，废弃原有的 electPreferredLeaders API，并提供 kafka-leader-election.sh 命令行工具。

**Proposal**: 引入新的 `electLeaders(ElectionType, Set<TopicPartition>, ElectLeadersOptions)` Admin API，通过 ElectionType 枚举区分选举类型。实现新的 ElectLeaders RPC 协议替代 ElectPreferredLeaders，在 Controller 层实现两种选举逻辑，废弃旧 API 但保持向后兼容，新 CLI 工具替代旧版命令行。
