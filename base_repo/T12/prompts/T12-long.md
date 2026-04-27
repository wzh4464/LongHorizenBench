# T12 – Consul: Mesh Gateways for WAN Federation

*Upstream reference:* https://github.com/hashicorp/consul/issues/6356 (implemented by https://github.com/hashicorp/consul/pull/6884). The full specification is inlined below; the implementing agent does not need network access.

## 1. Requirement

Extend Consul so that cross-datacenter WAN federation can flow through **mesh gateways** instead of requiring point-to-point TCP+UDP reachability between every server in every datacenter. When the feature is enabled, a new datacenter joining the federation only needs network access to the primary datacenter's mesh gateway endpoints; all Consul server-to-server traffic (Serf WAN gossip, server RPC, snapshot/restore, etc.) is tunnelled through the mesh gateways using the existing Connect TLS identity of the server.

## 2. Motivation

Historically, Consul's multi-datacenter WAN federation requires every server in every datacenter to be reachable by every other server on TCP 8300 (server RPC) and TCP/UDP 8302 (Serf WAN). In most real deployments this is not feasible:

- Kubernetes/VPC boundaries, dual-stack NAT, and enterprise firewalls break direct L3.
- Customers already operate a mesh-gateway edge for Connect service traffic; asking them to open a separate hole for control-plane traffic is an operational regression.
- The separate "federation" transport makes it hard to apply a consistent mTLS posture across the mesh.

Unifying everything through the mesh gateway collapses the control-plane and data-plane ingress to a single point of policy enforcement, simplifies the network model for operators, and makes WAN federation a first-class Connect citizen.

## 3. Detailed design

### 3.1 New `FederationState` resource

A new Raft-replicated resource `FederationState` represents the mesh gateway endpoints that external datacenters should dial when federating into the local DC:

```go
// in the Consul agent structs package
type FederationState struct {
    Datacenter         string
    MeshGateways       CheckServiceNodes      // latest gateway instances
    UpdatedAt          time.Time
    PrimaryModifyIndex uint64
    RaftIndex
}
```

- Each DC owns its own `FederationState`; primaries replicate every known DC's entry into secondaries so that any DC can discover any other DC's gateway set.
- The record is updated by a leader-only goroutine in every DC whenever the local `mesh-gateway` service catalog changes, so it stays within a few seconds of real-world state.

### 3.2 State-store methods

A new federation-state state-store module adds:

- `FederationStateSet(idx uint64, fs *structs.FederationState) error`
- `FederationStateGet(ws memdb.WatchSet, datacenter string) (uint64, *structs.FederationState, error)`
- `FederationStateList(ws memdb.WatchSet) (uint64, []*structs.FederationState, error)`
- `FederationStateDelete(idx uint64, datacenter string) error`

These are exposed through RPC endpoints `FederationState.Apply`, `FederationState.Get`, `FederationState.List` and `FederationState.Delete`.

### 3.3 Leader loops

- `leaderFederationStateAntiEntropy` — in the local datacenter, every 30 s walks the local mesh-gateway service registration and, if changed, writes a new `FederationState` record.
- `leaderReplicateFederationStates` (secondary DCs only) — every 30 s calls `FederationState.List` against the primary and upserts entries locally.

### 3.4 Dial path changes

On the client side (both for Serf WAN and inter-server RPC), when `use_mesh_gateway_wan_federation=true`:

1. Look up the local `FederationState[dc="self"]` to get the list of mesh gateways.
2. Open a TCP connection to one of those gateways.
3. Upgrade to TLS with the SNI set to `server.<target-dc>.<trust-domain>.consul`.
4. Hand the connection off to `memberlist` (for gossip) or `yamux/rpc` (for RPC).

The mesh gateway sees the SNI, recognises the `server.` prefix, and routes the connection to the remote DC's gateway, which in turn delivers it to the target server. This mirrors the pattern already used by Connect sidecars for cross-DC service-to-service traffic.

### 3.5 XDS updates

The mesh gateway's xDS listener must learn to serve `server.*` SNIs:

- The xDS gateway-listener generator emits a dedicated `public_listener` filter chain per remote DC with `server_names = ["server.<dc>.<trust_domain>"]`.
- Clusters point at the remote DC's mesh gateways (loaded from replicated `FederationState`).
- TCP proxy filter forwards the connection unchanged.

### 3.6 ACL model

New permissions are minimal: existing `operator:write` suffices to manipulate federation state; `service:*` on the mesh-gateway service identity covers the gateway xDS permissions. No new ACL resource is introduced.

## 4. Configuration surface

New agent options:

```hcl
connect {
  enable_mesh_gateway_wan_federation = true   # required on both ends
}

primary_gateways = ["1.2.3.4:8443", "5.6.7.8:8443"]         # for secondary DCs
primary_gateways_interval = "30s"                             # retry cadence
```

- `primary_gateways` on a secondary DC seeds the initial discovery; once federation is established, gateways are learned from `FederationState`.
- The flag is a no-op when set on only one end; both primary and secondary must agree before the secondary actually cuts over its WAN traffic.

## 5. Implementation Tasks

1. Add the `connect.enable_mesh_gateway_wan_federation`, `primary_gateways`, and `primary_gateways_interval` config knobs in the agent configuration layer with appropriate defaults and validation.
2. Introduce the `FederationState` type, state-store schema, and RPC endpoints (`FederationState.Apply/Get/List/Delete`).
3. Add cache type `federation-state-list` and stream the state for consumption by `proxycfg` / `xds` modules.
4. Implement a leader-side anti-entropy worker and a leader-side replication worker for primary↔secondary propagation; wire into the leader's loop.
5. Teach the Consul server RPC dispatcher and the Serf transport to dial via the mesh gateway when the feature flag is on, using the resolved `FederationState` for its target DC.
6. Extend the xDS server package so mesh gateway clusters include both user-service routes and the new `server.<dc>.*` / `gossip.<dc>.*` SNI entries.
7. Update the CLI (`consul federation-state …`) and HTTP API (the internal federation-state HTTP endpoint) with matching commands.
8. Add unit and integration tests covering primary/secondary bootstrap, replication latency, and gateway failover.

## 6. Acceptance Criteria

- With the feature disabled, existing multi-DC deployments behave identically.
- With the feature enabled on every server of every DC, traffic between DCs traverses only the mesh gateway (verifiable via tcpdump).
- Bringing down a gateway causes secondary DCs to fail over to another primary gateway within one `primary_gateways_interval`.
- `consul federation-state list` returns every DC's gateway set on any member.
- All existing Consul-server and xDS integration tests continue to pass; new tests cover the dual-mode and failover behaviour.
