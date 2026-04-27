# T34: Kubernetes — KEP-5598 Opportunistic Batching for the Scheduler

## Requirement (inlined from KEP-5598)

*Upstream source (do not fetch):* `https://github.com/kubernetes/enhancements/blob/master/keps/sig-scheduling/5598-opportunistic-batching/README.md`. The relevant content is reproduced below; no external access is needed.

### Summary

Today the kube-scheduler processes pods one at a time. For each pod it executes the full PreFilter / Filter / PostFilter / PreScore / Score pipeline, and then commits the binding. When a controller (Deployment, StatefulSet, Job, …) emits many similar pods at once, almost all of that work is duplicated. KEP-5598 adds an *opportunistic batching* mechanism: pods whose scheduling-relevant attributes are identical produce the same **pod signature**, and the scheduler can reuse the result of one full pipeline evaluation for every subsequent pod that shares the signature, falling back to a fresh evaluation only when something invalidates the prior result.

The KEP is intentionally limited to the simple "1-pod-per-node" workloads that appear most often in batch and inference workloads. It does not introduce true gang scheduling, but it lays the groundwork (signatures, validation, fast path) for future gang-scheduling work.

### Motivation

* For Jobs that schedule thousands of identical pods, the filtering and scoring phases dominate scheduler latency. Reusing the per-cycle work would amortise that cost across the entire batch.
* The 1-pod-per-node pattern is increasingly common (training jobs, inference serving, stateful operators) and is naturally amenable to a shared scheduling result.
* Existing scheduler optimisations (Equivalence cache, Equivalence Class, etc.) were considered too narrow or too tightly coupled to the legacy scheduler architecture.

### Design

#### Pod signature
Each plugin that participates in scheduling decisions optionally exposes a new method `SignPod(pod *v1.Pod) (SignatureFragment, error)`. The framework concatenates the returned fragments to compute the pod's `Signature` (a `[]byte`). Pods whose signature returns an error or `nil` from any contributing plugin are treated as "non-batchable" and follow the regular path.

The plugins that are expected to contribute fragments are listed in the KEP (see `Plugin Sign Behaviour` table). They include `NodeAffinity`, `NodeResources`, `NodeName`, `TaintToleration`, `PodTopologySpread`, `PodAffinity`, `VolumeBinding`, etc. Each plugin's fragment is a hash over the parts of the pod spec it consults; e.g. `NodeAffinity` hashes only `pod.spec.nodeAffinity`, `NodeResources` hashes only `pod.spec.containers[*].resources`. Plugins that depend on cluster state (e.g. `InterPodAffinity`) opt out and force the pod into the slow path.

#### `BatchEntry` cache

The scheduler maintains an in-memory map `signature -> BatchEntry` where:

```go
type BatchEntry struct {
    Node string                  // node selected by the previous identical pod
    SnapshotVersion uint64       // version of the cluster snapshot when this entry was created
    NodeInfo *framework.NodeInfo // pointer to the node that won
    Score    int64               // accumulated score from the previous schedule cycle
}
```

Entries are evicted when:
1. The cluster snapshot version advances (capacity changes, taints, allocatable, etc.) and a `Refresh()` call invalidates them.
2. The TTL passes (default 5 seconds).
3. Memory pressure: the cache is bounded.

#### `GetNodeHint` flow

```
fast := scheduler.fastPath(pod)
if fast != nil && fast.SnapshotVersion == cur && fast.Node still admits pod {
   bind(pod, fast.Node)
} else {
   normal scheduling; if signature exists, store result
}
```

### Plugin signing concepts

Each plugin implements:

```go
type Signer interface {
    SignPod(p *v1.Pod) ([]byte, error)
}
```

returning a deterministic, plugin-local hash of the relevant pod fields. The framework concatenates the byte slices in a fixed plugin order and feeds them to FNV-1a (the spec only requires a stable hash). Plugins that cannot produce a hash (e.g. they depend on dynamic cluster state) return an error, which makes the pod ineligible for batching.

### Cache correctness rules

1. The cache is invalidated when the snapshot version advances.
2. Plugins that advertise themselves as snapshot-sensitive can ask for cache invalidation when their internal data changes.
3. After a successful bind, the cache stores `(signature → node, snapshotVersion)`.
4. Before reusing a cached node, the scheduler re-runs the binding-permit hooks (DRA reservation, reservation arbiter, etc.); only the filter/score work is skipped.

### Feature gate

The KEP proposes one feature gate:

```
SchedulerOpportunisticBatching   alpha (default false)
```

The gate covers all behavioural changes; when `false` the scheduler is byte-for-byte identical to the unmodified version.

### Acceptance criteria (per the KEP)

* When the cache is warm, p99 scheduling latency for a homogeneous batch of pods drops by at least 50%.
* No identical pod sees a different scheduling decision under cache hit vs. cache miss.
* Existing single-pod scheduling APIs and external behaviour are unchanged.
* Feature gate disabled = no behaviour change vs. upstream main.
