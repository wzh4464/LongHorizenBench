# T31: Envoy Golang HTTP Filter

## Requirement (inlined)

*Upstream reference: Envoy GitHub issue "Golang HTTP filter extension". Relevant design points are summarised here so the implementing agent does not need network access.*

## 1. Motivation

Envoy ships with two main mechanisms for writing custom HTTP filters:
- **Lua** — limited typing, awkward for complex logic, no module ecosystem.
- **Native C++ filters** — fast, but high friction (must build the Envoy binary, must follow Envoy's coding conventions, slow iteration).

For many users — especially in service-mesh deployments — neither is ideal. The goal of the GoLang extension is to let operators ship dynamic, self-contained Go plugins that are loaded by Envoy at start-up via cgo.

## 2. Goals

1. Run user-supplied Go code as an Envoy HTTP filter, hooked into the normal filter chain.
2. Support both decode and encode lifecycle methods (headers, data, trailers).
3. Support sub-routing-level configuration: each route entry can override per-filter settings.
4. Allow filters to issue async control-plane responses (continue/stop, send-local-reply).
5. Plugins are deployed as Go shared objects (`.so`), one per Envoy instance, loaded on startup.

## 3. Filter API surface (Go side)

Plugins should implement an interface roughly equivalent to:

```go
type StreamFilter interface {
    DecodeHeaders(headers RequestHeaderMap, endStream bool) StatusType
    DecodeData(buffer BufferInstance, endStream bool) StatusType
    DecodeTrailers(trailers RequestTrailerMap) StatusType

    EncodeHeaders(headers ResponseHeaderMap, endStream bool) StatusType
    EncodeData(buf BufferInstance, endStream bool) StatusType
    EncodeTrailers(trailers ResponseTrailerMap) StatusType

    OnDestroy(reason DestroyReason)
}
```

`StatusType` is one of `Continue`, `StopAndBuffer`, `StopAndBufferWatermark`, `StopNoBuffer`. `BufferInstance` exposes append/prepend/replace operations and a `Bytes()` accessor.

### Configuration

Each filter instance has access to a typed configuration object:

- per-listener config from the bootstrap.
- per-route config that can override or merge with the listener config.
- both are arbitrary protobuf messages declared in the plugin's protobuf schema.

The Go SDK exposes the merged effective config as a Go `interface{}` whose concrete type is whatever the plugin author registered as the config parser.

### Plugin registration

A plugin author calls a registration helper (with a unique plugin name, a config parser callback, and a factory that returns a fresh filter instance per request) during the Go SDK's `init()`. Envoy looks up the plugin by name when it sees `golang { library_id, library_path, plugin_name }` in a route configuration.

## 2. Implementation scope

1. C++ HTTP filter that hosts the Go runtime (load the shared library, dispatch HTTP filter callbacks across the cgo boundary).
2. State machine that tracks "decoding phase / encoding phase" for each request and maps Java-Go return codes onto Envoy's `FilterStatus`.
3. Go SDK package providing the filter author with the `StreamFilter` interface, request/response header/body/trailer wrappers, helpers for `SendLocalReply`, and access to dynamic metadata.
4. cgo bridge that crosses the C++/Go boundary safely (no Go pointers retained on the C++ side past the call, all callbacks dispatched on a dedicated goroutine).
5. Configuration plumbing: a typed proto for the filter's config, plus a callback registered from Go to parse the proto into a Go struct.
6. Minimal end-to-end integration test: a Go filter that injects a header, modifies the body, and short-circuits with `SendLocalReply` for a particular path.

## 4. Operational concerns

- The Go runtime initialises lazily on the first request that hits the filter.
- A panic inside Go must not kill the Envoy process; the filter must surface a 500 to the downstream and continue.
- The Go shared library is loaded with `dlopen`; multiple filters may share or instantiate distinct libraries.
- All log messages from the Go side are routed through Envoy's logger with the configured component tag.

## 5. Acceptance criteria

- Envoy with the Golang filter compiled in can serve a request that traverses a Go-implemented filter chain that observes/modifies headers, body, and trailers.
- A Go filter can issue `SendLocalReply` to short-circuit the request lifecycle.
- A Go filter that panics is contained: the request fails locally, but the worker stays up.
- Documentation describes the Go API surface, the lifecycle of plugins, and the deployment model (one `.so` per plugin name).