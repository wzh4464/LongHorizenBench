# T19: gRPC

**Summary**: gRPC C++ 现有的异步 API（基于 CompletionQueue）使用复杂，需要手动管理轮询和 RPC 生命周期。本任务要求实现回调式异步 API，让库在 RPC 操作完成时直接调用用户指定的回调函数，简化异步编程模型，同时保持高性能。

**Motivation**: gRPC C++ 提供两种 API：同步 API 易于使用但性能受限于线程开销；CompletionQueue 异步 API 性能好但使用困难。CQ 模型要求用户显式轮询完成队列、手动请求新的服务器 RPC、管理复杂的生命周期状态。这导致很少有应用能充分利用其功能。许多用户已在 CQ 模型上自行封装回调机制，说明社区对简化异步 API 有强烈需求。

**Proposal**: 实现基于回调的异步 API，采用"反应器"（Reactor）设计模式。为不同 RPC 类型（unary、client streaming、server streaming、bidi streaming）提供客户端和服务端反应器基类。用户继承这些基类，重写完成回调方法（如 `OnReadDone`、`OnWriteDone`、`OnDone`）即可实现异步逻辑。库内部管理 CompletionQueue 轮询，用户无需关心。

**Design Details**:

1. 示例代码结构：在 `examples/cpp/helloworld/` 下创建回调示例。添加 `greeter_callback_client.cc` 演示客户端回调 API，添加 `greeter_callback_server.cc` 演示服务端回调 API。更新 BUILD、CMakeLists.txt、Makefile 构建这些示例。

2. 客户端回调 API：在 `include/grpcpp/impl/codegen/client_context.h` 和 `src/cpp/client/client_context.cc` 中扩展 ClientContext。支持通过 `stub_->async()->Method(&context, &request, &response, callback)` 模式发起异步调用。

3. 服务端回调 API：扩展 `include/grpcpp/server_builder.h` 和 `src/cpp/server/server_builder.cc`。支持注册回调式服务实现。服务实现类继承生成的回调服务基类。

4. Generic Stub 支持：更新 `include/grpcpp/generic/generic_stub.h` 支持 generic 回调调用。允许不依赖生成代码进行回调式 RPC。

5. Route Guide 示例：在 `examples/cpp/route_guide/` 下添加流式 RPC 的回调示例。`route_guide_callback_client.cc` 演示客户端流、服务端流、双向流的回调用法；`route_guide_callback_server.cc` 演示对应的服务端实现。

6. 端到端测试：更新 `test/cpp/end2end/` 下的测试。修改 `client_callback_end2end_test.cc` 测试客户端回调场景；更新 `test_service_impl.cc/h` 添加回调服务实现用于测试。

7. 拦截器支持：更新 `test/cpp/end2end/client_interceptors_end2end_test.cc` 和 `interceptors_util.cc`，确保拦截器与回调 API 兼容。

8. 性能基准：在 `test/cpp/microbenchmarks/` 下添加回调 API 的基准测试。创建 `callback_streaming_ping_pong.h`、`callback_unary_ping_pong.h` 测量回调模式的性能。实现 `callback_test_service.cc/h` 作为基准测试服务。

9. QPS 测试：更新 `test/cpp/qps/` 下的 QPS 测试工具。添加 `client_callback.cc` 和 `server_callback.cc` 支持使用回调 API 进行性能测试。

10. 平台兼容性：检查 `include/grpc/impl/codegen/port_platform.h` 确保回调 API 在支持的平台上正常工作。

## Requirement
https://github.com/grpc/proposal/blob/master/L67-cpp-callback-api.md
