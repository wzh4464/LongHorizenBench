# T35: Electron — RFC 0008 Preload Realm for Service Workers

*Upstream source, for reference only: https://github.com/electron/rfcs/blob/main/text/0008-preload-realm.md*

All information required for this task is contained below; the agent must **not** fetch the URL above.

---

## 1. Motivation

Modern Electron applications rely on Chrome extensions whose logic increasingly lives in service workers (Manifest V3). Electron's existing preload mechanism only runs in renderer frames, so there is no supported way to inject code into an extension's service worker before the extension's own JavaScript starts. This prevents applications from:

- filling in missing Chrome extension APIs that Electron does not implement;
- replacing or intercepting service-worker-bound APIs that are broken or undesirable (for example, `atob`/`btoa` behavior or global constructors);
- hiding portions of Node.js from untrusted extension code while still exposing a curated IPC bridge;
- communicating securely between the main process and a specific service worker instance via `contextBridge`.

Preload scripts for service workers also unblock future Electron integrations (DevTools, native-messaging shims, fetch-based cookie stores, etc.) that need to run code before the worker's first `install` event.

## Concept: the preload realm

A *preload realm* is a V8 context created alongside each service-worker script context in the renderer / utility process responsible for that worker. It has:

- its own isolated `Realm` / `globalThis`;
- access to the same microtask queue as the worker (so `contextBridge` handlers can return promises resolved from the worker's task queue);
- a shared ID — the `ServiceWorkerVersionId` returned from Chromium — used by the main process to route IPC;
- the ability to use `contextBridge.exposeInMainWorld(...)` (here the "main world" refers to the service worker's own JS context).

The preload realm runs before any developer-provided service worker code executes, in a side-thread that is blocked on the worker startup until the preload finishes.

## Required public API

### 3.1 Session
- `session.registerPreloadScript({ type: 'service-worker', filePath })` — register a preload script that applies to every service worker created in this session.
- `session.unregisterPreloadScript(id)` — existing method, must also clean up service-worker preloads.
- `session.getPreloadScripts({ type: 'service-worker' })` returns the registered scripts.

### `ServiceWorkers`
Existing class gains:
- `serviceWorkers.getFromVersionID(versionID)` — returns a `ServiceWorkerMain` instance.
- Event `'registration-completed'` (`{ scope, versionId }`).
- Event `'running-status-changed'` (`{ versionId, runningStatus }`).

### `ServiceWorkerMain` (new public class)
Represents a live service worker process. Methods:
- `send(channel, ...args)` — IPC to the service worker.
- `invoke(channel, ...args) → Promise` — asynchronous IPC.
- `startTask()` / `endTask()` — prevents the worker from being killed while a task is in flight.
- `stopWorker()` — admin kill switch.
- `isDestroyed()` — truthy after shutdown.
- Properties `scope`, `versionId`, `ipc` (an `IpcMain` limited to this worker).

### `ipcRenderer` inside preload realm
Service-worker preload scripts cannot use DOM APIs; instead they expose:
- `electron.ipcRenderer` for messaging the main process.
- `contextBridge.exposeInMainWorld` is not valid (no main world); replaced by `contextBridge.exposeInMainWorld` on the preload's realm scope.

### Preload realm isolation
The preload realm is a distinct `v8::Context` inside the same isolate that hosts the Service Worker's JS context. Values can be exchanged via `contextBridge` exactly like renderer preloads, with the same security invariants (primitives are cloned, functions are wrapped, prototype chains are not leaked).

### Session API

`session.registerPreloadScript(script, options)` is extended:
```ts
type PreloadScriptRegistration = {
  type: 'frame' | 'service-worker';
  id?: string;
  filePath: string;
  // frame-specific options unchanged
};
```
Both types can be registered concurrently per session. Scripts are resolved relative to the session's current working directory at registration time.

## Implementation scope

The repository snapshot corresponds to the commit immediately before the Electron PR that landed the preload-realm mechanism. You need to add support across five major layers: Node.js integration, Chromium embedding, Renderer IPC plumbing, public JavaScript API, and unit/integration tests.

1. **Shared definitions**
   - the common Node integration header, the Electron gin-converters source area — add conversions for the new `PreloadScriptRegistration` payload.
   - the protocol API source stays unchanged, but `electron_api_session.{h,cc}` gains `RegisterPreloadScript`, `UnregisterPreloadScript`, and `GetPreloadScripts` reflecting the worker-level registry.

2. **Service-worker preload glue**
   - the Electron extension service-worker client implementation: intercept `WillEvaluateServiceWorkerScript` and inject a `PreloadRealm` v8 context before the service-worker code executes.
   - the renderer-side Electron client: support `RenderFrame::WillReleaseScriptContext` hooks so the preload realm is torn down with the worker.
   - Implement `PreloadRealmContext` in a new preload-realm context implementation: owns the v8::Context, runs preload scripts, exposes `electron.ipcRenderer` and `contextBridge` limited to the worker scope.

3. **IPC plumbing**
   - New mojo interface `electron::mojom::ServiceWorkerMain` (in the Electron API mojom file). Methods: `OnPreloadLoaded`, `Send(name, args)`, `Invoke(name, args) => (result, error)`, `OnIpc(channel, args)`.
   - Host side: `ServiceWorkerMain` class in a new `ServiceWorkerMain` API source/header pair implementing `UtilityProcessObserver`, exposing the JavaScript `ServiceWorkerMain` API to the `app` module.

4. **Feature flags / build**
   - the relevant `BUILD.gn` build file: add new files to the `electron_lib` target with `is_enable_extensions` guard.
   - `DEPS` is untouched.
   - the Electron paks gni: bundle the new documentation pages (the `ServiceWorkers` documentation, the `ServiceWorkerMain` documentation).

## Edge cases & invariants

- `session.serviceWorkers.getFromVersionID` must still return the same `ServiceWorkerMain` when called twice for the same version; reuse a `std::weak_ptr` in the Electron browser context.
- When a Service Worker is `stopping`, its `ServiceWorkerMain` must refuse IPC sends with `Error: Service worker has been stopped`.
- Unhandled exceptions in preload scripts do not kill the worker; they are emitted as `'console-message'` events on the `ServiceWorkerMain`.
- A Session without any registered preload script must not spawn the extra renderer-side realm — no observable overhead for existing apps.
- Preload scripts run in sandbox-enforced v8 contexts; they have no `Node.js` globals except `ipcRenderer` and `contextBridge`. `contextBridge.exposeInIsolatedWorld` is explicitly disallowed.

## Acceptance criteria for the change

1. `session.serviceWorkers.getAllRunning()` lists `ServiceWorkerMain` objects with the expected shape.
2. Registering a preload script with `type: 'service-worker'` causes it to run before any user service-worker code, in every started service worker of that session.
3. `contextBridge.exposeInMainWorld` inside the preload realm injects an API into the service-worker's global object (i.e., `globalThis` inside the worker can see the exposed API keys).
4. IPC (`send`, `invoke`, `on`, `handle`) round-trips between the main process and the service worker, with arguments cloned using structured-clone semantics.
5. Cleanup: tearing down the session, stopping the service worker, or removing the extension releases all native resources and rejects pending IPC invocations with `Error: Service worker context destroyed`.

## Implementation Task

Modify the Electron source tree to ship the above surface. Concretely:

- Add TypeScript definitions in the internal Electron typings and public types in the public Electron TypeScript definitions.
- Add the `ServiceWorkerMain` and `ServiceWorkers` JS wrappers in the `ServiceWorkers` JS API module and the `ServiceWorkerMain` JS API module.
- Plumb the native `electron::api::ServiceWorkerMain` (headers under the browser API tree, implementations under the browser-side source tree).
- Extend the Electron session API with `RegisterPreloadScript`, `UnregisterPreloadScript`.
- Introduce a new preload-realm context implementation to create / destroy the V8 context for each service worker.
- Add integration tests under the service-workers spec test and the service-workers spec fixtures directory.
- Add docs pages the `ServiceWorkerMain` documentation, the `ServiceWorkers` documentation.

All changes must keep existing tests (`npm test -- --ci`) passing.
