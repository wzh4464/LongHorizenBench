# T50: Kubernetes — Dynamic Resource Allocation (KEP-3063)

## Requirement source

*Upstream KEP*: KEP-3063 "Dynamic Resource Allocation" in the kubernetes/enhancements repository. The KEP is the authoritative spec — implement against what it says, not against the summary below.

## 1. Motivation

Today, container resource needs are expressed via `ResourceRequirements`
(opaque resource counts) and the legacy device plugin framework, neither of
which is rich enough for modern accelerators. They cannot:

- Express that two pods need to share the same device, or that a single pod
  needs a specific topology of devices.
- Carry per-claim driver-specific parameters.
- Allocate devices that span beyond a single node.
- Allow third-party drivers to participate in scheduling decisions.

KEP-3063 introduces **Dynamic Resource Allocation (DRA)** in the new
`resource.k8s.io` API group: pods describe their needs as `ResourceClaim`
objects, and a per-driver controller (or, in newer iterations, the scheduler
itself, using "structured parameters") allocates concrete devices and writes
the result back into the claim's status. Kubelet picks up the allocation when
the pod is admitted and prepares the resources on the node before the
container starts.

## Goals

- Workloads describe device needs declaratively in a Kubernetes API resource
  (`ResourceClaim`/`ResourceClaimTemplate`).
- Drivers (or the scheduler with structured parameters) allocate devices to
  claims; allocation can be deferred until the pod is scheduled (`WaitForFirstConsumer`)
  or done eagerly (`Immediate`).
- Pods reference claims via the new `pod.spec.resourceClaims` field; containers
  in the pod opt into individual claims.
- Kubelet exposes a gRPC plugin contract with the on-node driver
  (`NodePrepareResources`/`NodeUnprepareResources`) so per-claim resources
  (devices, mounts, env vars, CDI annotations) are prepared just before
  containers start and torn down after they exit.

## Goals

- Provide a portable, vendor-neutral way for workloads to claim resources
  that are richer than what the existing `requests/limits` machinery can
  express (GPUs with mode, RDMA NICs with virtualisation level, FPGA
  bitstreams, etc.).
- Allow a per-pod resource scheduling decision to involve a vendor-specific
  controller without coupling that controller into the kubelet or kube-scheduler
  binaries.
- Keep all ownership, GC, and quota semantics consistent with the rest of
  Kubernetes by representing claims as first-class API objects.

## Non-Goals

- Replacing the existing device plugin framework outright. DRA and device
  plugins coexist; vendors can choose either.
- Defining a portable "device language" — DRA is a framework. The schemas
  for class parameters, claim parameters, and structured parameter selectors
  are vendor-specific.

## API surface

The KEP introduces the following types under the `resource.k8s.io` API group:

- `ResourceClass`: cluster-scoped, vendor-neutral declaration of a class of
  resources, referencing a driver and optional parameter object.
- `ResourceClaim`: namespace-scoped object representing a request, with
  parameters, allocation result, and reservedFor list.
- `ResourceClaimTemplate`: pod-scoped template that the controller materialises
  into a `ResourceClaim` per-pod, similar to PVC templates for StatefulSets.
- `PodSchedulingContext`: scheduler/driver coordination object that records
  potential nodes, the selected node, and per-driver scheduling state.

Allocation modes:

- `Immediate`: allocator runs as soon as the claim is created.
- `WaitForFirstConsumer`: the claim is left pending until a pod that uses it is
  ready to be scheduled, allowing per-pod context to influence allocation.

Reservation semantics:

- A claim can be reserved by one or more pods (controlled by
  `claim.spec.allocation.shareable`); the controller revokes the reservation
  when the consuming pods finish.

Pod plumbing:

- `Pod.Spec.ResourceClaims` lists the claims (or claim templates) the pod
  needs.
- `Container.Resources.Claims` references a subset of the pod's claims by
  local name; the kubelet uses this to set up runtime resources for the
  container only.

## Scheduler & kubelet integration

- The scheduler runs a `DynamicResources` plugin that defers binding until
  every claim is allocated (or, with structured parameters, allocates the
  claim itself in `Reserve`/`Bind`).
- The kubelet maintains a Plugin gRPC channel to each registered DRA driver
  and calls `NodePrepareResources` before container startup and
  `NodeUnprepareResources` on cleanup, mirroring the CSI lifecycle.
- All node-level state (claim → CDI device list, prepared/unprepared) is
  durably checkpointed so restarts do not strand allocations.

## Feature gates and APIs

- `DynamicResourceAllocation` gates the API group `resource.k8s.io`, the
  scheduler plugin, and the kubelet plumbing.
- `DRAControlPlaneController` (alpha) gates the older external-controller
  flow that uses `PodSchedulingContext` and a vendor controller.
- The two flows can coexist; the structured-parameters flow is the
  long-term direction.

## Test plan

- Unit tests for: validation, controller reconciliation, scheduler plugin
  filter/score/reserve/postbind transitions, kubelet plugin manager.
- Integration tests for: claim allocation modes, reserved-for lifecycle,
  pod admission denial when claims are missing, GC of claims with deleted
  pods.
- E2E with a test driver in `test/e2e/dra` covering: scheduling with
  structured parameters, two-claim pods, claim sharing, restart of the
  driver during pod startup, restart of kubelet during prepare/unprepare.

## Implementation Task

Implement the alpha for KEP-3063 / KEP-4381 (structured parameters):

1. Add the `resource.k8s.io` API group with `ResourceClass`,
   `ResourceClaim`, `ResourceClaimTemplate`, `PodSchedulingContext`,
   and (for structured parameters) `ResourceSlice` /
   `DeviceClass` / `ResourceClaim` parameter types as described in
   the KEP.
2. Wire a new `DynamicResources` scheduler plugin that drives
   `WaitForFirstConsumer` allocations through the
   `PodSchedulingContext` lifecycle, and (when structured parameters
   are enabled) performs in-scheduler allocation.
3. Add a kubelet plugin manager hook so DRA drivers can register
   over the kubelet plugin socket and receive
   `NodePrepareResources` / `NodeUnprepareResources` calls before
   container start.
4. Provide a feature gate `DynamicResourceAllocation` that guards
   the group registration, scheduler plugin, and kubelet plumbing.
5. Add admission/quota integration so claims and templates count
   against existing quota and namespaces.
6. Add tests at unit, integration, and (where feasible) e2e levels
   following the test plan above.

The PR layout, generated code, and exact package locations are not
prescribed by the KEP — implement them following Kubernetes
conventions for new API groups.
