# T38: Kubernetes Enhancement KEP-5793 — Manifest-Based Admission Control Configuration

## Requirement source

This task corresponds to KEP-5793 ("Manifest Based Admission Control Configuration") in `kubernetes/enhancements`, sig-api-machinery. The summary below is the contract you implement against; do not invent additional structure, paths, or naming beyond what the KEP specifies.

---

## 1. Motivation

Kubernetes admission control today is registered exclusively through API objects (`ValidatingWebhookConfiguration`, `MutatingWebhookConfiguration`, `ValidatingAdmissionPolicy`/`Binding`, `MutatingAdmissionPolicy`/`Binding`). Three gaps result:

1. There is a *bootstrap gap*: until the API server is serving and the controller manager has reconciled webhook objects, admission requests are not subject to those webhooks.
2. There is a *self-protection gap*: any actor with sufficient RBAC on the admissionregistration group can delete or weaken the very policies meant to protect the cluster (these objects are not subject to themselves to avoid recursion).
3. There is an *availability gap*: admission policies depend on etcd being readable; if etcd is unhealthy or partitioned, configurations cannot be reread.

KEP-5793 addresses all three by allowing the kube-apiserver to load admission configurations from a directory of manifest files at startup and on file changes, completely independent of the API server's etcd state.

## 2. Goals (per KEP)

1. *Bootstrap*: file-configured admission policies and webhooks are active before the first API request is admitted.
2. *Self-protection*: manifest-based objects exist outside the REST API; they cannot be edited or deleted through the API server.
3. *Etcd-independence*: manifest-based configurations remain in effect even if etcd is unavailable.
4. *Dynamic reload*: changes to manifest files on disk are picked up at runtime without restart.
5. *Namespacing*: all manifest-defined objects are reserved with names ending in `.static.k8s.io`; REST handlers reject creation of API-driven objects with this suffix.
6. *Observability*: metrics and audit annotations expose the source of each admission decision.

## 5. Configuration surface (from the KEP)

The feature extends the kube-apiserver `AdmissionConfiguration` (passed via `--admission-control-config-file`) so that each of the four admission plugins can be told to read additional configuration from disk. The new field is `staticManifestsDir`, an absolute path to a directory containing manifest YAML/JSON files. Example:

```yaml
apiVersion: apiserver.config.k8s.io/v1
kind: AdmissionConfiguration
plugins:
- name: ValidatingAdmissionWebhook
  configuration:
    apiVersion: apiserver.config.k8s.io/v1
    kind: WebhookAdmissionConfiguration
    staticManifestsDir: /etc/kubernetes/admission/validating-webhooks
- name: MutatingAdmissionWebhook
  configuration:
    apiVersion: apiserver.config.k8s.io/v1
    kind: WebhookAdmissionConfiguration
    staticManifestsDir: /etc/kubernetes/admission/mutating-webhooks
- name: ValidatingAdmissionPolicy
  configuration:
    apiVersion: apiserver.config.k8s.io/v1alpha1
    kind: ValidatingAdmissionPolicyConfiguration
    staticManifestsDir: /etc/kubernetes/admission/vap
- name: MutatingAdmissionPolicy
  configuration:
    apiVersion: apiserver.config.k8s.io/v1alpha1
    kind: MutatingAdmissionPolicyConfiguration
    staticManifestsDir: /etc/kubernetes/admission/map
```

### Supported manifest types

Files in each `staticManifestsDir` may contain only the resource kinds appropriate to that admission plugin:

- Webhook plugins: `ValidatingWebhookConfiguration`, `MutatingWebhookConfiguration` (`admissionregistration.k8s.io/v1`), or their `…List` forms. Each manifest may also be a `ValidatingWebhookConfigurationList` / `MutatingWebhookConfigurationList`, or a generic `v1.List` whose items are these types.
- VAP/MAP plugins: `ValidatingAdmissionPolicy` + `ValidatingAdmissionPolicyBinding` / `MutatingAdmissionPolicy` + `MutatingAdmissionPolicyBinding`, in the v1 group, or the equivalent List wrappers.

Mixing plugin types in a single directory is rejected at startup.

### Naming and constraints

- Every object loaded from disk must have a `metadata.name` ending in `.static.k8s.io`. Any other name is rejected at load time.
- The same suffix is rejected by the REST handlers for the corresponding API group/version: a `POST` of an object whose name ends in `.static.k8s.io` returns `Forbidden` ("name suffix is reserved for static manifests"). When the feature gate is off, the REST handler instead emits a warning header but still admits the create — this preserves backwards compatibility.
- Webhooks loaded from manifests must use `clientConfig.url`. `clientConfig.service` is rejected at load time, because the static manifest path runs before the service network is necessarily reachable.
- Webhooks must use static authentication (kubeconfig or in-line CA bundle); they may not reference a `Secret` for credentials.
- Policies and bindings reference each other only by name within the same manifest set — no cross-set references and no references to API-managed VAP/MAP objects.

## 5. Manifest layout

The API server is configured with one or more directories. Each directory is scanned non-recursively. Files matching `*.yaml` or `*.json` are read. Each file may contain one resource or a `v1.List` (or comma/`---`-separated documents in YAML). Mixing kinds within one file is allowed.

The same field is reachable from the existing `AdmissionConfiguration` config file plumbing — i.e. the alpha API version of `WebhookAdmissionConfiguration` / `ValidatingAdmissionPolicyConfiguration` / `MutatingAdmissionPolicyConfiguration` gains a new `StaticManifestsDir` (string) field that points at the directory.

## 5. Loading and reload semantics

1. On API server start, before any built-in admission plugin reads etcd, the new loader scans every configured `StaticManifestsDir`, parses each YAML/JSON document, and registers the resulting objects with the corresponding admission plugin in addition to whatever is configured via the API.
2. The loader uses `fsnotify` (or equivalent) on the directory; when files are added, removed, or modified the loader re-parses and atomically swaps the in-memory set for that directory. Changes are eventually consistent with running webhook/policy evaluation.
3. If a manifest is malformed, the loader logs a structured error, increments a failure metric, and **retains the previous good state** for that directory. It does not abort startup once the API server is running; at startup, malformed manifests cause the API server to fail fast.
4. Loaded objects are merged with API-server-stored configurations during admission: the same matching rules and ordering apply, but the manifest-loaded objects always evaluate first within their plugin so they cannot be silenced by REST configuration.

## 6. Validation and admission semantics

- Manifest objects go through the same versioning, defaulting, and validation as API-stored objects (the alpha implementation uses the same `Strategy` types).
- Manifest-loaded `ValidatingAdmissionPolicy` bindings may reference only manifest-loaded policies (not REST-stored ones). The same applies to mutating variants.
- Static objects are visible via a new read-only listing surface: `GET /apis/admissionregistration.k8s.io/v1/staticvalidatingadmissionpolicies` and the analogous endpoints for the other three kinds. These endpoints are list/watch only — no create/update/delete.
- Static objects are returned by the standard List/Watch endpoints if and only if the request includes the label selector `admissionregistration.k8s.io/static=true`. Default lists must not return them, to avoid breaking existing controllers.
- Admission events triggered by static configurations carry an audit annotation `admission.k8s.io/source=manifest` plus the manifest file path.

## 6. Reload metrics

A small set of Prometheus metrics is emitted by each plugin that supports the feature:

- a counter incremented every time a reload is attempted, labelled by plugin and by outcome (`success` / `failure`);
- a gauge holding the timestamp of the last successful reload per plugin;
- a counter of objects currently loaded from disk per plugin.

Failure to load any single manifest must not poison the rest: each file is parsed independently, errors are logged with file path, and only successfully parsed objects participate in admission.

## 7. Feature gate and graduation

The feature is guarded by the `ManifestBasedAdmissionControlConfig` feature gate (alpha). With the gate disabled, the new fields on the configuration types are ignored and the new endpoints are not registered.

## 8. Test plan (informative)

- **Unit:** YAML/JSON decoding, name-suffix validation, kind allow-list, conflict detection between manifests and API objects, and plugin-specific validation (e.g. `MatchConditions` parsing).
- **Integration:** start the API server with manifest directories populated; verify that the static manifests are enforced before any API objects exist; verify that file-watch reloads occur within a small bounded delay; verify the REST API path that lists static objects returns a stable view.
- **Conformance / e2e:** none initially; the feature is alpha and gated.

## 5. Implementation notes (informative)

The KEP does not prescribe a particular package layout. Implementations are expected to:

- Add a `staticManifestsDir` field to the alpha admission-plugin configuration types for each of the four affected plugins.
- Wire up a directory loader and `fsnotify` watcher in each plugin so that the same parsing and validation is reused for both startup and runtime reload.
- Reject any object whose name does not end in `.static.k8s.io` and any object whose `kind` is outside the per-plugin allow-list.
- Surface the loaded set through whatever in-memory store the plugin already uses for API-driven objects, tagging each object as manifest-sourced so that conflict checks and audit annotations can distinguish the two.
- Add the new feature gate `ManifestBasedAdmissionControlConfig` and gate all new behaviour on it.
- Add metrics named with the `apiserver_admission_manifest_` prefix covering load attempts, parse failures per directory, and the count of currently loaded objects per plugin.

The KEP intentionally leaves file naming and exact internal type layout to the implementation.
