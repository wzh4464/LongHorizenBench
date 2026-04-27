# T40: Kubernetes — KEP-4317 Pod Certificates

## Requirement

Source: KEP-4317 ("Pod Certificates"), `kubernetes/enhancements/keps/sig-auth/4317-pod-certificates/`. The KEP is the source of truth; the design content below summarises it. The agent must not invent file paths or internal type names that are not in the KEP — the KEP only specifies APIs and behaviour, not Kubernetes' source layout.

---

## Summary

The certificates.k8s.io API group already lets cluster administrators issue X.509 certificates by submitting a `CertificateSigningRequest` (CSR), but it leaves the actual issuance and renewal flow to controllers and operators. Pods that need a certificate today have to either talk to a sidecar that performs CSR signing, mount a long-lived secret, or rely on out-of-tree projects.

KEP-4317 introduces a first-class kubelet-driven flow:

1. A new namespaced resource `PodCertificateRequest` (in `certificates.k8s.io/v1alpha1`) that kubelet creates on behalf of a pod, carrying a CSR-equivalent payload plus pod identity attributes.
2. A new `PodCertificate` source for projected volumes; pods that include a `podCertificate` projection get a kubelet-managed credential bundle (private key, leaf certificate, optional chain) automatically rotated.

The signer is pluggable: an in-cluster controller picks up `PodCertificateRequest` resources whose `spec.signerName` it owns, validates them, and writes a signed certificate chain back into `.status`. Kubelet then mounts the resulting credential into the pod and rotates it as needed.

## Motivation (from KEP)

- Provide pod-scoped, automatically rotated TLS material without requiring workloads to ship a custom credential agent.
- Give cluster operators a uniform, auditable surface to express signing policy ("which signer mints which kind of cert for which pod identity?").
- Let third-party signers integrate cleanly: an external controller only needs to watch one resource type and write to its `.status`.

## Goals

- New resource: `PodCertificateRequest` in `certificates.k8s.io/v1alpha1`.
- New projected-volume source: `PodCertificate`.
- Kubelet flow that creates / watches / refreshes `PodCertificateRequest`s on behalf of pods that mount such projections.
- Authentication and authorization story: signers must explicitly opt into a signer name; kubelet uses its node identity to create PCRs for pods bound to its node.
- Strict admission validation: tying `nodeName` and `serviceAccountName` to the actual pod's node and service account; immutability of `spec` after submission.

## Non-goals

- Replacing CSR for non-pod use cases.
- Defining a built-in signer or default signing policy.
- API for arbitrary out-of-cluster CAs (left to the signer controller).

## API surface (verbatim from the KEP)

### `PodCertificateRequest` (new resource in `certificates.k8s.io/v1alpha1`)

Spec fields:

- `signerName` (string) — selector for the signer controller; signers watch by this field.
- `podName`, `podUID`, `serviceAccountName`, `serviceAccountUID`, `nodeName`, `nodeUID` — pod-identity attributes; the API server enforces consistency with the requesting kubelet's bound pod.
- `keyType` (string) — one of `RSA3072`, `RSA4096`, `ECDSAP256`, `ECDSAP384`, `ECDSAP521`, `ED25519`.
- `pkixPublicKey` (`[]byte`) — DER-encoded SubjectPublicKeyInfo for the public key the kubelet generated.
- `proofOfPossession` (`[]byte`) — signature, made with the private key, over a server-supplied challenge string.
- `maxExpirationSeconds` (optional) — request a maximum lifetime; signer is free to issue a shorter cert.

`PodCertificateRequestStatus` carries:
- `conditions` (Issued / Failed / Denied),
- `certificateChain` (PEM bundle),
- `notBefore`, `beginRefreshAt`, `notAfter`,
- `failureReason`, `failureMessage`.

PCR is *one-shot*: a controller updates `.status` exactly once. Kubelet creates a fresh PCR for each renewal cycle.

## `PodCertificate` projected-volume source

Pods opt in to per-pod certificates by adding a `PodCertificate` source to a projected volume. Spec fields (per KEP):

- `signerName` (required) — fully-qualified signer name; matched against PCRs the signer is responsible for.
- `keyType` — one of the supported types (`ECDSAP256`, `ECDSAP384`, `ED25519`, `RSA2048`, `RSA3072`, `RSA4096`). Default is implementation-defined.
- `maxExpirationSeconds` (optional) — passed through to the PCR.
- `credentialBundlePath` (optional) — relative path within the projected volume where the combined `key.pem` + `cert.pem` + `ca.pem` bundle is materialised.
- `keyPath`, `certificateChainPath`, `caPath` (optional) — split-file output paths.

When the source is present, kubelet:
1. Generates a fresh private key on the node, never persisted to disk.
2. Creates a `PodCertificateRequest` whose `pkixPublicKey` matches the generated key, signs a proof-of-possession over the API server-supplied challenge, and submits to the API server.
3. Watches the PCR for `Issued` condition; once observed, writes the chain (and key, if a key path is requested) to a tmpfs in the projected volume.
4. Re-issues a new PCR before `beginRefreshAt`.

### Authorization & admission

- A new admission plugin (or extension to the existing kubelet admission) ensures the kubelet can only create a PCR whose `nodeName` matches its own bound node, and whose `podName`/`podUID`/`serviceAccountName`/`serviceAccountUID` match a pod actually bound to that node.
- The signer impersonation rules: a signer principal must hold `sign` permission on the `signers` resource for the named signer.
- Kubelet refuses to start the pod if the projected volume references a `signerName` that the cluster's RBAC indicates no signer is permitted to fulfil (best-effort warning; final answer comes from the signer's success/failure on the PCR).

### Feature gate

The feature is alpha and guarded by the `PodCertificateRequest` feature gate (kube-apiserver, kubelet, kube-controller-manager). When the gate is off:
- The new types and the projected-volume source are not registered.
- Existing pods with the projection are rejected at admission with a clear error.

### Observability

The KEP requires the following metrics:
- Counters for PCR create/update/delete and signer outcomes (`issued`, `denied`, `failed`).
- Histograms for time-to-issue and time-to-mount.
- Kubelet-side gauges for in-flight rotations and pending PCRs per pod.

## Implementation scope for this task

Implement the API and kubelet pieces consistent with the KEP. The contributing PR should:

- Add the `certificates.k8s.io/v1alpha1` `PodCertificateRequest` type and its `Spec` / `Status`, validation, defaulting, registration, and storage. Validation must enforce immutable spec after creation, the signer-name format, the supported key types, and the proof-of-possession length.
- Add the `PodCertificate` projected-volume source to the core `Volume` API, including OpenAPI changes and validation that exactly one of bundle-path or split paths is set, that signer name is well-formed, and that key types are restricted to the documented set.
- Add the kubelet projected-volume integration: keypair generation, PCR creation, polling/watching for status, writing the credential bundle into the volume, and refreshing on the signer's schedule.
- Add the admission/authorization wiring so that:
  - Only kubelets can create `PodCertificateRequest`s, and only for pods scheduled on their own node.
  - The signer-name → controller mapping is honoured (built-in signers reject unknown signer names; no signer is shipped in-tree as part of this work).
- Add the feature gate `PodCertificateProjection` (the umbrella gate from the KEP) and gate every new code path on it.
- Add unit tests for the new admission/validation logic; integration tests that exercise the projected-volume flow with a fake signer; and an end-to-end test that verifies rotation across `beginRefreshAt`.

The KEP does not prescribe specific package paths in `kubernetes/kubernetes`. Place new code wherever the existing `certificates.k8s.io` types and projected-volume implementations live, mirroring their layout, and update the standard generated files (deepcopy, conversion, openapi, swagger).
