# T43: Kubernetes — Configurable Container Stop Signals (KEP-4960)

## Requirement source

The behaviour to implement is defined by KEP-4960, "Container Stop Signals", in the
`kubernetes/enhancements` repository (sig-node). This file inlines the parts of the
KEP that drive the implementation. Use the KEP as the source of truth; do not invent
file paths, type names, or test locations beyond what is described here.

## 1. Summary

OCI container images can declare a stop signal (Docker's `STOPSIGNAL`); container
runtimes use that signal to terminate the container, falling back to `SIGTERM`
when the image does not declare one. Today there is no way for a Kubernetes user
to override the stop signal for a container without rebuilding the image, and
the value the runtime will actually use is not visible through the Kubernetes
API.

KEP-4960 adds:

1. A new optional `StopSignal` lifecycle field on a container spec, allowing a
   pod author to override the stop signal at the spec level.
2. A new `StopSignal` field on container status that reflects the effective
   stop signal the runtime will use (image value, spec value, or runtime
   default — whichever applies).
3. A propagation path through the CRI to the runtime, so that the runtime can
   honour the user-supplied signal during termination.

The change is gated by a new feature gate, `ContainerStopSignals`.

## Goals

- Let users configure custom stop signals per container without modifying the
  image.
- Surface the effective stop signal in container status so operators can see
  what signal will actually be sent.
- Pass the configured signal to the container runtime via CRI so runtimes such
  as containerd and CRI-O can honour it.

## Non-goals

- Defining new termination semantics beyond signal selection.
- Per-probe (livenessProbe / readinessProbe) signal customisation.
- Changing how `terminationGracePeriodSeconds` is interpreted.

## API shape

A new `StopSignal` field is added to the container `Lifecycle` struct (alongside
`PostStart` and `PreStop`). Its type is a `Signal` enum (string) whose allowed
values depend on the pod's OS. Validation rules:

- `lifecycle.stopSignal` may only be set when `pod.spec.os.name` is also set.
  This avoids cross-OS ambiguity.
- For `os.name=linux`, the allowed values are the standard POSIX signal names
  (`SIGTERM`, `SIGKILL`, `SIGINT`, `SIGHUP`, `SIGQUIT`, `SIGUSR1`, `SIGUSR2`,
  `SIGTRAP`, `SIGABRT`, `SIGBUS`, `SIGFPE`, `SIGSEGV`, `SIGPIPE`, `SIGALRM`,
  `SIGSTKFLT`, `SIGCHLD`, `SIGCONT`, `SIGSTOP`, `SIGTSTP`, `SIGTTIN`, `SIGTTOU`,
  `SIGURG`, `SIGXCPU`, `SIGXFSZ`, `SIGVTALRM`, `SIGPROF`, `SIGWINCH`, `SIGIO`,
  `SIGPWR`, `SIGSYS`, `SIGRTMIN`...`SIGRTMAX`).
- For `os.name=windows`, the allowed values are `SIGTERM` and `SIGKILL` only.

Container status is extended with an `EffectiveStopSignal` field. Its value is:

1. The signal set in the container's spec, if any; otherwise
2. The signal that the container runtime reported (e.g. the image's `STOPSIGNAL`),
   if available; otherwise
3. Empty (the runtime will use its own default).

## CRI changes

The CRI `ContainerConfig` message is extended with an optional stop-signal field
of an enum-equivalent type. CRI's `ContainerStatus` reply gains an
`EffectiveStopSignal` field so kubelet can populate `EffectiveStopSignal` in the
PodStatus.

For backwards compatibility:
- A kubelet that supports the feature MUST detect runtime support via the
  existing CRI version negotiation. If the runtime does not understand the new
  field, kubelet falls back to the prior behaviour (the image's stop signal
  applies).
- A runtime that supports the feature MUST treat an unset stop-signal field as
  "use the existing default" (image's `STOPSIGNAL`, then `SIGTERM`).

## Validation

Pod admission rejects a pod whose `spec.os.name` is `linux` but whose
`stopSignal` is one of the Windows-only signals (none in the current proposal),
and vice versa for Windows pods, where only `SIGTERM` and `SIGKILL` are
permitted. The validation set lives alongside the existing OS-mismatch
validations.

`stopSignal` is restricted to a fixed list of POSIX signal names.

## Feature gate

The feature is alpha behind `ContainerStopSignals`. Both API server and kubelet
must have the gate enabled for the field to be respected. When the gate is off:

- API server drops the field on writes, exactly as for any other alpha field.
- Kubelet, on receipt of a pod whose container has `lifecycle.stopSignal` set,
  ignores the field and uses the existing default behaviour (image-defined or
  CRI-default `SIGTERM`).

## Test plan

The KEP requires:

- API validation tests for the new field (allowed signal names per OS).
- Round-trip tests for the new API field through API machinery (encoding,
  defaulting, conversion).
- Strategy tests for handling the field on update.
- Kubelet tests that verify the field is propagated into the CRI
  `ContainerConfig` and used at termination time.
- Integration tests that exercise the full path: pod with custom `stopSignal`,
  feature gate on, container actually stopped with the expected signal.
- Disabled-feature-gate tests that assert the field is ignored end-to-end.

## Implementation Task

Implement the alpha feature behind the `ContainerStopSignals` feature gate:

- Add the new field `Lifecycle.StopSignal *Signal` (or equivalent) to the
  container API and propagate through API machinery (validation, defaulting,
  conversion, OpenAPI, deep-copy). Mirror it in `ContainerStatus` so the value
  the runtime will use is observable.
- Extend the kubelet runtime adapter so the configured stop signal flows through
  to the runtime via CRI.
- Validate the value against the per-OS allowed-signal sets.
- Drop unknown / invalid stop signals on update for objects pre-dating the
  feature.
- Expose the effective stop signal back into `ContainerStatus`.

The KEP does not prescribe a particular file layout beyond what already exists
for similar lifecycle features (`PreStop`, `PostStart`). Place new logic next
to the existing equivalents.

## Acceptance

- A pod with `spec.containers[*].lifecycle.stopSignal: "SIGUSR1"` results in the
  container being stopped with `SIGUSR1` when the feature gate is enabled.
- With the feature gate disabled, the field is dropped and behaviour is
  unchanged.
- `kubectl get pod -o yaml` shows the effective stop signal under
  `status.containerStatuses[*].effectiveStopSignal` (or the equivalent name
  defined in this KEP).
- Validation tests cover OS / signal cross-compatibility.
- e2e and unit tests exist for the new API surface and CRI propagation.
