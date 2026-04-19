# T12: Consul - 通过 Mesh Gateway 实现 WAN 联邦

## Summary

Consul 1.6.0 引入的 Mesh Gateway 功能要求各数据中心的服务器仍需直接可达，这在网络隔离环境中造成安全隐患和部署困难。本任务需要实现通过 Mesh Gateway 进行 WAN 联邦的功能，使多个数据中心之间的 Consul 服务器只需通过 Mesh Gateway 通信，无需直接的服务器间网络连接。

## Motivation

当前 Consul 的多数据中心联邦存在以下问题：

- **安全风险**：各 DC 的 Consul 服务器必须直接暴露在共享网络上，增加攻击面
- **网络复杂性**：在 overlay 网络或复杂网络拓扑中，服务器间的直接路由难以实现
- **运维负担**：需要为服务器配置额外的网络规则和防火墙策略

通过 Mesh Gateway 进行 WAN 联邦可以：
- 仅需暴露 Mesh Gateway 到 WAN，服务器保持在内网
- 利用已有的 Mesh Gateway 基础设施
- 简化网络配置和安全策略

## Proposal

实现一种新的 WAN 联邦模式，使 Consul 服务器之间的所有通信（包括 Gossip 和 RPC）都通过 Mesh Gateway 中转：

1. 添加新的配置选项启用基于 Mesh Gateway 的 WAN 联邦
2. 修改 Serf/Memberlist 以支持纯 TCP 模式的 Gossip 通信
3. 实现 Federation State 机制来分发各 DC 的 Mesh Gateway 地址
4. 通过 SNI 路由和 TLS ALPN 实现不同协议的多路复用
5. 扩展 xDS/Envoy 配置以支持服务器端点的暴露

## Design Details

1. **配置选项**：添加 `connect.enable_mesh_gateway_wan_federation` 配置项，在 `agent/config` 包中定义并解析该选项，更新运行时配置结构。

2. **Federation State 数据结构**：在 `agent/structs` 中定义 `FederationState` 结构体，存储每个 DC 的 Mesh Gateway 地址列表；实现相应的 Raft FSM 操作（Apply, Snapshot, Restore）。

3. **Federation State RPC**：实现 `FederationState.Apply`、`FederationState.Get`、`FederationState.List`、`FederationState.ListMeshGateways` 等 RPC 端点；添加 ACL 权限检查。

4. **Federation State 复制**：在 Secondary DC 中实现从 Primary DC 复制 Federation State 的逻辑；实现 Anti-Entropy 机制，Secondary DC 定期将本地 Mesh Gateway 信息同步到 Primary DC。

5. **Gateway Locator**：实现 `GatewayLocator` 组件，负责选择合适的 Mesh Gateway 地址用于 RPC 和 Gossip 操作；支持从 Federation State 和 fallback 地址两个来源获取网关地址。

6. **RPC 协议扩展**：修改服务器的 RPC 端口（:8300）处理逻辑，通过嗅探首字节判断是否为 TLS 连接；使用 ALPN 头区分不同协议类型（普通 RPC、Gossip packet、Gossip stream）。

7. **WAN Federation Transport**：实现 `wanfed.Transport`，包装 `memberlist.NetTransport`；同 DC 内通信走原有路径，跨 DC 通信通过 TLS+ALPN 封装后经 Mesh Gateway 转发。

8. **Retry Join 修改**：调整 WAN retry join 逻辑，支持通过 Mesh Gateway 地址进行初始化 join；客户端模式下禁用 WAN retry join。

9. **Mesh Gateway xDS 配置**：在 `proxycfg` 和 `xds` 包中添加对服务器暴露的支持；生成额外的 Envoy cluster 配置，包括通配符 SNI 路由和每节点的专用路由。

10. **TLS 证书扩展**：扩展 `consul tls cert create` 命令，添加 `-node` 参数以在证书中包含节点名 SAN，支持 `<node>.server.<dc>.consul` 格式的 SNI 路由。

## Requirement

https://github.com/hashicorp/consul/issues/6356
