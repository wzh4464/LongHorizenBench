**Summary**: Consul 1.6.0 引入的 Mesh Gateway 功能要求各数据中心的服务器仍需直接可达，这在网络隔离环境中造成安全隐患和部署困难。本任务需要实现通过 Mesh Gateway 进行 WAN 联邦的功能，使多个数据中心之间的 Consul 服务器只需通过 Mesh Gateway 通信，无需直接的服务器间网络连接。

**Proposal**: 实现一种新的 WAN 联邦模式，使 Consul 服务器之间的所有通信（包括 Gossip 和 RPC）都通过 Mesh Gateway 中转。添加新配置选项启用该模式，修改 Serf/Memberlist 支持纯 TCP Gossip，实现 Federation State 机制分发网关地址，通过 SNI 路由和 TLS ALPN 实现协议多路复用，并扩展 xDS 配置支持服务器端点暴露。
