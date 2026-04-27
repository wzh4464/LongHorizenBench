# T19: gRPC C++ - Callback-based Async API (L67)

*Upstream reference (inlined below):* https://github.com/grpc/proposal/blob/master/L67-cpp-callback-api.md plus implementation PR [grpc/grpc#25728](https://github.com/grpc/grpc/pull/25728). All details required to implement this task are inlined below; the agent does not need to consult external resources.

## 1. Motivation

For years gRPC C++ has exposed two service-style APIs:

1. **Synchronous (sync) API** — straightforward, but the thread pool needs to be large enough to cover every in-flight RPC.
2. **Asynchronous (CompletionQueue / CQ) API** — scalable, but notoriously hard to use correctly; clients manage tag allocation, polling, lifetime, and cancellation by hand.

The **callback API** (L67) sits in between. It preserves the throughput of the async API while hiding tag/CQ mechanics: users implement **reactor** subclasses whose methods are invoked by gRPC when bytes are available, instead of polling a queue themselves. The callback API also shares infrastructure with the C++ `EventEngine` work, so it is the long-term successor to the CQ API.

## 2. Objectives

1. Provide a new high-level API for each RPC pattern (unary, client-streaming, server-streaming, bidi) using *reactors*.
2. Guarantee that reactor callbacks are **serialised per-RPC** — i.e. at most one callback per reactor executes at a time.
3. Remove the requirement for application-managed `CompletionQueue`s.
4. Support both **server-side** (handlers) and **client-side** (stubs) with symmetric APIs.
5. Coexist with the existing sync and async APIs; zero breakage for current users.

## 3. API surface

### 3.1 Reactor base classes

```cpp
// Server side
template <class Req, class Resp>
class ServerUnaryReactor {
 public:
  virtual void OnCancel() = 0;
  virtual void OnDone()   = 0;
  void Finish(Status);
};

template <class Req, class Resp>
class ServerWriteReactor {
  void StartWrite(const Resp* resp);
  void StartWriteAndFinish(const Resp* resp, WriteOptions, Status);
  virtual void OnWriteDone(bool ok) {}
  virtual void OnCancel() {}
  virtual void OnDone() {}
};

template <class Req, class Resp>
class ServerReadReactor {
  void StartRead(Req* req);
  virtual void OnReadDone(bool ok) {}
  virtual void OnCancel() {}
  virtual void OnDone() {}
  void Finish(Status);
};

template <class Req, class Resp>
class ServerBidiReactor {
  void StartRead(Req* req);
  void StartWrite(const Resp* resp);
  void StartWriteAndFinish(const Resp*, WriteOptions, Status);
  virtual void OnReadDone(bool ok)  {}
  virtual void OnWriteDone(bool ok) {}
  virtual void OnCancel();
  virtual void OnDone();
};
```

Corresponding client reactors:
- `ClientUnaryReactor`, `ClientReadReactor`, `ClientWriteReactor`, `ClientBidiReactor`.

### 2.2 Client helpers

Generated stubs expose new convenience methods:
- `async()->MethodName(ClientContext*, Request*, Response*, std::function<void(Status)> callback);` for unary.
- `async()->MethodName(ClientContext*, ClientReadReactor<Response>*);` for server-streaming.
- Equivalent helpers for client-streaming and bidi.

### 2.3 Server registration

The service registration API gains a callback-based implementation:

```cpp
class ExampleService : public Example::CallbackService {
 public:
   grpc::ServerUnaryReactor* Echo(
       grpc::CallbackServerContext* ctx,
       const EchoRequest* req,
       EchoResponse* resp) override {
     auto* reactor = ctx->DefaultReactor();
     reactor->Finish(grpc::Status::OK);
     return reactor;
   }
};
```

The existing synchronous/async completion-queue services continue to work; the callback API is additive.

## 4. Rules / Guarantees

The proposal lists the thread-safety and lifetime rules enforced by the library:

1. The library guarantees that `OnDone()` is the final callback invoked for a server reactor and `OnDone(Status)` for a client reactor.
2. `StartCall()` on the client side must be called exactly once before any `StartRead`/`StartWrite`.
3. Multiple concurrent `StartRead` or `StartWrite` invocations on the same reactor are illegal; one outstanding operation per direction is enforced.
4. Reactors may live longer than the RPC itself — applications typically delete them in `OnDone`.
5. Concurrent reactors across RPCs are allowed.

## 5. Implementation Notes

1. The gRPC core surface call layer gains callback dispatch paths so that `grpc_call_set_completion_queue` is not required for reactor-style calls.
2. New top-level callback-common support header in the gRPC C++ public include tree; individual reactor types live in the gRPC C++ codegen callback headers (one per direction).
3. The auto-generated stub/skeleton includes a `CallbackService` inner class with methods returning `::grpc::ServerUnaryReactor*`, `::grpc::ServerReadReactor<...>*` etc.
4. The existing generic async stubs delegate to the callback implementation when CompletionQueues are not used.
5. Documentation: update the C++ callback-API user docs and the hello-world example.

## 6. Acceptance Criteria

- `server_callback_end2end_test` and `client_callback_end2end_test` pass with the new implementation.
- The C++ microbenchmark suite shows parity or better than the async CQ API for unary RPCs.
- All four streaming modes (unary, server, client, bidi) can be implemented with only reactor-style code, no CQ plumbing in the sample.
- Legacy `ClientAsyncReader/Writer/ReaderWriter` APIs continue to compile unchanged.
