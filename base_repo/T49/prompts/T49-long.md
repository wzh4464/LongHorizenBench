# T49: Kubernetes — In-Place Update of Pod Resources (KEP-1287)

## Requirement source

Source: KEP-1287 ("In-Place Update of Pod Resources") in `kubernetes/enhancements/keps/sig-node/`. The KEP is the source of truth — implement to its specified API and behaviour. The information below summarises the KEP; you may consult the KEP for any detail not duplicated here.

## Motivation

Pod resource requests/limits are immutable today. Changing resource allocation for a running workload requires recreating the pod, which restarts the containers and disrupts in-flight work. KEP-1287 makes `spec.containers[*].resources.requests` and `.limits` mutable while the pod is running, with kubelet driving the actual cgroup updates and the API surface tracking both desired and actual state.

## Goals

1. Allow `spec.containers[i].resources.requests` and `.limits` for `cpu` and `memory` to be changed via a dedicated `/resize` subresource on `Pod`.
2. Let pod authors declare per-resource policy for resize: whether changing the value requires a container restart (`RestartContainer`) or can be applied in place (`NotRequired`).
3. Track resize lifecycle in `Pod.Status` so that controllers and humans can see why a desired resize has not yet taken effect.
4. Preserve the QoS class of the pod across resizes (no transitions between BestEffort, Burstable, and Guaranteed).

## Non-goals

- Resizing GPUs / extended resources / hugepages.
- Vertical autoscaling (HPA/VPA reuse the new API but are out of scope).
- Resizing init or ephemeral containers.

## API surface

A new container-level field `ResizePolicy` is added:

```go
type ContainerResizePolicy struct {
    // ResourceName is the name of the resource ("cpu" or "memory").
    ResourceName ResourceName
    // RestartPolicy is "NotRequired" or "RestartContainer".
    RestartPolicy ResourceResizeRestartPolicy
}

type Container struct {
    // ... existing fields ...
    ResizePolicy []ContainerResizePolicy
}
```

The `Pod` type gets a new subresource, `resize`, accepting a partial pod spec that contains only `spec.containers[*].resources` (and the related ResizePolicy entries). Updates to `spec.containers[*].resources` directly on the main `Pod` resource are rejected.

`PodStatus` gains:
- `Resize` (string): one of `Proposed`, `InProgress`, `Deferred`, `Infeasible`, `""` (none).
- `Resources` (per-container): the actual allocated resources after the most recent resize.

## Behaviour

The resize loop:

1. User submits `PUT /pods/<name>/resize` with the new `resources`.
2. API server validates: not changing `requests`/`limits` to QoS-violating values, no add/remove of containers, only `cpu` / `memory` allowed.
3. Pod's `status.resize` is set to `Proposed`.
4. Kubelet on the assigned node observes the desired state and either:
   - Accepts and applies via CRI `UpdateContainerResources`, transitions through `InProgress` to none.
   - Rejects (insufficient node capacity) and sets `Deferred` (will retry) or `Infeasible` (won't retry).
5. The container's `ResizePolicy` (per resource, per container) controls whether a restart is required to apply the new value.

Restart policies for resize per resource:
- `NotRequired`: kubelet attempts to apply the change without restarting the container. If the runtime cannot support an in-place update for that resource (e.g. some runtimes can resize CPU but not memory), kubelet falls back to `RestartContainer`.
- `RestartContainer`: kubelet restarts the container as part of applying the change.

`PodSpec` also gains `Resources` at the pod level (alpha-gated by `PodLevelResources`); resizing via the pod-level field is part of the same feature in newer iterations of the KEP.

## Status reporting

The following is added to `PodStatus`:

- `Resize` (string) — describes the current state of the resize operation: `""`, `Proposed`, `InProgress`, `Deferred`, `Infeasible`, `Error`.
- `ContainerStatuses[i].Resources` — the resources currently active in the running container (as observed from the runtime), distinct from the desired `spec` values.
- `ContainerStatuses[i].AllocatedResources` — the resources kubelet has admitted (may differ from `spec.containers[i].resources` while a resize is being processed).

## Resize subresource

To make changes a kubelet can act on, the API server adds a `resize` subresource on Pods. Only `spec.containers[*].resources` (and the per-pod-level resources, when applicable) and `spec.containers[*].resizePolicy` are mutable through this subresource.

Each container has a per-resource `ResizePolicy` list:

```go
type ContainerResizePolicy struct {
    ResourceName  ResourceName               // "cpu" or "memory"
    RestartPolicy ResourceResizeRestartPolicy // "NotRequired" | "RestartContainer"
}
```

Defaults: `RestartContainer` for memory; `NotRequired` for CPU.

## Feature gate

`InPlacePodVerticalScaling` (kubelet, kube-apiserver, kube-controller-manager). When the gate is off, the new fields are dropped on POST/PUT and the `/resize` subresource is unregistered. There is also a `InPlacePodVerticalScalingExclusiveCPUs` gate that scopes the feature on nodes using exclusive CPU pinning.

## Kubelet behaviour

Kubelet uses the per-container `ResizePolicy` to decide between an in-place cgroup update via the runtime's `UpdateContainerResources` CRI call, and a restart-driven update. Resize requests that cannot be satisfied within the node's available capacity are deferred or marked infeasible; a status condition `PodResizeInProgress` is emitted while a resize is being applied.

## Test plan

Per the KEP, tests cover: API validation under feature-gate flips, default values for `ResizePolicy`, conflict detection between resources and limits, the new `/resize` subresource, kubelet `UpdateContainerResources` integration, scheduler accounting against allocated rather than requested resources, and end-to-end pod-resize scenarios (CPU-only, memory-only, restart-required, deferred, infeasible).

## Implementation scope

Implementations must touch (in summary):

1. The core API: add `Resources` and `ResizePolicy` to the container spec; add `AllocatedResources` and per-container resize status to `PodStatus`; register the `/resize` subresource.
2. API server validation, defaulting, drop-on-no-feature-gate logic, and the `/resize` subresource handlers.
3. Kubelet: on observing a resize, plan whether the change can be applied in-place, ask the runtime via the CRI `UpdateContainerResources` call, observe success/failure, and update `PodStatus`. Honour `RestartContainer` semantics when the policy demands it.
4. Scheduler: account for `Pod.Status.AllocatedResources` (rather than spec) so that pending resizes do not over-commit a node.
5. CRI: pass the new resource configuration through to the container runtime.

The KEP intentionally leaves package and file layout to the implementer; do not invent specific paths beyond what the KEP itself references in its design discussion (such as the kubelet's container manager or the CRI plumbing).

## Acceptance / verification

- Patching a running pod's container resources via the `/resize` subresource succeeds when the node has capacity, with no container restart for `NotRequired` policies.
- Resizes that exceed node capacity are reported as `Deferred` or `Infeasible` via the per-container resize status.
- The pod's QoS class is preserved across in-place resize.
- Disabling the `InPlacePodVerticalScaling` feature gate hides the resize subresource and ignores any resize fields in the spec.
